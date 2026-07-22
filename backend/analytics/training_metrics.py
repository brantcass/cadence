"""
Derived training metrics.

Everything here is a pure function over the raw activity/recovery lists that
`garmin_source` hands back. Nothing in this module talks to Garmin, the model,
or the network — which is why the same functions can back BOTH an agent tool
and a dashboard endpoint without duplicating the math.

Two conventions worth knowing:

1. "Today" is the latest date present in the data, not the wall clock. The
   bundled sample data is a fixed snapshot, so anchoring to wall-clock time
   would make every window empty a week from now.
2. Weeks are ISO weeks (Monday-start), keyed by the Monday's date string. That
   matches how the sample data's `weekly_summary` is grouped.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

# Pace zones expressed as multipliers of the athlete's threshold pace.
# Slower pace = bigger min/km number, so recovery running has the HIGHEST
# multiplier. Boundaries are the common Friel-style running zones.
ZONE_BANDS = [
    ("Z5 VO2max",   0.00, 0.99),
    ("Z4 Threshold", 0.99, 1.06),
    ("Z3 Tempo",     1.06, 1.14),
    ("Z2 Endurance", 1.14, 1.30),
    ("Z1 Recovery",  1.30, 99.0),
]

# Distance buckets for personal-record detection. A 5.6 km run and a 5.0 km run
# are the same effort category; comparing raw paces across 5 km and 16 km is not
# meaningful, so PRs are tracked per bucket.
PR_BUCKETS = [
    ("5K-ish",    4.5,  6.5),
    ("10K-ish",   8.0,  12.0),
    ("Long run", 13.0, 99.0),
]

EFFORT_BUCKETS = [
    ("Easy (1-4)",     1, 4),
    ("Moderate (5-6)", 5, 6),
    ("Hard (7-10)",    7, 10),
]


# ---- small helpers ----

def _d(value) -> date:
    """Parse an ISO date string (or pass a date through)."""
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def latest_date(records) -> date | None:
    """The most recent date in a list of {date: ...} records."""
    dates = [_d(r["date"]) for r in records if r.get("date")]
    return max(dates) if dates else None


def _in_window(records, end: date, days: int):
    """Records falling in the `days`-long window ending on `end` (inclusive)."""
    start = end - timedelta(days=days - 1)
    return [r for r in records if start <= _d(r["date"]) <= end]


def _is_run(activity) -> bool:
    return activity.get("type") == "run" and activity.get("distance_km", 0) > 0


def pace_min_per_km(activity):
    """Pace for a run, or None for anything without distance."""
    if not _is_run(activity):
        return None
    return round(activity["duration_min"] / activity["distance_km"], 2)


def format_pace(pace) -> str:
    """4.55 -> '4:33/km'. Humans read pace as mm:ss, not decimal minutes."""
    if pace is None:
        return "—"
    minutes = int(pace)
    seconds = round((pace - minutes) * 60)
    if seconds == 60:          # e.g. 4.999 would render as 4:60
        minutes, seconds = minutes + 1, 0
    return f"{minutes}:{seconds:02d}/km"


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def session_load(activity) -> float:
    """Session-RPE load: duration x perceived effort.

    This is the standard way to put a hard 30-minute session and an easy
    90-minute session on the same scale, and unlike kilometres it also counts
    strength work — which matters when you're asking "is total stress rising?"
    """
    return float(activity.get("duration_min", 0)) * float(activity.get("perceived_effort", 0))


# ---- pace zones ----

def pace_zones(athlete):
    """Zone boundaries in min/km, derived from the athlete's threshold pace."""
    threshold = athlete.get("threshold_pace_min_per_km")
    if not threshold:
        return {"error": "No threshold_pace_min_per_km on the athlete profile."}

    zones = []
    for name, lo_mult, hi_mult in ZONE_BANDS:
        zones.append({
            "zone": name,
            "faster_than_min_per_km": round(threshold * lo_mult, 2) if lo_mult else None,
            "slower_than_min_per_km": round(threshold * hi_mult, 2) if hi_mult < 99 else None,
            "range": (
                f"{format_pace(threshold * lo_mult) if lo_mult else 'any'}"
                f" – {format_pace(threshold * hi_mult) if hi_mult < 99 else 'slower'}"
            ),
        })
    return {
        "threshold_pace_min_per_km": threshold,
        "threshold_pace": format_pace(threshold),
        "zones": zones,
    }


def classify_zone(pace, threshold) -> str | None:
    if pace is None or not threshold:
        return None
    ratio = pace / threshold
    for name, lo, hi in ZONE_BANDS:
        if lo <= ratio < hi:
            return name
    return ZONE_BANDS[-1][0]


def zone_distribution(activities, athlete, days=28):
    """How the last `days` of running split across pace zones, by distance."""
    threshold = athlete.get("threshold_pace_min_per_km")
    end = latest_date(activities)
    if end is None or not threshold:
        return {"as_of": None, "zones": [], "runs": []}

    window = [a for a in _in_window(activities, end, days) if _is_run(a)]

    km_by_zone = defaultdict(float)
    runs = []
    for a in window:
        pace = pace_min_per_km(a)
        zone = classify_zone(pace, threshold)
        km_by_zone[zone] += a["distance_km"]
        runs.append({
            "date": a["date"],
            "distance_km": a["distance_km"],
            "pace_min_per_km": pace,
            "pace": format_pace(pace),
            "zone": zone,
        })

    total_km = sum(km_by_zone.values()) or 1.0
    # Report every zone, including empty ones — "you did zero threshold work"
    # is a finding, and a chart with disappearing categories is hard to read.
    zones = [
        {
            "zone": name,
            "distance_km": round(km_by_zone.get(name, 0.0), 1),
            "share_pct": round(100 * km_by_zone.get(name, 0.0) / total_km, 1),
        }
        for name, _, _ in ZONE_BANDS
    ]
    return {"as_of": end.isoformat(), "window_days": days, "zones": zones, "runs": runs}


# ---- week-over-week trends ----

def weekly_buckets(activities):
    """Group activities into ISO weeks, newest last."""
    buckets = defaultdict(list)
    for a in activities:
        buckets[_week_start(_d(a["date"]))].append(a)
    return dict(sorted(buckets.items()))


def _pct_change(current, previous):
    if not previous:
        return None
    return round(100 * (current - previous) / previous, 1)


def week_over_week(activities, weeks=4):
    """Per-week totals plus the delta against the preceding week."""
    buckets = weekly_buckets(activities)
    # Keep one extra week so the oldest reported week still has a comparison.
    keys = list(buckets.keys())[-(weeks + 1):]

    rows = []
    for key in keys:
        week = buckets[key]
        runs = [a for a in week if _is_run(a)]
        rows.append({
            "week_of": key.isoformat(),
            "total_km": round(sum(a["distance_km"] for a in runs), 1),
            "sessions": sum(1 for a in week if a.get("type") != "rest"),
            "duration_min": sum(a.get("duration_min", 0) for a in week),
            "load": round(sum(session_load(a) for a in week), 0),
            "hard_days": sum(1 for a in week if a.get("perceived_effort", 0) >= 7),
            "longest_run_km": round(max((a["distance_km"] for a in runs), default=0), 1),
        })

    for i, row in enumerate(rows):
        prev = rows[i - 1] if i > 0 else None
        row["km_change_pct"] = _pct_change(row["total_km"], prev["total_km"]) if prev else None
        row["load_change_pct"] = _pct_change(row["load"], prev["load"]) if prev else None

    reported = rows[-weeks:] if len(rows) > weeks else rows
    latest = reported[-1] if reported else None

    # >10%/week is the classic (rough) threshold for ramping too fast.
    warning = None
    if latest and latest["km_change_pct"] is not None and latest["km_change_pct"] > 10:
        warning = (
            f"Mileage rose {latest['km_change_pct']}% week-over-week, above the "
            f"~10% guideline for safe progression."
        )

    return {"weeks": reported, "warning": warning}


# ---- personal records ----

def personal_records(activities, recent_days=14):
    """Best pace per distance bucket, plus longest run and biggest week.

    A record is flagged `is_recent` when it was set inside the last
    `recent_days` — that's the part a coach actually wants to mention.
    """
    end = latest_date(activities)
    if end is None:
        return {"as_of": None, "records": []}

    recent_cutoff = end - timedelta(days=recent_days - 1)
    runs = [a for a in activities if _is_run(a)]
    records = []

    for label, lo, hi in PR_BUCKETS:
        in_bucket = [a for a in runs if lo <= a["distance_km"] < hi]
        if not in_bucket:
            continue
        best = min(in_bucket, key=lambda a: pace_min_per_km(a))
        records.append({
            "category": f"Fastest pace, {label}",
            "value": format_pace(pace_min_per_km(best)),
            "pace_min_per_km": pace_min_per_km(best),
            "distance_km": best["distance_km"],
            "date": best["date"],
            "is_recent": _d(best["date"]) >= recent_cutoff,
        })

    if runs:
        longest = max(runs, key=lambda a: a["distance_km"])
        records.append({
            "category": "Longest run",
            "value": f"{longest['distance_km']} km",
            "distance_km": longest["distance_km"],
            "date": longest["date"],
            "is_recent": _d(longest["date"]) >= recent_cutoff,
        })

    weekly = week_over_week(activities, weeks=99)["weeks"]
    if weekly:
        biggest = max(weekly, key=lambda w: w["total_km"])
        records.append({
            "category": "Biggest week",
            "value": f"{biggest['total_km']} km",
            "date": biggest["week_of"],
            "is_recent": _d(biggest["week_of"]) >= recent_cutoff - timedelta(days=6),
        })

    return {
        "as_of": end.isoformat(),
        "recent_window_days": recent_days,
        "records": records,
        "recent_records": [r for r in records if r["is_recent"]],
    }


# ---- training load / ACWR ----

def training_load(activities):
    """Acute:chronic workload ratio on session-RPE load.

    Acute  = load over the last 7 days.
    Chronic = average 7-day load over the last 28 days.
    Ratio much above ~1.3 means you piled on stress faster than you built the
    base for it; well below ~0.8 means you're detraining.
    """
    end = latest_date(activities)
    if end is None:
        return {"as_of": None}

    acute = sum(session_load(a) for a in _in_window(activities, end, 7))
    chronic_total = sum(session_load(a) for a in _in_window(activities, end, 28))
    chronic = chronic_total / 4.0  # 28 days -> per-week average

    ratio = round(acute / chronic, 2) if chronic else None

    if ratio is None:
        status, guidance = "unknown", "Not enough history to compute a ratio."
    elif ratio > 1.5:
        status = "high risk"
        guidance = "Load spiked well past what you're adapted to. Back off this week."
    elif ratio > 1.3:
        status = "elevated"
        guidance = "Ramping faster than the sweet spot. Hold volume flat for a week."
    elif ratio >= 0.8:
        status = "optimal"
        guidance = "Load is progressing at a sustainable rate."
    else:
        status = "detraining"
        guidance = "Load has dropped off; fitness will fade if this continues."

    acute_km = round(sum(a.get("distance_km", 0) for a in _in_window(activities, end, 7)), 1)
    chronic_km = round(
        sum(a.get("distance_km", 0) for a in _in_window(activities, end, 28)) / 4.0, 1
    )

    return {
        "as_of": end.isoformat(),
        "acute_load_7d": round(acute, 0),
        "chronic_load_weekly_avg_28d": round(chronic, 0),
        "acute_chronic_ratio": ratio,
        "status": status,
        "guidance": guidance,
        "acute_km_7d": acute_km,
        "chronic_km_weekly_avg_28d": chronic_km,
        "optimal_range": [0.8, 1.3],
    }


# ---- effort distribution ----

def effort_distribution(activities, days=28):
    """Session count per perceived-effort bucket over the recent window."""
    end = latest_date(activities)
    if end is None:
        return {"as_of": None, "buckets": []}

    window = [a for a in _in_window(activities, end, days) if a.get("type") != "rest"]
    buckets = []
    for label, lo, hi in EFFORT_BUCKETS:
        sessions = [a for a in window if lo <= a.get("perceived_effort", 0) <= hi]
        buckets.append({
            "bucket": label,
            "sessions": len(sessions),
            "duration_min": sum(a.get("duration_min", 0) for a in sessions),
        })

    total = sum(b["sessions"] for b in buckets) or 1
    for b in buckets:
        b["share_pct"] = round(100 * b["sessions"] / total, 1)

    return {"as_of": end.isoformat(), "window_days": days, "buckets": buckets}


# ---- recovery series ----

def recovery_series(daily_recovery, days=28):
    """Trimmed sleep/HRV series plus a simple direction-of-travel readout."""
    end = latest_date(daily_recovery)
    if end is None:
        return {"as_of": None, "series": []}

    window = sorted(_in_window(daily_recovery, end, days), key=lambda r: r["date"])

    def _avg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    last7, prior7 = window[-7:], window[-14:-7]
    return {
        "as_of": end.isoformat(),
        "window_days": days,
        "series": window,
        "hrv_last_7d_avg": _avg(last7, "hrv_ms"),
        "hrv_prior_7d_avg": _avg(prior7, "hrv_ms"),
        "sleep_last_7d_avg": _avg(last7, "sleep_hours"),
        "sleep_prior_7d_avg": _avg(prior7, "sleep_hours"),
    }
