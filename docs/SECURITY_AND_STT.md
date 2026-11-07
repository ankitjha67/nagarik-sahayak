# Security architecture and the speech layer

*Added 2026-11-06. Companion to `PRODUCT_PLAN_UMANG.md` (delivers WP-01, most of WP-02, and the STT groundwork for WP-11).*

## 1. Security architecture

### 1.1 One rule, enforced everywhere

Every API request passes through `auth.deps.enforce` (attached to the router in `server.py`):

> **A request that names a user - in the path, the JSON body, or an `X-User-Id` header - must be authenticated as that user, or by a role allowed to act for them. A request that names nobody needs a token unless the route is on the public list.**

Multipart routes (uploads, voice) cannot be inspected generically, so they call `subject_for(request, user_id)` first thing; download routes call `principal_of(request)` and pass the caller to the ownership gate. There is no code path where a client-supplied id is trusted on its own.

Public routes are the catalog, languages, legal notice, stateless checks (`/verify/fields`, `/verify/eligibility`, `/eligibility-check`), the KYC *method list*, and `/auth/*`. Everything else - chat, profile, intake, generation, downloads, KYC verification, DPDP rights, notifications - needs identity.

### 1.2 Identity and sessions (`backend/auth/`)

| Concern | Design |
|---|---|
| Proof of phone | 6-digit code from OS entropy; stored as salted SHA-256; 5-minute life; **single use**; 5 wrong attempts lock the number 15 minutes; constant-time compare. (`otp.py`) |
| Delivery | `SmsProvider` interface: `log` (dev), `msg91` (DLT template, India), `twilio`, `webhook` (POST to any gateway you run - the portable option). A failed send answers 502 and discards the code; it never claims success. (`sms.py`) |
| Access token | HS256 JWT, `sub`/`role`/`sid`/`jti`/`iss`, life ≤ 60 min (NeGD ceiling), signed with `AUTH_JWT_SECRET`. Production refuses to start without the secret; development uses a per-process random key. (`tokens.py`, `settings.py`) |
| Refresh token | 48 random bytes, returned once, stored only as SHA-256. **Rotates on every use**; a retired token presented again means it was copied → the whole session is revoked (`refresh_reuse` audit event). |
| Revocation | Sessions live in Mongo (`auth_sessions`) or memory; `session_active()` is checked per request through a 10-second cache, so logout/theft response lands in seconds, not at token expiry. `logout-all` revokes every session of a user. |
| Roles | `citizen` (self only), `operator` (acts for a citizen who recorded consent in the operator's session), `reviewer`, `admin` (any user). Bootstrapped from `AUTH_*_PHONES`; carried in the token. |
| Operator consent | The citizen enters their OTP on the operator's device with `for_operator=true`: no session is started for the citizen; a time-boxed consent record (`operator_consents`) is written and audited. Operators cannot act without it. |
| Admin MFA | RFC 6238 TOTP (`totp.py`, no dependency; works with any authenticator app). `POST /auth/mfa/enroll` → secret + otpauth URI; `confirm` with a first code; from then on `verify-otp` needs `totp` for that admin. |
| Legacy admin header | `X-Admin-Secret` is accepted as an admin principal so existing tooling keeps working during migration. |
| Audit | `auth_audit` is a **hash chain**: each record carries `prev_hash` and `hash = sha256(prev_hash + canonical(record))`. `GET /auth/audit/verify` (admin) walks the tail and names the first broken link. Events: otp_issued, otp_failed, login, login_mfa_failed, refresh, refresh_reuse, logout, logout_all, consent_recorded, mfa_enrolled. |
| Demo builds | Only with `DEMO_MODE=1` *and* `APP_ENV≠production`: the OTP is `123456`, and chat/voice accept a placeholder id **that is not a Mongo ObjectId** without a token. Real accounts always have ObjectIds, so a placeholder can never reach a real citizen's data. |

### 1.3 Edge hygiene (`backend/api/middleware.py`)

Pure ASGI, so file downloads stream untouched:

- **RequestId** - `X-Request-Id` honoured or generated, echoed on the response.
- **SecurityHeaders** - `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (mic only), CSP `default-src 'none'`, `Cache-Control: no-store`, HSTS when served over TLS.
- **BodySizeLimit** - 413 by `Content-Length` and by counting chunks (256 KB JSON, 25 MB multipart by default).
- **RateLimit** - token bucket per bearer token (else per IP, honouring `X-Forwarded-For` only from `TRUSTED_PROXIES`), `429` with `Retry-After`.

### 1.4 Client (`frontend/src/lib/api.js`)

Stores access/refresh tokens, attaches `Authorization: Bearer`, refreshes once on a 401 (single in-flight refresh shared by concurrent requests), then ends the session; a 403 is reported, not treated as logout. Logout revokes server-side. The old `X-User-Id` header is gone.

### 1.5 What this closes from the bug-hunt, and what remains

Closed: unauthenticated chat/profile/intake reads by guessed id; mock OTP in production; `200` on a wrong OTP; no body limits; no per-client rate limit; missing security headers. Remaining (planned): AES-256-GCM at rest (WP-06), VAPT, tamper-evident audit for *all* data access (WP-05), a directory-backed role store.

### 1.6 Testing

- `tests/test_auth.py` - 17 unit tests (TOTP, OTP lockout/expiry/single-use, token expiry, refresh rotation and reuse detection, revocation, the enforcement rule on a minimal app, headers, body limit, rate limit, audit tamper detection).
- `tests/conftest.py` - for the live suite, remembers the token `verify-otp` returned for each user and attaches it to later requests naming that user; a user the suite never signed in as gets no token.

## 2. Speech to text (`backend/stt/`)

### 2.1 Why

The voice path was a single vendor SDK, hard-wired, with the browser recording a container that iPhones cannot produce. A GoI deployment must be able to run on Bhashini, or fully on-premise, or on whichever frontier engine a department licenses - without code changes.

### 2.2 Design

- `SttProvider` interface: `transcribe(audio, mime, language, translate_to) → Transcript`, plus `is_available()`, `supports(language)`, `describe()`.
- Every hosted engine speaks the vendor's **plain HTTP API through httpx** - no SDKs to install, so the backend runs anywhere Python runs. Local engines (`whisper_local`, `vosk`) import their package only if present.
- `stt/audio.py` sniffs the container from bytes (WebM, OGG, MP4/AAC, WAV, MP3, FLAC) and, when `ffmpeg` is on the machine, normalises to 16 kHz mono WAV, which every engine accepts; without ffmpeg the bytes pass through with the right type.
- `stt/registry.py` picks the chain: an explicitly requested provider first (`STT_STRICT=1` makes it final), then `STT_PROVIDER` if not `auto`, then a **language-aware default** (Indic speech → Bhashini, Sarvam, local Whisper, self-hosted, Groq, …; English → local first, then the strongest general engines), overridable by `STT_FALLBACKS`. Unavailable engines are skipped, a failing engine is logged and the next tried, and the **attempt log is returned** so an operator can see which key is dead.

### 2.3 Engines

| Key | Tier | Needs | Note |
|---|---|---|---|
| `bhashini` | free (GoI) | `BHASHINI_USER_ID`, `BHASHINI_ULCA_KEY` | ULCA pipeline config + Dhruva inference; 22 languages |
| `whisper_local` | free, on-server | `pip install faster-whisper` | no network; translate to English |
| `vosk` | free, on-server | `pip install vosk`, `VOSK_MODEL_PATH` | tiny models, feature-phone-class hardware |
| `openai_compatible` | free, self-hosted | `STT_COMPAT_BASE_URL` | any OpenAI-audio-compatible server (faster-whisper-server, speaches, LocalAI, a department GPU box) |
| `groq` | free tier | `GROQ_API_KEY` | Whisper large-v3-turbo, fast |
| `gemini` | free tier / paid | `GEMINI_API_KEY` | multimodal transcription (+ English line) |
| `openai` | frontier | `OPENAI_API_KEY` | gpt-4o-(mini-)transcribe or whisper-1 |
| `deepgram` | frontier | `DEEPGRAM_API_KEY` | nova-3 |
| `assemblyai` | frontier | `ASSEMBLYAI_API_KEY` | upload + poll |
| `google` | frontier | `GOOGLE_STT_API_KEY` | Speech-to-Text v1 |
| `azure` | frontier | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Indian locales |
| `sarvam` | frontier (Indic) | `SARVAM_API_KEY` | plain REST now, no SDK |
| `client` | on device | - | browser Web Speech API sends text; server records it |
| `mock` | tests/demo | - | fixed text |

### 2.4 Routes and client

- `GET /api/stt/providers?language=hi` (public) - every engine with availability, configuration hint, tier, languages, whether data leaves the host; the resolved chain; whether ffmpeg is present.
- `POST /api/stt/transcribe` (signed in) - `audio` (any container) or `text` (on-device), `language`, optional `provider`, `translate`.
- `POST /api/transcribe` - the chat turn, now on the same registry; the recording is stored **encrypted** like every other citizen document.
- `frontend/src/lib/stt.js` - picks the first container the browser can produce (`MediaRecorder.isTypeSupported` over WebM/Opus, OGG/Opus, MP4, AAC, WAV), so iPhone Safari works; offers on-device recognition (Web Speech API) as a mode; the provider is a per-viewer preference sent with each request.

### 2.5 Testing

`tests/test_stt.py` - sniffing, duration, normalisation pass-through, chain selection and fallback over an unavailable and a failing engine, strict mode, language support, default-chain preferences, `describe()` completeness, and the routes (public listing; 401 without sign-in; audio and on-device text; bad provider / empty audio → 400).
