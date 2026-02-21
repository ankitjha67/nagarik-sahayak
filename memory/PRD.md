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

### Intelligence + Execution Layer (P0 - COMPLETED Feb 2026)
1. **search_schemes(query)**: Prisma-backed search of Scheme table. Returns "Document scanned: [name]" + eligibilityCriteriaText. No match returns "I don't know" message.
2. **eligibilityMatcher(user_id)**: Fetches user.profile via Prisma. Defaults to Vidyasiri scheme (listed first). Compares yearly income < 150000, state == Karnataka. Returns {eligible, reason} in Hindi.
3. **generateFilledForm(user_id, scheme_id)**: Generates pre-filled application form PDF with Hindi labels (Naam, Umr, Aay, Rajya, Scheme Name, Date). Saved to static/uploads, returns public download URL.
4. **Full Chain**: Profile complete → search_schemes → eligibilityMatcher → generateFilledForm → download link in chat
5. **Streaming Bullets UI**: Reading Vidyasiri PDF → Checking eligibility → Generating form
6. **DEMO_MODE** (env var, default true): Triggers on "10th", "scholarship", "beta" → instant Vidyasiri eligible + pre-filled PDF
7. **Agnost Tracking**: All tools wrapped with agnost.track()

### UI/UX
- WhatsApp-style chat with saffron/blue government theme
- Large microphone button for voice input
- Animated double ticks (read receipts)
- Tool progress streaming bullets
- Eligibility cards with green/red badges
- PDF download button in chat
- Hindi voice reply (browser SpeechSynthesis)
- Sidebar with analytics link and demo toggle

### Database Seed (3 Schemes)
1. Pradhan Mantri Awas Yojana
2. Vidyasiri Scholarship
3. Vidya Lakshmi Education Loan

## Mocked Components
- Authentication (static OTP 1234)
- Speech-to-Text (hardcoded mock response, Sarvam AI ready)

## Key API Endpoints
- POST /api/auth/send-otp, /api/auth/verify-otp
- POST /api/chat (main chat with profiler + tool chain)
- POST /api/search-schemes, /api/eligibility-check, /api/generate-filled-form
- GET /api/pdf/{id}, /api/schemes, /api/chat/history/{user_id}
- POST /api/demo/toggle, GET /api/demo/status

## Upcoming Tasks
- P0: Migrate Frontend to Next.js (deferred until after VibeCon)
- P1: Real Speech-to-Text via Sarvam AI
- P2: Refactor monolithic server.py into modules
- P3: Real OTP authentication service
