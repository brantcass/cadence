# Cadence 🏃

A personal AI endurance coach. Pulls one athlete's training data, visualizes it,
and lets them chat with an AI coach that retrieves their data through tools to
answer questions and suggest workouts.

Built as a full-stack, AI-forward project: FastAPI + React, a swappable LLM
provider (Claude / Kimi K2), an agent loop with tool use, and an eval harness.

## Features
- **AI coach agent** — chats with the athlete, calling tools to retrieve their
  recent activities, weekly load, and recovery data before answering.
- **Dashboard** — charts of recent distance and heart-rate trends.
- **Evals** — a test suite that checks the agent's behavior and tool use, the
  way you'd unit-test classical code.
- **No-break demos** — reads live Garmin data when available, sample data
  otherwise.

## Tech stack
Python · FastAPI · React · Vite · recharts · Anthropic SDK · garminconnect

## Setup (one time)

Install dependencies and create your `.env`.

**Backend**
```bash
cd backend
python -m venv .venv
# activate it:
.\.venv\Scripts\Activate.ps1      # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
cp .env.example .env              # then edit .env and add your ANTHROPIC_API_KEY
```

**Frontend**
```bash
cd frontend
npm install
```

## Running it

The app is **two processes** — run each in its own terminal, and leave both
running. The frontend calls the backend, so start the backend first.

**Terminal 1 — backend** (from the repo root)
```bash
cd backend
.\.venv\Scripts\Activate.ps1      # Windows  (source .venv/bin/activate on mac/linux)
uvicorn main:app --reload --port 8000
```

**Terminal 2 — frontend**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173**.

- Health check: **http://localhost:8000/api/health** should return
  `{"status":"ok","provider":"claude","model":"..."}`.
- First page load can be slow when `USE_LIVE_GARMIN=true` — it's doing the live
  Garmin pull (cached for 15 min afterward). If Garmin throttles, it falls back
  to sample data automatically, so the page still works.
- Don't have Node? The backend runs fine on its own; hit the API endpoints
  directly (`/api/training-data`, `/api/metrics`, `/api/coach`).

## Evals
```bash
# from repo root, with backend deps installed and ANTHROPIC_API_KEY in backend/.env
python -m evals.run_evals            # deterministic checks (keyword + tool use)
python -m evals.run_evals --judge    # + LLM-as-judge scoring against a rubric
```
Evals always run against the bundled sample data, so results are reproducible
regardless of your `.env` Garmin setting.

## How the agent works
The coach agent is given tool definitions (see `backend/agent/tools.py`). When
asked a question, the model decides which tools to call, the backend runs them
and feeds results back, and the loop repeats until the model gives a final
answer (`backend/agent/coach_agent.py`). The agent is scoped to a single
athlete's data.

## Notes
- Garmin access uses the unofficial `garminconnect` wrapper (personal login) —
  fine for a personal prototype. Leave `USE_LIVE_GARMIN=false` to run on sample
  data with zero setup.
- Secrets live in `.env` (gitignored).
