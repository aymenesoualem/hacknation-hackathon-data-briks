import os

from app.pipeline.runner import process_facility_row
from app.config import settings


def setup_module():
    settings.openai_api_key = None
    os.environ.pop("OPENAI_API_KEY", None)


def _find_signal(extraction, name: str):
    return next((s for s in extraction.signals if s.canonical_name == name), None)


def test_c_section_conditional_when_visiting():
    row = {
        "procedures": "C-section available with visiting surgeon",
        "staffing_notes": "Visiting obstetrician rotates weekly",
        "source_row_id": "row-1",
    }
    result = process_facility_row(row)
    signal = _find_signal(result["extraction"], "c_section")
    assert signal is not None
    assert signal.status == "conditional"


def test_icu_claim_without_support_flag():
    row = {
        "procedures": "ICU services available",
        "equipment_notes": "Basic beds, no monitors listed",
        "source_row_id": "row-2",
    }
    result = process_facility_row(row)
    profile = result["derived_profile"]
    flag_types = {flag.type for flag in profile.flags}
    assert "icu_claim_without_support" in flag_types


def test_ct_conditional_when_pending():
    row = {
        "equipment_notes": "CT scanner pending installation",
        "source_row_id": "row-3",
    }
    result = process_facility_row(row)
    signal = _find_signal(result["extraction"], "ct")
    assert signal is not None
    assert signal.status == "conditional"
