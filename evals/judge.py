"""
LLM-as-judge grader for coach replies.

The keyword + tool-name checks in `run_evals` are cheap and deterministic, but
they grade the *mechanism*, not the answer: a correct reply that happens not to
contain the exact keyword, or that reached the answer via a different tool, gets
marked wrong. (The `longest_run` case is a real example — a correct "16.1 km"
answer failed only because it used a better tool than the case hardcoded.)

This grader closes that gap. It hands the question, the athlete's real data, the
coach's reply, and a per-case rubric to a strong Claude model and asks for a
structured verdict. It judges whether the answer is *right and well-grounded*,
independent of wording or which tool ran.

Design choices worth knowing:
  - The judge runs on its own model (`JUDGE_MODEL`, default Opus), separate from
    the coach, so grading quality doesn't drift when the coach's model changes.
  - The schema puts `reasoning` BEFORE `verdict`/`score` so the model reasons
    before it commits to a grade, rather than rationalising a snap judgement.
  - The judge sees the same sample data the coach saw, so it can catch fabricated
    numbers — the one failure mode a keyword check can never detect.
"""

import json

from analytics import training_metrics as metrics
from data import garmin_source
from models import llm_provider

# Structured-output schema. Property ORDER matters: the model generates fields
# top-to-bottom, so `reasoning` first forces it to think before grading.
_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {
            "type": "string",
            "description": "Brief justification: does the reply meet each rubric "
                           "point? Note any fabricated or unsupported numbers.",
        },
        "grounded": {
            "type": "boolean",
            "description": "True if every factual claim is supported by the "
                           "athlete data; false if anything was invented.",
        },
        "score": {
            "type": "integer",
            "description": "Overall quality, 1 (poor/wrong) to 5 (excellent).",
        },
        "verdict": {
            "type": "string",
            "enum": ["pass", "fail"],
            "description": "pass if the reply satisfies the rubric AND is grounded.",
        },
    },
    "required": ["reasoning", "grounded", "score", "verdict"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = """You are a strict evaluator of an AI endurance coach's answers.
You are given the athlete's raw training data, a set of DERIVED METRICS computed
from that data, the user's question, a rubric, and the coach's reply.

Both the raw data and the derived metrics are ground truth. The coach has tools
that compute those derived metrics (pace zones, acute:chronic load ratio,
personal records, week-over-week trends), so a number in the reply that matches
the derived metrics is CORRECT and grounded — do not treat computed figures like
the load ratio or zone percentages as fabricated just because they aren't in the
raw rows. A claim is ungrounded only if it contradicts BOTH the raw data and the
derived metrics, or invents a category of data that doesn't exist at all (e.g. a
cycling power number when there is no cycling data).

Judge against the rubric, the raw data, and the derived metrics together. Reward
correct, grounded answers even when the wording differs from what you'd expect.
Be fair but demanding."""


def _judge_prompt(case, reply, data_json, metrics_json):
    return (
        f"ATHLETE RAW DATA (ground truth):\n{data_json}\n\n"
        f"DERIVED METRICS computed from that data (also ground truth — the coach's "
        f"tools produce these):\n{metrics_json}\n\n"
        f"QUESTION:\n{case['question']}\n\n"
        f"RUBRIC (what a correct answer must do):\n{case['rubric']}\n\n"
        f"COACH'S REPLY:\n{reply}\n\n"
        "Grade the reply against the rubric, the raw data, and the derived metrics."
    )


def judge_reply(case, reply):
    """Grade one coach reply. Returns the parsed verdict dict.

    Falls back to a structured error verdict (rather than raising) so one bad
    grade doesn't abort the whole eval run.
    """
    if "rubric" not in case:
        return None  # case opted out of judging

    data_json = json.dumps(garmin_source.get_training_data(), indent=2)
    bundle = metrics.full_bundle(
        garmin_source.get_all_activities(),
        garmin_source.get_athlete(),
        garmin_source.get_daily_recovery(),
    )
    metrics_json = json.dumps(bundle, indent=2)
    try:
        response = llm_provider.chat(
            messages=[{"role": "user",
                       "content": _judge_prompt(case, reply, data_json, metrics_json)}],
            system=_JUDGE_SYSTEM,
            max_tokens=1024,
            provider="claude",            # always grade with Claude
            model=llm_provider.JUDGE_MODEL,
            output_config={"format": {"type": "json_schema", "schema": _VERDICT_SCHEMA}},
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception as e:  # noqa: BLE001 - a judge failure shouldn't kill the run
        return {
            "reasoning": f"Judge error: {e}",
            "grounded": None,
            "score": None,
            "verdict": "error",
        }
