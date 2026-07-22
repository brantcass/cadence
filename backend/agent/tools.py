"""
Tool definitions for the coach agent.

This is the "retrieval over the athlete's data" piece: instead of dumping every
data point into the prompt, the agent decides which tool it needs and calls it.
Each tool has (1) a schema the model sees and (2) a Python function that runs it.

Two kinds of tool live here:
  - Raw retrieval  (get_recent_activities, get_weekly_summary, ...) — hands back
    what's in the data source.
  - Derived analysis (get_pace_zones, get_week_over_week_trends, ...) — runs the
    math in `analytics.training_metrics` and hands back a conclusion.

The derived ones exist because a model doing arithmetic over 28 raw activities
in-context is slower and less reliable than a function doing it deterministically.
Tool descriptions say *when* to reach for each one, not just what it returns —
that's what drives the model to pick the right retrieval path.
"""

from analytics import training_metrics as metrics
from data import garmin_source

# ---- Schemas the model sees (Anthropic tool-use format) ----

TOOL_SCHEMAS = [
    {
        "name": "get_recent_activities",
        "description": "Get the athlete's most recent training sessions (runs, "
                       "strength, rest) with distance, duration, heart rate, and "
                       "perceived effort. Use when asked about recent workouts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "How many recent sessions to return (default 7).",
                }
            },
        },
    },
    {
        "name": "get_weekly_summary",
        "description": "Get this week's training totals: mileage, session count, "
                       "hard vs easy days, and the trend vs last week. Use for "
                       "questions about overall load or weekly volume.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_sleep_and_recovery",
        "description": "Get recovery signals: average sleep, HRV, and HRV trend. "
                       "Use when assessing fatigue, overtraining, or readiness.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_pace_zones",
        "description": "Get the athlete's training pace zones (Z1 recovery through "
                       "Z5 VO2max) derived from their threshold pace, plus how their "
                       "recent running distance was distributed across those zones. "
                       "Call this when asked how fast to run a workout, what pace a "
                       "given zone is, whether they are running easy days too hard, "
                       "or how their easy/hard mix looks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Window for the zone distribution, in days (default 28).",
                }
            },
        },
    },
    {
        "name": "get_week_over_week_trends",
        "description": "Get per-week training totals (distance, sessions, duration, "
                       "session-RPE load, longest run) with the percentage change "
                       "against the previous week, plus a warning if mileage is "
                       "ramping faster than the ~10%/week guideline. Call this for "
                       "any question about progression, ramp rate, whether volume is "
                       "increasing, or how this week compares to previous weeks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": "How many recent weeks to report (default 4).",
                }
            },
        },
    },
    {
        "name": "get_personal_records",
        "description": "Get the athlete's best efforts: fastest pace per distance "
                       "bucket (5K-ish, 10K-ish, long run), longest single run, and "
                       "biggest week. Each record is flagged if it was set recently. "
                       "Call this when asked about PRs, bests, breakthroughs, or "
                       "whether a given session was their fastest or longest.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recent_days": {
                    "type": "integer",
                    "description": "How recent a record must be to count as new (default 14).",
                }
            },
        },
    },
    {
        "name": "get_training_load",
        "description": "Get the acute:chronic workload ratio — last 7 days of "
                       "session-RPE load against the 28-day weekly average — with a "
                       "status (detraining / optimal / elevated / high risk) and "
                       "guidance. Call this when assessing injury or overtraining "
                       "risk, or when asked whether the athlete is doing too much. "
                       "Pair it with get_sleep_and_recovery for a full readiness read.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# ---- The actual functions, keyed by tool name ----

def _get_recent_activities(limit: int = 7):
    return garmin_source.get_recent_activities(limit)


def _get_weekly_summary():
    return garmin_source.get_weekly_summary()


def _get_sleep_and_recovery():
    return garmin_source.get_sleep_and_recovery()


def _get_pace_zones(days: int = 28):
    athlete = garmin_source.get_athlete()
    activities = garmin_source.get_all_activities()
    distribution = metrics.zone_distribution(activities, athlete, days=days)
    return {
        **metrics.pace_zones(athlete),
        "recent_distribution": distribution["zones"],
        "recent_runs": distribution["runs"],
    }


def _get_week_over_week_trends(weeks: int = 4):
    return metrics.week_over_week(garmin_source.get_all_activities(), weeks=weeks)


def _get_personal_records(recent_days: int = 14):
    return metrics.personal_records(
        garmin_source.get_all_activities(), recent_days=recent_days
    )


def _get_training_load():
    return metrics.training_load(garmin_source.get_all_activities())


TOOL_FUNCTIONS = {
    "get_recent_activities": _get_recent_activities,
    "get_weekly_summary": _get_weekly_summary,
    "get_sleep_and_recovery": _get_sleep_and_recovery,
    "get_pace_zones": _get_pace_zones,
    "get_week_over_week_trends": _get_week_over_week_trends,
    "get_personal_records": _get_personal_records,
    "get_training_load": _get_training_load,
}


def run_tool(name: str, tool_input: dict):
    """Dispatch a tool call by name. Returns the tool's result."""
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    try:
        return TOOL_FUNCTIONS[name](**(tool_input or {}))
    except TypeError as e:
        # The model passed an argument the tool doesn't accept. Hand the error
        # back as a normal result so the agent can correct itself rather than
        # crashing the whole request.
        return {"error": f"Bad arguments for {name}: {e}"}
