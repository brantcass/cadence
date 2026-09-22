import { useEffect, useMemo, useState } from "react";
import { fetchPlan } from "../api.js";
import { useUnits } from "../UnitContext.jsx";
import { formatDistance, formatPace } from "../units.js";
import { colors, phaseColor, kindColor } from "../theme.js";

// Plan: the periodized marathon build, week by week. This is the heart of the
// app — it turns the athlete's numbers into a concrete schedule through race day.
export default function Plan() {
  const { system } = useUnits();
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(() => new Set());

  // Refetch when units change — the workout prose is rendered server-side in the
  // chosen unit (the numeric fields the pills use stay canonical either way).
  useEffect(() => {
    fetchPlan(system).then(setPlan).catch((e) => setError(e.message));
  }, [system]);

  const todayISO = new Date().toISOString().slice(0, 10);
  const currentIndex = useMemo(() => {
    if (!plan) return null;
    const wk = plan.weeks.find((w) => addDays(w.week_of, 6) >= todayISO);
    return wk ? wk.index : plan.weeks[0]?.index;
  }, [plan, todayISO]);

  // Auto-expand the current week once the plan loads.
  useEffect(() => {
    if (currentIndex != null) setOpen(new Set([currentIndex]));
  }, [currentIndex]);

  if (error) return <div className="card" style={{ color: "crimson" }}>Error: {error} (is the backend running?)</div>;
  if (!plan) return <div className="card muted">Building your plan…</div>;

  const snap = plan.athlete_snapshot;
  const toggle = (i) =>
    setOpen((s) => {
      const n = new Set(s);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });

  return (
    <section>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
          <h2 style={{ margin: 0 }}>{plan.race.name} plan</h2>
          <span className="muted">
            {fmtDate(plan.race.date)} · <strong style={{ color: colors.forest }}>{plan.weeks_to_race} weeks</strong> to go
          </span>
        </div>

        <PhaseTimeline phases={plan.phases} />

        <div className="stat-row" style={{ marginTop: 14 }}>
          <Mini v={formatPace(snap.threshold_pace_min_per_km, system)} l={`Threshold pace${snap.threshold_pace_estimated ? " (est.)" : ""}`} />
          <Mini v={formatDistance(snap.current_weekly_km, system)} l="Current weekly volume" />
          <Mini v={formatDistance(snap.peak_long_run_km, system)} l="Peak long run" />
        </div>

        <h3>Target paces</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {["easy", "long", "marathon", "tempo", "threshold", "interval"].map((k) => (
            <span key={k} className="pill">
              {k}: <strong>{formatPace(plan.paces[k].min_per_km, system)}</strong>
            </span>
          ))}
        </div>
      </div>

      {plan.weeks.map((w) => (
        <WeekRow
          key={w.index}
          week={w}
          system={system}
          isCurrent={w.index === currentIndex}
          isOpen={open.has(w.index)}
          onToggle={() => toggle(w.index)}
        />
      ))}
    </section>
  );
}

function PhaseTimeline({ phases }) {
  const total = phases.reduce((s, p) => s + p.weeks, 0);
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", gap: 2 }}>
        {phases.map((p) => (
          <div key={p.phase} title={`${p.phase}: ${p.weeks} weeks`}
               style={{ flex: p.weeks, background: phaseColor(p.phase) }} />
        ))}
      </div>
      <div style={{ display: "flex", gap: 14, marginTop: 8, flexWrap: "wrap" }}>
        {phases.map((p) => (
          <span key={p.phase} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: phaseColor(p.phase) }} />
            {p.phase} <span className="muted">· {p.weeks}w</span>
          </span>
        ))}
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{total} weeks total</div>
    </div>
  );
}

function WeekRow({ week, system, isCurrent, isOpen, onToggle }) {
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden",
         border: isCurrent ? `2px solid ${colors.forest}` : undefined }}>
      <button onClick={onToggle}
        style={{ width: "100%", display: "flex", alignItems: "center", gap: 12,
                 padding: "14px 16px", background: "none", border: "none",
                 cursor: "pointer", textAlign: "left" }}>
        <span className="badge" style={{ background: phaseColor(week.phase) }}>{week.phase}</span>
        <span style={{ fontWeight: 700 }}>Week {week.index}</span>
        {isCurrent && <span className="pill" style={{ borderColor: colors.forest, color: colors.forest }}>this week</span>}
        {week.is_cutback && <span className="pill">cutback</span>}
        <span className="muted" style={{ fontSize: 12 }}>{fmtDate(week.week_of)}</span>
        <span style={{ marginLeft: "auto", fontSize: 13, color: colors.forest, fontWeight: 600 }}>
          long {formatDistance(week.long_run_km, system)} · wk {formatDistance(week.target_run_km, system)}
        </span>
        <span className="muted">{isOpen ? "▲" : "▼"}</span>
      </button>

      {isOpen && (
        <div style={{ padding: "0 16px 12px" }}>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>{week.focus}</p>
          {week.sessions.map((s, i) => <SessionRow key={i} s={s} system={system} />)}
        </div>
      )}
    </div>
  );
}

function SessionRow({ s, system }) {
  const dim = s.kind === "rest";
  return (
    <div style={{ display: "flex", gap: 12, padding: "8px 10px", alignItems: "flex-start",
                  borderLeft: `3px solid ${kindColor[s.kind] || colors.border}`,
                  background: colors.card, borderRadius: 6, marginBottom: 6, opacity: dim ? 0.7 : 1 }}>
      <div style={{ width: 34, fontWeight: 700, color: colors.muted, fontSize: 13 }}>{s.day}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{s.title}</div>
        <div className="muted" style={{ fontSize: 12.5 }}>{s.detail}</div>
      </div>
      {s.distance_km != null && (
        <div style={{ textAlign: "right", fontSize: 12, whiteSpace: "nowrap" }}>
          <div style={{ fontWeight: 600 }}>{formatDistance(s.distance_km, system)}</div>
          {s.target_pace_min_per_km && <div className="muted">{formatPace(s.target_pace_min_per_km, system)}</div>}
        </div>
      )}
    </div>
  );
}

function Mini({ v, l }) {
  return <div className="stat"><div className="val" style={{ fontSize: 18 }}>{v}</div><div className="lbl">{l}</div></div>;
}

// ---- tiny date helpers (plan dates are plain ISO strings) ----
function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
function fmtDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
