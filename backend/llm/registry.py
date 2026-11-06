"""Which model answers, and the fallback when one is down.

Order: a provider named in the call, then LLM_PROVIDER from the environment if
not "auto", then a default chain (overridable with LLM_FALLBACKS). Only
available providers (their key set) are tried; a failing one is logged and the
next is used, and the attempts are reported.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from llm.base import Completion, LlmError, LlmProvider
from llm.providers import ALL

logger = logging.getLogger(__name__)

_instances: dict[str, LlmProvider] = {}

# NVIDIA NIM first (the user's default), then the other hosted frontier and
# free engines, then the bundled key and local options.
DEFAULT_CHAIN = ["nvidia_nim", "openai", "anthropic", "gemini", "groq", "mistral",
                 "deepseek", "together", "fireworks", "cohere", "emergent",
                 "openai_compatible", "ollama"]


def providers() -> dict[str, LlmProvider]:
    if not _instances:
        for cls in ALL:
            _instances[cls.key] = cls()
    return _instances


def get(key: str) -> Optional[LlmProvider]:
    return providers().get((key or "").strip().lower())


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [x.strip().lower() for x in raw.replace(";", ",").split(",") if x.strip()]


def chain(requested: str = "") -> list[str]:
    order: list[str] = []
    if requested:
        order.append(requested.strip().lower())
        if os.environ.get("LLM_STRICT", "").lower() in ("1", "true", "yes"):
            return [k for k in order if k in providers()]
    configured = os.environ.get("LLM_PROVIDER", "auto").strip().lower()
    if configured and configured != "auto":
        order.append(configured)
    order.extend(_env_list("LLM_FALLBACKS") or DEFAULT_CHAIN)
    order.append("mock")
    seen: set[str] = set()
    return [k for k in order if k in providers() and not (k in seen or seen.add(k))]


def is_configured() -> bool:
    """True if any real (non-mock) provider has a key."""
    return any(p.is_available() for k, p in providers().items() if k != "mock")


async def complete(prompt: str, system: str = "", *, requested: str = "",
                   temperature: float = 0.2, max_tokens: int = 2048,
                   json_mode: bool = False) -> tuple[Completion, list[dict]]:
    attempts: list[dict] = []
    for key in chain(requested):
        p = providers()[key]
        if not p.is_available():
            attempts.append({"provider": key, "skipped": "not available"})
            continue
        t0 = time.time()
        try:
            c = await p.complete(prompt, system, temperature=temperature,
                                 max_tokens=max_tokens, json_mode=json_mode)
            attempts.append({"provider": key, "ok": True, "ms": int((time.time() - t0) * 1000)})
            if not c.text.strip():
                attempts[-1].update({"ok": False, "error": "empty completion"})
                continue
            return c, attempts
        except LlmError as e:
            attempts.append({"provider": key, "ok": False, "error": e.reason[:200],
                             "ms": int((time.time() - t0) * 1000)})
            logger.warning("LLM %s failed: %s", key, e.reason)
        except Exception as e:  # noqa: BLE001
            attempts.append({"provider": key, "ok": False, "error": f"{type(e).__name__}: {e}"[:200]})
            logger.exception("LLM %s raised", key)
    raise LlmError("registry", "no LLM provider produced a completion", retryable=True)


def describe() -> dict:
    return {
        "default": os.environ.get("LLM_PROVIDER", "auto"),
        "configured": is_configured(),
        "chain": chain(),
        "providers": [p.describe() for p in providers().values()],
    }
