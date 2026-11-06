"""The provider interface every text-generation engine implements."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

TIER_LOCAL = "local"          # runs on this machine, no key
TIER_FREE_API = "free_api"    # hosted, free tier, needs a key
TIER_FRONTIER = "frontier"    # hosted, paid
TIER_BUNDLED = "bundled"      # the key shipped with the project


class LlmError(Exception):
    """A provider could not answer; the registry tries the next one."""

    def __init__(self, provider: str, reason: str, retryable: bool = True):
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason
        self.retryable = retryable


@dataclass
class Completion:
    text: str
    provider: str = ""
    model: str = ""
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Any = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return {
            "text": self.text, "provider": self.provider, "model": self.model,
            "finish_reason": self.finish_reason,
            "tokens": {"prompt": self.prompt_tokens, "completion": self.completion_tokens},
        }


class LlmProvider:
    key: str = "base"
    display_name: str = "Base"
    tier: str = TIER_FRONTIER
    env_keys: tuple = ()
    default_model: str = ""
    data_leaves_host: bool = True
    note: str = ""

    def model(self) -> str:
        return self.default_model

    def is_configured(self) -> bool:
        return all(os.environ.get(k) for k in self.env_keys)

    def is_available(self) -> bool:
        return self.is_configured()

    async def complete(self, prompt: str, system: str = "", *, temperature: float = 0.2,
                       max_tokens: int = 2048, json_mode: bool = False) -> Completion:
        raise NotImplementedError

    def describe(self) -> dict:
        return {
            "key": self.key, "name": self.display_name, "tier": self.tier,
            "available": self.is_available(), "configured": self.is_configured(),
            "model": self.model(), "dataLeavesHost": self.data_leaves_host,
            "configure": list(self.env_keys), "note": self.note,
        }
