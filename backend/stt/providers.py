"""Speech engines. Each speaks the vendor's plain HTTP API through httpx, or
runs locally when its optional package is installed. Adding an engine is one
class with `transcribe()`; nothing else in the app changes.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from typing import Optional

import httpx

from stt import audio as audio_tools
from stt.base import (INDIC, TIER_CLIENT, TIER_FREE_API, TIER_FREE_LOCAL, TIER_FRONTIER,
                      SttError, SttProvider, Transcript)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def bcp47(lang: str) -> str:
    """'hi' -> 'hi-IN', 'en' -> 'en-IN', 'ta-IN' stays."""
    lang = (lang or "").strip()
    if not lang:
        return ""
    if "-" in lang:
        return lang
    return f"{lang}-IN" if lang in INDIC or lang == "en" else lang


def _iso(lang: str) -> str:
    return (lang or "").split("-")[0]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


async def _post(url: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        return await client.post(url, **kw)


def _fail(provider: str, r: httpx.Response) -> SttError:
    retryable = r.status_code >= 500 or r.status_code == 429
    return SttError(provider, f"HTTP {r.status_code}: {r.text[:160]}", retryable=retryable)


# ── Free, Government of India ───────────────────────────────────────────────

class Bhashini(SttProvider):
    """MeitY's Bhashini ASR through the ULCA pipeline and Dhruva inference."""
    key = "bhashini"
    display_name = "Bhashini (MeitY)"
    tier = TIER_FREE_API
    languages = INDIC | {"en"}
    data_leaves_host = True
    env_keys = ("BHASHINI_USER_ID", "BHASHINI_ULCA_KEY")
    note = "Free for Indian languages; register at bhashini.gov.in. Data stays with a GoI service."

    CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"

    async def transcribe(self, audio, mime, language="", translate_to=""):
        lang = _iso(language) or "hi"
        wav, _ = await audio_tools.to_wav16k(audio, mime)
        pipeline = _env("BHASHINI_PIPELINE_ID", "64392f96daac500b55c543cd")
        headers = {"userID": _env("BHASHINI_USER_ID"), "ulcaApiKey": _env("BHASHINI_ULCA_KEY")}
        cfg = await _post(self.CONFIG_URL, headers=headers, json={
            "pipelineTasks": [{"taskType": "asr", "config": {"language": {"sourceLanguage": lang}}}],
            "pipelineRequestConfig": {"pipelineId": pipeline},
        })
        if cfg.status_code >= 300:
            raise _fail(self.key, cfg)
        c = cfg.json()
        try:
            service_id = c["pipelineResponseConfig"][0]["config"][0]["serviceId"]
            endpoint = c["pipelineInferenceAPIEndPoint"]
            call_url = endpoint["callbackUrl"]
            auth = endpoint["inferenceApiKey"]
            call_headers = {auth["name"]: auth["value"]}
        except (KeyError, IndexError) as e:
            raise SttError(self.key, f"unexpected pipeline config: {e}", retryable=False)
        r = await _post(call_url, headers=call_headers, json={
            "pipelineTasks": [{"taskType": "asr", "config": {
                "language": {"sourceLanguage": lang}, "serviceId": service_id,
                "audioFormat": "wav", "samplingRate": 16000}}],
            "inputData": {"audio": [{"audioContent": base64.b64encode(wav).decode()}]},
        })
        if r.status_code >= 300:
            raise _fail(self.key, r)
        try:
            text = r.json()["pipelineResponse"][0]["output"][0]["source"]
        except (KeyError, IndexError, ValueError) as e:
            raise SttError(self.key, f"unexpected inference response: {e}", retryable=False)
        return Transcript(text=text.strip(), language=lang, provider=self.key, model=service_id,
                          duration_ms=audio_tools.wav_duration_ms(wav))


# ── Free, local ─────────────────────────────────────────────────────────────

class WhisperLocal(SttProvider):
    """OpenAI's Whisper on this machine via faster-whisper. No network, no key."""
    key = "whisper_local"
    display_name = "Whisper (on this server)"
    tier = TIER_FREE_LOCAL
    supports_translate = True
    data_leaves_host = False
    env_keys = ()
    note = "pip install faster-whisper; set WHISPER_MODEL (tiny/base/small/medium/large-v3)."

    _model = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _load(self):
        if WhisperLocal._model is None:
            from faster_whisper import WhisperModel
            WhisperLocal._model = WhisperModel(_env("WHISPER_MODEL", "small"),
                                               device=_env("WHISPER_DEVICE", "auto"),
                                               compute_type=_env("WHISPER_COMPUTE", "int8"))
        return WhisperLocal._model

    async def transcribe(self, audio, mime, language="", translate_to=""):
        wav, _ = await audio_tools.to_wav16k(audio, mime)
        import io

        def run():
            model = self._load()
            segments, info = model.transcribe(
                io.BytesIO(wav), language=_iso(language) or None,
                task="translate" if translate_to == "en" else "transcribe", vad_filter=True)
            text = " ".join(s.text.strip() for s in segments)
            return text, info.language, getattr(info, "language_probability", None)

        text, lang, prob = await asyncio.to_thread(run)
        t = Transcript(text=text, language=lang or _iso(language), provider=self.key,
                       model=_env("WHISPER_MODEL", "small"), confidence=prob,
                       duration_ms=audio_tools.wav_duration_ms(wav))
        if translate_to == "en":
            t.translated_text, t.text = t.text, t.text
        return t


class Vosk(SttProvider):
    """Kaldi-based offline recogniser; small models for Hindi, Tamil, Telugu, Gujarati…"""
    key = "vosk"
    display_name = "Vosk (offline)"
    tier = TIER_FREE_LOCAL
    data_leaves_host = False
    env_keys = ("VOSK_MODEL_PATH",)
    note = "pip install vosk; download a model from alphacephei.com/vosk/models and set VOSK_MODEL_PATH."

    _model = None

    def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            import vosk  # noqa: F401
            return True
        except ImportError:
            return False

    async def transcribe(self, audio, mime, language="", translate_to=""):
        wav, _ = await audio_tools.to_wav16k(audio, mime)

        def run():
            import vosk
            vosk.SetLogLevel(-1)
            if Vosk._model is None:
                Vosk._model = vosk.Model(_env("VOSK_MODEL_PATH"))
            rec = vosk.KaldiRecognizer(Vosk._model, 16000)
            pcm = wav[44:] if wav.startswith(b"RIFF") else wav
            for i in range(0, len(pcm), 4000):
                rec.AcceptWaveform(pcm[i:i + 4000])
            return json.loads(rec.FinalResult()).get("text", "")

        text = await asyncio.to_thread(run)
        return Transcript(text=text, language=_iso(language), provider=self.key, model="vosk",
                          duration_ms=audio_tools.wav_duration_ms(wav))


# ── OpenAI-compatible family (OpenAI, Groq, any self-hosted server) ─────────

class _OpenAICompatible(SttProvider):
    base_url = ""
    key_env = ""
    model_env = ""
    default_model = "whisper-1"
    translate_model = ""

    def _base(self) -> str:
        return self.base_url

    async def transcribe(self, audio, mime, language="", translate_to=""):
        model = _env(self.model_env, self.default_model) if self.model_env else self.default_model
        path = "/audio/transcriptions"
        if translate_to == "en" and self.translate_model:
            path, model = "/audio/translations", self.translate_model
        headers = {}
        api_key = _env(self.key_env) if self.key_env else ""
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        data = {"model": model, "response_format": "json"}
        if path.endswith("transcriptions") and _iso(language):
            data["language"] = _iso(language)
        files = {"file": (f"audio.{audio_tools.extension_for(mime)}", audio, mime)}
        r = await _post(self._base().rstrip("/") + path, headers=headers, data=data, files=files)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        body = r.json()
        text = (body.get("text") or "").strip()
        t = Transcript(text=text, language=body.get("language") or _iso(language), provider=self.key,
                       model=model, raw=body)
        if path.endswith("translations"):
            t.translated_text = text
        return t


class OpenAI(_OpenAICompatible):
    key = "openai"
    display_name = "OpenAI (gpt-4o-transcribe / Whisper)"
    tier = TIER_FRONTIER
    supports_translate = True
    env_keys = ("OPENAI_API_KEY",)
    base_url = "https://api.openai.com/v1"
    key_env = "OPENAI_API_KEY"
    model_env = "OPENAI_STT_MODEL"
    default_model = "gpt-4o-mini-transcribe"
    translate_model = "whisper-1"
    note = "Set OPENAI_STT_MODEL to whisper-1, gpt-4o-mini-transcribe or gpt-4o-transcribe."


class Groq(_OpenAICompatible):
    key = "groq"
    display_name = "Groq (Whisper large-v3, free tier)"
    tier = TIER_FREE_API
    supports_translate = True
    env_keys = ("GROQ_API_KEY",)
    base_url = "https://api.groq.com/openai/v1"
    key_env = "GROQ_API_KEY"
    model_env = "GROQ_STT_MODEL"
    default_model = "whisper-large-v3-turbo"
    translate_model = "whisper-large-v3"
    note = "Fast hosted Whisper with a free tier; good Hindi and English."


class OpenAICompatibleServer(_OpenAICompatible):
    """Any server that speaks the OpenAI audio API: faster-whisper-server,
    speaches, LocalAI, vLLM-whisper, a department's own GPU box."""
    key = "openai_compatible"
    display_name = "Self-hosted (OpenAI-compatible)"
    tier = TIER_FREE_LOCAL
    supports_translate = True
    data_leaves_host = False
    env_keys = ("STT_COMPAT_BASE_URL",)
    key_env = "STT_COMPAT_API_KEY"
    model_env = "STT_COMPAT_MODEL"
    default_model = "Systran/faster-whisper-small"
    translate_model = ""
    note = "Point STT_COMPAT_BASE_URL at your own Whisper server (e.g. http://stt.internal:8000/v1)."

    def _base(self) -> str:
        return _env("STT_COMPAT_BASE_URL")


class NvidiaRiva(_OpenAICompatible):
    """NVIDIA Riva / NIM speech recognition. Recent Riva ASR NIM containers
    expose an OpenAI-compatible /v1/audio/transcriptions endpoint; point
    NVIDIA_STT_BASE_URL at it (self-hosted, so audio stays on your infra)."""
    key = "nvidia_riva"
    display_name = "NVIDIA Riva / NIM"
    tier = TIER_FREE_LOCAL
    languages = INDIC | {"en"}
    data_leaves_host = False
    env_keys = ("NVIDIA_STT_BASE_URL",)
    key_env = "NVIDIA_API_KEY"
    model_env = "NVIDIA_STT_MODEL"
    default_model = "parakeet-1.1b"
    translate_model = ""
    note = "Set NVIDIA_STT_BASE_URL to your Riva/NIM ASR endpoint (e.g. http://riva:9000/v1)."

    def _base(self) -> str:
        return _env("NVIDIA_STT_BASE_URL")


class ElevenLabs(SttProvider):
    key = "elevenlabs"
    display_name = "ElevenLabs Scribe"
    tier = TIER_FRONTIER
    env_keys = ("ELEVENLABS_API_KEY",)
    note = "Scribe v1, 99 languages; set ELEVENLABS_STT_MODEL (default scribe_v1)."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        data = {"model_id": _env("ELEVENLABS_STT_MODEL", "scribe_v1")}
        iso = _iso(language)
        if iso:
            data["language_code"] = iso
        files = {"file": (f"audio.{audio_tools.extension_for(mime)}", audio, mime)}
        r = await _post("https://api.elevenlabs.io/v1/speech-to-text",
                        headers={"xi-api-key": _env("ELEVENLABS_API_KEY")}, data=data, files=files)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        body = r.json()
        return Transcript(text=(body.get("text") or "").strip(),
                          language=_iso(body.get("language_code") or language),
                          provider=self.key, model=data["model_id"], raw=body)


# ── Frontier hosted engines ─────────────────────────────────────────────────

class Deepgram(SttProvider):
    key = "deepgram"
    display_name = "Deepgram Nova"
    tier = TIER_FRONTIER
    env_keys = ("DEEPGRAM_API_KEY",)
    note = "Free credits on sign-up; set DEEPGRAM_MODEL (default nova-3)."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        params = {"model": _env("DEEPGRAM_MODEL", "nova-3"), "smart_format": "true"}
        if _iso(language):
            params["language"] = _iso(language)
        r = await _post("https://api.deepgram.com/v1/listen", params=params,
                        headers={"authorization": f"Token {_env('DEEPGRAM_API_KEY')}", "content-type": mime},
                        content=audio)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        try:
            alt = r.json()["results"]["channels"][0]["alternatives"][0]
        except (KeyError, IndexError, ValueError) as e:
            raise SttError(self.key, f"unexpected response: {e}", retryable=False)
        return Transcript(text=alt.get("transcript", "").strip(), language=_iso(language),
                          provider=self.key, model=params["model"], confidence=alt.get("confidence"))


class AssemblyAI(SttProvider):
    key = "assemblyai"
    display_name = "AssemblyAI Universal"
    tier = TIER_FRONTIER
    env_keys = ("ASSEMBLYAI_API_KEY",)
    note = "Upload, then poll; free credits on sign-up."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        headers = {"authorization": _env("ASSEMBLYAI_API_KEY")}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            up = await client.post("https://api.assemblyai.com/v2/upload", headers=headers, content=audio)
            if up.status_code >= 300:
                raise _fail(self.key, up)
            body = {"audio_url": up.json()["upload_url"], "speech_model": _env("ASSEMBLYAI_MODEL", "universal")}
            if _iso(language):
                body["language_code"] = _iso(language)
            job = await client.post("https://api.assemblyai.com/v2/transcript", headers=headers, json=body)
            if job.status_code >= 300:
                raise _fail(self.key, job)
            tid = job.json()["id"]
            deadline = time.time() + 120
            while time.time() < deadline:
                await asyncio.sleep(1.5)
                st = await client.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=headers)
                data = st.json()
                if data.get("status") == "completed":
                    return Transcript(text=(data.get("text") or "").strip(), language=_iso(language),
                                      provider=self.key, model=body["speech_model"],
                                      confidence=data.get("confidence"))
                if data.get("status") == "error":
                    raise SttError(self.key, data.get("error", "transcription error"), retryable=False)
        raise SttError(self.key, "timed out waiting for transcript")


class GoogleSTT(SttProvider):
    key = "google"
    display_name = "Google Cloud Speech-to-Text"
    tier = TIER_FRONTIER
    env_keys = ("GOOGLE_STT_API_KEY",)
    note = "API key for speech.googleapis.com (v1, synchronous, ≤60 s clips)."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        wav, _ = await audio_tools.to_wav16k(audio, mime)
        pcm = wav[44:] if wav.startswith(b"RIFF") else wav
        r = await _post(f"https://speech.googleapis.com/v1/speech:recognize?key={_env('GOOGLE_STT_API_KEY')}",
                        json={"config": {"encoding": "LINEAR16", "sampleRateHertz": 16000,
                                         "languageCode": bcp47(language) or "hi-IN",
                                         "enableAutomaticPunctuation": True},
                              "audio": {"content": base64.b64encode(pcm).decode()}})
        if r.status_code >= 300:
            raise _fail(self.key, r)
        results = r.json().get("results", [])
        text = " ".join(x["alternatives"][0].get("transcript", "") for x in results if x.get("alternatives"))
        conf = results[0]["alternatives"][0].get("confidence") if results and results[0].get("alternatives") else None
        return Transcript(text=text.strip(), language=_iso(language), provider=self.key, model="v1",
                          confidence=conf, duration_ms=audio_tools.wav_duration_ms(wav))


class AzureSpeech(SttProvider):
    key = "azure"
    display_name = "Azure AI Speech"
    tier = TIER_FRONTIER
    env_keys = ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")
    note = "Short-audio REST endpoint; Indian locales supported (hi-IN, ta-IN, …)."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        wav, _ = await audio_tools.to_wav16k(audio, mime)
        region = _env("AZURE_SPEECH_REGION")
        url = (f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/"
               f"cognitiveservices/v1?language={bcp47(language) or 'hi-IN'}&format=simple")
        r = await _post(url, headers={"Ocp-Apim-Subscription-Key": _env("AZURE_SPEECH_KEY"),
                                      "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"},
                        content=wav)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        body = r.json()
        if body.get("RecognitionStatus") != "Success":
            raise SttError(self.key, body.get("RecognitionStatus", "no speech"), retryable=False)
        return Transcript(text=body.get("DisplayText", "").strip(), language=_iso(language),
                          provider=self.key, model="azure-stt", duration_ms=audio_tools.wav_duration_ms(wav))


class Gemini(SttProvider):
    key = "gemini"
    display_name = "Google Gemini (audio understanding)"
    tier = TIER_FRONTIER
    supports_translate = True
    env_keys = ("GEMINI_API_KEY",)
    note = "Multimodal model; set GEMINI_STT_MODEL (default gemini-2.0-flash). Free tier available."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        model = _env("GEMINI_STT_MODEL", "gemini-2.0-flash")
        instruction = "Transcribe this audio verbatim in its original language. Output only the transcript."
        if translate_to == "en":
            instruction += " Then, on a new line starting with 'EN:', give an English translation."
        r = await _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                        f"?key={_env('GEMINI_API_KEY')}",
                        json={"contents": [{"parts": [{"text": instruction},
                                                      {"inline_data": {"mime_type": mime,
                                                                       "data": base64.b64encode(audio).decode()}}]}]})
        if r.status_code >= 300:
            raise _fail(self.key, r)
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, ValueError) as e:
            raise SttError(self.key, f"unexpected response: {e}", retryable=False)
        translated = ""
        if "\nEN:" in text:
            text, translated = text.split("\nEN:", 1)
        return Transcript(text=text.strip(), language=_iso(language), provider=self.key, model=model,
                          translated_text=translated.strip())


class Sarvam(SttProvider):
    key = "sarvam"
    display_name = "Sarvam Saarika / Saaras"
    tier = TIER_FRONTIER
    languages = INDIC | {"en"}
    supports_translate = True
    env_keys = ("SARVAM_API_KEY",)
    note = "Indian-language specialist; plain REST, no SDK needed."

    async def transcribe(self, audio, mime, language="", translate_to=""):
        headers = {"api-subscription-key": _env("SARVAM_API_KEY")}
        files = {"file": (f"audio.{audio_tools.extension_for(mime)}", audio, mime)}
        if translate_to == "en":
            r = await _post("https://api.sarvam.ai/speech-to-text-translate", headers=headers,
                            data={"model": _env("SARVAM_TRANSLATE_MODEL", "saaras:v2.5")}, files=files)
        else:
            r = await _post("https://api.sarvam.ai/speech-to-text", headers=headers,
                            data={"model": _env("SARVAM_STT_MODEL", "saarika:v2.5"),
                                  "language_code": bcp47(language) or "unknown"}, files=files)
        if r.status_code >= 300:
            raise _fail(self.key, r)
        body = r.json()
        text = (body.get("transcript") or "").strip()
        t = Transcript(text=text, language=_iso(body.get("language_code") or language), provider=self.key,
                       model=body.get("model") or "sarvam", raw=body)
        if translate_to == "en":
            t.translated_text = text
        return t


# ── The browser, and a test double ──────────────────────────────────────────

class ClientSide(SttProvider):
    """The browser's own recogniser (Web Speech API) sends text; nothing to run."""
    key = "client"
    display_name = "On device (browser)"
    tier = TIER_CLIENT
    data_leaves_host = False
    env_keys = ()
    note = "Chrome/Edge/Safari speech recognition; the server only records the text."

    def is_available(self) -> bool:
        return True

    async def transcribe(self, audio, mime, language="", translate_to=""):
        raise SttError(self.key, "client-side provider receives text, not audio", retryable=False)


class Mock(SttProvider):
    key = "mock"
    display_name = "Mock (tests and demo)"
    tier = TIER_FREE_LOCAL
    data_leaves_host = False
    env_keys = ()
    note = "Returns STT_MOCK_TEXT. Enabled in demo builds and tests only."

    def is_available(self) -> bool:
        from auth import settings
        return settings.demo_mode() or bool(_env("STT_MOCK_TEXT"))

    async def transcribe(self, audio, mime, language="", translate_to=""):
        text = _env("STT_MOCK_TEXT", "मेरा बेटा 10th पास है, कॉलेज के लिए पैसा चाहिए")
        return Transcript(text=text, language=_iso(language) or "hi", provider=self.key, model="mock",
                          translated_text="My son passed 10th, need money for college" if translate_to == "en" else "")


ALL: list[type[SttProvider]] = [
    Bhashini, WhisperLocal, Vosk, OpenAICompatibleServer, NvidiaRiva, Groq, OpenAI,
    Gemini, Deepgram, AssemblyAI, GoogleSTT, AzureSpeech, Sarvam, ElevenLabs,
    ClientSide, Mock,
]
