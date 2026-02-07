from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Facility, Extraction, EvidenceSpan, Anomaly
from app.geo import filter_within_km


def _latest_extraction_subquery():
    return select(Extraction).subquery()


def get_evidence_for_facility_field(facility_id: int, supports_path: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        spans = (
            session.query(EvidenceSpan)
            .filter(EvidenceSpan.facility_id == facility_id, EvidenceSpan.supports_path == supports_path)
            .all()
        )
        return [
            {
                "facility_id": span.facility_id,
                "evidence_span_id": span.id,
                "supports_path": span.supports_path,
                "quote": span.quote,
                "source_field": span.source_field,
            }
            for span in spans
        ]


def get_evidence_for_prefix(facility_id: int, prefix: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        spans = (
            session.query(EvidenceSpan)
            .filter(EvidenceSpan.facility_id == facility_id, EvidenceSpan.supports_path.like(f"{prefix}%"))
            .all()
        )
        return [
            {
                "facility_id": span.facility_id,
                "evidence_span_id": span.id,
                "supports_path": span.supports_path,
                "quote": span.quote,
                "source_field": span.source_field,
            }
            for span in spans
        ]


def sql_count_by_capability(capability: str, region_filters: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        if region_filters.get("region"):
            query = query.filter(Facility.region == region_filters["region"])
        if region_filters.get("district"):
            query = query.filter(Facility.district == region_filters["district"])
        facility_type = region_filters.get("facility_type")

        count = 0
        citations = []
        for facility, extraction in query.all():
            if facility_type:
                raw_structured = facility.raw_structured_json or {}
                if str(raw_structured.get("facility_type", "")).lower() != facility_type.lower():
                    continue
            extracted = extraction.extracted_json or {}
            procedures = extracted.get("procedures", [])
            services = extracted.get("services", {})
            if capability in procedures or services.get(capability, {}).get("available"):
                count += 1
                citations.extend(get_evidence_for_facility_field(facility.id, f"procedures.{capability}"))
                citations.extend(get_evidence_for_facility_field(facility.id, f"services.{capability}"))
        return {"count": count, "citations": citations}


def sql_facility_services(facility_name_or_id: str | int) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        if isinstance(facility_name_or_id, int):
            query = query.filter(Facility.id == facility_name_or_id)
        else:
            query = query.filter(Facility.name.ilike(f"%{facility_name_or_id}%"))
        row = query.first()
        if not row:
            return {"facility": None, "services": {}, "citations": []}
        facility, extraction = row
        extracted = extraction.extracted_json or {}
        citations = []
        for key in ["emergency_care", "maternity", "surgery", "lab"]:
            citations.extend(get_evidence_for_facility_field(facility.id, f"services.{key}"))
        return {"facility": facility.name, "services": extracted.get("services", {}), "citations": citations}


def sql_find_facilities_by_service(area_filters: dict[str, Any], service: str) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        if area_filters.get("region"):
            query = query.filter(Facility.region == area_filters["region"])
        if area_filters.get("district"):
            query = query.filter(Facility.district == area_filters["district"])
        facility_type = area_filters.get("facility_type")
        facilities = []
        citations = []
        for facility, extraction in query.all():
            if facility_type:
                raw_structured = facility.raw_structured_json or {}
                if str(raw_structured.get("facility_type", "")).lower() != facility_type.lower():
                    continue
            services = (extraction.extracted_json or {}).get("services", {})
            if services.get(service, {}).get("available"):
                facilities.append({"facility_id": facility.id, "name": facility.name})
                citations.extend(get_evidence_for_facility_field(facility.id, f"services.{service}"))
        return {"facilities": facilities, "citations": citations}


def sql_region_ranking(metric: str, filters: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        counts = Counter()
        for facility, extraction in query.all():
            extracted = extraction.extracted_json or {}
            if metric in extracted.get("procedures", []):
                counts[facility.region] += 1
        ranking = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return {"ranking": ranking}


def geo_within_km(condition_or_service: str, lat: float, lon: float, km: float) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        rows = []
        for facility, extraction in query.all():
            extracted = extraction.extracted_json or {}
            if condition_or_service in extracted.get("procedures", []):
                rows.append({"facility_id": facility.id, "name": facility.name, "lat": facility.lat, "lon": facility.lon})
            if extracted.get("services", {}).get(condition_or_service, {}).get("available"):
                rows.append({"facility_id": facility.id, "name": facility.name, "lat": facility.lat, "lon": facility.lon})
        within = filter_within_km(rows, lat, lon, km)
        return {"results": within}


def geo_cold_spots(service_or_bundle: str, km: float, region_level: str) -> dict[str, Any]:
    with SessionLocal() as session:
        facilities = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id).all()
        by_region = {}
        for facility, extraction in facilities:
            key = facility.region if region_level == "region" else facility.district
            if key not in by_region:
                by_region[key] = {"facilities": [], "meets": 0}
            by_region[key]["facilities"].append((facility, extraction))

        cold = []
        for key, payload in by_region.items():
            meets = 0
            for facility, extraction in payload["facilities"]:
                extracted = extraction.extracted_json or {}
                if service_or_bundle in extracted.get("procedures", []):
                    meets += 1
                if extracted.get("services", {}).get(service_or_bundle, {}).get("available"):
                    meets += 1
            if meets == 0:
                cold.append(key)
        return {"cold_spots": cold, "region_level": region_level}


def anomaly_facilities_missing_equipment(service: str, required_equipment: list[str]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        results = []
        for facility, extraction in query.all():
            extracted = extraction.extracted_json or {}
            services = extracted.get("services", {})
            if not services.get(service, {}).get("available"):
                continue
            equipment = extracted.get("equipment", {})
            missing = [eq for eq in required_equipment if not equipment.get(eq)]
            if missing:
                results.append({"facility_id": facility.id, "name": facility.name, "missing": missing})
        return {"results": results}


def anomaly_unrealistic_procedure_breadth() -> dict[str, Any]:
    with SessionLocal() as session:
        results = (
            session.query(Anomaly, Facility)
            .join(Facility, Facility.id == Anomaly.facility_id)
            .filter(Anomaly.type == "unrealistic_breadth_vs_infra")
            .all()
        )
        citations = []
        payload = []
        for a, f in results:
            payload.append({"facility_id": f.id, "name": f.name, "description": a.description})
            citations.extend(get_evidence_for_prefix(f.id, "procedures."))
            citations.extend(get_evidence_for_prefix(f.id, "equipment."))
        return {"results": payload, "citations": citations}


def correlation_feature_movement(features: list[str], filters: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        pairs = []
        for facility, extraction in query.all():
            extracted = extraction.extracted_json or {}
            row = {"facility_id": facility.id, "name": facility.name}
            for feature in features:
                if feature.startswith("procedures."):
                    value = feature.split(".")[1] in extracted.get("procedures", [])
                elif feature.startswith("services."):
                    value = extracted.get("services", {}).get(feature.split(".")[1], {}).get("available", False)
                else:
                    value = None
                row[feature] = value
            pairs.append(row)
        return {"results": pairs}


def workforce_where_practicing(subspecialty: str, filters: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        facilities = []
        for facility, extraction in query.all():
            specialists = (extraction.extracted_json or {}).get("staffing", {}).get("specialists", [])
            if subspecialty and subspecialty.lower() in [s.lower() for s in specialists]:
                facilities.append({"facility_id": facility.id, "name": facility.name, "region": facility.region})
        return {"results": facilities}


def scarcity_dependency_on_few(procedure: str, region_filters: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        if region_filters.get("region"):
            query = query.filter(Facility.region == region_filters["region"])
        providers = []
        for facility, extraction in query.all():
            if procedure in (extraction.extracted_json or {}).get("procedures", []):
                providers.append({"facility_id": facility.id, "name": facility.name})
        dependency = len(providers) <= 2
        return {"providers": providers, "dependency": dependency}


def oversupply_vs_scarcity(low_complexity_set: list[str], high_complexity_set: list[str], filters: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        low = 0
        high = 0
        for _, extraction in query.all():
            procedures = (extraction.extracted_json or {}).get("procedures", [])
            low += sum(1 for p in low_complexity_set if p in procedures)
            high += sum(1 for p in high_complexity_set if p in procedures)
        return {"low_complexity_count": low, "high_complexity_count": high, "ratio": (low / high) if high else None}


def ngo_gap_map(proxy_keyword: str = "ngo") -> dict[str, Any]:
    with SessionLocal() as session:
        query = session.query(Facility, Extraction).join(Extraction, Extraction.facility_id == Facility.id)
        regions_with_ngo = set()
        all_regions = set()
        for facility, extraction in query.all():
            all_regions.add(facility.region)
            notes = (extraction.extracted_json or {}).get("notes", [])
            if any(proxy_keyword in note for note in notes):
                regions_with_ngo.add(facility.region)
        gaps = sorted(all_regions - regions_with_ngo)
        return {
            "note": "Not available in internal dataset; computed need-only hotspots",
            "regions_without_ngo_mentions": gaps,
        }
