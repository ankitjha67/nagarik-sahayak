# Nagarik Sahayak — Full Codebase Audit Report

**Date:** 2026-03-20
**Auditor:** Automated (Claude Opus 4.6)
**Scope:** End-to-end audit of backend, frontend, configuration, infrastructure, security, and code quality

---

## Executive Summary

Nagarik Sahayak is a government services platform (mobile-first chat application) built with a **FastAPI (Python) backend** and **React (CRA) frontend**, using **Prisma ORM with MongoDB**. The application integrates with external LLM, speech-to-text, and analytics services.

### Overall Risk Ratings

| Area | Risk Level | Summary |
|------|-----------|---------|
| **Authentication & Authorization** | CRITICAL | Hardcoded OTP bypass, no rate limiting on auth endpoints |
| **Input Validation** | HIGH | Path traversal, insufficient file upload validation, prompt injection |
| **API Security** | HIGH | CORS misconfiguration, missing auth headers on frontend, no API versioning |
| **Code Quality** | MEDIUM | Monolithic backend, bare exceptions, race conditions |
| **Database** | MEDIUM | Missing indexes, no cascade deletes, unvalidated JSON fields |
| **Frontend Security** | MEDIUM | XSS risks, hardcoded demo OTP in UI, missing error boundaries |
| **Documentation** | MEDIUM | Placeholder README, missing setup/API docs |
| **Test Coverage** | LOW | Good E2E coverage (28/28 pass), but gaps in unit and security testing |
| **Configuration/Secrets** | LOW | No hardcoded secrets in repo; proper env var usage |

---

## CRITICAL Issues (Fix Immediately)

### 1. Hardcoded OTP — Authentication Bypass
- **File:** `backend/server.py:846`
- **Issue:** OTP verification accepts hardcoded `"1234"` for ALL users
- **Impact:** Complete authentication bypass — any user can login with any phone number
- **Fix:** Generate random OTP, store in Redis/DB with TTL, validate properly

### 2. Path Traversal in PDF Endpoints
- **Files:** `backend/server.py:1160-1166`, `backend/server.py:1215-1222`
- **Issue:** `pdf_id` parameter used directly in file path without sanitization
- **Impact:** Attacker could access arbitrary files via `../../../etc/passwd`
- **Fix:** Use `Path.resolve()` and validate the resolved path is within `PDF_DIR`

### 3. Overly Permissive CORS Configuration
- **File:** `backend/server.py:1606-1608`
- **Issue:** Defaults to `allow_origins=["*"]` with `allow_credentials=True` (invalid per CORS spec), `allow_methods=["*"]`, `allow_headers=["*"]`
- **Impact:** Cross-origin attacks, CSRF vulnerabilities
- **Fix:** Set explicit allowed origins; never combine `*` with `allow_credentials=True`

### 4. No Rate Limiting on Authentication Endpoints
- **Files:** `backend/server.py:832+` (`/auth/send-otp`, `/auth/verify-otp`)
- **Impact:** Brute force attacks, OTP enumeration, account takeover
- **Fix:** Add rate limiter middleware (e.g., `slowapi`)

### 5. Unvalidated File Uploads
- **File:** `backend/server.py:1250-1272`
- **Issue:** Only checks filename extension and size; no MIME type validation or magic bytes verification
- **Impact:** Arbitrary file upload disguised as PDF
- **Fix:** Validate MIME type, check PDF magic bytes (`%PDF-`), and scan content

### 6. Prompt Injection via PDF Content
- **File:** `backend/form_extractor.py:99`
- **Issue:** Raw PDF text injected directly into LLM prompt without sanitization
- **Impact:** LLM jailbreaking, information disclosure, data exfiltration
- **Fix:** Sanitize and truncate PDF text; use structured prompting with system/user message separation

---

## HIGH Issues

### 7. No Error Boundary in React App
- **File:** `frontend/src/App.js`
- **Issue:** No `ErrorBoundary` component wrapping page routes
- **Impact:** Runtime error in any child component crashes the entire app

### 8. Missing Auth Headers in Frontend API Layer
- **File:** `frontend/src/lib/api.js:6-9`
- **Issue:** Axios instance has no interceptor for auth tokens (no Bearer token, no session ID)
- **Impact:** All API requests are unauthenticated from the frontend perspective

### 9. XSS Risk in Chat Components
- **Files:** `frontend/src/components/ChatBubble.js:433`, `frontend/src/components/SmartProfiler.js:206`
- **Issue:** Message content and question text rendered directly without sanitization
- **Impact:** If backend returns unsanitized user input, XSS is possible

### 10. Hardcoded Demo OTP Exposed in UI
- **File:** `frontend/src/pages/LoginPage.js:28`
- **Issue:** Toast message shows `"OTP भेजा गया! (Use 1234)"` — exposes demo credential
- **Impact:** Users see hardcoded OTP in production deployments

### 11. Unauthenticated Demo Toggle Endpoint
- **File:** `backend/server.py:1191-1195`
- **Issue:** `/demo/toggle` endpoint has no authentication — any user can toggle demo mode
- **Impact:** Attacker can put entire application into demo mode, affecting all users

### 12. Insecure Temporary File Handling
- **Files:** `backend/form_extractor.py:73-79`, `backend/server.py:994-996`
- **Issue:** `tempfile.NamedTemporaryFile(delete=False)` without guaranteed cleanup
- **Impact:** Information disclosure via leaked temp files

### 13. N+1 Query Issues
- **File:** `backend/server.py:515-610` (eligibility_matcher)
- **Issue:** Fetches ALL schemes then processes individually; no batching
- **Impact:** Database performance degrades linearly with scheme count

---

## MEDIUM Issues

### 14. Bare Exception Handling Throughout Backend
- **File:** `backend/server.py` — 17+ instances (lines 101, 123, 217, 428, 492, 595, 640, 650, 776, 816, 1023, 1153, 1209, 1239, 1269, 1363)
- **Issue:** `except Exception:` catches all exceptions, logs generically, and often silently continues
- **Impact:** Masks real errors; debugging becomes nearly impossible

### 15. Race Condition in Global State
- **File:** `backend/server.py:1193-1195`
- **Issue:** Global `DEMO_MODE` toggled without asyncio Lock
- **Impact:** Concurrent requests see inconsistent state

### 16. Mock Fallback in Production Code
- **File:** `backend/server.py:1026-1031`
- **Issue:** If STT returns empty, hardcoded Hindi text is shown as real transcript
- **Impact:** Misleading behavior for users

### 17. Missing Request Cancellation in Frontend
- **File:** `frontend/src/lib/api.js`
- **Issue:** No `AbortController` for canceling requests on component unmount
- **Impact:** State updates on unmounted components; potential memory leaks

### 18. Memory Leaks in Audio Components
- **File:** `frontend/src/components/ChatBubble.js:87-105`
- **Issue:** `audioRef.current` created but never cleaned up on unmount
- **Impact:** Audio resources persist across component lifecycle

### 19. Inconsistent Error Handling Patterns
- **Frontend:** Some endpoints use `.catch()` with toast, others use `.catch(() => {})` (silent)
- **Backend:** Some endpoints return `HTTPException`, others return `{"error": "..."}` as 200 OK
- **Impact:** Unreliable error reporting; silent failures

### 20. Missing Database Indexes
- **File:** `backend/prisma/schema.prisma`
- **Missing indexes on:**
  - `ChatLog.userId` (queried frequently)
  - `Application.userId` (user-specific queries)
  - `Application.schemeId`
- **Impact:** Slow queries as data grows

### 21. No Cascade Delete Rules
- **File:** `backend/prisma/schema.prisma`
- **Issue:** No `onDelete` rules on relations (ChatLog→User, Application→User/Scheme)
- **Impact:** Orphaned records if parent entity is deleted

### 22. Unvalidated JSON Fields in Database
- **File:** `backend/prisma/schema.prisma` — `User.profile`, `User.fullProfile`, `FormTemplate.extractedFields`, `Application.filledFields`
- **Issue:** `Json` type fields with no schema validation
- **Impact:** Corrupt data can crash endpoints

### 23. Monolithic Backend
- **File:** `backend/server.py` (1608 lines)
- **Issue:** All routes, models, business logic, and configuration in one file
- **Impact:** Hard to maintain, test, and review

---

## LOW Issues

### 24. Insufficient Phone Number Validation
- **File:** `backend/server.py:834-835`
- **Issue:** Only checks `len(phone) >= 10`; no format/pattern validation

### 25. Missing Accessibility Attributes
- **Files:** `frontend/src/components/AppHeader.js` (back button), `frontend/src/pages/ChatPage.js:346` (file input), `frontend/src/components/Sidebar.js:37-42` (overlay)
- **Issue:** Missing `aria-label` on interactive elements

### 26. Unused Dependencies
- **File:** `frontend/package.json`
- `recharts` (53KB gzipped) imported but not used in any component
- `vaul` (drawer) imported but not visible in components

### 27. Duplicate API Base URL
- **Files:** `frontend/src/lib/api.js:3` and `frontend/src/components/Sidebar.js:8`
- **Issue:** `REACT_APP_BACKEND_URL` referenced in multiple places instead of single source

### 28. Dynamic Import Anti-pattern
- **File:** `frontend/src/components/ChatBubble.js:288`
- **Issue:** `const api = (await import("../lib/api")).default;` — should be static import

### 29. .gitignore Cleanup Needed
- Duplicate `*.env` / `*.env.*` entries (lines 81-88)
- Malformed android-sdk entry with stray `-e` flag (line 80)
- Missing `*.key`, `*.pub` patterns for SSH/crypto keys

### 30. Empty Placeholder Files
- `eligibility`, `PDF`, `multi-PDF` are empty 0-byte files committed to repo

### 31. README.md is Placeholder
- Only contains `"Here are your Instructions"` — not useful documentation

---

## Database Schema Review

```
Models: User, Scheme, FormTemplate, ChatLog, Application

Issues:
- @@index([userId]) missing on ChatLog and Application
- No onDelete cascade rules on any relation
- Json fields (profile, fullProfile, extractedFields, filledFields) have no validation
- No updatedAt timestamps on ChatLog or Application
```

### Recommended Schema Additions
```prisma
model ChatLog {
  @@index([userId])
  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model Application {
  @@index([userId])
  @@index([schemeId])
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
  scheme Scheme @relation(fields: [schemeId], references: [id], onDelete: Cascade)
}
```

---

## Test Coverage Summary

| Area | Status | Details |
|------|--------|---------|
| Backend API E2E | **28/28 PASS** | Comprehensive endpoint coverage |
| Frontend UI E2E | **13/13 PASS** | Playwright-based flow verification |
| Unit Tests (Backend) | **MISSING** | No isolated function tests |
| Unit Tests (Frontend) | **MISSING** | No React component tests |
| Security Tests | **MISSING** | No injection, auth bypass, or fuzzing tests |
| Performance Tests | **MISSING** | No load testing |
| Accessibility Tests | **MISSING** | No a11y testing |

---

## External Dependencies & Integrations

| Service | Purpose | Risk |
|---------|---------|------|
| Emergent LLM | Chat AI, form filling | API key in env var (safe) |
| Sarvam AI | Speech-to-text (Hindi/English) | API key in env var (safe) |
| Agnost | Analytics & tracking | Write key in env var (safe) |
| MongoDB | Database | Connection string in env var (safe) |
| Google Generative AI | Fallback LLM | Referenced in requirements |
| OpenAI | Fallback LLM | Referenced in requirements |

---

## Recommended Fix Priority

### Immediate (P0)
1. Remove hardcoded OTP; implement real OTP generation + validation
2. Add path traversal protection on PDF endpoints
3. Fix CORS configuration with explicit origins
4. Add rate limiting on auth endpoints

### Short-term (P1)
5. Add file upload content validation (magic bytes, MIME type)
6. Add ErrorBoundary to React app
7. Implement auth token interceptor in frontend API layer
8. Sanitize LLM prompt inputs
9. Add authentication to `/demo/toggle` endpoint
10. Add database indexes

### Medium-term (P2)
11. Replace bare `except Exception` with specific exception handling
12. Add request cancellation (AbortController) in frontend
13. Fix memory leaks in audio components
14. Refactor `server.py` into modular route files
15. Add cascade delete rules to Prisma schema
16. Write unit tests for backend functions and frontend components

### Long-term (P3)
17. Add security testing (OWASP ZAP, fuzzing)
18. Add performance/load testing
19. Add accessibility testing
20. Complete documentation (README, API docs, setup guide)
21. Remove unused dependencies
22. Clean up placeholder files

---

*End of Audit Report*
