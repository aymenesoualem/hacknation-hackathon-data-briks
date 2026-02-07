from __future__ import annotations

from typing import Any, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.agents import tools as toolset


class CountInput(BaseModel):
    capability: str
    region: Optional[str] = None
    district: Optional[str] = None
    facility_type: Optional[str] = None


class FacilityServicesInput(BaseModel):
    facility_name_or_id: str = Field(..., description="Facility name or id")


class FindFacilitiesByServiceInput(BaseModel):
    service: str
    region: Optional[str] = None
    district: Optional[str] = None
    facility_type: Optional[str] = None


class RegionRankingInput(BaseModel):
    metric: str


class GeoWithinInput(BaseModel):
    condition_or_service: str
    lat: float
    lon: float
    km: float


class GeoColdSpotInput(BaseModel):
    service_or_bundle: str
    km: float = 50
    region_level: str = "region"


class CorrelationInput(BaseModel):
    features: list[str]


class WorkforceInput(BaseModel):
    subspecialty: str
    region: Optional[str] = None
    district: Optional[str] = None


class ScarcityInput(BaseModel):
    procedure: str
    region: Optional[str] = None
    district: Optional[str] = None


class OversupplyInput(BaseModel):
    low_complexity_set: list[str]
    high_complexity_set: list[str]


@tool("sql_count_by_capability", args_schema=CountInput)
def lc_sql_count_by_capability(capability: str, region: str | None = None, district: str | None = None, facility_type: str | None = None):
    return toolset.sql_count_by_capability(capability, {"region": region, "district": district, "facility_type": facility_type})


@tool("sql_facility_services", args_schema=FacilityServicesInput)
def lc_sql_facility_services(facility_name_or_id: str):
    return toolset.sql_facility_services(facility_name_or_id)


@tool("sql_find_facilities_by_service", args_schema=FindFacilitiesByServiceInput)
def lc_sql_find_facilities_by_service(service: str, region: str | None = None, district: str | None = None, facility_type: str | None = None):
    return toolset.sql_find_facilities_by_service({"region": region, "district": district, "facility_type": facility_type}, service)


@tool("sql_region_ranking", args_schema=RegionRankingInput)
def lc_sql_region_ranking(metric: str):
    return toolset.sql_region_ranking(metric, {})


@tool("geo_within_km", args_schema=GeoWithinInput)
def lc_geo_within_km(condition_or_service: str, lat: float, lon: float, km: float):
    return toolset.geo_within_km(condition_or_service, lat, lon, km)


@tool("geo_cold_spots", args_schema=GeoColdSpotInput)
def lc_geo_cold_spots(service_or_bundle: str, km: float = 50, region_level: str = "region"):
    return toolset.geo_cold_spots(service_or_bundle, km, region_level)


@tool("anomaly_unrealistic_procedure_breadth")
def lc_anomaly_unrealistic_procedure_breadth():
    return toolset.anomaly_unrealistic_procedure_breadth()


@tool("correlation_feature_movement", args_schema=CorrelationInput)
def lc_correlation_feature_movement(features: list[str]):
    return toolset.correlation_feature_movement(features, {})


@tool("workforce_where_practicing", args_schema=WorkforceInput)
def lc_workforce_where_practicing(subspecialty: str, region: str | None = None, district: str | None = None):
    return toolset.workforce_where_practicing(subspecialty, {"region": region, "district": district})


@tool("scarcity_dependency_on_few", args_schema=ScarcityInput)
def lc_scarcity_dependency_on_few(procedure: str, region: str | None = None, district: str | None = None):
    return toolset.scarcity_dependency_on_few(procedure, {"region": region, "district": district})


@tool("oversupply_vs_scarcity", args_schema=OversupplyInput)
def lc_oversupply_vs_scarcity(low_complexity_set: list[str], high_complexity_set: list[str]):
    return toolset.oversupply_vs_scarcity(low_complexity_set, high_complexity_set, {})


@tool("ngo_gap_map")
def lc_ngo_gap_map():
    return toolset.ngo_gap_map()


TOOLS = [
    lc_sql_count_by_capability,
    lc_sql_facility_services,
    lc_sql_find_facilities_by_service,
    lc_sql_region_ranking,
    lc_geo_within_km,
    lc_geo_cold_spots,
    lc_anomaly_unrealistic_procedure_breadth,
    lc_correlation_feature_movement,
    lc_workforce_where_practicing,
    lc_scarcity_dependency_on_few,
    lc_oversupply_vs_scarcity,
    lc_ngo_gap_map,
]


def run_langchain_agent(question: str, filters: dict[str, Any], lat: float | None, lon: float | None, km: float | None) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    llm = ChatOpenAI(model=settings.openai_model, temperature=0.1, api_key=settings.openai_api_key)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are VF Agent. You must call exactly one tool based on the question. "
                "Use provided filters, coordinates, and km if relevant. "
                "If the question asks for geo within distance and missing lat/lon/km, do NOT call tools and respond with: MISSING_GEO. "
                "Return your final response as plain text after the tool call.",
            ),
            ("human", "Question: {question}\nFilters: {filters}\nLat: {lat}\nLon: {lon}\nKm: {km}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    agent = create_openai_tools_agent(llm, TOOLS, prompt)
    executor = AgentExecutor(agent=agent, tools=TOOLS, return_intermediate_steps=True, max_iterations=2)
    result = executor.invoke({"question": question, "filters": filters, "lat": lat, "lon": lon, "km": km})

    intermediate = result.get("intermediate_steps", [])
    if not intermediate:
        output_text = result.get("output", "")
        if "MISSING_GEO" in output_text:
            return {"error": "lat/lon/km required for geo queries"}
        return {"error": "No tool call made"}

    tool_name = intermediate[-1][0].tool
    tool_output = intermediate[-1][1]

    return {
        "tool": tool_name,
        "tool_output": tool_output,
        "output_text": result.get("output", ""),
    }
