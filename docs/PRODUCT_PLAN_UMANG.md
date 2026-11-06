# Nagarik Sahayak → a UMANG-grade "Application Readiness" service

*Product plan, bug-hunt report, and agent-ready work packages. Written 2026-11-06 on branch `claude/audit-codebase-87oUa`.*

This document is written to be executed by other engineers and coding agents. Part 1 is what we know (verified state, bugs found and fixed, bugs still open). Part 2 is what Government of India integration actually requires (from NeGD's own onboarding guideline, not guesswork). Part 3 is the feature roadmap and positioning. Part 4 is the work breakdown: every package has scope, files, acceptance criteria and a brief you can paste into a fresh Claude Code session. Part 5 is sequencing and how to dispatch.

---

## 0. Executive summary

**What the product is today.** A citizen gives their details once, in any of 22 scheduled languages; the engine finds the Central and State schemes they qualify for (57 curated schemes, 30+ States/UTs), screens the application for fraud and errors, tells them which documents to carry, collects every field the chosen form needs (one validated question at a time), and **fills the real published government PDF** — the department's own form, not a look-alike. Aadhaar is never stored or printed in full. DPDP Act 2023 obligations (consent, notice, ownership of generated documents, encryption at rest, data-principal requests) are implemented in code, with tests.

**Where it stands.** Backend suite: **2232 tests passing**. This session's adversarial pass found **34 defects** (20 of them 500s on malformed input, 9 validation gaps that would have misprinted a form, 5 input-shape holes) — all fixed and regression-tested. The remaining open items are design-level (no session authentication, a mock OTP) and are the first work packages below.

**The positioning that fits UMANG.** UMANG does not host third-party frontends: it integrates *department backends over APIs* and builds the citizen UI itself to its own design guidelines, and it stores no citizen data ([UMANG Department Onboarding](https://web.umang.gov.in/landing/partner-departments)). UMANG already offers scheme *discovery* through myScheme and its "askUMANG" assistant. So the pitch is not "another scheme finder". It is **Application Readiness as a Service**: a consent-driven backend API that, given a citizen's profile, returns (a) what they qualify for, (b) what is missing, (c) what to carry, and (d) the department's form, filled — the step that today ends at a CSC counter or a paid agent. That is the capability UMANG, myScheme, State portals and CSCs lack, and it is exactly the shape NeGD empanels under API Setu's "API as a service" guideline ([NeGD, May 2025](https://negd.gov.in/wp-content/uploads/2025/06/Guidelines-for-Onboarding-for-API-as-a-service-provider-v15-Rev-1-1.pdf)).

**Two tracks, run in parallel.**
- **Track A — a State department pilot.** A State social-welfare or education department adopts the service for 3–5 of its schemes; it then onboards onto UMANG through the *department* path (Apply → Share API → Integrate → Audit → Go Live), with the department as the service owner. This is the fastest route to a UMANG listing and the only one open to a company younger than three fiscal years.
- **Track B — API Setu empanelment.** Meet NeGD's provider criteria (§2.1 below) and publish the API on API Setu, where UMANG, myScheme and any department can subscribe. Udyam (MSME) registration waives the ₹10 crore turnover bar; the three-year incorporation and certification bars do not go away and must be planned for or met through a partner.

---

## 1. Verified state and bug-hunt report

### 1.1 What exists and is tested

| Layer | Capability | Evidence |
|---|---|---|
| Catalog | 57 schemes (Central + State), gated on domicile, with bilingual fields, options, eligibility rules | `backend/data/gov_forms.py`, `tests/test_gov_forms.py`, `test_catalog_levels.py` |
| Extraction | Fields from any government PDF, native text or OCR; wrong-document rejection | `form_extractor.py`, `field_rules.py`, `scripts/form_sweep.py` |
| Intake | Discover a form's fields, ask one at a time, validate/normalise, store, Aadhaar transient | `services/form_intake.py`, `routes/v2.py` (`/v2/smart-profiler`, `/v2/answer-field`) |
| Fill | Overlay onto the real PDF: grid recovery from scans, comb boxes, composite fields, verification pass, hand-write list | `pdf_filler.py`, `form_geometry.py`, `tests/test_form_stress.py` (41 cases) |
| Decide | Rule-based eligibility, absence ≠ invalidity, fraud/abuse signals, combined gate with audit record | `eligibility_engine.py`, `fraud_detection.py`, `services/application_guard.py` |
| Identity | Offline Aadhaar QR/XML, tolerant matching, 14 catalogued KYC methods, never a refusal on identity grounds | `kyc/` |
| DPDP | Consent, notice (en/hi only), processing register, retention, ownership gate on documents, encryption at rest, Aadhaar non-storage | `dpdp/`, `tests/test_dpdp.py`, `test_statutory_compliance.py` |
| Language | 22 Eighth-Schedule languages with honesty flags; RTL; State-aware suggestion | `i18n/` |
| Documents | "What to carry" checklist derived from the form, with lawful Aadhaar alternatives | `services/document_checklist.py` |

### 1.2 Fixed this session (all regression-tested)

| # | Finding | Fix |
|---|---|---|
| 1 | Any non-ObjectId `user_id` → **500** on 6 endpoints (`/v2/smart-profiler`, `/v2/answer-field`, `/v2/generate-filled-forms`, `/chat`, `/profile/{id}`, PUT `/profile/{id}`) | `database.find_user()` validates shape; all 23 lookups route through it |
| 2 | `scheme_names` as a string iterated as characters (200 with garbage); `[None, 5]` → 500 | `_require_scheme_names()` → 400 |
| 3 | `fields` not a dict → 500 | → 400 |
| 4 | Empty `user_id` on `/chat` filed a conversation under nobody | → 400 |
| 5 | Mobile with `+91`/trunk `0` stored as 12/11 digits | normalised to 10 |
| 6 | Devanagari/Indic digits in PIN, mobile, account accepted verbatim (unreadable to a bank) | transliterated to ASCII |
| 7 | Percentage unbounded; negative numbers accepted | 0–100; no negatives |
| 8 | Email unchecked | regex + lower-case |
| 9 | `maxLength` bypassed by keyed validators (5000-char name stored) | length cap first |
| 10 | `<script>`/control chars accepted into stored profile | refused |
| 11 | Field required in form B, optional in form A → treated optional, citizen refused later by B | stricter form wins; options back-filled |
| 12 | Transient-only form reported 0% complete | 100% |
| 13 | Aadhaar pre-stripped before storage erased the last-4 identity marker → gate refused Aadhaar-only schemes (PM-KISAN) | store through `profile_store`, which keeps the marker |
| 14 | Gate evaluated the stored profile without the fill-time Aadhaar → "no identity document" | gate sees `fill_profile` |
| 15 | Full Aadhaar echoed back in `answer-field` | masked `XXXX XXXX 1234` |

Tests: `tests/test_route_hardening.py` (33 live), `tests/test_form_intake.py` (24), 1 mocked test re-seamed.

### 1.3 Open findings (design-level; become work packages)

| Sev | Finding | Package |
|---|---|---|
| **P0** | **No session authentication.** `/chat`, `/chat/history/{id}`, `/profile/{id}`, `/v2/*` trust a client-supplied `user_id`; only PDF/audio downloads check ownership (via an unauthenticated `X-User-Id` header). Anyone who knows or guesses an id reads another citizen's chat and profile. | WP-01 |
| **P0** | **Mock OTP.** `verify-otp` accepts `123456` for any phone; there is no SMS gateway. Demo-grade only. | WP-01 |
| P1 | `verify-otp` answers a wrong OTP with `200 {success:false}`; API Setu requires proper HTTP codes. | WP-01 |
| P1 | No request-body size limit (1 MB answers accepted and parsed); no per-user quota beyond the OTP limiter. | WP-02 |
| P1 | Form fill is synchronous: a 14-page scanned form takes ~3.5 min in-request (OCR). Needs a job queue + status endpoint; cache extraction per source file. | WP-04 |
| P1 | Chat accepts "ghost" users (valid-shaped id with no record) because demo mode relies on placeholder ids. Acceptable only while demo mode exists; must go with WP-01. | WP-01 |
| P2 | Demo mode is a process-global toggle (`/api/demo/toggle`). Must not exist in a production build. | WP-01 |
| P2 | `_ensure_local_source` writes the downloaded form in one `write_bytes`; a crash mid-write could leave a truncated file >1 KB that is then reused. Write to temp + atomic rename; verify `%%EOF`. | WP-04 |
| P2 | Integration tests need a live Mongo+server; there is no CI. | WP-03 |
| P2 | LLM calls (Claude via `emergentintegrations`) and analytics (`agnost`) send redacted text off-host. For a GoI deployment, PII must not leave the data centre; the rule engine already works without an LLM key. | WP-07 |
| P3 | Scheme catalog is hand-curated (57). myScheme lists ~3,000+. | WP-08 |

---

## 2. What GoI integration actually requires

### 2.1 API Setu "API as a service" empanelment — provider eligibility (NeGD, §VII and Annexure I)

| Requirement | Threshold | Our status |
|---|---|---|
| Entity | Indian company / LLP / partnership, **≥3 completed fiscal years**, PAN + GST registered | Depends on the operating company — plan for it |
| Turnover | Avg **₹10 crore** over last 3 FY — **MSME (Udyam) registered firms exempt** | Register as MSME |
| Profitability | PBT-positive for 3 FY (CA-certified) | Depends on company |
| Certifications | **Any 3 of**: ISO 9001:2015, ISO/IEC 27001:2022, ISO/IEC 20000-1:2018, ISO 22301:2019, SOC 2 Type II | Not held — budget 6–9 months; ISO 27001 + 9001 + 20000-1 is the usual trio |
| Procurement order | Comply with OM F.7/10/2021-PPD (Public Procurement Order 4 — land-border-country restrictions, incl. OEM) | Attestation |
| Experience | 3 years delivering/operating RESTful APIs and API-management platforms, with work orders | Depends on company |
| Blacklisting / litigation / conflict of interest | Undertakings | Attestation |
| IPR | Code and docs developed under empanelment vest with NeGD; NDA + integrity pact | Legal decision before applying |
| Process | Registration → API documentation → compliance/security/privacy review → sandbox testing → SLA/DPA contract → publication; rolling submissions to partners.apisetu@digitalindia.gov.in | — |

### 2.2 API onboarding criterion (Annexure VI) and KPI scoring (Annexure VII)

Minimum 85/100 on a rolling 90-day score; 80–85 probation, <80 delisting. Each row below is a package item.

| Area (weight) | Requirement | Our status → package |
|---|---|---|
| Auth (10) | OAuth2/JWT, RBAC, **consent-based access**, token ≤60 min + refresh, MFA for admin, consent-artefact management | None → **WP-01** |
| Encryption (5) | TLS 1.3 in transit, AES-256 at rest, PII masked (PAN, Aadhaar) | At rest ✔ (Fernet/AES-128-CBC+HMAC → move to AES-256-GCM), masking ✔, TLS = deployment → **WP-06** |
| Security testing (5) | VAPT monthly, no high/critical; OWASP API Top 10 clean | Not done → **WP-06** |
| Breach (5) | Documented IRP; notify CERT-In/affected parties within **6 hours** | `dpdp/incident.py` exists; IRP doc + CERT-In runbook → **WP-06** |
| Compliance (5) | DPDP 2023 + IT Act evidence, localisation | Largely ✔; evidence pack → **WP-06** |
| Uptime (10) | 99.9%/30d, 48 h notice for maintenance, no unplanned outage >1 h, `GET /Heartbeat` 200 | Heartbeat trivial; DC+DR, HA → **WP-05** |
| Latency (5) | P95 <200 ms, P99 <500 ms | Eligibility/intake ✔ (ms); fill is seconds–minutes → async job (**WP-04**) |
| Error rate (5) | 4xx+5xx <1% of requests; spike <5% | 500s eliminated; need metrics → **WP-05** |
| Load (5) | 2000 RPS steady / 5000 burst; load-tested at 150% | Not tested → **WP-05** |
| Rate limiting | per user and IP, quotas, graceful 429 | OTP only → **WP-02** |
| Functional (10) | 100% documented endpoints working; correct HTTP codes; graceful 400s | Mostly ✔ after hardening |
| Compatibility (5) | No breaking changes; 90-day deprecation; 2 live versions; semver in URL | `/api/v2` exists; formalise → **WP-02** |
| Input validation (5) | SQLi/XSS/tampering; descriptive errors without internals | ✔ after hardening; keep in CI (**WP-03**) |
| Code quality | Peer review; static analysis; OWASP secure coding | Add ruff/bandit/semgrep in CI → **WP-03** |
| Audit (5+5) | 180-day log retention; **tamper-proof** logs | Not present → **WP-05** |
| Docs (5) | OpenAPI 3.0 **YAML**, samples, changelog, semver | FastAPI emits JSON; curate YAML → **WP-02** |
| Support (5) | 24 h support SLA; **sandbox**; SDKs (Python, Java, Node) | → **WP-09** |
| Pricing (5) | Free tier, billing basis, INR pricing, real-time usage tracking | → **WP-09** |
| Scope of work | DC + DR; separate Dev/UAT/Sandbox; KPI feed to NeGD dashboards; 4-hour issue resolution | → **WP-05**, **WP-09** |

Business purposes NeGD lists that we map to (Annexure VIII): *Ration Card and NFSA integration for subsidy management*; *SWAYAM and NSP scholarship APIs*; *DigiLocker for education certificate verification*; *eSign APIs*; *e-RUPI voucher disbursement*; *PFMS integration*.

### 2.3 UMANG department path

Apply online → share API → integrate with UMANG → testing/audit → go live. UMANG builds the citizen UI per the **UMANG Design Guidelines** (UX4G design system; GIGW 3.0 accessibility) and keeps no data. Our own web app remains the reference client and the CSC/assisted-mode client; the API is the product.

### 2.4 India Stack surfaces (verified status)

| Surface | What it gives us | Access path | Confidence |
|---|---|---|---|
| **DigiLocker (requester)** | Pull Aadhaar (masked), PAN, DL, marksheets, caste/income certificates with consent → zero-typing intake | Register on API Setu → API key → host APIs → integrate → audit → live; official-domain email, India-hosted server, explicit consent per document; **no sandbox** ([DigiLocker onboarding FAQ](https://www.digilocker.gov.in/assets/FAQ%20DL%20EL_onboarding.pdf), [Requester terms, June 2025](https://cf-media.api-setu.in/resources/DigiLocker-Terms-of-User-Requester-june-2025.pdf)) | High |
| **myScheme (API Setu Service API)** | Live scheme catalog, non-user-specific | Subscribe on the API Setu marketplace; publisher approval required ([API Setu docs](https://docs.apisetu.gov.in/document-central/explore-apisetu/Overview.html)) | Medium — eligibility API not publicly documented |
| **Bhashini** | GoI-endorsed translation (NMT), ASR, TTS for 22 languages, replacing our low-confidence machine translations | Register, get user-id + ULCA key, pipeline id; inference at the Dhruva API ([ULCA on GitHub](https://github.com/bhashini-dibd/ulca)) | Medium — endpoints from community sources; confirm on the Bhashini portal |
| **eSign** | Aadhaar-based signature on the filled form | Licensed ESP (ASP agreement) | Known |
| **UIDAI eKYC / Auth** | Online Aadhaar verification | AUA/KUA licence or sub-AUA under a licensed partner | Known; keep offline QR/XML as default |

---

## 3. Feature roadmap

Prioritised by (citizen value × GoI fit × feasibility). P0 = required to be allowed in the room; P1 = the pitch; P2 = citizen delight; P3 = department value.

**P0 — Trustworthy to run**
1. Real authentication: OTP via a licensed SMS gateway (DLT-registered), short-lived JWT + refresh, RBAC (citizen / VLE operator / department reviewer / admin), MFA for admin. Every endpoint authorises on the token, never on a body field.
2. API gateway hygiene: per-user and per-IP rate limits, quotas, body-size limits, graceful 429, semver, deprecation policy, OpenAPI 3.0 YAML, `/Heartbeat`.
3. CI with the full suite against an ephemeral Mongo; static analysis (ruff, bandit, semgrep); dependency audit.
4. Async document generation with job status; extraction cache per source file; atomic cache writes.
5. Observability + tamper-evident audit: structured logs, 180-day retention, hash-chained audit trail, metrics (uptime, P95/P99, error rate), KPI export in NeGD's shape.
6. Security pack: AES-256-GCM at rest, TLS 1.3 at the edge, VAPT and OWASP API Top 10 remediation, IRP with the 6-hour CERT-In runbook, DPDP evidence pack.

**P1 — The pitch**
7. **Sovereign mode**: a build flag under which no request leaves the data centre — rule engine only, Bhashini for language, no third-party analytics. (The product already works without an LLM key; make it a guarantee.)
8. **DigiLocker-first intake**: "Fetch from DigiLocker" replaces typing for every field a pulled document can answer; the intake loop asks only for what remains. The strongest single demo for UMANG.
9. **Live catalog from myScheme**: nightly sync of scheme metadata; our curated layer adds the form, the field model and the rules on top.
10. **Bhashini translation**: replace low-confidence machine translations with Bhashini NMT; voice intake (ASR) and read-back (TTS) in the citizen's language. Keep the legal notice en/hi human-reviewed, as now.
11. **Application Readiness API v1** (the UMANG-facing contract): `POST /readiness` — profile + consent in; eligibility, gaps, documents, risk, filled-form job out. OpenAPI YAML, sandbox, SDKs.
12. **Assisted (VLE/CSC) mode**: an operator serves many citizens with per-citizen consent capture, operator attribution in the audit trail, and a printable receipt.

**P2 — Citizen delight**
13. Proactive entitlement alerts ("you turned 60 → old-age pension"; "Class 10 result published → NSP scholarship window"), SMS/WhatsApp (MyGov channel) — opt-in.
14. Application status tracking where a department exposes it; otherwise a "what happens next" timeline.
15. Document-gap routing: for each missing certificate, where to get it (nearest tehsil/CSC via open data) and what it costs.
16. Offline-first PWA; IVR/USSD fallback for feature phones.

**P3 — Department value**
17. Department console: uptake by district/scheme, drop-off points, top rejection reasons, duplicate-claim signals — the analytics a Secretary wants and myScheme does not give.
18. Grievance → CPGRAMS hand-off with the application reference attached.
19. Leakage detection across schemes (the fraud engine already models shared accounts/Aadhaar; expose it as a department report, never as a citizen-facing refusal).

---

## 4. Work packages

Conventions for every package:
- Branch `wp-NN/<slug>` from `claude/audit-codebase-87oUa` (or `main` once merged). One PR per package.
- `cd backend && python -m pytest tests/ -q` must stay green; new behaviour gets tests. Live-server tests read `REACT_APP_BACKEND_URL`.
- Invariants that must survive any change: full Aadhaar is never persisted, logged or echoed (`dpdp/aadhaar_policy.py`); legal/consent text is served only in human-reviewed English and Hindi; generated documents are ownership-gated and encrypted at rest; absence of data is never reported as a refusal.
- Read `backend/CLAUDE.md`-style context: `backend/services/form_intake.py`, `backend/routes/v2.py`, `backend/dpdp/profile_store.py`, `backend/services/application_guard.py` are the spine.

### WP-01 · Authentication, sessions and RBAC (P0)
**Goal.** Replace trust-the-body `user_id` with bearer tokens; real OTP delivery; roles.
**Scope.** FastAPI dependency `current_user()` (JWT, ≤60 min, refresh tokens, revocation list in Mongo); roles `citizen|operator|reviewer|admin`; MFA (TOTP) for admin; SMS gateway adapter (interface + DLT-compliant provider + mock for tests); `verify-otp` returns 401 on a wrong code; delete the demo-mode toggle from production builds; every route that takes `user_id` derives it from the token (operators may act for a citizen only with a recorded consent); remove the `X-User-Id` header path from downloads in favour of the token.
**Files.** `backend/routes/auth.py`, `routes/*.py`, `config.py`, new `backend/auth/` (jwt.py, deps.py, sms.py), `frontend/src/lib/api.js` (Authorization header), tests.
**Acceptance.** Unauthenticated calls to every non-public route → 401; cross-citizen access → 403; token expiry honoured; all existing tests updated and green; demo flows run only under `DEMO_MODE=1` builds and are excluded from the production image.
**Depends on.** —. **Effort.** L. **Risk.** Breaks every integration test's auth assumptions — budget for it.

> **Agent brief.** You are adding real authentication to a FastAPI + Prisma (MongoDB) backend in `backend/`. Today routes accept `user_id` in the request body and trust it; PDF downloads check an unauthenticated `X-User-Id` header against `dpdp/ownership.py`. Build `backend/auth/` with JWT access tokens (≤60 min) + refresh tokens + server-side revocation, a `current_user` dependency, and roles (citizen/operator/reviewer/admin; TOTP MFA for admin). Replace body/header identity everywhere with the dependency; operators acting for a citizen must present a consent record. Add an SMS adapter interface with a mock used by tests and one real DLT-compliant provider behind env config; `verify-otp` must return 401 on a wrong code. Remove the global demo toggle from production (keep it behind `DEMO_MODE` for the demo build only). Update `frontend/src/lib/api.js` to send the bearer token. Never persist, log or echo a full Aadhaar; legal text stays en/hi only. All of `backend/tests` must pass (`python -m pytest tests/ -q`; live tests read `REACT_APP_BACKEND_URL`) — update the tests that assumed body-trusted ids. Write tests for 401/403 on every route.

### WP-02 · API contract: versioning, limits, OpenAPI YAML (P0)
**Scope.** Middleware for body-size limit (256 KB default; multipart upload limit separate), per-user/IP rate limiting with quotas and 429 + `Retry-After`; `/api/v2/heartbeat` (200, cheap); semver header and URL policy, 90-day deprecation notice mechanism, two live versions; curated `openapi.yaml` (3.0) generated from the app + reviewed descriptions/examples; changelog file.
**Files.** `backend/server.py` (middleware), new `backend/api/` (limits.py, versioning.py), `docs/openapi.yaml`, `CHANGELOG.md`.
**Acceptance.** 1 MB body → 413; 100 req/min/user → 429 with header; YAML validates with an OpenAPI linter; every documented endpoint has a request/response example and a test that exercises it.
**Depends on.** WP-01 for user-keyed limits (IP-keyed first). **Effort.** M.

> **Agent brief.** In `backend/`, add API-gateway hygiene required by NeGD's API Setu criteria: request-body size limit (413), per-user and per-IP rate limiting with configurable quotas and a graceful 429 with `Retry-After`, a `/api/v2/heartbeat` endpoint, URL semver with a documented 90-day deprecation policy and support for two concurrent versions, and a curated OpenAPI 3.0 **YAML** at `docs/openapi.yaml` with request/response samples for every endpoint plus `CHANGELOG.md`. Keep all tests green and add tests for each limit and for YAML validity.

### WP-03 · CI and static analysis (P0)
**Scope.** GitHub Actions: Mongo service container as a single-node replica set (`rs.initiate`), `prisma db push`, start server, run full suite with `REACT_APP_BACKEND_URL`; ruff, bandit, semgrep (OWASP rules), `pip-audit`, `npm audit`; frontend build + lint; coverage report; branch protection.
**Files.** `.github/workflows/ci.yml`, `backend/pyproject.toml` (tool config), `backend/requirements*.txt` pinning.
**Acceptance.** A PR that introduces a 500-on-bad-input fails CI; the suite runs in <10 min.
**Effort.** M.

> **Agent brief.** Create `.github/workflows/ci.yml` for this repo. Backend: Python 3.11, start MongoDB 7 as a one-node replica set (the app needs transactions), `python -m prisma generate && python -m prisma db push --skip-generate`, launch `uvicorn server:app` with env from `backend/.env.example` (create it, mirroring `backend/.env` keys with placeholder values; `RATE_LIMIT_MAX=100000` for tests), then `python -m pytest tests/ -q` with `REACT_APP_BACKEND_URL` set. Add ruff, bandit, semgrep (p/owasp-top-ten), pip-audit. Frontend: `npm ci && npm run build && npm run lint`. The recipe that works locally is in this document's §5.2; the stress tests need tesseract and pymupdf (apt: tesseract-ocr, tesseract-ocr-hin). Keep total time under 10 minutes; cache pip/npm.

### WP-04 · Async document generation and extraction cache (P0/P1)
**Scope.** Job queue (Mongo-backed collection + worker process; or RQ/Redis if available) for `generate-filled-forms`; `POST` returns `202 {job_id}`; `GET /v2/jobs/{id}` → queued/running/done/failed with per-scheme results; frontend polls and shows progress bullets. Cache OCR/extraction per source PDF (keyed by sha256 of bytes) across fills; atomic write (temp + rename) and `%%EOF` check in `_ensure_local_source`; eviction policy.
**Files.** `backend/routes/v2.py`, new `backend/jobs/`, `pdf_filler.py` (`_OCR_FILE_CACHE` → persistent), `frontend/src/components/SmartProfiler.js`.
**Acceptance.** Saraswati (14-page scan) fill: first run completes in the background; second run <5 s; API P95 for the POST <200 ms; a crash mid-download never leaves a reusable truncated file (test by injecting a failure).
**Effort.** M.

> **Agent brief.** `POST /api/v2/generate-filled-forms` in `backend/routes/v2.py` fills the real government PDF synchronously; a scanned 14-page form takes minutes (OCR in `backend/pdf_filler.py`). Make it asynchronous: return `202 {job_id}` and add `GET /api/v2/jobs/{job_id}` with states queued/running/done/failed and the same per-scheme result shape the sync call returns today (pdf_url, fill_method, filled_count, to_write_by_hand, refused, flagged_for_review). Use a Mongo-backed job collection and a worker started alongside the server (keep ownership recording and encryption exactly as now; see `dpdp/ownership.py`, `dpdp/file_vault.py`). Persist the OCR/extraction cache per source PDF (sha256 of bytes) so repeat fills are fast. In `_ensure_local_source`, download to a temp file, verify it starts with `%PDF` and ends with `%%EOF`, then atomically rename. Update `frontend/src/components/SmartProfiler.js` to poll. Keep the sync path available behind `?wait=true` for tests, and keep all tests green.

### WP-05 · Observability, audit trail, HA/DR posture (P0)
**Scope.** Structured JSON logs with request ids; 180-day retention policy; hash-chained (tamper-evident) audit collection for consent, access to a citizen's data, document issue/download, gate decisions (extend `application_guard.audit_record`); Prometheus metrics (latency histograms, error rate, uptime), Grafana dashboard JSON; KPI export job in the Annexure VII shape; runbooks for DC/DR (Mongo replica set across zones, backups + restore drill), scheduled-maintenance notice procedure (48 h).
**Files.** `backend/observability/`, `backend/dpdp/audit.py`, `server.py`, `docs/runbooks/`.
**Acceptance.** Audit chain verifies end-to-end; a modified record is detected; dashboards show P95/P99 and error rate; restore drill documented with timings.
**Effort.** M–L.

### WP-06 · Security pack and compliance evidence (P0)
**Scope.** Move at-rest crypto from Fernet to AES-256-GCM with key rotation (`dpdp/crypto.py`, migration for existing blobs); TLS 1.3 at the edge (deployment config); run VAPT + OWASP API Top 10 checklist and fix findings; Incident Response Plan with the 6-hour CERT-In notification runbook wired to `dpdp/incident.py`; DPDP evidence pack (processing register export, consent artefacts, retention schedule, data-principal request SLAs); secrets management (no secrets in env files in images).
**Acceptance.** VAPT report with zero high/critical; crypto migration round-trips every stored profile; evidence pack reviewed by counsel.
**Effort.** L (external VAPT).

### WP-07 · Sovereign mode (P1)
**Scope.** `SOVEREIGN_MODE=1` build flag: disables every outbound call except allow-listed GoI hosts (Bhashini, DigiLocker, API Setu, SMS gateway); the chat answers from the rule engine and catalog only; analytics off; a startup self-check that fails the process if any other egress is configured; a test that asserts no outbound hosts beyond the allow-list.
**Files.** `backend/config.py`, `services/chat.py`, `routes/chat.py`, `server.py`, tests.
**Effort.** S–M.

> **Agent brief.** Add a `SOVEREIGN_MODE` flag to `backend/config.py`. When set: no LLM calls (the rule-based paths in `services/chat.py`, `eligibility_engine.py`, `services/profiler.py` already work without an LLM key — make that the only path), no `agnost` analytics, and an explicit outbound allow-list (Bhashini, DigiLocker, API Setu, the configured SMS gateway). Add a startup self-check that aborts if any other egress is configured, and a test (monkeypatch `requests`/`httpx`) proving no call leaves the allow-list during a full intake → fill flow. Document it in README.

### WP-08 · myScheme catalog sync (P1)
**Scope.** Adapter for the myScheme Service API on API Setu (subscribe; store credentials via secrets); nightly sync of scheme metadata into a `scheme_source` layer; our curated layer (`data/gov_forms.py`) becomes an overlay that adds form, fields, rules; diff report; UI shows provenance. Until API access is approved: a fixture-driven adapter with the same interface.
**Acceptance.** Sync is idempotent; curated overlay survives a sync; a scheme removed upstream is flagged, not deleted.
**Effort.** M. **Blocked on** API Setu subscription approval (start the request now).

### WP-09 · Application Readiness API v1, sandbox, SDKs, pricing (P1)
**Scope.** A single UMANG-facing contract: `POST /api/v2/readiness` {profile, consent_artefact, scheme_names?} → {eligible[], incomplete[], documents[], risk, job_id}; consent-artefact validation; sandbox environment (seeded demo data, synthetic Aadhaar with valid checksums); SDKs (Python, Node, Java) generated from the OpenAPI YAML and published; usage metering per API key; pricing page (free tier, per-call, INR) and usage dashboard; 24-hour support channel.
**Depends on.** WP-01, WP-02, WP-04. **Effort.** M–L.

### WP-10 · DigiLocker-first intake (P1)
**Scope.** Requester integration (OAuth, consent per document, India-hosted callback); map issued documents to profile keys (Aadhaar → masked + last-4 + DOB/gender/address; PAN; DL; marksheets → `last_exam_percentage`, `roll_number`, `institution_name`; income/caste certificates); the intake loop (`form_intake.intake_state`) treats fetched values as `known` with a `source: digilocker` provenance; UI "Fetch from DigiLocker" step before any typing; store only what the form needs, with the consent artefact id.
**Depends on.** DigiLocker requester approval (no sandbox — plan a staged rollout). **Effort.** L.

> **Agent brief.** Integrate DigiLocker as a *requester* in `backend/` so a citizen can fetch issued documents instead of typing. Implement the OAuth flow and per-document consent, map pulled documents to the canonical profile keys used in `backend/data/gov_forms.py` (see `services/form_intake.py` for how known/missing is computed) and store values through `dpdp/profile_store.py` with a provenance field `{source:"digilocker", doc_type, fetched_at, consent_id}`. The full Aadhaar number must never be persisted — only the masked form and last four, exactly as `dpdp/aadhaar_policy.py` enforces. Add a frontend step "Fetch from DigiLocker" ahead of the question loop in `frontend/src/components/SmartProfiler.js`. Use a mock DigiLocker server for tests (there is no official sandbox). Keep all tests green.

### WP-11 · Bhashini language services (P1)
**Scope.** Bhashini NMT adapter behind `i18n/resolve.py` to replace entries marked low-confidence (keep human-reviewed en/hi legal text untouched); ASR for voice intake (`routes/chat.py` transcribe path) and TTS read-back; caching; graceful fallback to current bundles when Bhashini is unavailable; quality flag now says "Bhashini-translated".
**Effort.** M. **Blocked on** Bhashini credentials.

### WP-12 · Assisted (VLE/CSC) operator mode (P1)
**Scope.** Operator role (WP-01); per-citizen session with consent capture (DPDP s6) recorded to the audit chain with operator id; multi-citizen queue UI; printable receipt with application reference and the hand-write list; operator analytics.
**Depends on.** WP-01, WP-05. **Effort.** M.

### WP-13 · Frontend compliance: UX4G/GIGW 3.0, offline PWA (P1/P2)
**Scope.** Adopt UX4G components/tokens for the reference client; WCAG 2.1 AA audit (axe), keyboard and screen-reader paths in Hindi; PWA with offline catalog/document checklist; low-bandwidth mode; the UMANG-side UI is theirs, but the reference client must demonstrate the guideline.
**Effort.** M.

### WP-14 · Proactive entitlements and status (P2)
**Scope.** Rules that fire on profile changes/dates (age thresholds, academic year, scheme windows) → opt-in notifications (SMS/WhatsApp via approved channels); application timeline; department status adapters where available.
**Effort.** M.

### WP-15 · Department console and leakage report (P3)
**Scope.** Aggregated, k-anonymised analytics by district/scheme (uptake, drop-off by question, rejection reasons, duplicate-claim signals from `fraud_detection`); reviewer queue already exists (`services/review_queue.py`) — add the dashboard; CPGRAMS hand-off stub.
**Effort.** M.

### WP-16 · Document-gap routing and IVR/USSD (P2)
**Scope.** For each missing document in `services/document_checklist.py`, the issuing office type and nearest location from open data; a USSD/IVR flow for the four basic profiler questions on feature phones via a telecom partner.
**Effort.** M–L.

---

## 5. Sequencing and dispatch

### 5.1 Milestones
- **M0 — Trustworthy (4–6 weeks):** WP-01, WP-02, WP-03, WP-04, WP-05 core, WP-07. Exit: real auth, CI green, async fill, no PII egress.
- **M1 — Pilot-ready (6–8 weeks):** WP-06, WP-09 (readiness API + sandbox), WP-12, WP-13. Exit: a State department can run a 3-scheme pilot; VAPT clean. Start Track A conversations with this.
- **M2 — API Setu-ready (8–12 weeks, partly parallel):** WP-08, WP-10, WP-11, remaining WP-05 (DR drill, KPI feed). Exit: Annexure VI checklist complete; file the Request for Onboarding; certifications in progress.
- **M3 — Scale (ongoing):** WP-14, WP-15, WP-16.

Parallelism: WP-01/02/03 first (everything depends on auth and CI). WP-04, WP-05, WP-07 can run concurrently with them on separate branches. WP-08/10/11 are blocked on external approvals — **file the API Setu, DigiLocker and Bhashini requests this week**, they are the long pole.

### 5.2 Running the stack locally (what worked in this session)
```bash
# Mongo must be a replica set (Prisma uses transactions)
mongod --dbpath /tmp/mongo-rs/db --port 27018 --replSet rs0 --bind_ip 127.0.0.1 &
mongosh --port 27018 --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"127.0.0.1:27018"}]})'
cd backend && set -a && source .env && set +a
export MONGO_URL="mongodb://127.0.0.1:27018/nagarik_sahayak?replicaSet=rs0" RATE_LIMIT_MAX=100000
python -m prisma db push --skip-generate
python -m uvicorn server:app --host 127.0.0.1 --port 8006 &
REACT_APP_BACKEND_URL=http://127.0.0.1:8006 ADMIN_SECRET=<from .env> python -m pytest tests/ -q   # 2232 passed
python scripts/smoke_test.py          # 109 checks incl. a live government form
```

### 5.3 Dispatching to agents
Each package's **Agent brief** is self-contained. Start one Claude Code session per package on its own branch; paste the brief; require the suite to stay green and a PR with the package id in the title. Suggested order for a first wave of three parallel sessions: **WP-01**, **WP-03**, **WP-04** (independent files, no merge conflicts), then **WP-02 + WP-05 + WP-07**.

---

## Sources
- UMANG Department Onboarding — https://web.umang.gov.in/landing/partner-departments
- NeGD, *Guidelines for Onboarding for API as a service provider* (v15 Rev 1, May 2025) — https://negd.gov.in/wp-content/uploads/2025/06/Guidelines-for-Onboarding-for-API-as-a-service-provider-v15-Rev-1-1.pdf
- API Setu documentation overview — https://docs.apisetu.gov.in/document-central/explore-apisetu/Overview.html
- myScheme (about) — https://www.myscheme.gov.in/hi/about
- DigiLocker partner onboarding FAQ — https://www.digilocker.gov.in/assets/FAQ%20DL%20EL_onboarding.pdf
- DigiLocker Terms of Use (Requester), June 2025 — https://cf-media.api-setu.in/resources/DigiLocker-Terms-of-User-Requester-june-2025.pdf
- ULCA (Bhashini) on GitHub — https://github.com/bhashini-dibd/ulca
- PIB on UMANG integration — https://www.pib.gov.in/PressReleasePage.aspx?PRID=1627711
