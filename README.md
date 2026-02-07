# VF Agent

Intelligent Document Parsing + analytics agent for healthcare facility capability data.

## Quick start

```bash
docker compose up --build
```

Backend runs on `http://localhost:8000` and frontend on `http://localhost:5173`.

## Load sample data

```bash
curl -F "file=@backend/app/sample_data/sample_facilities.csv" http://localhost:8000/ingest/upload
```

## Must Have query examples

```bash
curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many hospitals have cardiology?"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many hospitals in North have ability to perform cardiology?","filters":{"region":"North"}}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What services does North Valley Hospital offer?","filters":{"facility":"North Valley Hospital"}}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Any clinics in South that do maternity?","filters":{"region":"South"}}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Which region has the most cardiology hospitals?"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many hospitals treating cardiology are within 20 km of location?","lat":0.8,"lon":36.3,"km":20}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Largest cold spots where a critical procedure is absent within 50 km","km":50}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Facilities claim unrealistic number of procedures relative to size"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Correlations exist between facility characteristics that move together"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Unusually high breadth of procedures relative to infrastructure signals"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Things that shouldn\u0027t move together"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Where is workforce for cardiology practicing"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Procedures depend on very few facilities"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Oversupply concentration vs scarcity of high complexity"}'

curl -X POST http://localhost:8000/planner/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Gaps in development map where no orgs working despite need"}'
```

## Project structure

- `backend/` FastAPI + LangGraph pipeline + Postgres
- `frontend/` Vite React UI
- `docker-compose.yml` local-first stack
