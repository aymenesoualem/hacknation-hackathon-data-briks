from __future__ import annotations

from typing import Any

import json

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError
from langchain.messages import SystemMessage, HumanMessage
from app.config import settings
from app.schemas import EvidenceItem, ExtractedSignal, ExtractionOutput
from app.pipeline.normalization import SERVICE_SYNONYMS, EQUIPMENT_SYNONYMS

SUPPORTED_TOOLS = [
    "sql_count_by_capability",
    "sql_facility_services",
    "sql_find_facilities_by_service",
    "sql_region_ranking",
    "geo_within_km",
    "geo_cold_spots",
    "anomaly_unrealistic_procedure_breadth",
    "correlation_feature_movement",
    "workforce_where_practicing",
    "scarcity_dependency_on_few",
    "oversupply_vs_scarcity",
    "ngo_gap_map",
]


class RouteDecision(BaseModel):
    tool: str = Field(..., description="One of the supported deterministic tools.")
    args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")
    rationale: str = Field(default="", description="Short explanation of the routing choice.")


class ExplanationOutput(BaseModel):
    explanation: str


def route_query(question: str, filters: dict[str, Any], lat: float | None, lon: float | None, km: float | None) -> RouteDecision:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    system_prompt = SystemMessage(
        content=(
            "You are VF Agent. Your only task is to route the user question to the correct deterministic tool. "
            "Do NOT compute answers. Do NOT infer results. "
            "Return JSON matching the RouteDecision schema. "
            f"Supported tools: {SUPPORTED_TOOLS}. "
            "If geo distance is required but lat/lon/km are missing, set tool=geo_within_km and args={\"error\":\"MISSING_GEO\"}."
        )
    )
    agent = create_agent(model=_llm(), tools=[], system_prompt=system_prompt, response_format=RouteDecision)
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=f"Question: {question}\nFilters: {filters}\nLat: {lat}\nLon: {lon}\nKm: {km}"
                )
            ]
        }
    )
    structured = result.get("structured_response")
    if isinstance(structured, RouteDecision):
        return structured
    return RouteDecision.model_validate(structured or {})


def explain_results(question: str, tool_name: str, tool_output: dict[str, Any]) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    system_prompt = SystemMessage(
        content=(
            "You are VF Agent. Explain deterministic results in plain language. "
            "Do NOT add new facts. Do NOT compute new metrics. "
            "Use only the provided tool output."
        )
    )
    agent = create_agent(model=_llm(), tools=[], system_prompt=system_prompt, response_format=ExplanationOutput)
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=f"Question: {question}\nTool: {tool_name}\nToolOutput: {json.dumps(tool_output)}"
                )
            ]
        }
    )
    structured = result.get("structured_response")
    if isinstance(structured, ExplanationOutput):
        return structured.explanation
    payload = ExplanationOutput.model_validate(structured or {})
    return payload.explanation


def extract_profile_with_agent(raw_structured: dict[str, Any], combined_text: str) -> ExtractionOutput:
    if not settings.openai_api_key:
        return _regex_mock_extract(raw_structured, combined_text)

    system_prompt = SystemMessage(
        content=(
            "You are an information extractor. Only extract items explicitly supported by the input text. "
            "For every signal include at least one evidence quote from a provided field. "
            "If hedged language (sometimes/visiting/on request/rotates) => status=conditional and add constraint staffing_dependent or temporary. "
            "If referral language (refers/sent to/closest surgeon) => status=claimed_unverified or absent and add constraint referral_only. "
            "If equipment is down/pending/not operational => status=conditional and add constraint maintenance_dependent. "
            "Never compute cold spots, deserts, counts, rankings, correlations. "
            "Output must be valid JSON matching ExtractionOutput."
        )
    )
    agent = create_agent(model=_llm(), tools=[], system_prompt=system_prompt, response_format=ExtractionOutput)
    try:
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content=f"Structured: {json.dumps(raw_structured)}\nFreeText: {combined_text}"
                    )
                ]
            }
        )
        structured = result.get("structured_response")
        if isinstance(structured, ExtractionOutput):
            return _anchor_evidence(structured, raw_structured, combined_text)
        return _anchor_evidence(ExtractionOutput.model_validate(structured or {}), raw_structured, combined_text)
    except Exception:
        repaired = _extract_with_llm_raw(raw_structured, combined_text, system_prompt)
        if repaired:
            return _anchor_evidence(repaired, raw_structured, combined_text)
        return ExtractionOutput(signals=[], warnings=["EXTRACTION_FAILED"])


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, temperature=0.1, api_key=settings.openai_api_key)


def _extract_with_llm_raw(
    raw_structured: dict[str, Any],
    combined_text: str,
    system_prompt: SystemMessage,
) -> ExtractionOutput | None:
    response = _llm().invoke(
        [
            system_prompt,
            HumanMessage(content=f"Structured: {json.dumps(raw_structured)}\nFreeText: {combined_text}"),
        ]
    )
    try:
        payload = json.loads(response.content)
        return ExtractionOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError):
        return _repair_extraction_payload(response.content, raw_structured, combined_text)


def _repair_extraction_payload(payload: Any, raw_structured: dict[str, Any], combined_text: str) -> ExtractionOutput | None:
    system_prompt = SystemMessage(
        content=(
            "Fix this JSON to match ExtractionOutput exactly; do not add new info; only remove/rename fields. "
            "Return JSON only."
        )
    )
    schema_hint = {
        "signals": [
            {
                "kind": "capability|equipment|staffing|infrastructure",
                "raw_mention": "string",
                "canonical_name": "string|null",
                "status": "present|conditional|absent|claimed_unverified",
                "confidence": 0.0,
                "constraints": ["string"],
                "evidence": [
                    {
                        "supports_path": "capabilities.c_section",
                        "source_field": "notes",
                        "row_id": "row123",
                        "start_char": 0,
                        "end_char": 10,
                        "quote": "short snippet",
                    }
                ],
            }
        ],
        "warnings": ["string"],
    }
    content = (
        f"Schema: {json.dumps(schema_hint)}\n"
        f"Invalid payload: {json.dumps(payload)}\n"
        f"Structured: {json.dumps(raw_structured)}\n"
        f"FreeText: {combined_text}"
    )
    response = _llm().invoke([system_prompt, HumanMessage(content=content)])
    try:
        repaired = json.loads(response.content)
        return ExtractionOutput.model_validate(repaired)
    except (json.JSONDecodeError, ValidationError):
        return None


def _anchor_evidence(output: ExtractionOutput, raw_structured: dict[str, Any], combined_text: str) -> ExtractionOutput:
    row_id = str(raw_structured.get("source_row_id") or raw_structured.get("facility_id") or "unknown")
    for signal in output.signals:
        for item in signal.evidence:
            if not item.row_id:
                item.row_id = row_id
            if item.quote:
                location = combined_text.find(item.quote)
                if location >= 0:
                    item.start_char = location
                    item.end_char = location + len(item.quote)
    return output


def _regex_mock_extract(raw_structured: dict[str, Any], combined_text: str) -> ExtractionOutput:
    signals: list[ExtractedSignal] = []
    row_id = str(raw_structured.get("source_row_id") or raw_structured.get("facility_id") or "unknown")
    text = combined_text.lower()

    def _add_signal(kind: str, raw_mention: str, canonical_name: str, source_field: str):
        signals.append(
            ExtractedSignal(
                kind=kind,
                raw_mention=raw_mention,
                canonical_name=canonical_name,
                status="present",
                confidence=0.55,
                evidence=[
                    EvidenceItem(
                        supports_path=f"{'equipment' if kind == 'equipment' else 'capabilities'}.{canonical_name}",
                        source_field=source_field,
                        row_id=row_id,
                        quote=raw_mention[:240],
                    )
                ],
            )
        )

    for canon, patterns in SERVICE_SYNONYMS.items():
        for pattern in patterns:
            if pattern.search(text):
                _add_signal("capability", pattern.pattern, canon, "combined_text")
                break

    for canon, patterns in EQUIPMENT_SYNONYMS.items():
        for pattern in patterns:
            if pattern.search(text):
                _add_signal("equipment", pattern.pattern, canon, "combined_text")
                break

    return ExtractionOutput(signals=signals, warnings=["MOCK_EXTRACTOR_USED"])
