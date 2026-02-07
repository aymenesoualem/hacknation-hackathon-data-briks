from __future__ import annotations

from dataclasses import dataclass


INTENTS = {
    "BASIC_COUNT_QUERY",
    "FACILITY_LOOKUP",
    "REGION_RANKING",
    "GEO_WITHIN_DISTANCE",
    "GEO_COLD_SPOT",
    "VALIDATION_MISSING_DEPENDENCY",
    "MISREP_BREADTH_VS_INFRA",
    "MISREP_CORRELATION_ANALYSIS",
    "WORKFORCE_DISTRIBUTION",
    "SCARCITY_DEPENDENCY_ON_FEW",
    "OVERSUPPLY_VS_SCARCITY",
    "NGO_GAP_MAP",
}


@dataclass
class RoutedQuery:
    intent: str
    explain: str


def classify_query(question: str) -> RoutedQuery:
    q = question.lower()

    if "cold spot" in q or "absent within" in q or "no facility" in q:
        return RoutedQuery("GEO_COLD_SPOT", "cold spot detection")
    if "within" in q and "km" in q:
        return RoutedQuery("GEO_WITHIN_DISTANCE", "geo within distance")
    if "most" in q and "region" in q:
        return RoutedQuery("REGION_RANKING", "region ranking")
    if "services does" in q or "offer" in q:
        return RoutedQuery("FACILITY_LOOKUP", "facility services lookup")
    if "clinic" in q and ("do" in q or "offer" in q):
        return RoutedQuery("FACILITY_LOOKUP", "clinic lookup")
    if "workforce" in q or "practicing" in q or "where is" in q:
        return RoutedQuery("WORKFORCE_DISTRIBUTION", "workforce distribution")
    if "depend on" in q or "few facilities" in q:
        return RoutedQuery("SCARCITY_DEPENDENCY_ON_FEW", "scarcity dependency")
    if "oversupply" in q or "scarcity" in q:
        return RoutedQuery("OVERSUPPLY_VS_SCARCITY", "oversupply vs scarcity")
    if "correlation" in q or "move together" in q:
        return RoutedQuery("MISREP_CORRELATION_ANALYSIS", "correlation analysis")
    if "unrealistic" in q or "breadth" in q:
        return RoutedQuery("MISREP_BREADTH_VS_INFRA", "breadth vs infrastructure")
    if "shouldn't move together" in q:
        return RoutedQuery("MISREP_CORRELATION_ANALYSIS", "mismatch signals")
    if "gap" in q or "development map" in q:
        return RoutedQuery("NGO_GAP_MAP", "ngo gap map")

    return RoutedQuery("BASIC_COUNT_QUERY", "default count query")
