"""
Eval harness for the coach agent.

Runs each case in eval_cases.json against the real agent and checks:
  1. Did the reply contain an expected keyword? (behavioral correctness)
  2. Did the agent use the expected tool? (used the right retrieval path)

This is the "write evals for AI features the same way you'd write unit tests"
piece. It's intentionally simple: keyword + tool-use assertions, pass/fail,
summary at the end. Extend it with an LLM-as-judge grader as a next step.

Run from the repo root:
    python -m evals.run_evals
(Requires backend deps installed and an API key set, since it calls the agent.)
"""

import sys
import json
from pathlib import Path

# Make the backend importable when running from repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from agent import coach_agent  # noqa: E402

CASES_PATH = Path(__file__).parent / "eval_cases.json"


def check_case(case):
    result = coach_agent.ask_coach(case["question"])
    reply = result["reply"].lower()
    tools_used = result["tool_calls"]

    # Check 1: reply contains at least one expected keyword.
    keywords = [k.lower() for k in case.get("expect_contains_any", [])]
    keyword_ok = any(k in reply for k in keywords) if keywords else True

    # Check 2: expected tool was used (if the case specifies one).
    expected_tool = case.get("expect_tool_used")
    if expected_tool is None:
        tool_ok = True
    else:
        tool_ok = expected_tool in tools_used

    passed = keyword_ok and tool_ok
    return {
        "id": case["id"],
        "passed": passed,
        "keyword_ok": keyword_ok,
        "tool_ok": tool_ok,
        "tools_used": tools_used,
        "reply": result["reply"],
    }


def main():
    cases = json.loads(CASES_PATH.read_text())
    results = [check_case(c) for c in cases]

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print("\n=== Cadence Coach Agent Evals ===\n")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']}")
        if not r["passed"]:
            print(f"       keyword_ok={r['keyword_ok']} tool_ok={r['tool_ok']} "
                  f"tools_used={r['tools_used']}")
            print(f"       reply: {r['reply'][:160]}...")
    print(f"\n{passed}/{total} passed\n")

    # Non-zero exit on failure so this can gate CI later.
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
