# Cadence — project context for Claude Code

## What this is
Cadence is a personal AI endurance coach. It pulls one athlete's training data
(from Garmin, with a sample-data fallback), shows it on a dashboard, and lets the
user chat with an AI coach agent that retrieves their data via tools to answer
questions and suggest workouts.

The agent is deliberately scoped to a SINGLE athlete — architecturally parallel
to a per-student tutoring agent.

## Architecture
- **backend/** — FastAPI. Three endpoints: `/api/health`, `/api/training-data`,
  `/api/coach`.
  - `models/llm_provider.py` — swappable model layer. `LLM_PROVIDER` env var
    picks Claude (default) or Kimi K2. Everything calls `llm_provider.chat(...)`.
  - `agent/tools.py` — tool schemas + functions the agent uses to retrieve data.
  - `agent/coach_agent.py` — the agent loop (handles multi-turn tool use).
  - `data/garmin_source.py` — data layer. Live Garmin OR bundled sample data.
    Never let a demo depend on live Garmin working.
- **frontend/** — React + Vite. Dashboard (recharts) + chat panel.
- **evals/** — eval harness. `eval_cases.json` + `run_evals.py`.

## Key design decisions (don't undo these)
- The model provider is swappable via one interface. Keep new model calls going
  through `llm_provider.chat`, never call the SDK directly elsewhere.
- All training data is read through `garmin_source`, never hard-coded, so the
  sample fallback always works.
- The agent must NOT fabricate data. If a tool returns nothing, it says so.

## Conventions
- Python: clear names, small functions, comments explain *why* not *what*.
- Keep secrets in `.env` (gitignored). `.env.example` documents the vars.

## How to run
Backend:  `cd backend && pip install -r requirements.txt && uvicorn main:app --reload`
Frontend: `cd frontend && npm install && npm run dev`
Evals:    `python -m evals.run_evals`  (needs an API key set)

## Good next steps (ideas to build out)
- Add more tools (pace zones, week-over-week trends, PR detection).
- Add an LLM-as-judge grader to the eval harness beyond keyword checks.
- Persist chat history; add a real athlete profile.
- Flesh out the dashboard (HRV chart, effort distribution, load ratio).
