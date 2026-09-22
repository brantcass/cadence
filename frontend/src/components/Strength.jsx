import { useEffect, useState } from "react";
import { fetchStrength, updateStrengthWeight } from "../api.js";
import { useUnits } from "../UnitContext.jsx";
import { kgToLb, lbToKg, IMPERIAL } from "../units.js";
import { colors } from "../theme.js";

// Strength: the two condensed strength sessions (the marathon-build version of the
// athlete's 6-day PPL split). Working weights are editable and persist to SQLite;
// they start blank for the athlete to fill in over time.
export default function Strength() {
  const { system } = useUnits();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState({});   // id -> in-progress text (user's units)

  useEffect(() => {
    fetchStrength().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="card" style={{ color: "crimson" }}>Error: {error} (is the backend running?)</div>;
  if (!data) return <div className="card muted">Loading strength plan…</div>;

  const imperial = system === IMPERIAL;
  const wUnit = imperial ? "lb" : "kg";
  const toDisplay = (kg) => (kg == null ? "" : (imperial ? kgToLb(kg) : kg).toFixed(1).replace(/\.0$/, ""));

  async function commit(ex) {
    const text = draft[ex.id];
    if (text === undefined) return;                 // nothing typed
    const parsed = text.trim() === "" ? null : parseFloat(text);
    const kg = parsed == null || isNaN(parsed) ? null : (imperial ? lbToKg(parsed) : parsed);
    setDraft((d) => { const n = { ...d }; delete n[ex.id]; return n; });
    try {
      const updated = await updateStrengthWeight(ex.id, kg);
      // Reflect the saved value back into the catalog rows we hold.
      setData((prev) => ({
        ...prev,
        sessions: Object.fromEntries(
          Object.entries(prev.sessions).map(([label, list]) => [
            label, list.map((e) => (e.id === ex.id ? { ...e, working_weight_kg: updated.working_weight_kg } : e)),
          ])
        ),
      }));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section>
      <div className="card">
        <h2 style={{ marginBottom: 6 }}>Strength — 2×/week</h2>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          Your PPL split condensed for the marathon build: legs + pressing prioritized
          (climbing covers pulling). Enter your working weights ({wUnit}) — they save automatically.
        </p>
        <p className="muted" style={{ fontSize: 12.5, borderLeft: `3px solid ${colors.forest}`, paddingLeft: 10, margin: 0 }}>
          {data.progression_note}
        </p>
      </div>

      {Object.entries(data.sessions).map(([label, exercises]) => (
        <div key={label} className="card">
          <h3 style={{ marginTop: 0 }}>{label}</h3>
          <table>
            <thead>
              <tr>
                <th>Exercise</th><th>Scheme</th><th>%1RM</th><th style={{ textAlign: "right" }}>Weight ({wUnit})</th>
              </tr>
            </thead>
            <tbody>
              {exercises.map((ex) => (
                <tr key={ex.id}>
                  <td style={{ fontWeight: ex.is_compound ? 700 : 500 }}>
                    {ex.name}
                    {/* is_compound comes back as 0/1 from SQLite; coerce so a
                        falsy 0 doesn't render as a literal "0". */}
                    {!!ex.is_compound && <span className="pill" style={{ marginLeft: 6 }}>compound</span>}
                  </td>
                  <td className="muted">{ex.scheme || "—"}</td>
                  <td>{ex.pct_1rm ? `${ex.pct_1rm}%` : "—"}</td>
                  <td style={{ textAlign: "right" }}>
                    <input
                      className="weight"
                      inputMode="decimal"
                      placeholder="—"
                      value={draft[ex.id] !== undefined ? draft[ex.id] : toDisplay(ex.working_weight_kg)}
                      onChange={(e) => setDraft((d) => ({ ...d, [ex.id]: e.target.value }))}
                      onBlur={() => commit(ex)}
                      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
