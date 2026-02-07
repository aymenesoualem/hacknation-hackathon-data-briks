import { useState } from "react";
import { uploadCsv, plannerAsk, facilityProfile } from "./api";

type Tab = "ingest" | "planner" | "facility";

const QUESTION_TEMPLATES = [
  "How many hospitals have cardiology?",
  "How many hospitals in North have ability to perform cardiology?",
  "What services does North Valley Hospital offer?",
  "Any clinics in South that do maternity?",
  "Which region has the most cardiology hospitals?",
  "How many hospitals treating cardiology are within 20 km of location?",
  "Largest cold spots where a critical procedure is absent within 50 km",
  "Facilities claim unrealistic number of procedures relative to size",
  "Correlations exist between facility characteristics that move together",
  "Unusually high breadth of procedures relative to infrastructure signals",
  "Things that shouldn\u0027t move together",
  "Where is workforce for cardiology practicing",
  "Procedures depend on very few facilities",
  "Oversupply concentration vs scarcity of high complexity",
  "Gaps in development map where no orgs working despite need",
];

export default function App() {
  const [tab, setTab] = useState<Tab>("ingest");
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [question, setQuestion] = useState(QUESTION_TEMPLATES[0]);
  const [region, setRegion] = useState("");
  const [district, setDistrict] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [km, setKm] = useState("");
  const [plannerResult, setPlannerResult] = useState<any>(null);
  const [facilityId, setFacilityId] = useState("");
  const [facilityResult, setFacilityResult] = useState<any>(null);
  const [error, setError] = useState<string>("");

  async function handleUpload(file: File) {
    setError("");
    setUploadStatus("Uploading...");
    try {
      const res = await uploadCsv(file);
      setUploadStatus(`Ingested ${res.ingested} rows`);
    } catch (err: any) {
      setError(err.message || "Upload failed");
    }
  }

  async function handleAsk() {
    setError("");
    try {
      const payload: any = {
        question,
        filters: { region: region || undefined, district: district || undefined },
      };
      if (lat && lon && km) {
        payload.lat = Number(lat);
        payload.lon = Number(lon);
        payload.km = Number(km);
      }
      const res = await plannerAsk(payload);
      setPlannerResult(res);
    } catch (err: any) {
      setError(err.message || "Planner failed");
    }
  }

  async function handleFacilityLookup() {
    setError("");
    try {
      const res = await facilityProfile(Number(facilityId));
      setFacilityResult(res);
    } catch (err: any) {
      setError(err.message || "Facility lookup failed");
    }
  }

  return (
    <div className="container">
      <header>
        <h1>VF Agent</h1>
        <p className="disclaimer">
          Disclaimer: Internal dataset only. External data is not used in responses.
        </p>
      </header>

      <nav className="tabs">
        <button className={tab === "ingest" ? "active" : ""} onClick={() => setTab("ingest")}>
          Ingest
        </button>
        <button className={tab === "planner" ? "active" : ""} onClick={() => setTab("planner")}>
          Planner
        </button>
        <button className={tab === "facility" ? "active" : ""} onClick={() => setTab("facility")}>
          Facility
        </button>
      </nav>

      {error && <div className="error">{error}</div>}

      {tab === "ingest" && (
        <section>
          <h2>Upload CSV</h2>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
            }}
          />
          <p className="status">{uploadStatus}</p>
          <p>Sample data is available in backend/app/sample_data/sample_facilities.csv</p>
        </section>
      )}

      {tab === "planner" && (
        <section>
          <h2>Planner</h2>
          <label>
            Question type
            <select value={question} onChange={(e) => setQuestion(e.target.value)}>
              {QUESTION_TEMPLATES.map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </label>
          <label>
            Question
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
          </label>
          <div className="grid">
            <label>
              Region
              <input value={region} onChange={(e) => setRegion(e.target.value)} />
            </label>
            <label>
              District
              <input value={district} onChange={(e) => setDistrict(e.target.value)} />
            </label>
            <label>
              Latitude
              <input value={lat} onChange={(e) => setLat(e.target.value)} />
            </label>
            <label>
              Longitude
              <input value={lon} onChange={(e) => setLon(e.target.value)} />
            </label>
            <label>
              Km
              <input value={km} onChange={(e) => setKm(e.target.value)} />
            </label>
          </div>
          <button onClick={handleAsk}>Ask</button>
          {plannerResult && (
            <div className="result">
              <h3>Answer</h3>
              <p>{plannerResult.answer_text}</p>
              <pre>{JSON.stringify(plannerResult.answer_json, null, 2)}</pre>
              <h4>Citations</h4>
              <pre>{JSON.stringify(plannerResult.citations, null, 2)}</pre>
              <p>Trace ID: {plannerResult.trace_id}</p>
            </div>
          )}
        </section>
      )}

      {tab === "facility" && (
        <section>
          <h2>Facility Profile</h2>
          <label>
            Facility ID
            <input value={facilityId} onChange={(e) => setFacilityId(e.target.value)} />
          </label>
          <button onClick={handleFacilityLookup}>Load</button>
          {facilityResult && (
            <div className="result">
              <pre>{JSON.stringify(facilityResult, null, 2)}</pre>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
