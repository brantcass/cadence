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
from analytics import units
from data import garmin_source
from data import db
import plan_service

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
    {
        "name": "get_plan_overview",
        "description": "Get the big-picture structure of the athlete's marathon "
                       "training plan: race date and distance, weeks remaining, a "
                       "current-fitness snapshot (threshold pace, weekly volume), the "
                       "phase breakdown (Base / Build / Peak / Taper), the target "
                       "training paces, and a one-line summary of every week. Call "
                       "this for questions about the plan as a whole: how long until "
                       "the race, what phase they're in, how the plan progresses, or "
                       "when they peak and taper.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_training_plan",
        "description": "Get the detailed day-by-day workouts for the upcoming week(s) "
                       "of the plan — every session with its type, target distance, "
                       "target pace, and instructions. Call this when asked what to do "
                       "today, this week, or next week; what tomorrow's run is; or for "
                       "the specifics of any upcoming session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks_ahead": {
                    "type": "integer",
                    "description": "How many upcoming weeks of detail to return (default 2).",
                }
            },
        },
    },
    {
        "name": "get_strength_workout",
        "description": "Get the athlete's two condensed strength sessions (the "
                       "marathon-build version of their Push/Pull/Legs plan): the "
                       "exercises, sets/reps schemes, %1RM targets, and current working "
                       "weights. Call this when asked what lifts to do, for strength-day "
                       "details, how much weight to use, or about their gym workouts.",
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


def _get_plan_overview():
    return plan_service.plan_overview()


def _get_training_plan(weeks_ahead: int = 2):
    return plan_service.upcoming(count=weeks_ahead)


def _get_strength_workout():
    db.init_db()   # idempotent; makes the tool safe to call before app startup ran
    catalog = db.load_catalog()
    return {
        "sessions": db.condensed_sessions(),
        "progression_note": catalog.get("progression_note"),
    }


TOOL_FUNCTIONS = {
    "get_recent_activities": _get_recent_activities,
    "get_weekly_summary": _get_weekly_summary,
    "get_sleep_and_recovery": _get_sleep_and_recovery,
    "get_pace_zones": _get_pace_zones,
    "get_week_over_week_trends": _get_week_over_week_trends,
    "get_personal_records": _get_personal_records,
    "get_training_load": _get_training_load,
    "get_plan_overview": _get_plan_overview,
    "get_training_plan": _get_training_plan,
    "get_strength_workout": _get_strength_workout,
}


def _enrich_activities(activities, system):
    """Add unit-converted display strings to each activity.

    The coach must quote distances/paces in the athlete's units WITHOUT doing the
    conversion itself (model arithmetic is the thing this app avoids). So we do it
    here, in Python, and hand the coach ready-made strings. Copy each dict first —
    the source list may be the cached live payload, and we must not mutate it.
    """
    out = []
    for a in activities:
        a = dict(a)
        if a.get("distance_km"):
            a["distance_display"] = units.format_distance(a["distance_km"], system)
            pace = metrics.pace_min_per_km(a)
            if pace is not None:
                a["pace_display"] = units.format_pace(pace, system)
        out.append(a)
    return out


def _enrich_plan(result, system):
    """Add unit-converted display strings throughout a plan result so an imperial
    athlete gets miles, not kilometres. Metric values stay canonical."""
    if not isinstance(result, dict):
        return result

    paces = result.get("paces")
    if isinstance(paces, dict):
        for v in paces.values():
            if isinstance(v, dict) and v.get("min_per_km") is not None:
                v["display"] = units.format_pace(v["min_per_km"], system)

    # Detailed weeks (get_training_plan): convert every session's numbers.
    for w in result.get("weeks", []) or []:
        for s in w.get("sessions", []) or []:
            if s.get("distance_km"):
                s["distance_display"] = units.format_distance(s["distance_km"], system)
            if s.get("target_pace_min_per_km"):
                s["pace_display"] = units.format_pace(s["target_pace_min_per_km"], system)
        if w.get("long_run_km"):
            w["long_run_display"] = units.format_distance(w["long_run_km"], system)

    # Week summaries (get_plan_overview).
    for w in result.get("week_summaries", []) or []:
        if w.get("long_run_km"):
            w["long_run_display"] = units.format_distance(w["long_run_km"], system)
        if w.get("target_run_km"):
            w["weekly_distance_display"] = units.format_distance(w["target_run_km"], system)
    return result


def _enrich_strength(result, system):
    """Add a `weight_display` (kg or lb) next to each working weight that's set."""
    if not isinstance(result, dict):
        return result
    for exercises in result.get("sessions", {}).values():
        for ex in exercises:
            if ex.get("working_weight_kg") is not None:
                ex["weight_display"] = units.format_weight(ex["working_weight_kg"], system)
    return result


def enrich_display(name, result, system):
    """Attach `*_display` fields (in the athlete's units) to results that carry
    distances, paces, or weights. Central place to add more tools as we go."""
    if name == "get_recent_activities" and isinstance(result, list):
        return _enrich_activities(result, system)
    if name in ("get_training_plan", "get_plan_overview"):
        return _enrich_plan(result, system)
    if name == "get_strength_workout":
        return _enrich_strength(result, system)
    return result


def run_tool(name: str, tool_input: dict, unit_system: str = units.METRIC):
    """Dispatch a tool call by name. Returns the tool's result.

    `unit_system` ('metric' | 'imperial') controls the display strings added to
    the result so the coach can quote the athlete's preferred units directly.
    """
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = TOOL_FUNCTIONS[name](**(tool_input or {}))
    except TypeError as e:
        # The model passed an argument the tool doesn't accept. Hand the error
        # back as a normal result so the agent can correct itself rather than
        # crashing the whole request.
        return {"error": f"Bad arguments for {name}: {e}"}
    return enrich_display(name, result, unit_system)
