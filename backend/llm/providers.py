"""LLM engines. Each speaks the vendor's HTTP API through httpx. Most major
providers expose an OpenAI-compatible chat endpoint, so one class covers them
by base URL and model; Anthropic, Gemini and Cohere have their own shapes.
"""
from __future__ import annotations

import os

import httpx

from llm.base import (TIER_BUNDLED, TIER_FRONTIER, TIER_FREE_API, TIER_LOCAL,
                      Completion, LlmError, LlmProvider)

_TIMEOUT = httpx.Timeout(90.0, connect=10.0)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


async def _post(url: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        return await client.post(url, **kw)


def _fail(provider: str, r: httpx.Response) -> LlmError:
    return LlmError(provider, f"HTTP {r.status_code}: {r.text[:200]}",
                    retryable=r.status_code >= 500 or r.status_code == 429)


# ── OpenAI-compatible family ────────────────────────────────────────────────

class _OpenAICompatible(LlmProvider):
    base_url = ""
    key_env = ""
    model_env = ""

    def _base(self) -> str:
        return self.base_url

    def model(self) -> str:
        return _env(self.model_env, self.default_model) if self.model_env else self.default_model

    async def complete(self, prompt, system="", *, temperature=0.2, max_tokens=2048, json_mode=False):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.model(), "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"content-type": "application/json"}
        key = _env(self.key_env) if self.key_env else ""
        if key:
            headers["authorization"] = f"Bearer {key}"
        r = await _post(self._base().rstrip("/") + "/chat/completions", headers=headers, json=body)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        data = r.json()
        try:
            choice = data["choices"][0]
            text = (choice["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as e:
            raise LlmError(self.key, f"unexpected response: {e}", retryable=False)
        usage = data.get("usage") or {}
        return Completion(text=text, provider=self.key, model=self.model(),
                          finish_reason=choice.get("finish_reason", ""),
                          prompt_tokens=usage.get("prompt_tokens", 0),
                          completion_tokens=usage.get("completion_tokens", 0), raw=data)


class NvidiaNim(_OpenAICompatible):
    key = "nvidia_nim"
    display_name = "NVIDIA NIM"
    tier = TIER_FRONTIER
    env_keys = ("NVIDIA_API_KEY",)
    key_env = "NVIDIA_API_KEY"
    model_env = "NVIDIA_NIM_MODEL"
    default_model = "meta/llama-3.1-70b-instruct"
    note = ("NVIDIA-hosted models at integrate.api.nvidia.com (key nvapi-…); "
            "set NVIDIA_NIM_BASE_URL to point at a self-hosted NIM instead.")

    def _base(self) -> str:
        return _env("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")


class OpenAI(_OpenAICompatible):
    key = "openai"
    display_name = "OpenAI"
    tier = TIER_FRONTIER
    env_keys = ("OPENAI_API_KEY",)
    base_url = "https://api.openai.com/v1"
    key_env = "OPENAI_API_KEY"
    model_env = "OPENAI_MODEL"
    default_model = "gpt-4o-mini"

    def _base(self) -> str:
        return _env("OPENAI_BASE_URL", self.base_url)


class Groq(_OpenAICompatible):
    key = "groq"
    display_name = "Groq"
    tier = TIER_FREE_API
    env_keys = ("GROQ_API_KEY",)
    base_url = "https://api.groq.com/openai/v1"
    key_env = "GROQ_API_KEY"
    model_env = "GROQ_MODEL"
    default_model = "llama-3.3-70b-versatile"
    note = "Fast hosted inference with a free tier."


class Mistral(_OpenAICompatible):
    key = "mistral"
    display_name = "Mistral"
    tier = TIER_FRONTIER
    env_keys = ("MISTRAL_API_KEY",)
    base_url = "https://api.mistral.ai/v1"
    key_env = "MISTRAL_API_KEY"
    model_env = "MISTRAL_MODEL"
    default_model = "mistral-large-latest"


class DeepSeek(_OpenAICompatible):
    key = "deepseek"
    display_name = "DeepSeek"
    tier = TIER_FRONTIER
    env_keys = ("DEEPSEEK_API_KEY",)
    base_url = "https://api.deepseek.com"
    key_env = "DEEPSEEK_API_KEY"
    model_env = "DEEPSEEK_MODEL"
    default_model = "deepseek-chat"


class Together(_OpenAICompatible):
    key = "together"
    display_name = "Together AI"
    tier = TIER_FRONTIER
    env_keys = ("TOGETHER_API_KEY",)
    base_url = "https://api.together.xyz/v1"
    key_env = "TOGETHER_API_KEY"
    model_env = "TOGETHER_MODEL"
    default_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"


class Fireworks(_OpenAICompatible):
    key = "fireworks"
    display_name = "Fireworks AI"
    tier = TIER_FRONTIER
    env_keys = ("FIREWORKS_API_KEY",)
    base_url = "https://api.fireworks.ai/inference/v1"
    key_env = "FIREWORKS_API_KEY"
    model_env = "FIREWORKS_MODEL"
    default_model = "accounts/fireworks/models/llama-v3p3-70b-instruct"


class Ollama(_OpenAICompatible):
    key = "ollama"
    display_name = "Ollama (local)"
    tier = TIER_LOCAL
    data_leaves_host = False
    env_keys = ()
    key_env = ""
    model_env = "OLLAMA_MODEL"
    default_model = "llama3.1"
    note = "A local Ollama server; set OLLAMA_BASE_URL (default http://localhost:11434/v1)."

    def _base(self) -> str:
        return _env("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    def is_available(self) -> bool:
        return bool(_env("OLLAMA_BASE_URL")) or _env("LLM_PROVIDER") == "ollama"


class OpenAICompatibleServer(_OpenAICompatible):
    key = "openai_compatible"
    display_name = "Self-hosted (OpenAI-compatible)"
    tier = TIER_LOCAL
    data_leaves_host = False
    env_keys = ("LLM_COMPAT_BASE_URL",)
    key_env = "LLM_COMPAT_API_KEY"
    model_env = "LLM_COMPAT_MODEL"
    default_model = "local-model"
    note = "Any server with an OpenAI /chat/completions endpoint (vLLM, TGI, LocalAI, LM Studio…)."

    def _base(self) -> str:
        return _env("LLM_COMPAT_BASE_URL")


# ── Native schemas ──────────────────────────────────────────────────────────

class Anthropic(LlmProvider):
    key = "anthropic"
    display_name = "Anthropic Claude"
    tier = TIER_FRONTIER
    env_keys = ("ANTHROPIC_API_KEY",)
    default_model = "claude-3-5-sonnet-latest"

    def model(self):
        return _env("ANTHROPIC_MODEL", self.default_model)

    async def complete(self, prompt, system="", *, temperature=0.2, max_tokens=2048, json_mode=False):
        body = {"model": self.model(), "max_tokens": max_tokens, "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        r = await _post("https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": _env("ANTHROPIC_API_KEY"),
                                 "anthropic-version": "2023-06-01", "content-type": "application/json"},
                        json=body)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        data = r.json()
        try:
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text").strip()
        except (KeyError, TypeError) as e:
            raise LlmError(self.key, f"unexpected response: {e}", retryable=False)
        usage = data.get("usage") or {}
        return Completion(text=text, provider=self.key, model=self.model(),
                          finish_reason=data.get("stop_reason", ""),
                          prompt_tokens=usage.get("input_tokens", 0),
                          completion_tokens=usage.get("output_tokens", 0), raw=data)


class Gemini(LlmProvider):
    key = "gemini"
    display_name = "Google Gemini"
    tier = TIER_FREE_API
    env_keys = ("GEMINI_API_KEY",)
    default_model = "gemini-2.0-flash"

    def model(self):
        return _env("GEMINI_MODEL", self.default_model)

    async def complete(self, prompt, system="", *, temperature=0.2, max_tokens=2048, json_mode=False):
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        r = await _post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model()}"
                        f":generateContent?key={_env('GEMINI_API_KEY')}", json=body)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        data = r.json()
        try:
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
        except (KeyError, IndexError, TypeError) as e:
            raise LlmError(self.key, f"unexpected response: {e}", retryable=False)
        return Completion(text=text, provider=self.key, model=self.model(), raw=data)


class Cohere(LlmProvider):
    key = "cohere"
    display_name = "Cohere"
    tier = TIER_FRONTIER
    env_keys = ("COHERE_API_KEY",)
    default_model = "command-r-plus"

    def model(self):
        return _env("COHERE_MODEL", self.default_model)

    async def complete(self, prompt, system="", *, temperature=0.2, max_tokens=2048, json_mode=False):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        r = await _post("https://api.cohere.com/v2/chat",
                        headers={"authorization": f"Bearer {_env('COHERE_API_KEY')}",
                                 "content-type": "application/json"},
                        json={"model": self.model(), "messages": messages,
                              "temperature": temperature, "max_tokens": max_tokens})
        if r.status_code >= 300:
            raise _fail(self.key, r)
        data = r.json()
        try:
            text = "".join(b.get("text", "") for b in data["message"]["content"]).strip()
        except (KeyError, TypeError) as e:
            raise LlmError(self.key, f"unexpected response: {e}", retryable=False)
        return Completion(text=text, provider=self.key, model=self.model(), raw=data)


class Emergent(LlmProvider):
    """The key shipped with the project (Claude via emergentintegrations)."""
    key = "emergent"
    display_name = "Emergent LLM key"
    tier = TIER_BUNDLED
    env_keys = ("EMERGENT_LLM_KEY",)
    default_model = "claude-sonnet-4-20250514"

    def is_available(self):
        if not self.is_configured():
            return False
        try:
            import emergentintegrations.llm.chat  # noqa: F401
            return True
        except ImportError:
            return False

    async def complete(self, prompt, system="", *, temperature=0.2, max_tokens=2048, json_mode=False):
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except ImportError:
            raise LlmError(self.key, "emergentintegrations not installed", retryable=False)
        import uuid
        chat = LlmChat(api_key=_env("EMERGENT_LLM_KEY"),
                       session_id=f"llm_{uuid.uuid4().hex[:8]}",
                       system_message=system or "You are a helpful assistant.")
        provider, model = _env("EMERGENT_PROVIDER", "anthropic"), _env("EMERGENT_MODEL", self.default_model)
        chat = chat.with_model(provider, model)
        try:
            text = await chat.send_message(UserMessage(text=prompt))
        except Exception as e:  # noqa: BLE001 — their SDK raises broadly
            raise LlmError(self.key, f"{type(e).__name__}: {e}")
        return Completion(text=(text or "").strip(), provider=self.key, model=model)


class Mock(LlmProvider):
    key = "mock"
    display_name = "Mock (tests)"
    tier = TIER_LOCAL
    data_leaves_host = False
    env_keys = ()

    def is_available(self):
        return bool(_env("LLM_MOCK_TEXT")) or _env("LLM_PROVIDER") == "mock"

    async def complete(self, prompt, system="", *, temperature=0.2, max_tokens=2048, json_mode=False):
        return Completion(text=_env("LLM_MOCK_TEXT", "{}"), provider=self.key, model="mock")


ALL: list[type[LlmProvider]] = [
    NvidiaNim, OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, Together,
    Fireworks, Cohere, OpenAICompatibleServer, Ollama, Emergent, Mock,
]
