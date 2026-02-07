from __future__ import annotations

from app.models import Facility, Extraction, EvidenceSpan, Anomaly
from app.db import SessionLocal


def detect_anomalies_for_facility(facility: Facility, extraction: Extraction) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    extracted = extraction.extracted_json or {}
    procedures = extracted.get("procedures", [])
    equipment = extracted.get("equipment", {})

    bed_count = None
    operating_rooms = None
    raw_structured = facility.raw_structured_json or {}
    if isinstance(raw_structured, dict):
        bed_count = raw_structured.get("bed_count")
        operating_rooms = raw_structured.get("operating_rooms")

    breadth = len(procedures)
    equipment_score = sum(1 for value in equipment.values() if value)

    if breadth >= 4 and equipment_score <= 1:
        anomalies.append(
            Anomaly(
                facility_id=facility.id,
                type="unrealistic_breadth_vs_infra",
                severity="high",
                description="High procedure breadth with minimal equipment listed.",
                evidence_span_ids=[],
            )
        )

    if bed_count and bed_count >= 150 and (operating_rooms is None or operating_rooms <= 1):
        anomalies.append(
            Anomaly(
                facility_id=facility.id,
                type="size_vs_surgery_mismatch",
                severity="medium",
                description="Large bed count but minimal operating rooms.",
                evidence_span_ids=[],
            )
        )

    if equipment.get("operating_microscope") and not equipment.get("anesthesia_machine"):
        anomalies.append(
            Anomaly(
                facility_id=facility.id,
                type="equipment_mismatch",
                severity="low",
                description="Operating microscope listed without anesthesia machine.",
                evidence_span_ids=[],
            )
        )

    return anomalies


def refresh_anomalies() -> None:
    with SessionLocal() as session:
        session.query(Anomaly).delete()
        facilities = session.query(Facility).all()
        for facility in facilities:
            extraction = (
                session.query(Extraction)
                .filter(Extraction.facility_id == facility.id)
                .order_by(Extraction.id.desc())
                .first()
            )
            if not extraction:
                continue
            for anomaly in detect_anomalies_for_facility(facility, extraction):
                session.add(anomaly)
        session.commit()
