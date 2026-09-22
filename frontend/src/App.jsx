import { useState } from "react";
import { useUnits } from "./UnitContext.jsx";
import { unitLabel } from "./units.js";
import Dashboard from "./components/Dashboard.jsx";
import Plan from "./components/Plan.jsx";
import Strength from "./components/Strength.jsx";
import ChatPanel from "./components/ChatPanel.jsx";

const TABS = [
  { id: "plan", label: "Plan" },
  { id: "dashboard", label: "Dashboard" },
  { id: "strength", label: "Strength" },
];

export default function App() {
  const { system, toggle } = useUnits();
  const [tab, setTab] = useState("plan");

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1 style={{ margin: 0 }}>Cadence</h1>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Your personal AI endurance coach
          </p>
        </div>
        {/* One global units toggle — flips the whole UI (dashboard, plan, coach)
            between metric and imperial; the choice persists in localStorage. */}
        <button className="btn" onClick={toggle} title="Switch units">
          Units: {unitLabel(system)}
        </button>
      </header>

      <div className="cols">
        <main>
          <nav className="tabbar">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`tab ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>

          {tab === "plan" && <Plan />}
          {tab === "dashboard" && <Dashboard />}
          {tab === "strength" && <Strength />}
        </main>

        {/* Coach stays visible beside every tab — it's the point of the app. */}
        <aside>
          <ChatPanel />
        </aside>
      </div>
    </div>
  );
}
