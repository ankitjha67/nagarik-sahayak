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
- [x] 90%+ overall test pass rate (backend 93%, frontend 85%)

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
