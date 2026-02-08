from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class ServiceDetail(BaseModel):
    available: bool = False
    details: Optional[str] = None


class Services(BaseModel):
    emergency_care: ServiceDetail = Field(default_factory=ServiceDetail)
    maternity: ServiceDetail = Field(default_factory=ServiceDetail)
    surgery: ServiceDetail = Field(default_factory=ServiceDetail)
    lab: ServiceDetail = Field(default_factory=ServiceDetail)


class Equipment(BaseModel):
    oxygen: bool = False
    ventilator: bool = False
    ultrasound: bool = False
    incubator: bool = False
    operating_microscope: bool = False
    anesthesia_machine: bool = False
    xray: bool = False


class Staffing(BaseModel):
    doctors: Optional[int] = None
    nurses: Optional[int] = None
    specialists: list[str] = Field(default_factory=list)


class Flag(BaseModel):
    type: str
    severity: str
    description: str
    evidence_paths: list[str] = Field(default_factory=list)


class FacilityCapabilityProfile(BaseModel):
    services: Services = Field(default_factory=Services)
    equipment: Equipment = Field(default_factory=Equipment)
    staffing: Staffing = Field(default_factory=Staffing)
    procedures: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    supports_path: str
    source_field: str
    row_id: str = ""
    start_char: int | None = None
    end_char: int | None = None
    quote: str

    @field_validator("quote")
    @classmethod
    def _limit_quote(cls, value: str) -> str:
        if len(value) <= 240:
            return value
        return value[:237] + "..."


class ExtractedSignal(BaseModel):
    kind: str
    raw_mention: str
    canonical_name: str | None
    status: str
    confidence: float = Field(ge=0, le=1)
    constraints: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ExtractionOutput(BaseModel):
    signals: list[ExtractedSignal] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceCitation(BaseModel):
    facility_id: int
    evidence_span_id: int
    supports_path: str
    quote: str
    source_field: str


class PlannerRequest(BaseModel):
    question: str
    filters: dict[str, Any] = Field(default_factory=dict)
    lat: Optional[float] = None
    lon: Optional[float] = None
    km: Optional[float] = None


class PlannerResponse(BaseModel):
    answer_text: str
    answer_json: dict[str, Any]
    citations: list[EvidenceCitation] = Field(default_factory=list)
    trace_id: int
