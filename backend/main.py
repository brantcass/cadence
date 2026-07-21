"""
Cadence backend — FastAPI.

Endpoints:
    GET  /api/health          -> liveness + which model provider is active
    GET  /api/training-data   -> raw training data for the dashboard charts
    POST /api/coach           -> ask the coach agent a question

Run:  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from data import garmin_source          # noqa: E402  (after load_dotenv)
from models import llm_provider          # noqa: E402
from agent import coach_agent            # noqa: E402

app = FastAPI(title="Cadence API")

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


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": llm_provider.PROVIDER,
            "model": llm_provider.active_model()}


@app.get("/api/training-data")
def training_data():
    """Feeds the dashboard. Reads through the source layer (live or sample)."""
    return garmin_source.get_training_data()


@app.post("/api/coach")
def coach(req: CoachRequest):
    """Ask the coach agent. Returns its reply and which tools it used."""
    result = coach_agent.ask_coach(req.message, req.history)
    return result
