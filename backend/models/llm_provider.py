"""
Swappable LLM provider layer.

The whole app talks to ONE interface (`chat`), so the underlying model can be
switched with a single env var. Defaults to Claude;
Kimi K2 is supported because Moonshot exposes an Anthropic-compatible endpoint,
so the same SDK works with just a different base_url + key.

Set in .env:
    LLM_PROVIDER=claude   # or: kimi
    ANTHROPIC_API_KEY=...
    MOONSHOT_API_KEY=...   # only needed if LLM_PROVIDER=kimi
"""

import os
from anthropic import Anthropic

# Which provider is active, Claude is the default.
PROVIDER = os.getenv("LLM_PROVIDER", "claude").lower()

# Model the eval judge uses. Kept separate from the coach model on purpose: the
# judge should be at least as capable as what it grades, and shouldn't silently
# change when someone swaps the coach's provider. Defaults to the strongest Opus.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-opus-4-8")

# Per-provider config 
_PROVIDERS = {
    "claude": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": None,  # SDK default
        "model": "claude-opus-4-8",  # Anthropic's most capable Opus-tier model
    },
    "kimi": {
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.ai/anthropic",
        "model": "kimi-k2-0711-preview",
    },
}


def _build_client(provider: str):
    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Options: {list(_PROVIDERS)}"
        )
    cfg = _PROVIDERS[provider]
    api_key = os.getenv(cfg["api_key_env"])
    if not api_key:
        raise RuntimeError(
            f"Missing {cfg['api_key_env']} in environment (needed for '{provider}')."
        )
    kwargs = {"api_key": api_key}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
    return Anthropic(**kwargs)


# Cache one client per provider. The judge may use a different provider than the
# coach (e.g. coach on Kimi, judge on Claude), so a single global client won't do.
_clients: dict[str, Anthropic] = {}


def get_client(provider: str = PROVIDER):
    """Lazy per-provider client so importing this module needs no keys until use."""
    if provider not in _clients:
        _clients[provider] = _build_client(provider)
    return _clients[provider]


def active_model() -> str:
    return _PROVIDERS[PROVIDER]["model"]


def chat(messages, tools=None, system=None, max_tokens=1024,
         provider: str = PROVIDER, model: str | None = None, output_config=None):
    """Single entry point the rest of the app uses. Provider-agnostic.

    Returns the raw response object (same shape for Claude and Kimi, since Kimi
    speaks the Anthropic message format).

    `provider` / `model` override the active provider and its default model —
    used by the eval judge to grade with a specific strong model regardless of
    which provider the coach runs on. `output_config` forwards structured-output
    settings (e.g. a JSON schema) to the Messages API.
    """
    client = get_client(provider)
    kwargs = {
        "model": model or _PROVIDERS[provider]["model"],
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    if output_config:
        kwargs["output_config"] = output_config
    return client.messages.create(**kwargs)
