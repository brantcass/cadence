// Tiny API layer. Base URL points at the local FastAPI server.
const BASE = "http://localhost:8000";

export async function fetchTrainingData() {
  const res = await fetch(`${BASE}/api/training-data`);
  if (!res.ok) throw new Error(`training-data failed: ${res.status}`);
  return res.json();
}

export async function fetchMetrics() {
  const res = await fetch(`${BASE}/api/metrics`);
  if (!res.ok) throw new Error(`metrics failed: ${res.status}`);
  return res.json();
}

export async function askCoach(message, history = []) {
  const res = await fetch(`${BASE}/api/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) throw new Error(`coach failed: ${res.status}`);
  return res.json();
}
