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
- **Swappable model** — Claude by default; switch to Kimi K2 with one env var
  (Kimi is used via its Anthropic-compatible endpoint).
- **Evals** — a test suite that checks the agent's behavior and tool use, the
  way you'd unit-test classical code.
- **No-break demos** — reads live Garmin data when available, sample data
  otherwise.

## Tech stack
Python · FastAPI · React · Vite · recharts · Anthropic SDK · garminconnect

## Setup

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                 # opens http://localhost:5173
```

### Evals
```bash
# from repo root, with backend deps installed and an API key set
python -m evals.run_evals
```

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
