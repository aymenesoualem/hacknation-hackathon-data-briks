from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from app.db import SessionLocal
from app.models import Facility
from app.agents.langgraph_pipeline import build_extraction_graph, ExtractionState
from app.anomalies import refresh_anomalies


def ingest_csv(content: str) -> dict[str, Any]:
    reader = csv.DictReader(StringIO(content))
    facilities = []
    with SessionLocal() as session:
        for row in reader:
            facility = Facility(
                name=row.get("name") or "Unknown Facility",
                country=row.get("country"),
                region=row.get("region"),
                district=row.get("district"),
                lat=_to_float(row.get("lat")),
                lon=_to_float(row.get("lon")),
                source_row_id=row.get("source_row_id"),
                raw_structured_json={
                    "facility_type": row.get("facility_type"),
                    "bed_count": _to_int(row.get("bed_count")),
                    "operating_rooms": _to_int(row.get("operating_rooms")),
                    "specialties": row.get("specialties"),
                    "source_row_id": row.get("source_row_id"),
                },
                raw_text_json={
                    "capability_notes": row.get("capability_notes"),
                    "equipment_notes": row.get("equipment_notes"),
                    "procedure_notes": row.get("procedure_notes"),
                    "staffing_notes": row.get("staffing_notes"),
                    "ngo_notes": row.get("ngo_notes"),
                },
            )
            session.add(facility)
            session.flush()
            facilities.append(facility)
        session.commit()

    graph = build_extraction_graph()
    for facility in facilities:
        raw_structured = facility.raw_structured_json or {}
        raw_text = facility.raw_text_json or {}
        graph.invoke(
            ExtractionState(
                facility_id=facility.id,
                raw_structured=raw_structured,
                raw_text=raw_text,
            )
        )

    refresh_anomalies()
    return {"ingested": len(facilities)}


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None
