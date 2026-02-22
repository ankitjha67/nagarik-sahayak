# Nagarik Sahayak - Product Requirements Document

## Original Problem Statement
Build a full-stack, mobile-first chat application called 'Nagarik Sahayak' - a WhatsApp-style chat interface with a government service theme (saffron #FF9933 and Ashok blue #000080 accents). The app helps citizens discover government scheme eligibility through a conversational AI profiler.

## Core Architecture
- **Frontend**: React (Create React App), Tailwind CSS, shadcn/ui
- **Backend**: Python/FastAPI, Prisma ORM, MongoDB (replica set)
- **Database**: MongoDB with Prisma schema (User, Scheme, ChatLog, Application)

## Implemented Features

### Authentication (MOCKED)
- Mock phone authentication using static OTP '1234'
- Any 10-digit phone number accepted

### Profiler Agent
- Conversational agent collecting: name, age, income (yearly), state
- One question at a time in Hindi
- Validates input for each field

### Intelligence + Execution Layer (COMPLETED Feb 2026)
1. **search_schemes(query)**: Prisma-backed search. Returns "Document scanned: [name]" + eligibilityCriteriaText.
2. **eligibilityMatcher(user_id)**: Defaults to Vidyasiri. Income compared YEARLY < 150000. State == Karnataka.
3. **generateFilledForm(user_id, scheme_id)**: Pre-filled PDF with Hindi labels (Naam, Umr, Aay, Rajya, Scheme Name, Date DD/MM/YYYY).
4. **Full Chain**: profiler → search_schemes → eligibility → generateFilledForm → download link
5. **Streaming Bullets**: "Reading Vidyasiri PDF" → "Checking eligibility" → "Generating form"
6. **DEMO_MODE** (default true): Triggers on "10th", "scholarship", "beta"
7. **Agnost Tracking**: All tools wrapped

### Final Polish (COMPLETED Feb 2026)
- WhatsApp Share button (Web Share API + web.whatsapp.com fallback, fixed from wa.me redirect block)
- PDF download via blob fetch (fixed about:blank issue from target=_blank)
- "Agent is thinking..." with saffron spinner during tools
- Mic pulse animation when recording
- Instant blue double ticks on agent replies
- Hindi date DD/MM/YYYY in PDF
- PDF labels: "PDF डाउनलोड करें" / "Pre-filled Application Form"

### Database Seed (3 Schemes)
1. Pradhan Mantri Awas Yojana
2. Vidyasiri Scholarship
3. Vidya Lakshmi Education Loan

### Sarvam AI STT Integration (COMPLETED Feb 2026)
- Sarvam Saaras v3 model for speech-to-text
- Supports Hindi and English — user toggles via "हि"/"EN" button in input bar
- Language preference persisted in localStorage
- Mock fallback when Sarvam returns empty transcript (silence)
- Both Hindi and English transcripts shown in chat bubble
- Agnost tracking for STT calls

### UX Features (COMPLETED Feb 2026)
- Paperclip PDF upload button (left of mic, accepts .pdf only, max 10MB)
- New Chat button (header top-right, clears history + resets profiler)
- Sukanya Samriddhi Yojana link updated to PIB 2026 guidelines

## Upcoming Tasks
- P0: Migrate Frontend to Next.js (deferred until after VibeCon)
- P1: Real Speech-to-Text via Sarvam AI
- P1: Dynamic RAG with uploaded PDF documents
- P2: Refactor monolithic server.py into modules
- P3: Real OTP authentication service
