from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from langgraph.graph import StateGraph, END

from app.schemas import FacilityCapabilityProfile
from app.models import Facility, Extraction, EvidenceSpan, AgentTrace
from app.db import SessionLocal


SERVICE_KEYWORDS = {
    "services.emergency_care": ["emergency", "er", "urgent care"],
    "services.maternity": ["maternity", "obstetric", "labor", "delivery"],
    "services.surgery": ["surgery", "surgical", "operating theater", "operating room"],
    "services.lab": ["lab", "laboratory", "pathology"],
}

EQUIPMENT_KEYWORDS = {
    "equipment.oxygen": ["oxygen", "oxygen concentrator"],
    "equipment.ventilator": ["ventilator", "ventilation"],
    "equipment.ultrasound": ["ultrasound", "sonography"],
    "equipment.incubator": ["incubator", "neonatal incubator"],
    "equipment.operating_microscope": ["operating microscope", "surgical microscope"],
    "equipment.anesthesia_machine": ["anesthesia machine", "anaesthesia machine"],
    "equipment.xray": ["x-ray", "xray", "radiography"],
}

PROCEDURE_KEYWORDS = {
    "procedures.cardiology": ["cardiology", "cardiac clinic"],
    "procedures.c_section": ["c-section", "cesarean"],
    "procedures.appendectomy": ["appendectomy"],
    "procedures.dialysis": ["dialysis", "hemodialysis"],
    "procedures.orthopedic_surgery": ["orthopedic surgery", "orthopaedic"],
    "procedures.cataract_surgery": ["cataract surgery", "phacoemulsification"],
}

NOTE_KEYWORDS = {
    "notes.visiting": ["visiting specialist", "rotating", "temporary", "visiting"],
    "notes.ngo": ["ngo", "non-governmental", "charity"],
}


def _find_spans(text: str, keyword: str) -> list[tuple[int, int]]:
    spans = []
    for match in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
        spans.append((match.start(), match.end()))
    return spans


def _quote(text: str, start: int, end: int, padding: int = 40) -> str:
    left = max(0, start - padding)
    right = min(len(text), end + padding)
    return text[left:right].strip()


@dataclass
class ExtractionState:
    facility_id: int
    raw_structured: dict[str, Any]
    raw_text: dict[str, Any]
    combined_text: str = ""
    profile: FacilityCapabilityProfile | None = None
    evidence: list[dict[str, Any]] = None
    trace: dict[str, Any] = None


def clean_and_chunk(state: ExtractionState) -> ExtractionState:
    text_fields = [str(v) for v in state.raw_text.values() if v]
    state.combined_text = " ".join(text_fields)
    state.trace = {"step": "clean_and_chunk", "text_length": len(state.combined_text)}
    return state


def extract_profile(state: ExtractionState) -> ExtractionState:
    profile = FacilityCapabilityProfile()
    evidence = []
    text = state.combined_text

    for supports_path, keywords in SERVICE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text.lower():
                if supports_path.endswith("emergency_care"):
                    profile.services.emergency_care.available = True
                if supports_path.endswith("maternity"):
                    profile.services.maternity.available = True
                if supports_path.endswith("surgery"):
                    profile.services.surgery.available = True
                if supports_path.endswith("lab"):
                    profile.services.lab.available = True
                for start, end in _find_spans(text, keyword):
                    evidence.append(
                        {
                            "supports_path": supports_path,
                            "source_field": "raw_text",
                            "start_char": start,
                            "end_char": end,
                            "quote": _quote(text, start, end),
                        }
                    )
                break

    for supports_path, keywords in EQUIPMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text.lower():
                field = supports_path.split(".")[1]
                setattr(profile.equipment, field, True)
                for start, end in _find_spans(text, keyword):
                    evidence.append(
                        {
                            "supports_path": supports_path,
                            "source_field": "raw_text",
                            "start_char": start,
                            "end_char": end,
                            "quote": _quote(text, start, end),
                        }
                    )
                break

    for supports_path, keywords in PROCEDURE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text.lower():
                procedure = supports_path.split(".")[1]
                if procedure not in profile.procedures:
                    profile.procedures.append(procedure)
                for start, end in _find_spans(text, keyword):
                    evidence.append(
                        {
                            "supports_path": supports_path,
                            "source_field": "raw_text",
                            "start_char": start,
                            "end_char": end,
                            "quote": _quote(text, start, end),
                        }
                    )
                break

    for supports_path, keywords in NOTE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text.lower():
                note_value = supports_path.split(".")[1].replace("_", " ")
                if note_value not in profile.notes:
                    profile.notes.append(note_value)
                for start, end in _find_spans(text, keyword):
                    evidence.append(
                        {
                            "supports_path": supports_path,
                            "source_field": "raw_text",
                            "start_char": start,
                            "end_char": end,
                            "quote": _quote(text, start, end),
                        }
                    )
                break

    specialties = state.raw_structured.get("specialties", "")
    if isinstance(specialties, str) and specialties:
        for spec in [s.strip().lower() for s in specialties.split(";")]:
            if spec and spec not in profile.staffing.specialists:
                profile.staffing.specialists.append(spec)

    state.profile = profile
    state.evidence = evidence
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
            extracted_json=state.profile.model_dump(),
            confidence_json={"rule_based": 0.9},
            model_version="rule-based-v1",
        )
        session.add(extraction)
        session.flush()

        for item in state.evidence or []:
            span = EvidenceSpan(
                facility_id=state.facility_id,
                extraction_id=extraction.id,
                source_row_id=state.raw_structured.get("source_row_id"),
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
        "combined_text_length": len(state.combined_text or ""),
        "profile": state.profile.model_dump() if state.profile else {},
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
