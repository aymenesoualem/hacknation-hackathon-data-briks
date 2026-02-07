import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+pysqlite:////tmp/vf_agent_test.db"

from fastapi.testclient import TestClient

from app.main import app
from app.db import engine
from app.models import Base
from app.ingest import ingest_csv


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    sample_path = Path(__file__).resolve().parents[1] / "app" / "sample_data" / "sample_facilities.csv"
    ingest_csv(sample_path.read_text(encoding="utf-8"))


client = TestClient(app)


def _ask(question: str, **payload):
    response = client.post("/planner/ask", json={"question": question, **payload})
    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"]
    assert "answer_json" in body
    return body


def test_q1_1_count_cardiology():
    body = _ask("How many hospitals have cardiology?")
    assert body["answer_json"]["count"] > 0


def test_q1_2_count_procedure_in_region():
    body = _ask("How many hospitals in North have ability to perform cardiology?", filters={"region": "North"})
    assert body["answer_json"]["count"] > 0


def test_q1_3_services_offer():
    body = _ask("What services does North Valley Hospital offer?", filters={"facility": "North Valley"})
    assert body["answer_json"]["services"]


def test_q1_4_clinic_service_in_area():
    body = _ask("Any clinics in South that do maternity?", filters={"region": "South"})
    assert body["answer_json"]["services"] or body["answer_json"].get("facilities") is not None


def test_q1_5_region_most_type():
    body = _ask("Which region has the most cardiology hospitals?")
    assert body["answer_json"]["ranking"]


def test_q2_1_within_km():
    body = _ask(
        "How many hospitals treating cardiology are within 20 km of location?",
        lat=0.8,
        lon=36.3,
        km=20,
    )
    assert len(body["answer_json"]["results"]) >= 0


def test_q2_3_cold_spots():
    body = _ask("Largest cold spots where a critical procedure is absent within 50 km")
    assert "cold_spots" in body["answer_json"]


def test_q4_4_unrealistic_breadth():
    body = _ask("Facilities claim unrealistic number of procedures relative to size")
    assert "results" in body["answer_json"]


def test_q4_7_correlations_move_together():
    body = _ask("Correlations exist between facility characteristics that move together")
    assert "results" in body["answer_json"]


def test_q4_8_high_breadth_vs_infra():
    body = _ask("Unusually high breadth of procedures relative to infrastructure signals")
    assert "results" in body["answer_json"]


def test_q4_9_shouldnt_move_together():
    body = _ask("Things that shouldn\u0027t move together")
    assert "results" in body["answer_json"]


def test_q6_1_workforce():
    body = _ask("Where is workforce for cardiology practicing")
    assert "results" in body["answer_json"]


def test_q7_5_dependency_on_few():
    body = _ask("Procedures depend on very few facilities")
    assert "providers" in body["answer_json"]


def test_q7_6_oversupply_vs_scarcity():
    body = _ask("Oversupply concentration vs scarcity of high complexity")
    assert "low_complexity_count" in body["answer_json"]


def test_q8_3_gap_map():
    body = _ask("Gaps in development map where no orgs working despite need")
    assert "regions_without_ngo_mentions" in body["answer_json"]
