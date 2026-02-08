from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import StateGraph, END

from app.models import Extraction, EvidenceSpan, AgentTrace
from app.db import SessionLocal
from app.pipeline.runner import process_facility_row


@dataclass
class ExtractionState:
    facility_id: int
    raw_structured: dict[str, Any]
    raw_text: dict[str, Any]
    combined_text: str = ""
    profile: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = None
    trace: dict[str, Any] = None
    model_version: str = "rule-based-v1"
    confidence_json: dict[str, Any] = None


def clean_and_chunk(state: ExtractionState) -> ExtractionState:
    state.trace = {"step": "clean_and_chunk"}
    return state


def extract_profile(state: ExtractionState) -> ExtractionState:
    raw_row = {
        **(state.raw_structured or {}),
        **(state.raw_text or {}),
        "facility_id": state.facility_id,
    }
    output = process_facility_row(raw_row)
    extraction = output["extraction"]
    profile = output["derived_profile"]

    state.profile = profile.model_dump()
    state.evidence = [
        item.model_dump()
        for signal in extraction.signals
        for item in signal.evidence
    ]
    state.model_version = "deterministic-pipeline-v1"
    state.confidence_json = {"pipeline": 0.9}
    return state


def collect_evidence(state: ExtractionState) -> ExtractionState:
    state.trace = {
        "step": "collect_evidence",
        "evidence_count": len(state.evidence or []),
    }
    return state


def persist(state: ExtractionState) -> ExtractionState:
    with SessionLocal() as session:
        extraction = Extraction(
            facility_id=state.facility_id,
            extracted_json=state.profile or {},
            confidence_json=state.confidence_json or {"rule_based": 0.9},
            model_version=state.model_version,
        )
        session.add(extraction)
        session.flush()

        for item in state.evidence or []:
            span = EvidenceSpan(
                facility_id=state.facility_id,
                extraction_id=extraction.id,
                source_row_id=item.get("row_id") or state.raw_structured.get("source_row_id"),
                source_field=item["source_field"],
                quote=item["quote"],
                supports_path=item["supports_path"],
                start_char=item["start_char"],
                end_char=item["end_char"],
            )
            session.add(span)
        session.commit()
    return state


def log_trace(state: ExtractionState) -> ExtractionState:
    trace_payload = {
        "facility_id": state.facility_id,
        "profile": state.profile or {},
        "evidence_count": len(state.evidence or []),
    }
    with SessionLocal() as session:
        session.add(AgentTrace(trace_type="extraction", trace_json=trace_payload))
        session.commit()
    return state


def build_extraction_graph():
    graph = StateGraph(ExtractionState)
    graph.add_node("clean_and_chunk", clean_and_chunk)
    graph.add_node("extract_profile", extract_profile)
    graph.add_node("collect_evidence", collect_evidence)
    graph.add_node("persist", persist)
    graph.add_node("log_trace", log_trace)
    graph.set_entry_point("clean_and_chunk")
    graph.add_edge("clean_and_chunk", "extract_profile")
    graph.add_edge("extract_profile", "collect_evidence")
    graph.add_edge("collect_evidence", "persist")
    graph.add_edge("persist", "log_trace")
    graph.add_edge("log_trace", END)
    return graph.compile()
