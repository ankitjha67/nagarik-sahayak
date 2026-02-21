# Nagarik Sahayak - PRD

## Problem Statement
Build a mobile-first full-stack chat application called 'Nagarik Sahayak' — a digital citizen assistant for Indian government schemes. Design: trustworthy government service aesthetic with saffron (#FF9933) accents and Ashok Chakra blue (#000080) text. WhatsApp-style chat with double tick read status. Mock phone auth (OTP 1234). Hindi + English bilingual. Voice input via OpenAI Whisper. 3 seeded government schemes.

## Architecture
- **Backend**: FastAPI + MongoDB (Motor async driver)
- **Frontend**: React 19 + Tailwind CSS + shadcn/ui
- **STT**: OpenAI Whisper via Emergent LLM Key
- **Auth**: Mock phone OTP (hardcoded 1234)
- **Bot**: Rule-based responses (LLM placeholders configured)

## User Personas
1. **Rural farmer** — needs PM-KISAN info, prefers Hindi, voice input
2. **Urban parent** — needs Sukanya Samriddhi info, bilingual
3. **Low-income family** — needs Ayushman Bharat health scheme info

## Core Requirements
- Mock phone auth (OTP 1234)
- WhatsApp-style chat with double tick indicators
- Voice-to-text input (OpenAI Whisper)
- 3 government schemes with full Hindi/English eligibility + benefits
- User profile with language preference
- Mobile-first responsive design

## What's Been Implemented (Feb 21, 2026)
- [x] Full backend with auth, chat, profile, schemes, voice APIs
- [x] 3 government schemes seeded (PM-KISAN, Ayushman Bharat, Sukanya Samriddhi)
- [x] Mock phone auth with OTP 1234
- [x] WhatsApp-style chat with double tick read status
- [x] Voice input via OpenAI Whisper
- [x] Hindi + English bilingual support
- [x] LLM provider placeholders (OpenAI, Anthropic, Google, Mistral, Meta, Cohere)
- [x] STT provider placeholders (OpenAI Whisper active, Sarvam AI placeholder)
- [x] Mobile-first UI with saffron + navy design
- [x] Bottom navigation (Home, Chat, Schemes, Profile)
- [x] Profile management with language toggle
- [x] **MCP Tool Simulation: search_schemes(query)** — scans 3 scheme PDFs, returns "Document scanned: [name]" + eligibility criteria
- [x] **No-match handling**: returns "I don't know — criteria not explicitly stated in PDFs"
- [x] **/api/mcp/tools** endpoint listing available MCP tools
- [x] **/api/search-schemes** direct tool invocation endpoint
- [x] Chat bot responses include `tool_calls` array with MCP trace
- [x] Frontend ChatBubble renders MCP tool-call trace (documents scanned, match/no-match indicator)
- [x] **/api/transcribe** endpoint using **Sarvam Saaras v3** (model="saaras:v3")
  - mode="transcribe" → Hindi transcript
  - mode="translate" → English translation
- [x] Frontend mic records **5s auto-stop** audio via MediaRecorder with countdown badge
- [x] TranscriptionBlock component renders Hindi + English side by side
- [x] Transcriptions stored in ChatLog with type="transcription", transcript_hi, transcript_en
- [x] Bot auto-responds to transcribed text (MCP tool if scheme-related)
- [x] **Audio playback button** on transcription bubbles — audio saved to disk, served via `GET /api/audio/{msg_id}`, play/pause toggle button in TranscriptionBlock
- [x] **Profiler Agent**: asks ONE question at a time in Hindi (name → age → income → state). Stores in `user.profile_data` JSONB. When complete, auto-triggers eligibility check (`check_eligibility` tool) against all 3 schemes
- [x] Profiler validates inputs (age must be number, income parsed from text)
- [x] After profile complete, normal MCP chat resumes
- [x] **eligibility_matcher** MCP tool: uses `search_schemes` → compares profile vs scheme criteria → returns per-scheme `{eligible, reason}` JSON with exact limit comparisons (e.g. "Income ₹80,000 exceeds ₹50,000 limit")
- [x] `POST /api/eligibility-check` endpoint (accepts profile inline or user_id + optional query filter)
- [x] Registered in MCP_TOOLS alongside search_schemes
- [x] Profiler completion auto-triggers eligibility_matcher
- [x] Frontend EligibilityCard component: green/red shield icon, पात्र/अपात्र badge, reason text, benefit info
- [x] **PDF generation** via `fpdf2` with Noto Sans (English) + Noto Sans Devanagari (Hindi) fonts
- [x] `POST /api/generate-pdf` — accepts profile inline or user_id, runs eligibility_matcher, generates clean PDF report
- [x] `GET /api/pdf/{pdf_id}` — serves PDF for download
- [x] Profiler completion auto-generates PDF and includes download link in chat
- [x] Frontend: navy-blue PDF download button with "PDF रिपोर्ट डाउनलोड करें" + download icon
- [x] 100% backend test pass rate (27/27 endpoints)

- [x] **Agnost AI SDK** tracking for all MCP tool calls (search_schemes, eligibility_matcher, generate_pdf)
- [x] `agnost.track()` wraps every tool call with agent_name="nagarik_tool", user_id, properties={tool}
- [x] `GET /api/analytics/status` endpoint returns tracking enabled state + dashboard URL
- [x] Sidebar drawer on all pages with hamburger menu, Analytics Dashboard link to https://app.agnost.ai
- [x] Green active badge when Agnost tracking is enabled
- [x] **DEMO_MODE** env flag: any scholarship query instantly returns Vidyasiri eligible + pre-filled PDF in <2s
- [x] Demo fast-path in `/api/chat` and `/api/search-schemes` endpoints
- [x] Pre-filled demo profile (Priya Sharma, 20, Karnataka, Rs 15k/month)
- [x] Agnost tracking for demo tool calls
- [x] 100% backend test pass rate (13/13 Agnost integration tests)

- [x] **Streaming tool progress bullets** in chat — replaces typing dots with 3 animated steps:
  1. "Reading Vidyasiri Scholarship PDF..." (Search icon)
  2. "Checking eligibility..." (ClipboardCheck icon)
  3. "Generating filled form..." (FileOutput icon)
- [x] Each step slides in with 650ms stagger, active step has pulsing loader, completed steps show green checkmark
- [x] Saffron-to-navy shimmer bar across the top of the progress card
- [x] Hindi + English bilingual text on each step
- [x] Progress card auto-disappears when response arrives

- [x] **Hardcoded stage demo**: "Mera beta 10th pass hai" → Rajesh Kumar profile + Vidyasiri + PM-KISAN eligible + PDF (~300ms)
- [x] Exact trigger phrases (English + Hindi) + fuzzy keyword matching (scholarship, student, 10th, pass, etc.)
- [x] DB writes & Agnost tracking wrapped in try/except for 100% offline reliability
- [x] 2 eligible schemes in single response with full reasons + benefits
- [x] Streaming tool progress bullets updated: "Scanning scholarship PDFs..." → "Checking eligibility..." → "Generating report & form..."

## P0 Backlog
- Integrate real LLM for intelligent chat responses
- Implement Sarvam AI STT (needs API key)

## P1 Backlog
- Scheme eligibility checker (form-based)
- Multi-turn conversation context
- Push notifications for scheme updates

## P2 Backlog
- Document upload for scheme applications
- Multilingual support beyond Hindi/English
- Analytics dashboard for admin
