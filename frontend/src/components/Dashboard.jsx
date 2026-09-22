import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line,
} from "recharts";
import { useUnits } from "../UnitContext.jsx";
import { formatDistance, kmToMi, IMPERIAL } from "../units.js";

// Dashboard: shows the athlete's recent training. Intentionally simple —
// build this out in Claude Code (add HRV, effort, weekly trend, etc.).
export default function Dashboard({ data }) {
  const { system } = useUnits();
  if (!data) return <div>Loading training data…</div>;

  const imperial = system === IMPERIAL;
  const distUnit = imperial ? "mi" : "km";

  // Store canonical km; add a converted `distance` field only for the chart's
  // axis/bars. We never mutate the source — map into fresh objects.
  const runs = (data.activities || [])
    .filter((a) => a.type === "run")
    .map((a) => ({
      ...a,
      distance: imperial ? +kmToMi(a.distance_km).toFixed(2) : a.distance_km,
    }));

  return (
    <section>
      <h2>This Week</h2>
      {data.weekly_summary && (
        <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
          <Stat label={`Total ${distUnit}`}
                value={formatDistance(data.weekly_summary.total_km, system)} />
          <Stat label="Sessions" value={data.weekly_summary.total_sessions} />
          <Stat label="vs last wk" value={data.weekly_summary.trend_vs_last_week_km} />
        </div>
      )}

      <h3>Distance by run ({distUnit})</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={runs}>
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => `${v} ${distUnit}`} />
          <Bar dataKey="distance" />
        </BarChart>
      </ResponsiveContainer>

      <h3>Heart rate trend</h3>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={runs}>
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis domain={["dataMin - 10", "dataMax + 10"]} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line dataKey="avg_hr" />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div style={{ padding: "8px 14px", background: "#f4f4f5", borderRadius: 8 }}>
      <div style={{ fontSize: 20, fontWeight: 600 }}>{value}</div>
      <div style={{ fontSize: 12, color: "#666" }}>{label}</div>
    </div>
  );
}
