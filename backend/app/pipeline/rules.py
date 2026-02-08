from __future__ import annotations

from typing import Iterable

from app.schemas import FacilityCapabilityProfile, Flag, ExtractedSignal

MIN_REQUIREMENTS = {
    "c_section": {
        "requires_any": [["operating_room", "or_table"]],
        "requires_all": [["anesthesia_machine", "anesthesia_staff_signal"]],
    },
    "icu": {
        "requires_any": [["ventilator", "monitors"]],
        "requires_all": [["icu_staffing_signal"]],
    },
    "ct": {
        "requires_any": [["ct"]],
        "requires_all": [],
    },
}


def apply_confidence_policy(signals: list[ExtractedSignal], raw_row: dict) -> list[ExtractedSignal]:
    for signal in signals:
        if signal.status == "claimed_unverified":
            signal.confidence = min(signal.confidence, 0.55)
        if signal.status == "conditional":
            signal.confidence = min(signal.confidence, 0.7)
        if signal.status == "absent":
            signal.confidence = min(signal.confidence, 0.2)
    return signals


def derive_profile(signals: list[ExtractedSignal], raw_row: dict) -> FacilityCapabilityProfile:
    profile = FacilityCapabilityProfile()
    for signal in signals:
        if not signal.canonical_name:
            continue

        if signal.kind == "equipment":
            _apply_equipment(profile, signal)
        elif signal.kind in {"capability", "infrastructure"}:
            _apply_capability(profile, signal)
        elif signal.kind == "staffing":
            if signal.canonical_name not in profile.staffing.specialists:
                profile.staffing.specialists.append(signal.canonical_name)

        if signal.constraints:
            profile.notes.extend(signal.constraints)

    profile.notes = sorted(set(profile.notes))
    return profile


def compute_flags(derived_profile: FacilityCapabilityProfile, raw_row: dict) -> list[Flag]:
    flags: list[Flag] = []

    if "c_section" in derived_profile.procedures:
        if not _has_equipment(derived_profile, ["anesthesia_machine"]):
            flags.append(
                Flag(
                    type="c_section_missing_anesthesia",
                    severity="warning",
                    description="C-section listed without anesthesia equipment.",
                    evidence_paths=["equipment.anesthesia_machine"],
                )
            )

    if "icu" in derived_profile.procedures and not _has_equipment(derived_profile, ["ventilator", "monitors"]):
        flags.append(
            Flag(
                type="icu_claim_without_support",
                severity="critical",
                description="ICU claim without ventilator or monitoring equipment.",
                evidence_paths=["equipment.ventilator", "equipment.monitors"],
            )
        )

    if "ct" in derived_profile.procedures and not _has_equipment(derived_profile, ["ct"]):
        flags.append(
            Flag(
                type="ct_claim_without_device",
                severity="warning",
                description="CT service listed without CT equipment confirmed.",
                evidence_paths=["equipment.ct"],
            )
        )

    return flags


def _apply_capability(profile: FacilityCapabilityProfile, signal: ExtractedSignal) -> None:
    name = signal.canonical_name or ""
    if name == "emergency_care":
        profile.services.emergency_care.available = signal.status in {"present", "conditional"}
        profile.services.emergency_care.details = _detail_from_signal(signal)
    elif name == "maternity":
        profile.services.maternity.available = signal.status in {"present", "conditional"}
        profile.services.maternity.details = _detail_from_signal(signal)
    elif name == "surgery":
        profile.services.surgery.available = signal.status in {"present", "conditional"}
        profile.services.surgery.details = _detail_from_signal(signal)
    elif name == "lab":
        profile.services.lab.available = signal.status in {"present", "conditional"}
        profile.services.lab.details = _detail_from_signal(signal)
    else:
        if name and name not in profile.procedures:
            profile.procedures.append(name)


def _apply_equipment(profile: FacilityCapabilityProfile, signal: ExtractedSignal) -> None:
    if signal.status not in {"present", "conditional"}:
        return
    mapping = {
        "oxygen": "oxygen",
        "ventilator": "ventilator",
        "ultrasound": "ultrasound",
        "incubator": "incubator",
        "operating_microscope": "operating_microscope",
        "anesthesia_machine": "anesthesia_machine",
        "xray": "xray",
    }
    field = mapping.get(signal.canonical_name or "")
    if field:
        setattr(profile.equipment, field, True)
    else:
        if signal.canonical_name and signal.canonical_name not in profile.procedures:
            profile.procedures.append(signal.canonical_name)


def _detail_from_signal(signal: ExtractedSignal) -> str | None:
    if signal.status == "conditional" and signal.constraints:
        return ", ".join(signal.constraints)
    if signal.status == "claimed_unverified":
        return "claimed unverified"
    return None


def _has_equipment(profile: FacilityCapabilityProfile, items: Iterable[str]) -> bool:
    for item in items:
        if hasattr(profile.equipment, item) and getattr(profile.equipment, item):
            return True
    return False
