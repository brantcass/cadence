import { useEffect, useState } from "react";
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, LabelList,
} from "recharts";
import { fetchMetrics } from "../api.js";
import { useUnits } from "../UnitContext.jsx";
import { formatDistance, kmToMi, IMPERIAL } from "../units.js";
import { colors, statusColor } from "../theme.js";

// Dashboard: the derived-metrics view. Everything here comes from /api/metrics —
// the SAME functions the coach's tools call, so a number on a chart and a number
// the coach quotes can never disagree.
export default function Dashboard() {
  const { system } = useUnits();
  const [m, setM] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchMetrics().then(setM).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="card" style={{ color: "crimson" }}>Error: {error} (is the backend running?)</div>;
  if (!m) return <div className="card muted">Loading metrics…</div>;

  const imperial = system === IMPERIAL;
  const distUnit = imperial ? "mi" : "km";
  const conv = (km) => (imperial ? +kmToMi(km).toFixed(1) : +km.toFixed(1));

  const load = m.training_load || {};
  const rec = m.recovery || {};
  const wow = (m.week_over_week?.weeks || []).map((w) => ({
    week: w.week_of.slice(5),          // MM-DD
    dist: conv(w.total_km),
  }));
  const effort = (m.effort_distribution?.buckets || []).map((b) => ({
    bucket: b.bucket.split(" ")[0],    // "Easy", "Moderate", "Hard"
    sessions: b.sessions,
  }));
  const series = (rec.series || []).map((r) => ({ date: r.date.slice(5), ...r }));

  const hrvDelta = num(rec.hrv_last_7d_avg) - num(rec.hrv_prior_7d_avg);
  const currentWeekly = wow.length ? wow[wow.length - 1].dist : null;

  return (
    <section>
      <div className="card">
        <h2>At a glance</h2>
        <div className="stat-row">
          <Stat val={currentWeekly != null ? `${currentWeekly} ${distUnit}` : "—"} lbl="This week's volume" />
          <Stat val={load.acute_chronic_ratio ?? "—"} lbl="Load ratio (ACWR)"
                accent={statusColor(load.status)} />
          <Stat val={rec.hrv_last_7d_avg != null ? `${rec.hrv_last_7d_avg} ms` : "—"}
                lbl={`HRV 7-day avg ${arrow(hrvDelta)}`} />
          <Stat val={rec.sleep_last_7d_avg != null ? `${rec.sleep_last_7d_avg} h` : "—"} lbl="Sleep 7-day avg" />
        </div>
      </div>

      {/* Training load — a status readout, not a chart. Status word always shown. */}
      <div className="card">
        <h2>Training load</h2>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span style={{ fontSize: 40, fontWeight: 800, color: statusColor(load.status) }}>
            {load.acute_chronic_ratio ?? "—"}
          </span>
          <span className="badge" style={{ background: statusColor(load.status) }}>
            {(load.status || "unknown").toUpperCase()}
          </span>
          <span className="muted" style={{ fontSize: 13 }}>
            acute:chronic (optimal {load.optimal_range?.join("–") ?? "0.8–1.3"})
          </span>
        </div>
        <p className="muted" style={{ marginBottom: 0 }}>{load.guidance}</p>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Weekly mileage ({distUnit})</h3>
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={wow} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
            <XAxis dataKey="week" tick={{ fontSize: 11, fill: colors.muted }} />
            <YAxis tick={{ fontSize: 11, fill: colors.muted }} />
            <Tooltip {...tip} formatter={(v) => [`${v} ${distUnit}`, "distance"]} />
            <Bar dataKey="dist" fill={colors.mileage} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Effort mix (last 28 days)</h3>
        <p className="muted" style={{ marginTop: -4, fontSize: 12 }}>
          Sessions by intensity — most training should sit in Easy.
        </p>
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={effort} margin={{ top: 16, right: 8, left: -18, bottom: 0 }}>
            <XAxis dataKey="bucket" tick={{ fontSize: 12, fill: colors.muted }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: colors.muted }} />
            <Tooltip {...tip} formatter={(v) => [`${v} sessions`, "count"]} />
            <Bar dataKey="sessions" radius={[4, 4, 0, 0]}>
              {/* Ordinal ramp Easy->Hard; direct labels give the contrast relief
                  the light end needs. */}
              <LabelList dataKey="sessions" position="top" style={{ fontSize: 12, fill: colors.ink }} />
              {effort.map((_, i) => <Cell key={i} fill={colors.effort[i] || colors.effort[2]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>HRV trend (ms)</h3>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={series} margin={{ top: 8, right: 10, left: -18, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: colors.muted }} interval={5} />
            <YAxis domain={["dataMin - 5", "dataMax + 5"]} tick={{ fontSize: 11, fill: colors.muted }} />
            <Tooltip {...tip} />
            <Line dataKey="hrv_ms" name="HRV" stroke={colors.hrv} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Sleep trend (hours)</h3>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={series} margin={{ top: 8, right: 10, left: -18, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: colors.muted }} interval={5} />
            <YAxis domain={["dataMin - 1", "dataMax + 1"]} tick={{ fontSize: 11, fill: colors.muted }} />
            <Tooltip {...tip} />
            <Line dataKey="sleep_hours" name="Sleep" stroke={colors.sleep} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

const tip = {
  contentStyle: {
    background: colors.surface, border: `1px solid ${colors.border}`,
    borderRadius: 8, fontSize: 12,
  },
  labelStyle: { color: colors.muted },
};

function Stat({ val, lbl, accent }) {
  return (
    <div className="stat">
      <div className="val" style={accent ? { color: accent } : undefined}>{val}</div>
      <div className="lbl">{lbl}</div>
    </div>
  );
}

const num = (x) => (typeof x === "number" ? x : 0);
const arrow = (d) => (Math.abs(d) < 0.5 ? "" : d > 0 ? "▲" : "▼");
