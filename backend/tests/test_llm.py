"""The provider-agnostic LLM layer: selection, fallback, and the routes.

No model is called for real; fakes stand in so the registry's behaviour - try
the chain, skip the unconfigured, survive a failing provider, report attempts -
is what is under test.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTH_JWT_SECRET", "unit-test-secret-which-is-long-enough-0123456789")
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from llm import registry  # noqa: E402
from llm.base import Completion, LlmError, LlmProvider  # noqa: E402


class Fake(LlmProvider):
    def __init__(self, key, text="", fail=False, available=True):
        self.key = key
        self.display_name = key
        self._text, self._fail, self._available = text, fail, available

    def is_available(self):
        return self._available

    async def complete(self, prompt, system="", **kw):
        if self._fail:
            raise LlmError(self.key, "boom")
        return Completion(text=self._text, provider=self.key, model="fake")


@pytest.fixture
def engines(monkeypatch):
    fakes = {
        "nocfg": Fake("nocfg", "N", available=False),
        "broken": Fake("broken", "B", fail=True),
        "good": Fake("good", "G"),
        "spare": Fake("spare", "S"),
    }
    monkeypatch.setattr(registry, "_instances", fakes)
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("LLM_FALLBACKS", "nocfg,broken,good,spare")
    monkeypatch.delenv("LLM_STRICT", raising=False)
    return fakes


@pytest.mark.asyncio
async def test_chain_skips_unconfigured_survives_failure(engines):
    c, attempts = await registry.complete("hi")
    assert c.text == "G" and c.provider == "good"
    assert [a["provider"] for a in attempts] == ["nocfg", "broken", "good"]
    assert attempts[0]["skipped"] == "not available"
    assert attempts[1]["ok"] is False and "boom" in attempts[1]["error"]
    assert engines["spare"]  # never reached


@pytest.mark.asyncio
async def test_requested_provider_first_then_fallback(engines):
    c, attempts = await registry.complete("hi", requested="spare")
    assert c.provider == "spare" and attempts[0]["provider"] == "spare"
    c, _ = await registry.complete("hi", requested="broken")
    assert c.provider == "good"            # broken failed, chain continued


@pytest.mark.asyncio
async def test_strict_does_not_fall_back(engines, monkeypatch):
    monkeypatch.setenv("LLM_STRICT", "1")
    with pytest.raises(LlmError):
        await registry.complete("hi", requested="broken")


@pytest.mark.asyncio
async def test_all_failing_raises(engines, monkeypatch):
    monkeypatch.setenv("LLM_FALLBACKS", "nocfg,broken")
    with pytest.raises(LlmError):
        await registry.complete("hi")


def test_default_chain_puts_nvidia_first(monkeypatch):
    monkeypatch.setattr(registry, "_instances", {})
    monkeypatch.delenv("LLM_FALLBACKS", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    assert registry.chain()[0] == "nvidia_nim"
    assert registry.chain()[-1] == "mock"


def test_describe_lists_every_provider(monkeypatch):
    monkeypatch.setattr(registry, "_instances", {})
    d = registry.describe()
    keys = {p["key"] for p in d["providers"]}
    assert {"nvidia_nim", "openai", "anthropic", "gemini", "groq", "mistral", "deepseek",
            "together", "fireworks", "cohere", "openai_compatible", "ollama", "emergent",
            "mock"} <= keys
    nv = next(p for p in d["providers"] if p["key"] == "nvidia_nim")
    assert nv["configure"] == ["NVIDIA_API_KEY"] and nv["available"] is False


def test_is_configured_ignores_mock(monkeypatch):
    monkeypatch.setattr(registry, "_instances", {})
    # No real key set in the unit env -> not configured, even though mock exists.
    assert registry.is_configured() is False


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
    import routes.llm as llm_routes
    importlib.reload(llm_routes)
    app = FastAPI()
    app.include_router(router, dependencies=[Depends(enforce)])
    return TestClient(app, raise_server_exceptions=False)


def test_providers_endpoint_is_public(client):
    r = client.get("/api/llm/providers")
    assert r.status_code == 200 and r.json()["chain"]


def test_complete_is_admin_only(client, bearer_for):
    body = {"prompt": "hello"}
    assert client.post("/api/llm/complete", json=body).status_code == 401
    assert client.post("/api/llm/complete", json=body, headers=bearer_for("u1", "citizen")).status_code == 403
    r = client.post("/api/llm/complete", json=body, headers=bearer_for("admin", "admin"))
    assert r.status_code == 200 and r.json()["completion"]["text"] == "G"
