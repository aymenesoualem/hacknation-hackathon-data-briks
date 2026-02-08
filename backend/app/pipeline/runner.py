from __future__ import annotations

from typing import Any

from app.agents.langchain_agent import extract_profile_with_agent
from app.pipeline.normalization import build_combined_text, normalize_signal
from app.pipeline.rules import apply_confidence_policy, compute_flags, derive_profile
from app.schemas import FacilityCapabilityProfile, ExtractionOutput, ExtractedSignal


def process_facility_row(raw_row: dict) -> dict[str, Any]:
    combined_text = build_combined_text(
        raw_row,
        [
            "procedures",
            "equipment",
            "notes",
            "staffing_notes",
            "infrastructure_notes",
            "capability_notes",
            "equipment_notes",
            "procedure_notes",
            "ngo_notes",
        ],
    )
    extraction = extract_profile_with_agent(raw_row, combined_text)

    normalized_signals: list[ExtractedSignal] = []
    warnings = list(extraction.warnings)
    for signal in extraction.signals:
        normalized = normalize_signal(signal, raw_row)
        if not normalized.canonical_name:
            warnings.append(f"UNMAPPED_SIGNAL:{signal.raw_mention}")
        normalized_signals.append(normalized)

    normalized_signals = apply_confidence_policy(normalized_signals, raw_row)
    derived_profile: FacilityCapabilityProfile = derive_profile(normalized_signals, raw_row)
    derived_profile.flags = compute_flags(derived_profile, raw_row)

    extraction = ExtractionOutput(signals=normalized_signals, warnings=warnings)
    return {"extraction": extraction, "derived_profile": derived_profile}
