import { useEffect, useState } from "react";
import { fetchTrainingData } from "./api.js";
import { useUnits } from "./UnitContext.jsx";
import { unitLabel } from "./units.js";
import Dashboard from "./components/Dashboard.jsx";
import ChatPanel from "./components/ChatPanel.jsx";

export default function App() {
  const { system, toggle } = useUnits();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTrainingData().then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 1100, margin: "0 auto", padding: 24 }}>
      <header style={{ display: "flex", alignItems: "flex-start",
                       justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0 }}>Cadence</h1>
          <p style={{ color: "#666", marginTop: 4 }}>
            Your personal AI endurance coach
          </p>
        </div>
        {/* One global units toggle. Flips the whole UI (dashboard + coach)
            between metric and imperial; the choice persists in localStorage. */}
        <button
          onClick={toggle}
          title="Switch units"
          style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #ccc",
                   background: "#fff", cursor: "pointer", fontSize: 13 }}
        >
          Units: {unitLabel(system)}
        </button>
      </header>

      {error && <p style={{ color: "crimson" }}>Error: {error} (is the backend running?)</p>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <Dashboard data={data} />
        <ChatPanel />
      </div>
    </div>
  );
}
