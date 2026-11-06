# Nagarik Sahayak

**Nagarik Sahayak** ("citizen helper") helps people in India find the government
welfare schemes they actually qualify for — and fills out the real application
forms for them. A citizen gives their details once, in any of the 22 scheduled
languages, and the app finds the Central and State schemes they are eligible
for, tells them which documents to carry, collects every field the chosen form
needs one validated question at a time, and produces the department's own
published PDF, filled.

The whole decision path — eligibility, fraud screening, document checklist,
form filling — is rule-based and runs with **no LLM key and no internet
dependency**. The citizen's Aadhaar number is never stored or printed in full.

> This repository began as a hackathon entry and has since grown into a working
> product. Some older crawler files remain at the repository root; the live
> application is `backend/` (FastAPI) and `frontend/` (React + Capacitor).

---

## What it does

- **Find what you qualify for.** 57 curated Central and State schemes across 33
  states and union territories, gated on domicile, with bilingual fields and
  real eligibility rules.
- **Collect a form's details, one question at a time.** The intake engine reads
  a chosen form's own fields, asks only for what it does not already know,
  validates and normalises each answer (dates to ISO, IFSC upper-cased, Indic
  numerals to ASCII, bad phone/PIN/Aadhaar rejected in both languages), and
  remembers answers for the next form.
- **Fill the real government PDF.** The filler overlays answers onto the
  published form — recovering the ruled grid from a scanned page, placing comb
  boxes and composite fields, verifying nothing spills a cell — and names any
  field the form has no slot for so the citizen can write it by hand.
- **Screen before issuing.** Eligibility is decided against each scheme's stated
  rules; a fraud/abuse pass flags the usual gaming without ever refusing an
  honest applicant. Absence of data is a request for more, never a rejection.
- **Say what to carry.** A "what to carry to the counter" checklist derived from
  the form, bilingual, with the lawful alternatives to Aadhaar named.
- **Speak, in your language.** Voice intake through a provider-agnostic
  speech-to-text layer; the interface in 22 Eighth Schedule languages, including
  right-to-left scripts, with honesty flags on unreviewed translations.

## Built in

- **Privacy and law (DPDP Act 2023, Aadhaar Act).** Consent and notice,
  data-principal rights, processing register, retention, documents encrypted at
  rest and gated to their owner. The full Aadhaar number is never persisted,
  logged or displayed — only the last four and a keyed fingerprint. Legal and
  consent text is served only in human-reviewed English and Hindi, never
  machine-translated.
- **Identity without exclusion (KYC).** Offline Aadhaar QR/XML, tolerant name
  and date matching, 14 catalogued verification methods — and a benefit is never
  refused for want of verification (Aadhaar Act s7 proviso).
- **Security.** Phone-OTP login (codes hashed at rest, single-use,
  attempt-limited, delivered through a pluggable SMS provider), short-lived JWT
  access tokens with rotating refresh tokens and theft detection, roles
  (citizen / operator / reviewer / admin) with TOTP for admins, one
  authorisation rule enforced on every route, a hash-chained audit, security
  headers, body-size limits and rate limiting.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Prisma (MongoDB, replica set), Motor; PyMuPDF + Tesseract for forms |
| Frontend | React (CRA + CRACO), Tailwind, Radix UI |
| Mobile | Capacitor 7 Android app (same UI in a WebView) |
| Speech | Bhashini, local Whisper / Vosk, self-hosted, Groq, OpenAI, Gemini, Deepgram, AssemblyAI, Google, Azure, Sarvam, on-device |
| Tests | ~2,260 backend tests (pytest) |

## Repository layout

```
backend/        FastAPI application
  routes/       HTTP endpoints (auth, chat, v2 intake, forms, kyc, dpdp, i18n, stt, …)
  services/     form_intake, application_guard, eligibility, document_checklist, …
  auth/         sessions, tokens, OTP, TOTP, RBAC enforcement
  api/          edge middleware (security headers, limits, rate limiting)
  dpdp/         consent, notice, ownership, encryption, Aadhaar policy
  kyc/          offline Aadhaar, tolerant matching, method catalogue
  i18n/         22-language catalogue and resolution
  stt/          provider-agnostic speech-to-text
  data/         curated government-form catalogue
  pdf_filler.py, form_geometry.py, eligibility_engine.py, fraud_detection.py, …
  tests/        pytest suite
frontend/       React app + Capacitor Android project (android/)
mobile/         ADB_RUNBOOK.md — install and test the app on a real phone
docs/           PRODUCT_PLAN_UMANG.md (UMANG / API Setu plan), SECURITY_AND_STT.md
```

## Run it locally

MongoDB must be a replica set (Prisma uses transactions).

```bash
# MongoDB (Docker is the quickest)
docker run -d --name ns-mongo -p 27017:27017 mongo:7 --replSet rs0
docker exec ns-mongo mongosh --quiet --eval \
  'rs.initiate({_id:"rs0",members:[{_id:0,host:"127.0.0.1:27017"}]})'

# Backend
cd backend
pip install -r requirements.txt
python -m prisma generate
cp .env.example .env            # then fill in the values (see the file's comments)
export MONGO_URL="mongodb://127.0.0.1:27017/nagarik_sahayak?replicaSet=rs0"
export DEMO_MODE=true            # OTP is 123456 and speech falls back to a mock
python -m prisma db push --skip-generate
python -m uvicorn server:app --host 127.0.0.1 --port 8001

# Frontend (in another shell)
cd frontend
npm install --legacy-peer-deps
REACT_APP_BACKEND_URL="http://localhost:8001" npm start
```

`backend/.env.example` documents every setting, including real SMS providers
and the fourteen speech engines. Nothing but MongoDB is required to run the core
flow; an LLM key is optional.

### Tests

```bash
cd backend
# unit tests need no server
python -m pytest tests/ -q
# the integration tests talk to a running server:
REACT_APP_BACKEND_URL=http://127.0.0.1:8001 python -m pytest tests/ -q
python scripts/smoke_test.py    # end-to-end against a live government form
```

## On a phone

A debug APK can be installed and tested over USB. `mobile/ADB_RUNBOOK.md` has the
full procedure: `adb install`, start the backend in `DEMO_MODE`, bridge the phone
to it with `adb reverse tcp:8001 tcp:8001`, then test on-device and debug through
`chrome://inspect`. The installed app can be pointed at any backend at runtime
(`localStorage` key `ns_backend_url`) without rebuilding.

## Where it is headed

`docs/PRODUCT_PLAN_UMANG.md` sets out the path to integrating with UMANG and
API Setu as an "Application Readiness" service — what Government of India
onboarding actually requires, and the work packages to get there — written to be
executed by other engineers.

## Licence

See the repository for licensing. Government form templates and scheme
information are reproduced from official public sources and belong to their
respective departments.
