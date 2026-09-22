"""
Map Garmin's raw API shape into the app's internal data shape.

Why this module exists
----------------------
Everything downstream — the agent tools, the analytics module, the dashboard —
reads ONE schema: the one `sample_data.json` documents. Garmin's unofficial API
returns something quite different:

  - distances in metres, durations in seconds, nested `activityType.typeKey`;
  - no "perceived effort" at all (that's an RPE the athlete logs by hand, which
    Garmin doesn't capture);
  - recovery (sleep / HRV / resting HR) only through separate per-day endpoints,
    not bundled with activities.

So this file is the single translation layer. Keeping it isolated means the rest
of the app never learns Garmin's field names, and the sample-data fallback stays
byte-for-byte compatible with the live path.

Everything here is defensive: Garmin's wrapper is unofficial and its payloads
drift, so every field is pulled with `.get()` and coerced, and a malformed record
is skipped rather than allowed to crash the pull. The caller
(`garmin_source._try_live_garmin`) treats ANY exception as "fall back to sample
data", so partial or missing data never takes the demo down.
"""

from datetime import date, datetime, timedelta

# Garmin has no RPE field. We approximate perceived effort (1-10) from how hard
# the average heart rate was relative to the athlete's max — a standard, if
# rough, %HRmax -> RPE mapping. Boundaries are (lower_%hrmax_inclusive, rpe).
_HR_RESERVE_TO_RPE = [
    (0.50, 2),
    (0.60, 3),
    (0.68, 4),
    (0.76, 5),
    (0.82, 6),
    (0.87, 7),
    (0.92, 8),
    (0.96, 9),
]
_RPE_MAX = 10

# Garmin `typeKey` values are granular ("trail_running", "treadmill_running",
# "indoor_cycling", ...). We only distinguish the categories the app models.
_RUN_KEYS = ("running", "run")
_STRENGTH_KEYS = ("strength", "strength_training")


def _num(value, default=0.0):
    """Coerce a possibly-missing / string value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _activity_date(raw) -> str | None:
    """Garmin gives 'startTimeLocal' as 'YYYY-MM-DD HH:MM:SS'. We want the day."""
    ts = raw.get("startTimeLocal") or raw.get("startTimeGMT")
    if not ts:
        return None
    return str(ts)[:10]


def _classify_type(raw) -> str:
    type_key = ((raw.get("activityType") or {}).get("typeKey") or "").lower()
    if any(k in type_key for k in _RUN_KEYS):
        return "run"
    if any(k in type_key for k in _STRENGTH_KEYS):
        return "strength"
    # Everything else (cycling, swim, cardio, ...) keeps its raw category so the
    # data isn't silently dropped; run-specific tools just won't pick it up.
    return type_key or "other"


def _rpe_from_hr(avg_hr, resting_hr, max_hr) -> int:
    """Perceived-effort proxy from heart-rate reserve (Karvonen %).

    Reserve = (avg - resting) / (max - resting), which is a better effort proxy
    than raw %max because it accounts for the athlete's own resting floor. Zero
    HR (Garmin's value for a session with no HR strap) yields 0, matching how the
    sample data marks rest days.
    """
    avg = _num(avg_hr)
    if avg <= 0 or max_hr <= resting_hr:
        return 0
    reserve = (avg - resting_hr) / (max_hr - resting_hr)
    reserve = max(0.0, min(reserve, 1.0))
    rpe = _RPE_MAX
    for threshold, value in _HR_RESERVE_TO_RPE:
        if reserve < threshold:
            rpe = value
            break
    return rpe


def map_activity(raw, resting_hr, max_hr):
    """One Garmin activity -> one app activity, or None if it can't be parsed."""
    day = _activity_date(raw)
    if day is None:
        return None
    avg_hr = int(_num(raw.get("averageHR")))
    return {
        "date": day,
        "type": _classify_type(raw),
        "distance_km": round(_num(raw.get("distance")) / 1000.0, 2),   # m -> km
        "duration_min": round(_num(raw.get("duration")) / 60.0, 1),    # s -> min
        "avg_hr": avg_hr,
        "perceived_effort": _rpe_from_hr(avg_hr, resting_hr, max_hr),
    }


def map_activities(raw_activities, resting_hr, max_hr):
    """Map + clean the activity list, sorted oldest-first (the app's convention)."""
    mapped = []
    for raw in raw_activities or []:
        activity = map_activity(raw, resting_hr, max_hr)
        if activity is not None:
            mapped.append(activity)
    mapped.sort(key=lambda a: a["date"])
    return mapped


# ---- recovery series (per-day endpoints) ----

def _extract_sleep_hours(sleep_payload):
    dto = (sleep_payload or {}).get("dailySleepDTO") or {}
    seconds = dto.get("sleepTimeSeconds")
    return round(_num(seconds) / 3600.0, 1) if seconds else None


def _extract_hrv(hrv_payload):
    summary = (hrv_payload or {}).get("hrvSummary") or {}
    # `lastNightAvg` is Garmin's overnight average HRV in ms.
    val = summary.get("lastNightAvg")
    return int(_num(val)) if val else None


def build_recovery_series(client, days=28, end_day=None):
    """Assemble a day-by-day sleep / HRV / resting-HR series from Garmin.

    Garmin exposes these only per-day, so this is `days` iterations of a few
    calls each — the slow part of a live pull. Each day is wrapped in its own
    try/except: a single missing day drops out of the series instead of aborting
    the whole thing. Returns oldest-first, matching sample_data.json.
    """
    end = end_day or date.today()
    series = []
    for offset in range(days - 1, -1, -1):
        cdate = (end - timedelta(days=offset)).isoformat()
        row = {"date": cdate}
        try:
            row["sleep_hours"] = _extract_sleep_hours(client.get_sleep_data(cdate))
        except Exception:  # noqa: BLE001 - best-effort per field
            row["sleep_hours"] = None
        try:
            row["hrv_ms"] = _extract_hrv(client.get_hrv_data(cdate))
        except Exception:  # noqa: BLE001
            row["hrv_ms"] = None
        try:
            summary = client.get_user_summary(cdate) or {}
            rhr = summary.get("restingHeartRate")
            row["resting_hr"] = int(_num(rhr)) if rhr else None
        except Exception:  # noqa: BLE001
            row["resting_hr"] = None

        # Only keep days that produced at least one real signal.
        if any(row.get(k) is not None for k in ("sleep_hours", "hrv_ms", "resting_hr")):
            series.append(row)
    return series


# ---- athlete profile + derived summaries ----

def build_athlete(profile, resting_hr, max_hr, threshold_pace=None):
    """Assemble the athlete block. Threshold pace is optional.

    Garmin doesn't expose a clean running-threshold pace through the wrapper, so
    when we can't determine one we leave it out — `pace_zones` already degrades
    gracefully (returns an explanatory error) rather than inventing zones.
    """
    athlete = {
        "name": (profile or {}).get("displayName") or "Garmin Athlete",
        "resting_hr": resting_hr,
        "max_hr": max_hr,
    }
    if threshold_pace:
        athlete["threshold_pace_min_per_km"] = round(float(threshold_pace), 2)
    return athlete


def assemble(profile, raw_activities, recovery_series, resting_hr, max_hr,
             threshold_pace=None):
    """Compose the full app-schema payload the rest of the app consumes.

    `weekly_summary` and the `recovery` summary are DERIVED here (via the same
    analytics module the tools use) so the live payload has the same keys the
    sample file does — nothing downstream has to special-case the source.
    """
    from analytics import training_metrics as metrics

    activities = map_activities(raw_activities, resting_hr, max_hr)
    athlete = build_athlete(profile, resting_hr, max_hr, threshold_pace)

    # Derive weekly_summary from the most recent complete-ish week.
    wow = metrics.week_over_week(activities, weeks=1)["weeks"]
    latest = wow[-1] if wow else {}
    weekly_summary = {
        "week_of": latest.get("week_of"),
        "total_km": latest.get("total_km", 0),
        "total_sessions": latest.get("sessions", 0),
        "total_duration_min": latest.get("duration_min", 0),
        "hard_days": latest.get("hard_days", 0),
        "trend_vs_last_week_km": (
            f"{latest['km_change_pct']:+g}%"
            if latest.get("km_change_pct") is not None else "n/a"
        ),
    }

    # Derive the recovery summary block from the daily series.
    rec = metrics.recovery_series(recovery_series)
    hrv_now, hrv_prior = rec.get("hrv_last_7d_avg"), rec.get("hrv_prior_7d_avg")
    if hrv_now is not None and hrv_prior is not None:
        trend = "declining" if hrv_now < hrv_prior else "improving"
    else:
        trend = "unknown"
    recovery = {
        "avg_sleep_hours": rec.get("sleep_last_7d_avg"),
        "avg_hrv_ms": hrv_now,
        "hrv_trend": trend,
        "notes": "Derived from the last 7 days of Garmin recovery data.",
    }

    return {
        "source": "garmin_live",
        "athlete": athlete,
        "activities": activities,
        "daily_recovery": recovery_series,
        "weekly_summary": weekly_summary,
        "recovery": recovery,
    }


def _latest_activity_day(raw_activities):
    """The most recent activity date, so the recovery window lines up with it."""
    days = [_activity_date(a) for a in (raw_activities or [])]
    days = [d for d in days if d]
    if not days:
        return None
    return datetime.strptime(max(days), "%Y-%m-%d").date()
