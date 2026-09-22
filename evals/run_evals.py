"""
Eval harness for the coach agent.

Runs each case in eval_cases.json against the real agent and checks:
  1. Did the reply contain an expected keyword? (behavioral correctness)
  2. Did the agent use the expected tool? (used the right retrieval path)

Two layers of grading:
  1. Deterministic checks (always on): keyword presence + expected tool used.
     Cheap, fast, reproducible.
  2. LLM-as-judge (opt in with --judge): a strong Claude model scores each reply
     against a per-case rubric, judging the *answer* rather than the mechanism.
     This catches correct answers the keyword check misses, and fabricated
     numbers the keyword check can't see.

Run from the repo root:
    python -m evals.run_evals            # deterministic checks only
    python -m evals.run_evals --judge    # + LLM-as-judge grading
(Requires backend deps installed and an API key in backend/.env — it calls the
agent, and the judge makes an extra model call per case.)
"""

import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv

# Make the backend importable when running from repo root.
_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))

# Load the same .env the app uses, so the eval runner picks up ANTHROPIC_API_KEY
# without needing it exported separately.
load_dotenv(_BACKEND / ".env")

# Evals are reproducible unit tests: they assert against the bundled sample data
# (fixed numbers like the 45.7 km week). Live Garmin data changes daily and would
# make the suite flap, so we force sample mode for the eval run regardless of what
# .env says for the live app. Must be set BEFORE importing the agent/data layer.
os.environ["USE_LIVE_GARMIN"] = "false"

from agent import coach_agent  # noqa: E402
from evals import judge         # noqa: E402

CASES_PATH = Path(__file__).parent / "eval_cases.json"


def check_case(case, use_judge=False):
    result = coach_agent.ask_coach(case["question"])
    reply = result["reply"]
    reply_lc = reply.lower()
    tools_used = result["tool_calls"]

    # Check 1: reply contains at least one expected keyword.
    keywords = [k.lower() for k in case.get("expect_contains_any", [])]
    keyword_ok = any(k in reply_lc for k in keywords) if keywords else True

    # Check 2: expected tool was used. `expect_tool_used` may be a single tool
    # name, a list of acceptable names, or null (no tool requirement).
    expected_tool = case.get("expect_tool_used")
    if expected_tool is None:
        tool_ok = True
    elif isinstance(expected_tool, list):
        tool_ok = any(t in tools_used for t in expected_tool)
    else:
        tool_ok = expected_tool in tools_used

    deterministic_ok = keyword_ok and tool_ok

    out = {
        "id": case["id"],
        "deterministic_ok": deterministic_ok,
        "keyword_ok": keyword_ok,
        "tool_ok": tool_ok,
        "tools_used": tools_used,
        "reply": reply,
        "verdict": None,
    }

    # Check 3 (opt-in): LLM-as-judge grades the answer against the rubric.
    if use_judge:
        out["verdict"] = judge.judge_reply(case, reply)

    return out


def _judge_passed(verdict):
    return verdict is not None and verdict.get("verdict") == "pass"


def main():
    use_judge = "--judge" in sys.argv
    cases = json.loads(CASES_PATH.read_text())
    results = [check_case(c, use_judge=use_judge) for c in cases]

    det_passed = sum(1 for r in results if r["deterministic_ok"])
    total = len(results)

    print("\n=== Cadence Coach Agent Evals ===")
    print(f"    (deterministic checks{' + LLM judge' if use_judge else ''})\n")
    for r in results:
        mark = "PASS" if r["deterministic_ok"] else "FAIL"
        line = f"[{mark}] {r['id']}"
        if use_judge and r["verdict"] is not None:
            v = r["verdict"]
            line += (f"   judge={v.get('verdict')} "
                     f"score={v.get('score')} grounded={v.get('grounded')}")
        print(line)
        if not r["deterministic_ok"]:
            print(f"       keyword_ok={r['keyword_ok']} tool_ok={r['tool_ok']} "
                  f"tools_used={r['tools_used']}")
            print(f"       reply: {r['reply'][:160]}...")
        # Surface any disagreement between the two layers — that's the
        # interesting signal (e.g. keyword-fail but judge-pass = brittle case).
        if use_judge and r["verdict"] is not None:
            judge_ok = _judge_passed(r["verdict"])
            if judge_ok != r["deterministic_ok"]:
                print(f"       ⚠ layers disagree: deterministic="
                      f"{r['deterministic_ok']} judge={judge_ok}")
                print(f"         judge reasoning: {r['verdict'].get('reasoning')}")

    print(f"\nDeterministic: {det_passed}/{total} passed")
    if use_judge:
        judge_passed = sum(1 for r in results if _judge_passed(r["verdict"]))
        errored = sum(1 for r in results
                      if r["verdict"] and r["verdict"].get("verdict") == "error")
        print(f"LLM judge:     {judge_passed}/{total} passed"
              + (f" ({errored} judge errors)" if errored else ""))
    print()

    # Gate on the strictest signal we ran. Non-zero exit on failure so this can
    # gate CI later.
    if use_judge:
        overall_ok = all(
            r["deterministic_ok"] and _judge_passed(r["verdict"]) for r in results
        )
    else:
        overall_ok = det_passed == total
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
