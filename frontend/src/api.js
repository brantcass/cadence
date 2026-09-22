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

export async function fetchPlan() {
  const res = await fetch(`${BASE}/api/plan`);
  if (!res.ok) throw new Error(`plan failed: ${res.status}`);
  return res.json();
}

export async function fetchStrength() {
  const res = await fetch(`${BASE}/api/strength`);
  if (!res.ok) throw new Error(`strength failed: ${res.status}`);
  return res.json();
}

export async function updateStrengthWeight(exerciseId, weightKg) {
  const res = await fetch(`${BASE}/api/strength/${exerciseId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weight_kg: weightKg }),
  });
  if (!res.ok) throw new Error(`weight update failed: ${res.status}`);
  return res.json();
}

export async function askCoach(message, history = [], unitSystem = "metric") {
  const res = await fetch(`${BASE}/api/coach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // The backend defaults to metric, but we always send the user's current
    // choice so the coach quotes distances/paces in the units they're viewing.
    body: JSON.stringify({ message, history, unit_system: unitSystem }),
  });
  if (!res.ok) throw new Error(`coach failed: ${res.status}`);
  return res.json();
}
