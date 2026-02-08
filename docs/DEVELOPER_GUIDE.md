# VF Agent Developer Guide

This guide explains how the current codebase works, the data flow, and what you need to extend it yourself.

## High-level architecture

- Backend: FastAPI + SQLAlchemy + LangGraph (extraction) + LangChain agent (routing + explanation).
- Frontend: React (Vite + TS) with 3 pages (Ingest, Planner, Facility).
- Database: Postgres in Docker, SQLite for local dev (default).

Core flow:
1. Ingest CSV -> persist facilities -> run extraction (LLM agent if API key, else rule-based) -> persist extractions + evidence -> detect anomalies.
2. Planner endpoint -> LangChain agent routes to a deterministic tool -> tool runs deterministic SQL/logic -> LangChain explains results -> response stored with trace.

## Directory map

- `backend/app/main.py` FastAPI routes, planner orchestration, trace logging.
- `backend/app/models.py` SQLAlchemy models (tables).
- `backend/app/db.py` DB engine + session.
- `backend/app/config.py` config (envs, DB URL, OpenAI).
- `backend/app/ingest.py` CSV ingest + run extraction graph + anomaly refresh.
- `backend/app/agents/langgraph_pipeline.py` extraction + evidence (LLM or rule-based).
- `backend/app/agents/tools.py` deterministic tools (SQL/logic only).
- `backend/app/agents/langchain_agent.py` LLM routing + explanation + extraction helper.
- `backend/app/anomalies.py` anomaly detection rules.
- `backend/tests/test_must_have.py` Must Have tests.
- `frontend/src/App.tsx` UI shell (ingest/planner/map/trace/reports).
- `frontend/src/api.ts` fetch calls to backend.
- `frontend/src/main.tsx` Leaflet CSS + marker icon setup.
- `backend/app/sample_data/sample_facilities.csv` sample data.

## Data model (Postgres/SQLite)

Tables:
- `facilities`: input rows + raw JSON.
- `extractions`: normalized capability profile JSON per facility.
- `evidence_spans`: row-level quotes and field paths.
- `anomalies`: rule-based misrepresentation flags.
- `agent_traces`: store planner/extraction trace JSON.
- `planner_queries`: saved questions + answers + citations.

All models are in `backend/app/models.py`. Alembic migrations are in `backend/alembic/`.

## Facility capability schema

Pydantic model: `FacilityCapabilityProfile` in `backend/app/schemas.py`
- `services`: emergency_care, maternity, surgery, lab (each has `available` + `details`)
- `equipment`: oxygen, ventilator, ultrasound, incubator, operating_microscope, anesthesia_machine, xray
- `staffing`: doctors, nurses, specialists[]
- `procedures`: list of normalized procedure names
- `notes`: normalized notes (e.g., `visiting`, `ngo`)

This is what gets stored in `extractions.extracted_json`.

## Ingest + extraction pipeline

Entry point: `POST /ingest/upload` in `backend/app/main.py`.

1. `ingest_csv()` in `backend/app/ingest.py`
   - Parses CSV into `facilities`.
   - Stores structured fields into `raw_structured_json`.
   - Stores free text into `raw_text_json`.
2. LangGraph pipeline in `backend/app/agents/langgraph_pipeline.py`
   - `clean_and_chunk`: merges text into one string.
   - `extract_profile`: LLM extraction via LangChain agent (if API key) with rule-based fallback.
   - `collect_evidence`: tracks evidence counts.
   - `persist`: saves `extractions` and `evidence_spans`.
   - `log_trace`: stores extraction trace.
3. `refresh_anomalies()` in `backend/app/anomalies.py`
   - Inserts `anomalies` based on rule checks.

### Extraction rules to extend
If you want rule-based fallback coverage, edit keyword dictionaries in `langgraph_pipeline.py`:
- `SERVICE_KEYWORDS`
- `EQUIPMENT_KEYWORDS`
- `PROCEDURE_KEYWORDS`
- `NOTE_KEYWORDS`

Add rules by adding new keywords and mapping to `supports_path`.

## Planner + agent routing (LangChain)

Entry: `POST /planner/ask` in `backend/app/main.py`.

Planner flow:
1. `route_query()` in `backend/app/agents/langchain_agent.py` returns tool + args (no computation).
2. Deterministic tool runs from `backend/app/agents/tools.py`.
3. `explain_results()` converts tool output to natural language.
4. Response saved to `agent_traces` + `planner_queries`.
5. API returns `answer_text`, `answer_json`, `citations`, `trace_id`.

### Tools
Tools live in `backend/app/agents/tools.py` and are wrapped for LangChain in `langchain_agent.py`.

Available tools:
- `sql_count_by_capability`
- `sql_facility_services`
- `sql_find_facilities_by_service`
- `sql_region_ranking`
- `geo_within_km`
- `geo_cold_spots`
- `anomaly_unrealistic_procedure_breadth`
- `correlation_feature_movement`
- `workforce_where_practicing`
- `scarcity_dependency_on_few`
- `oversupply_vs_scarcity`
- `ngo_gap_map`

Each tool returns:
- `result rows` (varies by tool)
- `metrics`
- `citations` (when derived from extracted text)
- small `explain` string (optional)

### Extending tools
1. Implement tool logic in `tools.py`.
2. Add tool name to `SUPPORTED_TOOLS` in `langchain_agent.py`.
3. Update `_run_deterministic_tool()` in `backend/app/main.py`.
4. Update tests to cover the new question type.

### Geo behavior
`geo_within_km()` uses `backend/app/geo.py` (Haversine).
If lat/lon/km missing, the router returns `MISSING_GEO`.

## Geolocation dashboard

- Backend endpoint: `GET /facilities/geo`
  - Returns facility id, name, region, district, lat/lon, and facility_type.
- Frontend map: Leaflet (OpenStreetMap tiles) in `frontend/src/App.tsx`
  - Pins rendered from `/facilities/geo`
  - Map centers on the average of available coordinates

### Extending the map
1. Add filters to `/facilities/geo` (region, facility_type).
2. Pass filter params from the Map tab in `App.tsx`.
3. Add clustering/heatmap if needed (Leaflet plugins).

## Anomaly detection

Rules in `backend/app/anomalies.py`:
- `unrealistic_breadth_vs_infra`
- `size_vs_surgery_mismatch`
- `equipment_mismatch`

To add rules:
1. Add checks in `detect_anomalies_for_facility()`.
2. Re-run `refresh_anomalies()` after ingest.

## Must-Have tests

File: `backend/tests/test_must_have.py`

Coverage:
- Q1.1, Q1.2, Q1.3, Q1.4, Q1.5
- Q2.1, Q2.3
- Q4.4, Q4.7, Q4.8, Q4.9
- Q6.1, Q7.5, Q7.6, Q8.3

To extend tests:
- Add a new `_ask()` call.
- Assert that `answer_json` has expected keys and non-empty values.

## Environment variables

Required for agentic mode:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default `gpt-4o-mini`)

DB:
- `DATABASE_URL` (default SQLite local)

Docker compose sets Postgres URL for the backend.

## Running locally

Backend:
```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
python -m app.main
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Load sample data:
```bash
curl -F "file=@backend/app/sample_data/sample_facilities.csv" http://localhost:8000/ingest/upload
```

## Common extension tasks

### Add a new question type
1. Add a tool in `tools.py`.
2. Wrap in LangChain in `langchain_agent.py`.
3. Update the UI template list in `frontend/src/App.tsx`.
4. Add a test case.

### Add new extraction fields
1. Update `FacilityCapabilityProfile` in `schemas.py`.
2. Update `extract_profile()` in `langgraph_pipeline.py`.
3. Add evidence `supports_path` for new fields.
4. Update tools that query these fields.

### Add more evidence
Use `get_evidence_for_prefix()` or `get_evidence_for_facility_field()` in `tools.py` to attach citations.

## Known limitations (intentional)

- LLM extraction is single-pass (no multi-step review).
- LangChain router selects a single deterministic tool.
- Geo cold spots are region-based only (no grid coverage).
- No advanced ontology mapping beyond tool selection.

You can lift these by:
- Adding multi-step extraction validation.
- Allowing multi-tool orchestration in the planner.
- Adding spatial grids for cold spots.

## Quick mental model

- `ingest -> extract -> evidence -> anomalies`
- `planner -> agent -> tool -> response + trace`

That’s the backbone. Extend the tools and schema to grow the system.
