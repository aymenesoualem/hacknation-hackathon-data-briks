from __future__ import annotations

import re
from typing import Iterable

from app.schemas import ExtractedSignal

CANON_SERVICES = {
    "emergency_care",
    "maternity",
    "surgery",
    "lab",
    "icu",
    "c_section",
    "cardiology",
}

CANON_EQUIPMENT = {
    "oxygen",
    "ventilator",
    "ultrasound",
    "incubator",
    "operating_microscope",
    "anesthesia_machine",
    "xray",
    "ct",
    "monitors",
    "operating_room",
    "or_table",
}

SERVICE_SYNONYMS: dict[str, list[re.Pattern[str]]] = {
    "emergency_care": [re.compile(r"\bemergency\b", re.I), re.compile(r"\ber\b", re.I)],
    "maternity": [re.compile(r"\bmaternity\b", re.I), re.compile(r"\bobstetric\b", re.I)],
    "surgery": [re.compile(r"\bsurgery\b", re.I), re.compile(r"\boperating\b", re.I)],
    "lab": [re.compile(r"\blab\b", re.I), re.compile(r"\blaboratory\b", re.I)],
    "icu": [re.compile(r"\bicu\b", re.I), re.compile(r"\bintensive care\b", re.I)],
    "c_section": [re.compile(r"\bc[- ]?section\b", re.I), re.compile(r"\bcesarean\b", re.I)],
    "cardiology": [re.compile(r"\bcardiology\b", re.I), re.compile(r"\bcardiac\b", re.I)],
}

EQUIPMENT_SYNONYMS: dict[str, list[re.Pattern[str]]] = {
    "oxygen": [re.compile(r"\boxygen\b", re.I), re.compile(r"\boxygen concentrator\b", re.I)],
    "ventilator": [re.compile(r"\bventilator\b", re.I)],
    "ultrasound": [re.compile(r"\bultrasound\b", re.I), re.compile(r"\bsonography\b", re.I)],
    "incubator": [re.compile(r"\bincubator\b", re.I)],
    "operating_microscope": [re.compile(r"\boperating microscope\b", re.I)],
    "anesthesia_machine": [re.compile(r"\banesthesia machine\b", re.I), re.compile(r"\banaesthesia machine\b", re.I)],
    "xray": [re.compile(r"\bx[- ]?ray\b", re.I)],
    "ct": [re.compile(r"\bct\b", re.I), re.compile(r"\bct scan\b", re.I), re.compile(r"\bct scanner\b", re.I)],
    "monitors": [re.compile(r"\bmonitor\b", re.I)],
    "operating_room": [re.compile(r"\boperating room\b", re.I), re.compile(r"\bor\b", re.I)],
    "or_table": [re.compile(r"\bor table\b", re.I), re.compile(r"\boperating table\b", re.I)],
}

HEDGE_PATTERNS = [
    re.compile(r"\bsometimes\b", re.I),
    re.compile(r"\bvisiting\b", re.I),
    re.compile(r"\bon request\b", re.I),
    re.compile(r"\brotat", re.I),
]
REFERRAL_PATTERNS = [
    re.compile(r"\brefer", re.I),
    re.compile(r"\breferral\b", re.I),
    re.compile(r"\bsent to\b", re.I),
]
POWER_PATTERNS = [re.compile(r"\bpower\b", re.I), re.compile(r"\bgenerator\b", re.I)]
TEMPORARY_PATTERNS = [re.compile(r"\btemporary\b", re.I), re.compile(r"\bshort[- ]term\b", re.I)]
MAINTENANCE_PATTERNS = [re.compile(r"\bdown\b", re.I), re.compile(r"\bpending\b", re.I), re.compile(r"\bnot operational\b", re.I)]


def build_combined_text(raw_row: dict, fields: Iterable[str]) -> str:
    lines = []
    for field in fields:
        value = raw_row.get(field)
        if value:
            lines.append(f"{field}: {value}")
    return "\n".join(lines)


def normalize_signal(signal: ExtractedSignal, raw_row: dict) -> ExtractedSignal:
    text = " ".join(str(v) for v in raw_row.values() if v).lower()
    if signal.canonical_name:
        if signal.kind == "equipment" and signal.canonical_name not in CANON_EQUIPMENT:
            signal.canonical_name = _match_synonym(signal.raw_mention, EQUIPMENT_SYNONYMS)
        elif signal.kind != "equipment" and signal.canonical_name not in CANON_SERVICES:
            signal.canonical_name = _match_synonym(signal.raw_mention, SERVICE_SYNONYMS)
    else:
        if signal.kind == "equipment":
            signal.canonical_name = _match_synonym(signal.raw_mention, EQUIPMENT_SYNONYMS)
        else:
            signal.canonical_name = _match_synonym(signal.raw_mention, SERVICE_SYNONYMS)

    if any(pattern.search(text) for pattern in REFERRAL_PATTERNS):
        if "referral_only" not in signal.constraints:
            signal.constraints.append("referral_only")
        if signal.status == "present":
            signal.status = "claimed_unverified"

    if any(pattern.search(text) for pattern in HEDGE_PATTERNS):
        signal.status = "conditional"
        if "staffing_dependent" not in signal.constraints:
            signal.constraints.append("staffing_dependent")

    if any(pattern.search(text) for pattern in TEMPORARY_PATTERNS):
        signal.status = "conditional"
        if "temporary" not in signal.constraints:
            signal.constraints.append("temporary")

    if any(pattern.search(text) for pattern in POWER_PATTERNS):
        if "power_dependent" not in signal.constraints:
            signal.constraints.append("power_dependent")

    if any(pattern.search(text) for pattern in MAINTENANCE_PATTERNS):
        signal.status = "conditional"
        if "maintenance_dependent" not in signal.constraints:
            signal.constraints.append("maintenance_dependent")

    return signal


def _match_synonym(text: str, synonyms: dict[str, list[re.Pattern[str]]]) -> str | None:
    for canon, patterns in synonyms.items():
        if any(pattern.search(text) for pattern in patterns):
            return canon
    return None
