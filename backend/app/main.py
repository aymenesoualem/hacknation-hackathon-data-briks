from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db import SessionLocal, engine
from app.models import Base, Facility, Extraction, EvidenceSpan, AgentTrace, PlannerQuery, Anomaly
from app.schemas import PlannerRequest, PlannerResponse, EvidenceCitation
from app.ingest import ingest_csv
from app.agents.router import classify_query
from app.agents.reasoning import normalize_question
from app.agents import tools as toolset


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


@app.post("/planner/ask", response_model=PlannerResponse)
def planner_ask(payload: PlannerRequest) -> PlannerResponse:
    routed = classify_query(payload.question)
    normalized = normalize_question(payload.question)
    citations: list[dict[str, Any]] = []
    answer_json: dict[str, Any] = {"intent": routed.intent}
    answer_text = ""

    question_lower = payload.question.lower()
    if "hospital" in question_lower:
        payload.filters.setdefault("facility_type", "Hospital")
    if "clinic" in question_lower:
        payload.filters.setdefault("facility_type", "Clinic")

    if routed.intent == "BASIC_COUNT_QUERY":
        capability = normalized.procedure or normalized.service
        if not capability:
            capability = "cardiology"
        result = toolset.sql_count_by_capability(capability, payload.filters)
        answer_json.update({"capability": capability, "count": result["count"]})
        citations = result["citations"]
        answer_text = f"{result['count']} facilities provide {capability}."
    elif routed.intent == "FACILITY_LOOKUP":
        if (payload.filters.get("region") or payload.filters.get("district")) and normalized.service:
            result = toolset.sql_find_facilities_by_service(payload.filters, normalized.service)
            answer_json.update({"service": normalized.service, "facilities": result["facilities"]})
            citations = result["citations"]
            answer_text = f"Found {len(result['facilities'])} facilities with {normalized.service}."
        else:
            facility_name = payload.filters.get("facility") or payload.question
            result = toolset.sql_facility_services(facility_name)
            answer_json.update({"facility": result["facility"], "services": result["services"]})
            citations = result["citations"]
            answer_text = f"Services for {result['facility']}: {json.dumps(result['services'])}"
    elif routed.intent == "REGION_RANKING":
        metric = normalized.procedure or normalized.service or "cardiology"
        result = toolset.sql_region_ranking(metric, payload.filters)
        answer_json.update({"metric": metric, "ranking": result["ranking"]})
        if result["ranking"]:
            top = result["ranking"][0]
            answer_text = f"{top[0]} has the most facilities with {metric} ({top[1]})."
        else:
            answer_text = "No regions found for the metric."
    elif routed.intent == "GEO_WITHIN_DISTANCE":
        if payload.lat is None or payload.lon is None or payload.km is None:
            raise HTTPException(status_code=400, detail="lat/lon/km required for geo queries")
        condition = normalized.procedure or normalized.service or "cardiology"
        result = toolset.geo_within_km(condition, payload.lat, payload.lon, payload.km)
        answer_json.update({"condition": condition, "results": result["results"]})
        answer_text = f"{len(result['results'])} facilities within {payload.km} km provide {condition}."
    elif routed.intent == "GEO_COLD_SPOT":
        service = normalized.procedure or normalized.service or "maternity"
        result = toolset.geo_cold_spots(service, payload.km or 50, payload.filters.get("region_level", "region"))
        answer_json.update(result)
        answer_text = f"Cold spots for {service}: {', '.join(result['cold_spots']) or 'none'}."
    elif routed.intent == "MISREP_BREADTH_VS_INFRA":
        result = toolset.anomaly_unrealistic_procedure_breadth()
        answer_json.update(result)
        citations = result.get("citations", [])
        answer_text = f"Found {len(result['results'])} facilities with unrealistic breadth."
    elif routed.intent == "MISREP_CORRELATION_ANALYSIS":
        features = payload.filters.get("features") or ["services.surgery", "equipment.operating_microscope"]
        result = toolset.correlation_feature_movement(features, payload.filters)
        answer_json.update(result)
        answer_text = f"Computed correlations for {len(result['results'])} facilities."
    elif routed.intent == "WORKFORCE_DISTRIBUTION":
        subspecialty = normalized.subspecialty or "cardiology"
        result = toolset.workforce_where_practicing(subspecialty, payload.filters)
        answer_json.update({"subspecialty": subspecialty, "results": result["results"]})
        answer_text = f"{len(result['results'])} facilities list {subspecialty} specialists."
    elif routed.intent == "SCARCITY_DEPENDENCY_ON_FEW":
        procedure = normalized.procedure or "cardiology"
        result = toolset.scarcity_dependency_on_few(procedure, payload.filters)
        answer_json.update({"procedure": procedure, "providers": result["providers"], "dependency": result["dependency"]})
        answer_text = f"{len(result['providers'])} facilities provide {procedure}."
    elif routed.intent == "OVERSUPPLY_VS_SCARCITY":
        low = payload.filters.get("low_complexity_set") or ["appendectomy", "c_section"]
        high = payload.filters.get("high_complexity_set") or ["cardiology", "orthopedic_surgery"]
        result = toolset.oversupply_vs_scarcity(low, high, payload.filters)
        answer_json.update(result)
        answer_text = "Computed oversupply vs scarcity ratios."
    elif routed.intent == "NGO_GAP_MAP":
        result = toolset.ngo_gap_map()
        answer_json.update(result)
        answer_text = result["note"]
    else:
        answer_text = "Unsupported query type."

    trace_payload = {
        "intent": routed.intent,
        "explain": routed.explain,
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
