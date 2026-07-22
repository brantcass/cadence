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
from pathlib import Path

_SAMPLE_PATH = Path(__file__).parent / "sample_data.json"


def _load_sample():
    with open(_SAMPLE_PATH) as f:
        return json.load(f)


def _try_live_garmin():
    """Attempt a real pull. Returns None on any failure so callers fall back."""
    if os.getenv("USE_LIVE_GARMIN", "false").lower() != "true":
        return None
    try:
        from garminconnect import Garmin

        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        if not (email and password):
            return None

        client = Garmin(email, password)
        client.login()

        # NOTE: this is a starting point — extend the shape to match sample_data.
        # Kept minimal on purpose so you build it out yourself in Claude Code.
        activities = client.get_activities(0, 14)  # last 14 activities
        return {"source": "garmin_live", "activities": activities}
    except Exception as e:  # noqa: BLE001 - any failure means "use the fallback"
        print(f"[garmin_source] live pull failed, using sample data: {e}")
        return None


def get_training_data():
    """Primary accessor. Live data if available, otherwise sample data."""
    live = _try_live_garmin()
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
    """Athlete profile: goal, resting/max HR, threshold pace."""
    data = get_training_data()
    return data.get("athlete", {})
