"""
The coach agent loop.

The model is given tools, and it runs a loop that
lets it call tools, feeds results back, and repeats until it produces a final
answer. This is the pattern the job description calls an "agent loop."

The agent is scoped to ONE person (their data is what the tools read)
"""

import json
from models import llm_provider
from agent import tools

SYSTEM_PROMPT = """You are Cadence, a personal endurance coach for ONE person.

You have tools to read the athlete's recent training, weekly load, and recovery
data. Use them before making claims — don't guess at numbers you can retrieve.

Your job:
- Answer questions about the athlete's training clearly and specifically.
- Flag overtraining risk when the data shows it (e.g. big mileage jumps plus
  declining HRV or sleep).
- When asked for a workout or plan, ground it in their recent load and recovery.

Be direct and practical. Cite the specific numbers you looked up. Do not invent
data. If a tool gives you nothing, say so rather than making something up."""

# Appended to the system prompt per request, so the coach speaks the athlete's
# units. Conversion already happened in Python (tool results carry `*_display`
# strings); the coach must NOT convert numbers itself.
_UNIT_GUIDANCE = {
    "imperial": "\n\nThe athlete uses IMPERIAL units (miles, pounds). Tool "
                "results include pre-converted `*_display` fields "
                "(e.g. distance_display, pace_display). When you state a "
                "distance, pace, or weight, quote those display strings "
                "verbatim. Never convert numbers yourself.",
    "metric": "\n\nThe athlete uses METRIC units (kilometres, kilograms). Use "
              "the metric values in the tool results.",
}


def _system_prompt(unit_system: str) -> str:
    return SYSTEM_PROMPT + _UNIT_GUIDANCE.get(unit_system, _UNIT_GUIDANCE["metric"])


MAX_TURNS = 6  # safety cap so a misbehaving loop can't run forever


def ask_coach(user_message: str, history=None, unit_system: str = "metric"):
    """Run one coach interaction, resolving any tool calls along the way.

    Returns a dict: {"reply": str, "tool_calls": [names...]}.
    `history` is an optional list of prior {role, content} messages.
    `unit_system` ('metric' | 'imperial') controls the units the coach speaks in.
    """
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    system_prompt = _system_prompt(unit_system)
    tool_calls_made = []

    for _ in range(MAX_TURNS):
        response = llm_provider.chat(
            messages=messages,
            tools=tools.TOOL_SCHEMAS,
            system=system_prompt,
            max_tokens=1024,
        )

        # If the model didn't ask for a tool, it's giving its final answer.
        if response.stop_reason != "tool_use":
            reply_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return {"reply": reply_text, "tool_calls": tool_calls_made}

        # Otherwise: record the assistant's turn, run each requested tool,
        # and feed the results back in as a user turn.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls_made.append(block.name)
                result = tools.run_tool(block.name, block.input, unit_system)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        messages.append({"role": "user", "content": tool_results})

    # Hit the turn cap without a final answer.
    return {
        "reply": "Sorry, I couldn't finish reasoning about that in time.",
        "tool_calls": tool_calls_made,
    }
