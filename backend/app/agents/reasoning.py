from __future__ import annotations

from dataclasses import dataclass


SERVICE_MAP = {
    "emergency": "emergency_care",
    "er": "emergency_care",
    "urgent care": "emergency_care",
    "maternity": "maternity",
    "obstetric": "maternity",
    "labor": "maternity",
    "delivery": "maternity",
    "surgery": "surgery",
    "surgical": "surgery",
    "lab": "lab",
    "laboratory": "lab",
}

PROCEDURE_MAP = {
    "cardiology": "cardiology",
    "cardiac": "cardiology",
    "c-section": "c_section",
    "cesarean": "c_section",
    "appendectomy": "appendectomy",
    "dialysis": "dialysis",
    "orthopedic": "orthopedic_surgery",
    "orthopaedic": "orthopedic_surgery",
    "cataract": "cataract_surgery",
}

EQUIPMENT_MAP = {
    "oxygen": "oxygen",
    "ventilator": "ventilator",
    "ultrasound": "ultrasound",
    "incubator": "incubator",
    "operating microscope": "operating_microscope",
    "anesthesia machine": "anesthesia_machine",
    "x-ray": "xray",
    "xray": "xray",
}


@dataclass
class NormalizedQuery:
    service: str | None = None
    procedure: str | None = None
    equipment: str | None = None
    subspecialty: str | None = None


def normalize_question(question: str) -> NormalizedQuery:
    q = question.lower()
    service = None
    procedure = None
    equipment = None
    subspecialty = None

    for key, value in SERVICE_MAP.items():
        if key in q:
            service = value
            break

    for key, value in PROCEDURE_MAP.items():
        if key in q:
            procedure = value
            break

    for key, value in EQUIPMENT_MAP.items():
        if key in q:
            equipment = value
            break

    if "cardiology" in q:
        subspecialty = "cardiology"
    if "neonatal" in q:
        subspecialty = "neonatology"

    return NormalizedQuery(service=service, procedure=procedure, equipment=equipment, subspecialty=subspecialty)
