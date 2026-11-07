"""The speech layer: sniffing, engine selection, fallback, and the routes.

No engine is called for real. Each test swaps in small fake providers so the
registry's behaviour - try the chain, skip what is unavailable, survive a
broken engine, report every attempt - is what is under test.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi import Request  # module level: nested handlers resolve the annotation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTH_JWT_SECRET", "unit-test-secret-which-is-long-enough-0123456789")
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from stt import audio, registry  # noqa: E402
from stt.base import SttError, SttProvider, Transcript  # noqa: E402

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
WAV = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"fmt " + b"\x00" * 20 + b"data" + b"\x00\x00\x00\x00" + b"\x00" * 32000
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64


class Fake(SttProvider):
    tier = "free_api"
    env_keys = ()

    def __init__(self, key, text="", fail=False, available=True, langs=None):
        self.key = key
        self.display_name = key
        self._text, self._fail, self._available = text, fail, available
        self.languages = frozenset(langs or ())
        self.calls = 0

    def is_available(self):
        return self._available

    async def transcribe(self, audio_bytes, mime, language="", translate_to=""):
        self.calls += 1
        if self._fail:
            raise SttError(self.key, "boom")
        return Transcript(text=self._text, language=language, provider=self.key, model="fake")


@pytest.fixture
def engines(monkeypatch):
    """Install a fake engine set: a (unavailable), b (fails), c (works), d (works)."""
    fakes = {
        "a": Fake("a", "A", available=False),
        "b": Fake("b", "B", fail=True),
        "c": Fake("c", "C"),
        "d": Fake("d", "D"),
        "en_only": Fake("en_only", "E", langs=["en"]),
    }
    monkeypatch.setattr(registry, "_instances", fakes)
    monkeypatch.setenv("STT_PROVIDER", "auto")
    monkeypatch.setenv("STT_FALLBACKS", "a,b,c,d,en_only")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("STT_STRICT", raising=False)
    return fakes


# ── Audio ───────────────────────────────────────────────────────────────────

def test_sniff_recognises_browser_containers():
    assert audio.sniff_mime(WEBM) == "audio/webm"          # Chrome, Android
    assert audio.sniff_mime(MP4) == "audio/mp4"            # Safari, iPhone
    assert audio.sniff_mime(WAV) == "audio/wav"
    assert audio.sniff_mime(b"OggS" + b"\x00" * 8) == "audio/ogg"
    assert audio.sniff_mime(b"garbage", "audio/aac") == "audio/aac"


def test_wav_duration():
    assert audio.wav_duration_ms(WAV) == 1000               # 32000 bytes at 16 kHz mono 16-bit
    assert audio.wav_duration_ms(WEBM) == 0


@pytest.mark.asyncio
async def test_normalise_passes_through_or_converts():
    out, mime = await audio.to_wav16k(WEBM, "audio/webm")
    # ffmpeg cannot decode 64 bytes of header, so either way we get usable output
    assert isinstance(out, bytes) and mime in ("audio/webm", "audio/wav")


# ── Selection and fallback ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chain_skips_unavailable_survives_failure_and_reports(engines):
    t, attempts = await registry.transcribe(WEBM, "audio/webm", language="hi")
    assert t.text == "C" and t.provider == "c"
    assert [a["provider"] for a in attempts] == ["a", "b", "c"]
    assert attempts[0]["skipped"] == "not available"
    assert attempts[1]["ok"] is False and "boom" in attempts[1]["error"]
    assert attempts[2]["ok"] is True
    assert engines["d"].calls == 0                          # never reached


@pytest.mark.asyncio
async def test_requested_provider_goes_first_then_falls_back(engines):
    t, attempts = await registry.transcribe(WEBM, "audio/webm", language="hi", requested="d")
    assert t.provider == "d" and attempts[0]["provider"] == "d"

    t, attempts = await registry.transcribe(WEBM, "audio/webm", language="hi", requested="b")
    assert t.provider == "c"                                # b failed, chain continued


@pytest.mark.asyncio
async def test_strict_mode_does_not_fall_back(engines, monkeypatch):
    monkeypatch.setenv("STT_STRICT", "1")
    with pytest.raises(SttError):
        await registry.transcribe(WEBM, "audio/webm", language="hi", requested="b")


@pytest.mark.asyncio
async def test_language_support_is_respected(engines, monkeypatch):
    monkeypatch.setenv("STT_FALLBACKS", "en_only,d")
    t, attempts = await registry.transcribe(WEBM, "audio/webm", language="hi")
    assert t.provider == "d" and attempts[0]["skipped"] == "no hi"
    t, _ = await registry.transcribe(WEBM, "audio/webm", language="en")
    assert t.provider == "en_only"


@pytest.mark.asyncio
async def test_all_engines_failing_raises_one_error(engines, monkeypatch):
    monkeypatch.setenv("STT_FALLBACKS", "a,b")
    with pytest.raises(SttError):
        await registry.transcribe(WEBM, "audio/webm", language="hi")


def test_default_chain_prefers_indian_engines_for_indic_speech(monkeypatch):
    monkeypatch.setattr(registry, "_instances", {})
    monkeypatch.delenv("STT_FALLBACKS", raising=False)
    monkeypatch.setenv("STT_PROVIDER", "auto")
    monkeypatch.setenv("DEMO_MODE", "false")
    hi = registry.chain("hi")
    en = registry.chain("en")
    assert hi[0] == "bhashini" and "sarvam" in hi[:2]
    assert en[0] == "whisper_local"
    assert "mock" not in hi
    monkeypatch.setenv("DEMO_MODE", "true")
    assert registry.chain("hi")[-1] == "mock"


def test_describe_lists_every_engine_with_configuration_hints(monkeypatch):
    monkeypatch.setattr(registry, "_instances", {})
    d = registry.describe("hi")
    keys = {p["key"] for p in d["providers"]}
    assert {"bhashini", "whisper_local", "vosk", "openai_compatible", "groq", "openai",
            "deepgram", "assemblyai", "google", "azure", "gemini", "sarvam", "client", "mock"} <= keys
    groq = next(p for p in d["providers"] if p["key"] == "groq")
    assert groq["configure"] == ["GROQ_API_KEY"] and groq["available"] is False
    assert isinstance(d["ffmpeg"], bool)


# ── Routes ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch, engines):
    from fastapi import APIRouter, Depends, FastAPI
    from fastapi.testclient import TestClient
    import routes
    from auth.deps import enforce

    router = APIRouter(prefix="/api")
    monkeypatch.setattr(routes, "api_router", router)
    import importlib
    import routes.stt as stt_routes
    importlib.reload(stt_routes)                 # re-register the handlers on the private router
    app = FastAPI()
    app.include_router(router, dependencies=[Depends(enforce)])
    return TestClient(app, raise_server_exceptions=False)


def test_providers_endpoint_is_public(client):
    r = client.get("/api/stt/providers?language=ta")
    assert r.status_code == 200 and r.json()["chain"]


def test_transcribe_requires_sign_in_then_works(client, bearer_for):
    files = {"audio": ("clip.webm", WEBM, "audio/webm")}
    assert client.post("/api/stt/transcribe", files=files, data={"language": "hi"}).status_code == 401
    r = client.post("/api/stt/transcribe", files=files, data={"language": "hi"}, headers=bearer_for("u1"))
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"]["text"] == "C" and body["transcript"]["provider"] == "c"
    assert len(body["attempts"]) == 3


def test_transcribe_accepts_browser_text(client, bearer_for):
    r = client.post("/api/stt/transcribe", data={"text": "मेरा नाम सीता है", "language": "hi", "provider": "client"},
                    headers=bearer_for("u1"))
    assert r.status_code == 200 and r.json()["transcript"]["provider"] == "client"


def test_transcribe_rejects_unknown_provider_and_empty_audio(client, bearer_for):
    h = bearer_for("u1")
    r = client.post("/api/stt/transcribe", files={"audio": ("c.webm", WEBM, "audio/webm")},
                    data={"provider": "nope"}, headers=h)
    assert r.status_code == 400
    r = client.post("/api/stt/transcribe", files={"audio": ("c.webm", b"", "audio/webm")}, headers=h)
    assert r.status_code == 400
