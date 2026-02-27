# Nagarik Sahayak - Product Requirements Document

## Original Problem Statement
Full-stack mobile-first chat application to help Indian citizens find and apply for government schemes. WhatsApp-style UI with voice input, real form filling, and multi-PDF download.

## V2.0 Production Upgrade (Feb 2026)
Upgraded from prototype to production-grade real-form capability with 4 official government schemes.

## Core Architecture
- **Backend**: FastAPI + Prisma (MongoDB replica set) + Claude Sonnet 4.5 (via Emergent LLM key)
- **Frontend**: React (CRA) + Tailwind CSS + shadcn/ui
- **Integrations**: Sarvam AI (STT), Agnost (analytics), Emergent LLM (form extraction)

## Database Schema (Prisma)
- **User**: phone, profile, fullProfile (persistent), profileLastUpdated, schemeHistory
- **Scheme**: 4 real schemes with eligibility criteria, official URLs
- **FormTemplate**: 4 templates with 82 total extractedFields (real official form fields)
- **ChatLog**: Message history per user
- **Application**: userId, schemeId, status, formUrl, filledFields

## 4 Real Government Schemes
1. **PMAY-U** (Housing): 22 fields, 5 sections — pmaymis.gov.in
2. **Vidyasiri Scholarship** (Education): 20 fields, 5 sections — bcw.karnataka.gov.in
3. **Startup India Seed Fund** (Startup): 21 fields, 5 sections — seedfund.startupindia.gov.in
4. **PM-KISAN Samman Nidhi** (Agriculture): 19 fields, 5 sections — pmkisan.gov.in

## Completed Features

### V2.0 Steps Completed (Feb 27, 2026)
- **Step 1: Database Upgrade** — Prisma schema with FormTemplate model, enhanced User with fullProfile, seeded 4 real schemes with 82 real form fields
- **Step 2: Form Extraction Engine** — Claude Sonnet 4.5 via Emergent LLM for PDF analysis (backend/form_extractor.py)
- **Step 3: Intelligent Multi-Form Profiler** — Smart profiler API that deduplicates fields across schemes, tracks filled/missing, returns next question in Hindi
- **Step 4: Real Filled PDF Generation** — Production-grade PDFs with all fields organized by sections, saffron header, declaration, signature blocks
- **Step 5: Frontend UX** — SchemeSelector cards with category icons, SmartProfiler with progress bar + question flow + review & confirm + PDF download

### V1.0 Features (Prior)
- WhatsApp-style chat UI with saffron/blue theme
- Mock phone auth (OTP: 1234)
- Sarvam AI speech-to-text (Hindi/English toggle)
- Multi-PDF download with blob fetch + zip fallback
- Paperclip upload, New Chat, Copy to Clipboard
- Agnost analytics tracking
- DEMO_MODE for presentations

## V2 API Endpoints
- `GET /api/v2/schemes` — List all 4 schemes
- `GET /api/v2/form-templates` — Summary of all templates
- `GET /api/v2/form-template/{name}` — Full template with fields
- `GET /api/v2/user-profile/{id}` — Get persistent profile
- `POST /api/v2/user-profile/{id}` — Update (merge) profile fields
- `POST /api/v2/smart-profiler` — Get profiler state for selected schemes
- `POST /api/v2/generate-filled-forms` — Generate real PDFs
- `POST /api/v2/extract-form-fields` — LLM-powered PDF analysis

## Testing Status
- Iteration 15: 405 fix — 100% (9/9 backend, 7/7 frontend)
- Iteration 16: V2.0 upgrade — 100% (28/28 backend, 13/13 frontend)

## Upcoming Tasks
- P0: Polish & Live Demo Ready (Step 6) — thinking animations, Agnost tracking, DEMO_MODE auto-complete
- P1: Migrate Frontend to Next.js (deferred per user for demo stability)
- P2: Implement RAG with uploaded PDFs
- P3: Refactor monolithic server.py into modules
- P4: Real OTP authentication service

## Credentials
- Phone: Any 10-digit number
- OTP: 1234 (MOCKED)
- Emergent LLM Key: In backend/.env
- Sarvam API Key: In backend/.env
