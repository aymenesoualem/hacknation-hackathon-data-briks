const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function uploadCsv(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/ingest/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function plannerAsk(payload: unknown) {
  const res = await fetch(`${API_URL}/planner/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function facilityProfile(id: number) {
  const res = await fetch(`${API_URL}/facility/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
