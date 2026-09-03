# Deploying Nagarik Sahayak

Every step below is here because skipping it breaks something quietly rather
than loudly. Where an item is a legal obligation the provision is named, so it
can be checked against the statute rather than taken on trust.

---

## 1. System packages

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-hin
```

Most real government forms are scanned images, not text PDFs. Without the OCR
engine and the Hindi language pack the extractor falls back to the curated
field definitions and silently stops learning anything from a live form.

---

## 2. Secrets

Generate the data key **before** the first migration and put it in a secret
manager:

```bash
cd backend
python scripts/encrypt_at_rest.py --generate-key   # → DATA_ENCRYPTION_KEY
```

This one key protects both the database columns and every generated document.
**Lose it and both are unrecoverable.** That is deliberate: a recovery path
would be a second way in. There is no support process that can retrieve it.

Then set, at minimum:

| Variable | Why |
|---|---|
| `DATA_ENCRYPTION_KEY` | Personal-data columns and document files at rest |
| `IDENTITY_HASH_SALT` | One-way fingerprints for duplicate detection |
| `ADMIN_SECRET` | Gates the reviewer console and admin routes |
| `GRIEVANCE_OFFICER_NAME` / `_EMAIL` / `_PHONE` / `_ADDRESS` | IT Rules 3(2), DPDP s8(7) |

The Grievance Officer must be a real person who will answer. The Rules require
acknowledgement within 24 hours and resolution within 15 days. Publishing a
contact nobody monitors is worse than publishing nothing, because a citizen
who writes to it believes their complaint is being dealt with.

See `backend/.env.example` for the full list including optional KYC providers.

---

## 3. Database

```bash
cd backend
prisma generate
python scripts/encrypt_at_rest.py          # encrypt existing personal columns
python scripts/encrypt_files_at_rest.py    # encrypt existing document files
python scripts/backfill_identity_index.py  # populate fingerprint columns
```

Run them in that order. `prisma generate` is required after any pull that
touches `schema.prisma` — the `Scheme` and `FormTemplate` models gained
`level` and `state` columns for the Central/State split, and a stale client
will reject writes to them.

The catalog seeds itself on startup, idempotently. To force a reseed after a
catalog change:

```bash
python scripts/seed_gov_forms.py seed --overwrite
```

---

## 4. Time and logs (CERT-In Directions 2022)

- Synchronise to `samay1.nic.in` or `samay2.nic.in`. The Directions require
  Indian NTP; a clock that drifts makes an incident timeline unusable as
  evidence.
- Retain logs for 180 days **within India**. This is an infrastructure
  decision the application cannot make for you — if logs ship to a region
  outside India, the obligation is unmet regardless of what the app does.
- A reportable incident must reach CERT-In within **6 hours**. The application
  records and times incidents (`dpdp/incident.py`) but has no transmission
  channel configured; wiring one is an operator task.

---

## 5. What is deliberately not switched on

These are marked `needs_licence` in `/api/kyc/methods` and cannot be enabled
by configuration:

- **Aadhaar OTP e-KYC** and **biometric authentication** — require appointment
  as a KUA/AUA by UIDAI.

Aadhaar **offline e-KYC** and **Secure QR** work with no licence and no
external account, and are the highest assurance the application reaches
unaided. Without `UIDAI_SIGNING_CERT` the signature is parsed but not checked,
and results are reported at `DOCUMENTED` rather than `VERIFIED` — the citizen
is told, and the case goes to a reviewer. That downgrade is the correct
behaviour, not a defect to work around.

---

## 6. Before going live in a State

- **Language.** All 22 Eighth Schedule languages have interface translations
  and none has been checked by a native speaker. `GET /api/i18n/coverage`
  reports two grades: `draft` (script and register well attested) and
  `low_confidence` (Bodo, Kashmiri, Manipuri, Santali — the orthography itself
  may be wrong, and those ship with a standing warning to the reader). Full
  coverage is not full confidence; commission a review for the languages of
  any State you launch in, starting with `summary.reviewPriority`.
- **Languages outside the Schedule.** Mizo, Khasi, Garo, Kokborok, Nagamese,
  Nyishi and others are not in the Eighth Schedule, so no s5(3) entitlement
  reaches them and this application does not offer them. Arunachal Pradesh,
  Meghalaya, Mizoram and Nagaland are therefore served in English, which is
  their declared official language. `GET /api/i18n/suggest?state=…` reports the
  unscheduled local languages so the gap stays visible.
- **Legal notices** are served in English and Hindi only, deliberately. A
  mistranslated consent notice is a defective consent under s6 and the person
  giving it does not know. Commission real translations; do not machine-fill
  them.
- **Accessibility.** `GET /api/dpdp/accessibility` states partial WCAG 2.1 AA
  conformance, which is what it is. Claiming full conformance without an
  assistive-technology audit misleads exactly the people the statement exists
  to serve (RPwD Act s40–46, GIGW 3.0).

---

## 7. Known gaps

Recorded here rather than left implicit, so they are decisions rather than
oversights.

| Gap | Blocked on |
|---|---|
| s9 verifiable parental consent | A KYC method that can establish a parent–child relationship |
| CERT-In incident transmission | A channel and credentials |
| ISO 27001 control set | An organisational decision |
| 180-day in-India log retention | Infrastructure |
| RTI / Consumer Protection applicability | Whether this is run by or for the State |
| Frontend test runner | No runner is installed; `frontend/` has no test suite |
| Native review of all 22 languages | Translator time; `low_confidence` first |
| Languages outside the Eighth Schedule | Mizo, Khasi, Kokborok and the rest carry no s5(3) entitlement |

The backend suite has 91 pre-existing failures in
`test_e2e_with_mocks`, `test_v2_api_endpoints`, `test_agnost_integration`,
`test_prisma_migration`, `test_comprehensive_e2e`, `test_new_features`,
`test_iteration_14_features`, `test_download_405_fix` and
`test_tool_progress_chat`. They drive a live server over HTTP and fail with
`MissingSchema` when `BACKEND_URL` is unset. They pass against a running
deployment; they are not unit tests and should not be read as a regression
signal.

---

## 8. Smoke test

```bash
cd backend
python scripts/smoke_test.py            # full run, needs network for stages 1-2
python scripts/smoke_test.py --offline  # everything else
```

Fourteen stages: live-form fetch, OCR extraction, validation, eligibility,
fraud screening, PDF generation, adversarial cases, the combined gate,
Central/State catalog coverage, demo applicants in four States, KYC, language
coverage, DPDP notice scope, and the wiring between all of them. Exit code is
non-zero if any check fails, so it doubles as a CI gate. It needs no database
and no LLM key.

Stage 14 exists because two bugs lived in the gaps between layers that every
unit test passed over: KYC evidence that never reached the decision function
the API calls, and a missing identity document classified as invalid data —
a refusal — rather than an unfinished form. Both are pinned there and in
`tests/test_gate_integration.py`.

All 88 smoke-test checks pass on the current tree (83 with `--offline`).
