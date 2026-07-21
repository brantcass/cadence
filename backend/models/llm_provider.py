"""
Swappable LLM provider layer.

The whole app talks to ONE interface (`chat`), so the underlying model can be
switched with a single env var. Defaults to Claude (matches the team's stack);
Kimi K2 is supported because Moonshot exposes an Anthropic-compatible endpoint,
so the same SDK works with just a different base_url + key.

Set in .env:
    LLM_PROVIDER=claude   # or: kimi
    ANTHROPIC_API_KEY=...
    MOONSHOT_API_KEY=...   # only needed if LLM_PROVIDER=kimi
"""

import os
from anthropic import Anthropic

# Which provider is active. Claude is the default.
PROVIDER = os.getenv("LLM_PROVIDER", "claude").lower()

# Per-provider config. Kimi reuses the Anthropic SDK via its compatible endpoint.
_PROVIDERS = {
    "claude": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": None,  # SDK default
        "model": "claude-sonnet-4-6",
    },
    "kimi": {
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.ai/anthropic",
        "model": "kimi-k2-0711-preview",
    },
}


def _build_client():
    if PROVIDER not in _PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{PROVIDER}'. Options: {list(_PROVIDERS)}"
        )
    cfg = _PROVIDERS[PROVIDER]
    api_key = os.getenv(cfg["api_key_env"])
    if not api_key:
        raise RuntimeError(
            f"Missing {cfg['api_key_env']} in environment (needed for '{PROVIDER}')."
        )
    kwargs = {"api_key": api_key}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
    return Anthropic(**kwargs)


_client = None


def get_client():
    """Lazy singleton so importing this module doesn't require keys until use."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def active_model() -> str:
    return _PROVIDERS[PROVIDER]["model"]


def chat(messages, tools=None, system=None, max_tokens=1024):
    """Single entry point the rest of the app uses. Provider-agnostic.

    Returns the raw response object (same shape for Claude and Kimi, since Kimi
    speaks the Anthropic message format).
    """
    client = get_client()
    kwargs = {
        "model": active_model(),
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)
