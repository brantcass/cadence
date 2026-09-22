"""
Training-data source with a safety net.

The demo must never die because Garmin's login is being flaky. So the agent and
dashboard ALWAYS read through this layer, which returns real Garmin data when a
live connection works and falls back to bundled sample data otherwise.

Real access uses the unofficial `garminconnect` PyPI wrapper (personal login,
no developer-program approval needed) — appropriate for a personal prototype.

Set in .env to try live data:
    USE_LIVE_GARMIN=true
    GARMIN_EMAIL=...
    GARMIN_PASSWORD=...
"""

import os
import json
import time
from pathlib import Path

_SAMPLE_PATH = Path(__file__).parent / "sample_data.json"


def _load_sample():
    with open(_SAMPLE_PATH) as f:
        return json.load(f)


# A single live pull is ~100 Garmin calls (login + activities + per-day recovery).
# get_training_data() is hit on every endpoint AND every agent tool call, so
# without a cache one coach question would trigger hundreds of Garmin requests
# and get the IP rate-limited. Cache the live payload for a few minutes so the
# app makes at most one pull per window regardless of how often it reads.
_LIVE_TTL_SECONDS = 900  # 15 minutes
_live_cache = {"at": 0.0, "data": None}


# How much history to pull live. 28 days keeps the derived metrics (week-over-
# week, acute:chronic load) meaningful without hammering the per-day recovery
# endpoints too hard.
_LIVE_ACTIVITY_COUNT = 30
_LIVE_RECOVERY_DAYS = 28
# Fallback max HR when Garmin doesn't report one (used only for the RPE proxy).
_DEFAULT_MAX_HR = 190
_DEFAULT_RESTING_HR = 55


def _try_live_garmin():
    """Attempt a real pull, mapped into the app schema.

    Returns the full app-shape payload on success, or None on ANY failure so the
    caller transparently falls back to sample data. The unofficial Garmin wrapper
    is flaky (logins get throttled, payloads drift), so "fail safe, never crash
    the demo" is the whole contract of this function.
    """
    if os.getenv("USE_LIVE_GARMIN", "false").lower() != "true":
        return None
    try:
        from garminconnect import Garmin
        from data import garmin_mapper

        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        if not (email and password):
            print("[garmin_source] USE_LIVE_GARMIN set but no credentials; using sample.")
            return None

        client = Garmin(email, password)
        client.login()

        raw_activities = client.get_activities(0, _LIVE_ACTIVITY_COUNT)

        # Resting / max HR: read the profile if available, else sensible defaults.
        # These feed the perceived-effort proxy, so approximate is fine.
        profile = {}
        resting_hr, max_hr = _DEFAULT_RESTING_HR, _DEFAULT_MAX_HR
        try:
            profile = client.get_user_profile() or {}
            resting_hr = int(profile.get("restingHeartRate") or resting_hr)
        except Exception:  # noqa: BLE001 - profile is a nice-to-have
            pass
        # Anchor the recovery window to the latest activity so the series and the
        # activities describe the same period.
        end_day = garmin_mapper._latest_activity_day(raw_activities)
        recovery = garmin_mapper.build_recovery_series(
            client, days=_LIVE_RECOVERY_DAYS, end_day=end_day
        )
        # Pull resting HR from the recovery series if the profile didn't have it.
        rhr_vals = [r["resting_hr"] for r in recovery if r.get("resting_hr")]
        if rhr_vals:
            resting_hr = round(sum(rhr_vals) / len(rhr_vals))

        payload = garmin_mapper.assemble(
            profile, raw_activities, recovery, resting_hr, max_hr,
            threshold_pace=os.getenv("GARMIN_THRESHOLD_PACE"),
        )
        if not payload["activities"]:
            print("[garmin_source] live pull returned no usable activities; using sample.")
            return None
        return payload
    except Exception as e:  # noqa: BLE001 - any failure means "use the fallback"
        print(f"[garmin_source] live pull failed, using sample data: {e}")
        return None


def _get_live_cached():
    """Live payload, cached for _LIVE_TTL_SECONDS. None if live is off/unavailable.

    If a refresh fails (e.g. Garmin throttles us mid-session), we keep serving the
    last good payload rather than dropping the user back to sample data — a stale
    real pull beats fake data. Only when we've never had a successful pull do we
    return None so the caller falls back to sample.
    """
    if os.getenv("USE_LIVE_GARMIN", "false").lower() != "true":
        return None

    fresh = _live_cache["data"] is not None and (
        time.monotonic() - _live_cache["at"] < _LIVE_TTL_SECONDS
    )
    if fresh:
        return _live_cache["data"]

    live = _try_live_garmin()
    if live is not None:
        _live_cache["at"] = time.monotonic()
        _live_cache["data"] = live
        return live
    # Refresh failed — fall back to the last good pull if we have one.
    return _live_cache["data"]


def get_training_data():
    """Primary accessor. Live data if available, otherwise sample data."""
    live = _get_live_cached()
    if live is not None:
        return live
    return _load_sample()


# ---- Convenience accessors the agent's tools call ----

def get_recent_activities(limit: int = 7):
    """The `limit` MOST RECENT sessions, oldest-first.

    Sort explicitly rather than trusting the source's ordering: the sample file
    is chronological ascending, but the live Garmin API returns newest-first.
    Slicing the raw list would silently return the wrong end for one of them.
    """
    activities = sorted(get_all_activities(), key=lambda a: a.get("date", ""))
    return activities[-limit:] if limit else activities


def get_all_activities():
    """Full activity history. Derived metrics need the whole series, not a slice."""
    return get_training_data().get("activities", [])


def get_weekly_summary():
    data = get_training_data()
    return data.get("weekly_summary", {})


def get_sleep_and_recovery():
    data = get_training_data()
    return data.get("recovery", {})


def get_daily_recovery():
    """Day-by-day sleep/HRV/resting-HR series (for trend charts and analysis)."""
    data = get_training_data()
    return data.get("daily_recovery", [])


def get_athlete():
    """Athlete profile: goal, resting/max HR, threshold pace.

    If the profile has no threshold pace (the live Garmin path can't supply one),
    estimate it from the run history so pace zones and the training plan still
    work. An explicit value — sample data or GARMIN_THRESHOLD_PACE — always wins.
    """
    data = get_training_data()
    athlete = dict(data.get("athlete", {}))   # copy: don't mutate the cached payload
    if not athlete.get("threshold_pace_min_per_km"):
        from analytics import training_metrics as metrics
        estimated = metrics.estimate_threshold_pace(data.get("activities", []))
        if estimated is not None:
            athlete["threshold_pace_min_per_km"] = estimated
            athlete["threshold_pace_estimated"] = True   # flag it as a guess, not a test
    return athlete
