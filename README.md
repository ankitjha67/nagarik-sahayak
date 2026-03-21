# Nagarik Sahayak (नागरिक सहायक)

A mobile-first WhatsApp-style chat application that helps Indian citizens discover and apply for government welfare schemes. AI-powered eligibility checking with real PDF form generation.

## Features

- **AI Chat Interface** — WhatsApp-style UI with Hindi/English voice input (Sarvam AI STT)
- **4 Real Government Schemes** — PMAY-U, Vidyasiri Scholarship, Startup India Seed Fund, PM-KISAN
- **Smart Profiler** — Deduplicates fields across schemes, tracks progress, asks one question at a time
- **Real PDF Generation** — Pre-filled application forms with saffron-themed government styling
- **Eligibility Matching** — Automated criteria checking against user profile
- **Voice Input** — Hindi/English speech-to-text via Sarvam Saaras v3
- **Demo Mode** — Stage-ready responses for live presentations

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI + Prisma (MongoDB) + Claude Sonnet 4.5 (via Emergent LLM) |
| **Frontend** | React 19 + Tailwind CSS + shadcn/ui + Framer Motion |
| **Speech** | Sarvam AI (Hindi/English bilingual STT) |
| **Analytics** | Agnost AI |
| **PDF** | fpdf2 + pdfplumber + PyMuPDF + pytesseract |

## Project Structure

```
backend/
  server.py              # App entry, startup, CORS, route mounting
  config.py              # Configuration, constants, validators
  database.py            # Prisma + Motor clients
  models.py              # Pydantic request/response models
  routes/                # API route handlers
    auth.py              # OTP send/verify
    chat.py              # Chat messages, voice transcription
    profile.py           # User profile CRUD
    schemes.py           # Scheme listing, search, eligibility
    pdf.py               # PDF serving, generation, upload
    demo.py              # Demo mode toggle
    v2.py                # V2 smart profiler, filled forms, templates
  services/              # Business logic
    chat.py              # Chat history persistence
    profiler.py          # Profiler agent (question flow + PDF gen)
    eligibility.py       # Eligibility matching engine
    search.py            # Scheme search (Prisma + in-memory)
    demo.py              # Demo mode data and responses
  form_extractor.py      # LLM-powered PDF field extraction
  pdf_generator.py       # PDF creation with saffron styling
  pdf_filler.py          # Intelligent field matching & form filling
  prisma/
    schema.prisma        # MongoDB schema (5 models)
    seed.py              # Seed 4 real government schemes

frontend/
  src/
    pages/               # LoginPage, HomePage, ChatPage, SchemesPage, ProfilePage
    components/          # ChatBubble, SchemeSelector, SmartProfiler, AppHeader, Sidebar
    lib/api.js           # Axios instance with auth interceptors
    components/ui/       # 60+ shadcn/ui components
```

## Quick Start

### Prerequisites
- Python 3.11+, Node.js 18+, MongoDB

### Backend
```bash
cd backend
cp .env.example .env   # Configure MONGO_URL, EMERGENT_LLM_KEY, etc.
pip install -r requirements.txt
prisma generate
python -m prisma.seed   # Seed 4 government schemes
uvicorn server:app --reload
```

### Frontend
```bash
cd frontend
cp .env.example .env   # Set REACT_APP_BACKEND_URL
yarn install
yarn start
```

## API Endpoints

### Auth
- `POST /api/auth/send-otp` — Send OTP to phone number
- `POST /api/auth/verify-otp` — Verify OTP and create user

### V2 APIs
- `GET /api/v2/schemes` — List all 4 real schemes
- `GET /api/v2/form-templates` — Summary of all form templates
- `POST /api/v2/smart-profiler` — Intelligent field profiler
- `POST /api/v2/generate-filled-forms` — Generate pre-filled PDFs
- `POST /api/v2/extract-form-fields` — LLM-powered PDF analysis

### Chat
- `POST /api/chat` — Send message, get AI response
- `POST /api/transcribe` — Voice-to-text via Sarvam AI
- `GET /api/chat/history/{user_id}` — Message history

## Testing

```bash
cd backend
pytest tests/ -v   # 28/28 tests passing
```

## Security

See [AUDIT_REPORT.md](./AUDIT_REPORT.md) for the full security audit. Key protections:
- Cryptographic OTP generation with 5-minute expiry
- Path traversal prevention on all file endpoints
- CORS restricted to explicit origins
- Rate limiting on authentication endpoints
- PDF magic bytes + MIME type validation on uploads
- Prompt injection sanitization for LLM inputs
- React auto-escaping prevents XSS
