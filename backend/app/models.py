from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship

from app.db import Base


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    region = Column(String, nullable=True)
    district = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    source_row_id = Column(String, nullable=True)
    raw_structured_json = Column(JSON, nullable=True)
    raw_text_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    extractions = relationship("Extraction", back_populates="facility")
    evidence_spans = relationship("EvidenceSpan", back_populates="facility")
    anomalies = relationship("Anomaly", back_populates="facility")


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    extracted_json = Column(JSON, nullable=False)
    confidence_json = Column(JSON, nullable=True)
    model_version = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    facility = relationship("Facility", back_populates="extractions")
    evidence_spans = relationship("EvidenceSpan", back_populates="extraction")


class EvidenceSpan(Base):
    __tablename__ = "evidence_spans"

    id = Column(Integer, primary_key=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    extraction_id = Column(Integer, ForeignKey("extractions.id"), nullable=False)
    source_row_id = Column(String, nullable=True)
    source_field = Column(String, nullable=False)
    quote = Column(String, nullable=False)
    supports_path = Column(String, nullable=False)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    facility = relationship("Facility", back_populates="evidence_spans")
    extraction = relationship("Extraction", back_populates="evidence_spans")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    description = Column(String, nullable=False)
    evidence_span_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    facility = relationship("Facility", back_populates="anomalies")


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True)
    trace_type = Column(String, nullable=False)
    trace_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PlannerQuery(Base):
    __tablename__ = "planner_queries"

    id = Column(Integer, primary_key=True)
    query_text = Column(String, nullable=False)
    answer_text = Column(String, nullable=False)
    answer_json = Column(JSON, nullable=False)
    citations_json = Column(JSON, nullable=True)
    trace_id = Column(Integer, ForeignKey("agent_traces.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
