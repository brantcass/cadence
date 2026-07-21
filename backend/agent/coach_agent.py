"""
The coach agent loop.

This is the core "agent" piece: the model is given tools, and we run a loop that
lets it call tools, feeds results back, and repeats until it produces a final
answer. This is the pattern the job description calls an "agent loop."

The agent is scoped to ONE athlete (their data is what the tools read), which is
deliberately parallel to a per-student tutoring agent.
"""

import json
from models import llm_provider
from agent import tools

SYSTEM_PROMPT = """You are Cadence, a personal endurance coach for ONE athlete.

You have tools to read the athlete's recent training, weekly load, and recovery
data. Use them before making claims — don't guess at numbers you can retrieve.

Your job:
- Answer questions about the athlete's training clearly and specifically.
- Flag overtraining risk when the data shows it (e.g. big mileage jumps plus
  declining HRV or sleep).
- When asked for a workout or plan, ground it in their recent load and recovery.

Be direct and practical. Cite the specific numbers you looked up. Do not invent
data. If a tool gives you nothing, say so rather than making something up."""

MAX_TURNS = 6  # safety cap so a misbehaving loop can't run forever


def ask_coach(user_message: str, history=None):
    """Run one coach interaction, resolving any tool calls along the way.

    Returns a dict: {"reply": str, "tool_calls": [names...]}.
    `history` is an optional list of prior {role, content} messages.
    """
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    tool_calls_made = []

    for _ in range(MAX_TURNS):
        response = llm_provider.chat(
            messages=messages,
            tools=tools.TOOL_SCHEMAS,
            system=SYSTEM_PROMPT,
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
                result = tools.run_tool(block.name, block.input)
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
