"""
Cadence backend — FastAPI.

Endpoints:
    GET  /api/health          -> liveness + which model provider is active
    GET  /api/training-data   -> raw training data for the dashboard charts
    GET  /api/metrics         -> derived metrics (zones, trends, PRs, load, recovery)
    POST /api/coach           -> ask the coach agent a question

Run:  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from data import garmin_source                       # noqa: E402  (after load_dotenv)
from data import db                                  # noqa: E402
from models import llm_provider                      # noqa: E402
from agent import coach_agent                        # noqa: E402
from analytics import training_metrics as metrics    # noqa: E402
import plan_service                                  # noqa: E402

app = FastAPI(title="Cadence API")


@app.on_event("startup")
def _startup():
    # Create the SQLite schema and seed the strength catalog once (idempotent).
    db.init_db()

# Allow the local React dev server to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CoachRequest(BaseModel):
    message: str
    history: list = []
    unit_system: str = "metric"   # "metric" | "imperial" — how the coach should speak


class WeightUpdate(BaseModel):
    # None clears the working weight; a number sets it (canonical kilograms).
    weight_kg: float | None = None


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": llm_provider.PROVIDER,
            "model": llm_provider.active_model()}


@app.get("/api/training-data")
def training_data():
    """Feeds the dashboard. Reads through the source layer (live or sample)."""
    return garmin_source.get_training_data()


@app.get("/api/metrics")
def training_metrics():
    """Derived metrics for the dashboard.

    Deliberately the SAME functions the agent's tools call, so a number on the
    chart and the number the coach quotes can never drift apart.
    """
    return metrics.full_bundle(
        garmin_source.get_all_activities(),
        garmin_source.get_athlete(),
        garmin_source.get_daily_recovery(),
    )


@app.get("/api/plan")
def training_plan(units: str = "imperial"):
    """The full periodized plan (all weeks + day-by-day sessions) for the plan view.

    `units` sets the unit system the workout prose is written in.
    """
    return plan_service.build_current_plan(system=units)


@app.get("/api/plan/overview")
def plan_overview(units: str = "imperial"):
    """Plan summary without per-day detail (phases + one line per week)."""
    return plan_service.plan_overview(system=units)


@app.get("/api/strength")
def strength():
    """The two condensed strength sessions with exercises and working weights."""
    catalog = db.load_catalog()
    return {
        "sessions": db.condensed_sessions(),
        "progression_note": catalog.get("progression_note"),
    }


@app.put("/api/strength/{exercise_id}")
def update_strength_weight(exercise_id: int, body: WeightUpdate):
    """Set or clear the working weight (kg) for one exercise."""
    updated = db.set_working_weight(exercise_id, body.weight_kg)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No exercise with id {exercise_id}")
    return updated


@app.post("/api/coach")
def coach(req: CoachRequest):
    """Ask the coach agent. Returns its reply and which tools it used."""
    result = coach_agent.ask_coach(req.message, req.history, req.unit_system)
    return result
