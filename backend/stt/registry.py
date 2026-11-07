"""Which engine answers, and what happens when it cannot.

Selection, in order:
  1. a provider the caller asked for by key (STT_STRICT=1 makes that final;
     otherwise the usual chain follows it as fallback);
  2. STT_PROVIDER from the environment, if not "auto";
  3. the language-aware default chain, with STT_FALLBACKS overriding the order.

Every engine that is available and supports the language is tried in turn;
the first transcript wins and the attempts are reported, so an operator can
see which key is dead and a citizen is never silenced by one outage.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from stt import audio as audio_tools
from stt.base import INDIC, SttError, SttProvider, Transcript
from stt.providers import ALL

logger = logging.getLogger(__name__)

_instances: dict[str, SttProvider] = {}

# Indic speech: GoI and Indian-specialist engines first, then general ones.
DEFAULT_INDIC = ["bhashini", "sarvam", "whisper_local", "openai_compatible", "nvidia_riva",
                 "groq", "openai", "gemini", "google", "azure", "deepgram", "assemblyai",
                 "elevenlabs", "vosk"]
# English and everything else: local first, then the strongest general engines.
DEFAULT_OTHER = ["whisper_local", "openai_compatible", "nvidia_riva", "groq", "openai",
                 "deepgram", "assemblyai", "elevenlabs", "google", "azure", "gemini",
                 "sarvam", "bhashini", "vosk"]


def providers() -> dict[str, SttProvider]:
    if not _instances:
        for cls in ALL:
            _instances[cls.key] = cls()
    return _instances


def get(key: str) -> Optional[SttProvider]:
    return providers().get((key or "").strip().lower())


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [x.strip().lower() for x in raw.replace(";", ",").split(",") if x.strip()]


def chain(language: str = "", requested: str = "") -> list[str]:
    """The ordered engine keys to try for this request."""
    lang = (language or "").split("-")[0]
    order: list[str] = []
    if requested:
        order.append(requested.strip().lower())
        if os.environ.get("STT_STRICT", "").lower() in ("1", "true", "yes"):
            return order
    configured = os.environ.get("STT_PROVIDER", "auto").strip().lower()
    if configured and configured != "auto":
        order.append(configured)
    fallbacks = _env_list("STT_FALLBACKS") or (DEFAULT_INDIC if lang in INDIC else DEFAULT_OTHER)
    order.extend(fallbacks)
    from auth import settings
    if settings.demo_mode():
        order.append("mock")
    seen: set[str] = set()
    return [k for k in order if k in providers() and not (k in seen or seen.add(k))]


async def transcribe(audio: bytes, mime: str = "", language: str = "", translate_to: str = "",
                     requested: str = "") -> tuple[Transcript, list[dict]]:
    """Try the chain; return the first transcript and the attempt log."""
    if not audio:
        raise SttError("registry", "no audio", retryable=False)
    mime = audio_tools.sniff_mime(audio, mime)
    attempts: list[dict] = []
    for key in chain(language, requested):
        p = providers()[key]
        if key == "client":
            continue
        if not p.is_available():
            attempts.append({"provider": key, "skipped": "not available"})
            continue
        if not p.supports(language):
            attempts.append({"provider": key, "skipped": f"no {language}"})
            continue
        t0 = time.time()
        try:
            t = await p.transcribe(audio, mime, language=language,
                                   translate_to=translate_to if p.supports_translate else "")
            ms = int((time.time() - t0) * 1000)
            attempts.append({"provider": key, "ok": True, "ms": ms})
            if not t.text.strip():
                attempts[-1].update({"ok": False, "error": "empty transcript"})
                continue
            if not t.duration_ms:
                t.duration_ms = ms
            return t, attempts
        except SttError as e:
            attempts.append({"provider": key, "ok": False, "error": e.reason[:160], "ms": int((time.time() - t0) * 1000)})
            logger.warning("STT %s failed: %s", key, e.reason)
        except Exception as e:  # noqa: BLE001 - one engine's bug must not stop the chain
            attempts.append({"provider": key, "ok": False, "error": f"{type(e).__name__}: {e}"[:160]})
            logger.exception("STT %s raised", key)
    raise SttError("registry", "no speech engine produced a transcript", retryable=True)


def describe(language: str = "hi") -> dict:
    """What the deployment can do, for the settings screen and the ops console."""
    return {
        "default": os.environ.get("STT_PROVIDER", "auto"),
        "chain": chain(language),
        "ffmpeg": audio_tools.ffmpeg_available(),
        "providers": [p.describe() for p in providers().values()],
    }
