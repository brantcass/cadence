"""
Application service: assemble the athlete's live training plan.

The plan ENGINE (`analytics/plan.py`) is pure — it takes numbers and returns a
schedule. This thin layer is where the impure wiring lives: read the race/schedule
config, pull the athlete's real threshold pace and history from `garmin_source`,
and hand them to the engine. Both the /api/plan endpoint and the coach's plan
tools go through here, so there's one definition of "the current plan."
"""

import json
from datetime import date
from pathlib import Path

from analytics import plan
from data import garmin_source

_CONFIG_PATH = Path(__file__).parent / "data" / "plan_config.json"


def load_config() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def build_current_plan() -> dict:
    """The full plan, grounded in the athlete's current data and today's date."""
    cfg = load_config()
    start = date.fromisoformat(cfg["start_date"]) if cfg.get("start_date") else date.today()
    race = date.fromisoformat(cfg["race_date"])
    return plan.build_plan(
        start_date=start,
        race_date=race,
        athlete=garmin_source.get_athlete(),
        activities=garmin_source.get_all_activities(),
        race_type=cfg.get("race_type", "marathon"),
        options=cfg.get("schedule", {}),
    )


def plan_overview() -> dict:
    """The plan without the full week-by-week session detail — the summary a
    coach quotes when asked 'what does my plan look like?'."""
    p = build_current_plan()
    return {
        "race": p["race"],
        "start_date": p["start_date"],
        "weeks_to_race": p["weeks_to_race"],
        "athlete_snapshot": p["athlete_snapshot"],
        "paces": p["paces"],
        "phases": p["phases"],
        "week_summaries": [
            {k: w[k] for k in ("index", "phase", "week_of", "is_cutback",
                               "focus", "long_run_km", "target_run_km")}
            for w in p["weeks"]
        ],
    }


def upcoming(count: int = 2, as_of: date = None) -> dict:
    """The next `count` weeks of detailed sessions from `as_of` (default today)."""
    p = build_current_plan()
    as_of = as_of or date.today()
    weeks = plan.upcoming_weeks(p, as_of, count=count)
    return {"race": p["race"], "as_of": as_of.isoformat(),
            "paces": p["paces"], "weeks": weeks}
