from __future__ import annotations

from typing import Any

import json

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain.messages import SystemMessage, HumanMessage
from app.config import settings
from app.schemas import FacilityCapabilityProfile
import os 
from dotenv import load_dotenv

load_dotenv()

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


class EvidenceItem(BaseModel):
    supports_path: str
    source_field: str
    start_char: int | None = None
    end_char: int | None = None
    quote: str


class ExtractionOutput(BaseModel):
    profile: FacilityCapabilityProfile
    evidence: list[EvidenceItem] = Field(default_factory=list)


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
    if not os.getenv():
        raise RuntimeError("OPENAI_API_KEY is not set")

    system_prompt = SystemMessage(
        content=(
            "Extract a facility capability profile from structured fields and free-text. "
            "Return JSON matching ExtractionOutput. "
            "Only use information present in the inputs."
        )
    )
    agent = create_agent(model=_llm(), tools=[], system_prompt=system_prompt, response_format=ExtractionOutput)
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
        return structured
    return ExtractionOutput.model_validate(structured or {})


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, temperature=0.1, api_key=os.getenv("OPENAI_API_KEY"))
