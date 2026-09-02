"""Application configuration, constants, and utility helpers."""
import os
import re
import secrets
import asyncio
import time as _time
from collections import defaultdict
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# --- Agnost Analytics ---
AGNOST_WRITE_KEY = os.environ.get("AGNOST_WRITE_KEY", "")

# --- Demo Mode ---
DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("true", "1", "yes")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
demo_lock = asyncio.Lock()

# --- Directories ---
AUDIO_DIR = ROOT_DIR / "audio_files"
AUDIO_DIR.mkdir(exist_ok=True)
PDF_DIR = ROOT_DIR / "pdf_reports"
PDF_DIR.mkdir(exist_ok=True)

# --- Rate Limiting ---
_rate_limit_store: Dict[str, list] = defaultdict(list)
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60


def check_rate_limit(key: str) -> bool:
    """Return True if rate-limited (too many requests)."""
    now = _time.time()
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[key]) >= RATE_LIMIT_MAX:
        return True
    _rate_limit_store[key].append(now)
    return False


# --- Validators ---

def validate_phone(phone: str) -> bool:
    """Validate Indian phone number: 10 digits, starts with 6-9."""
    return bool(re.match(r'^[6-9]\d{9}$', phone))


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input: strip control chars, limit length."""
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text[:max_length].strip()


def validate_path_within(path: Path, base_dir: Path) -> bool:
    """Validate a resolved path is within the base directory (prevent path traversal)."""
    try:
        resolved = path.resolve()
        return resolved.is_relative_to(base_dir.resolve())
    except (ValueError, OSError):
        return False


PDF_MAGIC_BYTES = b'%PDF-'


def validate_pdf_content(content: bytes) -> bool:
    """Check if file content starts with PDF magic bytes."""
    return content[:5] == PDF_MAGIC_BYTES


# --- CORS ---
CORS_ORIGINS_RAW = os.environ.get('CORS_ORIGINS', 'http://localhost:3000')
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_RAW.split(',') if o.strip()]
