"""The provider interface every speech engine implements."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional


class SttError(Exception):
    """An engine could not produce a transcript; the registry tries the next."""

    def __init__(self, provider: str, reason: str, retryable: bool = True):
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason
        self.retryable = retryable


@dataclass
class Transcript:
    text: str
    language: str = ""            # BCP-47-ish, e.g. "hi", "en", "ta"
    provider: str = ""
    model: str = ""
    confidence: Optional[float] = None
    duration_ms: int = 0
    translated_text: str = ""     # English rendering when the engine can translate
    raw: Any = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return {
            "text": self.text, "language": self.language, "provider": self.provider,
            "model": self.model, "confidence": self.confidence, "duration_ms": self.duration_ms,
            "translated_text": self.translated_text,
        }


# The 22 scheduled languages the app serves, by ISO 639-1/639-3 code.
INDIC = frozenset({
    "hi", "bn", "te", "mr", "ta", "ur", "gu", "kn", "ml", "or", "pa", "as",
    "mai", "sat", "ks", "ne", "sd", "kok", "doi", "mni", "brx", "sa",
})

TIER_FREE_LOCAL = "free_local"      # runs on this machine, no network, no key
TIER_FREE_API = "free_api"          # hosted, free (or free tier), needs a key
TIER_FRONTIER = "frontier"          # hosted, paid, strongest accuracy
TIER_CLIENT = "client"              # the browser transcribes; the server records


class SttProvider:
    key: str = "base"
    display_name: str = "Base"
    tier: str = TIER_FRONTIER
    languages: frozenset = frozenset()       # empty means "any"
    supports_translate: bool = False
    data_leaves_host: bool = True
    env_keys: tuple = ()                     # what configures it
    note: str = ""

    def is_configured(self) -> bool:
        return all(os.environ.get(k) for k in self.env_keys)

    def is_available(self) -> bool:
        """Configured and, for local engines, importable."""
        return self.is_configured()

    def supports(self, language: str) -> bool:
        return not self.languages or (language or "").split("-")[0] in self.languages

    async def transcribe(self, audio: bytes, mime: str, language: str = "",
                         translate_to: str = "") -> Transcript:
        raise NotImplementedError

    def describe(self) -> dict:
        return {
            "key": self.key, "name": self.display_name, "tier": self.tier,
            "available": self.is_available(), "configured": self.is_configured(),
            "languages": sorted(self.languages) if self.languages else "any",
            "translate": self.supports_translate, "dataLeavesHost": self.data_leaves_host,
            "configure": list(self.env_keys), "note": self.note,
        }
