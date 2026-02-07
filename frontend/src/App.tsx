import { useState } from "react";
import { uploadCsv, plannerAsk, facilityProfile } from "./api";

type Tab = "ingest" | "planner" | "map" | "trace" | "reports";

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
  "Things that shouldn't move together",
  "Where is workforce for cardiology practicing",
  "Procedures depend on very few facilities",
  "Oversupply concentration vs scarcity of high complexity",
  "Gaps in development map where no orgs working despite need",
];

const KPI_CARDS = [
  { label: "Facilities processed" },
  { label: "Verified capabilities" },
  { label: "Suspected claims" },
  { label: "Medical deserts detected" },
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
    <div className="app">
      <header className="top-nav">
        <div className="brand">
          <div className="brand-mark">VF</div>
          <div>
            <h1>Bridging Medical Deserts</h1>
            <p>Virtue Foundation - Intelligent document parsing agents</p>
          </div>
        </div>
        <nav className="nav-tabs">
          <button className={tab === "ingest" ? "tab active" : "tab"} onClick={() => setTab("ingest")}>
            Upload
          </button>
          <button className={tab === "planner" ? "tab active" : "tab"} onClick={() => setTab("planner")}>
            Explore
          </button>
          <button className={tab === "map" ? "tab active" : "tab"} onClick={() => setTab("map")}>
            Map
          </button>
          <button className={tab === "trace" ? "tab active" : "tab"} onClick={() => setTab("trace")}>
            Trace
          </button>
          <button className={tab === "reports" ? "tab active" : "tab"} onClick={() => setTab("reports")}>
            Reports
          </button>
        </nav>
        <div className="nav-actions">
          <button className="btn btn-secondary">User Menu</button>
          <button className="btn btn-primary">New analysis</button>
        </div>
      </header>

      <main className="page">
        <div className="page-header">
          <div>
            <h2>Medical Coverage Intelligence</h2>
            <p>
              Parse facility documents, verify claims, and prioritize regions with limited access to
              care.
            </p>
          </div>
          <div className="dataset-select">
            <label>
              Dataset
              <select>
                <option>National facility registry - Feb 2026</option>
                <option>Regional extraction pilot - Jan 2026</option>
              </select>
            </label>
          </div>
        </div>

        {error && <div className="alert alert-critical">{error}</div>}

        <section className="kpi-strip">
          {KPI_CARDS.map((kpi) => (
            <div key={kpi.label} className="card kpi-card">
              <div>
                <p className="kpi-label">{kpi.label}</p>
                <div className="skeleton" />
              </div>
              <div className="kpi-meta">
                <span className="badge badge-info">Awaiting data</span>
                <div className="sparkline" />
              </div>
            </div>
          ))}
        </section>

        {tab === "ingest" && (
          <section className="grid-2">
            <div className="card upload-card">
              <div className="card-header">
                <h3>Upload + parsing</h3>
                <span className="badge badge-info">CSV</span>
              </div>
              <div className="dropzone">
                <div>
                  <h4>Drag & drop facility files</h4>
                  <p>We will extract claims, evidence, and geocodes.</p>
                </div>
                <label className="btn btn-secondary">
                  Select file
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleUpload(file);
                    }}
                  />
                </label>
              </div>
              <div className="status-row">
                <span className="status-dot" />
                <p>{uploadStatus || "Awaiting upload."}</p>
              </div>
              <p className="helper">
                Sample data: backend/app/sample_data/sample_facilities.csv
              </p>
            </div>
            <div className="card progress-card">
              <div className="card-header">
                <h3>Extraction progress</h3>
                <span className="badge badge-info">Live</span>
              </div>
              <ul className="stepper">
                <li className="step active">Ingest</li>
                <li className="step active">Parse</li>
                <li className="step">Normalize</li>
                <li className="step">Verify</li>
                <li className="step">Output</li>
              </ul>
              <div className="skeleton-list">
                <div className="skeleton" />
                <div className="skeleton" />
                <div className="skeleton" />
              </div>
            </div>
            <div className="card dataset-preview">
              <div className="card-header">
                <h3>Dataset preview</h3>
                <span className="badge badge-info">Snapshot</span>
              </div>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Facility</th>
                      <th>Region</th>
                      <th>Procedure</th>
                      <th>Last updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td colSpan={4} className="empty-state">
                        No dataset loaded yet.
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="skeleton-list">
                <div className="skeleton" />
                <div className="skeleton" />
              </div>
            </div>
          </section>
        )}

        {tab === "planner" && (
          <section className="grid-2">
            <div className="card">
              <div className="card-header">
                <h3>Query bar</h3>
                <span className="badge badge-info">NL query</span>
              </div>
              <div className="query-bar">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask a question in plain language"
                />
                <button className="btn btn-primary" onClick={handleAsk}>
                  Analyze
                </button>
              </div>
              <div className="chip-row">
                <span className="chip active">Region: {region || "All"}</span>
                <span className="chip">Confidence: 0.7+</span>
                <span className="chip">Anomalies: include</span>
                <button className="btn btn-ghost btn-small">Reset filters</button>
              </div>
              <label>
                Template
                <select value={question} onChange={(e) => setQuestion(e.target.value)}>
                  {QUESTION_TEMPLATES.map((q) => (
                    <option key={q} value={q}>
                      {q}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Query context
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
              <div className="advanced-filters">
                <label>
                  Expert mode
                  <div className="toggle">
                    <input type="checkbox" />
                    <span className="toggle-track" />
                  </div>
                </label>
                <label>
                  Confidence threshold
                  <input placeholder="0.65" />
                </label>
                <label>
                  Constraints
                  <input placeholder="Exclude private-only facilities" />
                </label>
              </div>
              <div className="button-row">
                <button className="btn btn-primary" onClick={handleAsk}>
                  Run analysis
                </button>
                <button className="btn btn-ghost">Save as template</button>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h3>Summary response</h3>
                <span className="badge badge-success">Verified</span>
              </div>
              {plannerResult ? (
                <div className="result">
                  <p>{plannerResult.answer_text}</p>
                  <pre>{JSON.stringify(plannerResult.answer_json, null, 2)}</pre>
                </div>
              ) : (
                <div className="result">
                  <p>
                    The agent synthesizes facility data and highlights where access is most limited.
                  </p>
                  <div className="pill-row">
                    <span className="badge badge-info">Coverage gaps</span>
                    <span className="badge badge-warning">Anomalies</span>
                    <span className="badge badge-success">Verified</span>
                  </div>
                </div>
              )}
              <div className="divider" />
              <h4>Planner actions</h4>
              <ul className="checklist">
                <li className="checked">Identify region</li>
                <li className="checked">Select facilities</li>
                <li>Assign actions</li>
                <li>Export brief</li>
              </ul>
              <div className="template-actions">
                <button className="btn btn-secondary">Request equipment</button>
                <button className="btn btn-secondary">Route doctor</button>
                <button className="btn btn-secondary">Escalate verification</button>
              </div>
            </div>

            <div className="card table-card">
              <div className="card-header">
                <h3>Facility results</h3>
                <div className="pill-row">
                  <span className="badge badge-info">Source</span>
                  <span className="badge badge-warning">Flagged</span>
                </div>
              </div>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Facility</th>
                      <th>Region</th>
                      <th>Capability</th>
                      <th>Confidence</th>
                      <th>Status</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td colSpan={6} className="empty-state">
                        No results yet. Run an analysis to populate the table.
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card chart-card">
              <div className="card-header">
                <h3>Coverage analytics</h3>
                <span className="badge badge-info">Insights</span>
              </div>
              <div className="chart-grid">
                <div className="chart-panel">
                  <h4>Facilities by region</h4>
                  <div className="bar-chart">
                    <div className="empty-state">Awaiting backend data.</div>
                  </div>
                </div>
                <div className="chart-panel">
                  <h4>Procedure breadth vs equipment</h4>
                  <div className="scatter-chart">
                    <div className="empty-state">Awaiting backend data.</div>
                  </div>
                </div>
                <div className="chart-panel">
                  <h4>Correlation heatmap</h4>
                  <div className="heatmap">
                    <div className="empty-state">Awaiting backend data.</div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {tab === "map" && (
          <section className="grid-2">
            <div className="card filter-card">
              <div className="card-header">
                <h3>Filters</h3>
                <span className="badge badge-info">Region</span>
              </div>
              <label>
                Region
                <select>
                  <option>All regions</option>
                  <option>North</option>
                  <option>South</option>
                  <option>East</option>
                  <option>West</option>
                </select>
              </label>
              <label>
                Capability
                <select>
                  <option>All capabilities</option>
                  <option>Cardiology</option>
                  <option>Surgery</option>
                  <option>Maternity</option>
                </select>
              </label>
              <label>
                Confidence
                <select>
                  <option>All</option>
                  <option>Above 0.8</option>
                  <option>0.5 - 0.8</option>
                  <option>Below 0.5</option>
                </select>
              </label>
              <label>
                Anomalies
                <select>
                  <option>Include anomalies</option>
                  <option>Verified only</option>
                </select>
              </label>
            </div>
            <div className="card map-card">
              <div className="card-header">
                <h3>Coverage map</h3>
                <span className="badge badge-info">Preview</span>
              </div>
              <div className="map-canvas">
                <div className="map-grid" />
                <div className="empty-state overlay">Map data loads from backend.</div>
                <div className="legend">
                  <h4>Legend</h4>
                  <p>
                    <span className="legend-dot coverage" />
                    Coverage density
                  </p>
                  <p>
                    <span className="legend-dot desert" />
                    Desert zones
                  </p>
                  <p>
                    <span className="legend-dot facility" />
                    Facility pins
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {tab === "trace" && (
          <section className="grid-2">
            <div className="card">
              <div className="card-header">
                <h3>Facility detail</h3>
                <span className="badge badge-info">Profile</span>
              </div>
              <label>
                Facility ID
                <input value={facilityId} onChange={(e) => setFacilityId(e.target.value)} />
              </label>
              <button className="btn btn-primary" onClick={handleFacilityLookup}>
                Load profile
              </button>
              <div className="summary-grid">
                <div className="summary-card">
                  <p>Equipment</p>
                  <h4>12 verified</h4>
                </div>
                <div className="summary-card">
                  <p>Procedures</p>
                  <h4>38 listed</h4>
                </div>
                <div className="summary-card">
                  <p>Staff</p>
                  <h4>74 listed</h4>
                </div>
                <div className="summary-card">
                  <p>Confidence</p>
                  <h4>0.81</h4>
                </div>
              </div>
              <div className="split">
                <div>
                  <h4>What the agent believes</h4>
                  <p>
                    This facility is a regional referral center with verified cardiology equipment
                    and limited surgical capacity.
                  </p>
                </div>
                <div>
                  <h4>Evidence</h4>
                  <p>Source citations, equipment manifests, staffing rosters.</p>
                </div>
              </div>
              {facilityResult && (
                <div className="result">
                  <pre>{JSON.stringify(facilityResult, null, 2)}</pre>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h3>Trace timeline</h3>
                <span className="badge badge-info">Agentic steps</span>
              </div>
              <div className="timeline">
                <div className="empty-state">Trace steps will appear after analysis.</div>
              </div>
            </div>

            <div className="card facility-drawer">
              <div className="card-header">
                <h3>Facility drawer</h3>
                <span className="badge badge-info">Details</span>
              </div>
              <div className="drawer-tabs">
                <button className="tab active">Summary</button>
                <button className="tab">Evidence</button>
                <button className="tab">Flags</button>
                <button className="tab">History</button>
              </div>
              <div className="summary-grid">
                <div className="summary-card">
                  <p>Utilization</p>
                  <h4>78%</h4>
                </div>
                <div className="summary-card">
                  <p>Coverage gap</p>
                  <h4>42 km</h4>
                </div>
              </div>
              <div className="evidence-panel">
                <h4>Evidence panel</h4>
                <div className="snippet">
                  <p>
                    "Facility reports <span className="highlight">two cardiac cath labs</span>
                    installed in 2024. Staffing includes <span className="highlight">one specialist
                    cardiologist</span>."
                  </p>
                  <span className="badge badge-info">Source: Registry PDF</span>
                </div>
                <div className="snippet warning">
                  <p>
                    "Equipment list shows <span className="highlight">no anesthesia units</span>
                    despite surgery claims."
                  </p>
                  <span className="badge badge-warning">Flagged</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {tab === "reports" && (
          <section className="grid-2">
            <div className="card plan-wizard">
              <div className="card-header">
                <h3>Plan an intervention</h3>
                <span className="badge badge-info">Wizard</span>
              </div>
              <ol className="wizard-steps">
                <li className="active">
                  <strong>Choose region / radius / landmark</strong>
                  <p>Default: 50 km radius around capital clinic.</p>
                </li>
                <li>
                  <strong>Select target service</strong>
                  <p>Cardiology, C-section, trauma, or emergency.</p>
                </li>
                <li>
                  <strong>Review coverage + gaps</strong>
                  <p>See verified coverage and flagged facilities.</p>
                </li>
                <li>
                  <strong>Select facilities + actions</strong>
                  <p>Use templates with clear recommendations.</p>
                </li>
                <li>
                  <strong>Export brief</strong>
                  <p>Generate PDF-like brief and share link.</p>
                </li>
              </ol>
              <div className="wizard-actions">
                <button className="btn btn-secondary">Back</button>
                <button className="btn btn-primary">Next</button>
              </div>
              <div className="expert-row">
                <label>
                  Expert mode
                  <div className="toggle">
                    <input type="checkbox" />
                    <span className="toggle-track" />
                  </div>
                </label>
                <div className="chip-row">
                  <span className="chip">Confidence 0.65+</span>
                  <span className="chip">Exclude anomalies</span>
                  <span className="chip">Constraint: budget cap</span>
                </div>
              </div>
            </div>
            <div className="card reports-card">
              <div className="card-header">
                <h3>Reports</h3>
                <span className="badge badge-info">Export</span>
              </div>
              <div className="report-grid">
                <div className="report-item">
                  <h4>Regional brief</h4>
                  <p>Export a summary of gaps, risks, and interventions.</p>
                  <button className="btn btn-secondary">Generate</button>
                </div>
                <div className="report-item">
                  <h4>Facility dossier</h4>
                  <p>Package claims, evidence, and confidence notes.</p>
                  <button className="btn btn-secondary">Generate</button>
                </div>
                <div className="report-item">
                  <h4>Desert risk list</h4>
                  <p>Prioritize zones by severity and population impact.</p>
                  <button className="btn btn-secondary">Generate</button>
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
