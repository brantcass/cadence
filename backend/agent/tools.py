"""
Tool definitions for the coach agent.

This is the "retrieval over the athlete's data" piece: instead of dumping every
data point into the prompt, the agent decides which tool it needs and calls it.
Each tool has (1) a schema the model sees and (2) a Python function that runs it.
"""

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
]

# ---- The actual functions, keyed by tool name ----

def _get_recent_activities(limit: int = 7):
    return garmin_source.get_recent_activities(limit)


def _get_weekly_summary():
    return garmin_source.get_weekly_summary()


def _get_sleep_and_recovery():
    return garmin_source.get_sleep_and_recovery()


TOOL_FUNCTIONS = {
    "get_recent_activities": _get_recent_activities,
    "get_weekly_summary": _get_weekly_summary,
    "get_sleep_and_recovery": _get_sleep_and_recovery,
}


def run_tool(name: str, tool_input: dict):
    """Dispatch a tool call by name. Returns the tool's result."""
    if name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {name}"}
    return TOOL_FUNCTIONS[name](**(tool_input or {}))
