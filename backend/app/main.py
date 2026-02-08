from __future__ import annotations

if __package__ is None:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db import SessionLocal, engine
from app.models import Base, Facility, Extraction, EvidenceSpan, AgentTrace, PlannerQuery, Anomaly
from app.schemas import PlannerRequest, PlannerResponse, EvidenceCitation
from app.ingest import ingest_csv
from app.agents import tools as toolset
from app.agents.langchain_agent import route_query, explain_results, SUPPORTED_TOOLS
from app.config import settings


Base.metadata.create_all(bind=engine)

app = FastAPI(title="VF Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/upload")
async def ingest_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be utf-8") from exc
    return ingest_csv(decoded)


@app.get("/facility/{facility_id}")
def facility_profile(facility_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        facility = session.query(Facility).filter(Facility.id == facility_id).first()
        if not facility:
            raise HTTPException(status_code=404, detail="Facility not found")
        extraction = (
            session.query(Extraction)
            .filter(Extraction.facility_id == facility_id)
            .order_by(Extraction.id.desc())
            .first()
        )
        if not extraction:
            raise HTTPException(status_code=404, detail="Extraction not found")
        evidence = (
            session.query(EvidenceSpan)
            .filter(EvidenceSpan.facility_id == facility_id)
            .all()
        )
        anomalies = session.query(Anomaly).filter(Anomaly.facility_id == facility_id).all()

        return {
            "facility": {
                "id": facility.id,
                "name": facility.name,
                "region": facility.region,
                "district": facility.district,
                "lat": facility.lat,
                "lon": facility.lon,
                "raw_structured_json": facility.raw_structured_json,
            },
            "profile": extraction.extracted_json,
            "anomalies": [
                {"type": a.type, "description": a.description, "severity": a.severity} for a in anomalies
            ],
            "citations": [
                {
                    "evidence_span_id": span.id,
                    "supports_path": span.supports_path,
                    "quote": span.quote,
                    "source_field": span.source_field,
                }
                for span in evidence
            ],
        }


@app.get("/facilities/geo")
def facilities_geo() -> dict[str, Any]:
    with SessionLocal() as session:
        facilities = session.query(Facility).all()
        rows = []
        for facility in facilities:
            rows.append(
                {
                    "id": facility.id,
                    "name": facility.name,
                    "region": facility.region,
                    "district": facility.district,
                    "lat": facility.lat,
                    "lon": facility.lon,
                    "facility_type": (facility.raw_structured_json or {}).get("facility_type"),
                }
            )
        return {"facilities": rows}


@app.post("/planner/ask", response_model=PlannerResponse)
def planner_ask(payload: PlannerRequest) -> PlannerResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not set")
    decision = route_query(payload.question, payload.filters, payload.lat, payload.lon, payload.km)
    tool_name = decision.tool
    if tool_name not in SUPPORTED_TOOLS:
        raise HTTPException(status_code=400, detail="Unsupported tool")
    if decision.args.get("error") == "MISSING_GEO":
        raise HTTPException(status_code=400, detail="lat/lon/km required for geo queries")

    tool_output = _run_deterministic_tool(tool_name, decision.args)
    answer_text = explain_results(payload.question, tool_name, tool_output)
    answer_json = {"tool": tool_name, "args": decision.args, "result": tool_output}
    citations = tool_output.get("citations", []) if isinstance(tool_output, dict) else []

    trace_payload = {
        "intent": tool_name,
        "explain": decision.rationale or "langchain-agent",
        "answer_json": answer_json,
    }
    with SessionLocal() as session:
        trace = AgentTrace(trace_type="planner", trace_json=trace_payload)
        session.add(trace)
        session.flush()
        session.add(
            PlannerQuery(
                query_text=payload.question,
                answer_text=answer_text,
                answer_json=answer_json,
                citations_json=citations,
                trace_id=trace.id,
            )
        )
        session.commit()
        trace_id = trace.id

    citation_models = [EvidenceCitation(**c) for c in citations]
    return PlannerResponse(answer_text=answer_text, answer_json=answer_json, citations=citation_models, trace_id=trace_id)


def _run_deterministic_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "sql_count_by_capability":
        return toolset.sql_count_by_capability(args.get("capability", ""), args)
    if tool_name == "sql_facility_services":
        return toolset.sql_facility_services(args.get("facility_name_or_id", ""))
    if tool_name == "sql_find_facilities_by_service":
        return toolset.sql_find_facilities_by_service(args, args.get("service", ""))
    if tool_name == "sql_region_ranking":
        return toolset.sql_region_ranking(args.get("metric", ""), args)
    if tool_name == "geo_within_km":
        return toolset.geo_within_km(
            args.get("condition_or_service", ""),
            args.get("lat"),
            args.get("lon"),
            args.get("km"),
        )
    if tool_name == "geo_cold_spots":
        return toolset.geo_cold_spots(args.get("service_or_bundle", ""), args.get("km", 50), args.get("region_level", "region"))
    if tool_name == "anomaly_unrealistic_procedure_breadth":
        return toolset.anomaly_unrealistic_procedure_breadth()
    if tool_name == "correlation_feature_movement":
        return toolset.correlation_feature_movement(args.get("features", []), args)
    if tool_name == "workforce_where_practicing":
        return toolset.workforce_where_practicing(args.get("subspecialty", ""), args)
    if tool_name == "scarcity_dependency_on_few":
        return toolset.scarcity_dependency_on_few(args.get("procedure", ""), args)
    if tool_name == "oversupply_vs_scarcity":
        return toolset.oversupply_vs_scarcity(
            args.get("low_complexity_set", []),
            args.get("high_complexity_set", []),
            args,
        )
    if tool_name == "ngo_gap_map":
        return toolset.ngo_gap_map()
    raise HTTPException(status_code=400, detail="Unsupported tool")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)