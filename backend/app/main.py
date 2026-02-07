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
from app.agents.langchain_agent import run_langchain_agent


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
    lc_result = run_langchain_agent(payload.question, payload.filters, payload.lat, payload.lon, payload.km)
    if lc_result.get("error"):
        raise HTTPException(status_code=400, detail=lc_result["error"])
    tool_name = lc_result.get("tool", "")
    tool_output = lc_result.get("tool_output", {})
    answer_json = {"intent": tool_name, "result": tool_output}
    citations = tool_output.get("citations", []) if isinstance(tool_output, dict) else []
    answer_text = lc_result.get("output_text") or f"Executed {tool_name}."

    trace_payload = {
        "intent": tool_name,
        "explain": "langchain-agent",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)