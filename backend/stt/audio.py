"""Audio sniffing and normalisation.

Browsers produce different containers: Chrome and Android record WebM/Opus,
Safari on iPhone records MP4/AAC, Firefox OGG/Opus. Engines differ in what
they accept. With ffmpeg on the machine, everything is converted to 16 kHz
mono 16-bit WAV, which every engine takes; without it, the bytes pass
through with the sniffed type so that engines that accept the native
container still work.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

_FFMPEG = shutil.which("ffmpeg")


def sniff_mime(data: bytes, declared: str = "") -> str:
    head = data[:16]
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    if data[4:8] in (b"ftyp", b"moov", b"mdat"):
        return "audio/mp4"
    if head.startswith(b"fLaC"):
        return "audio/flac"
    return (declared or "application/octet-stream").split(";")[0].strip() or "application/octet-stream"


def extension_for(mime: str) -> str:
    return {
        "audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/aac": "aac", "audio/flac": "flac",
        "video/webm": "webm", "video/mp4": "mp4",
    }.get(mime, "bin")


def ffmpeg_available() -> bool:
    return bool(_FFMPEG)


async def to_wav16k(data: bytes, mime: str, timeout: float = 30.0) -> tuple[bytes, str]:
    """Convert to 16 kHz mono PCM WAV via ffmpeg; pass through if unavailable."""
    if not _FFMPEG:
        return data, mime
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"in.{extension_for(mime)}"
        dst = Path(d) / "out.wav"
        src.write_bytes(data)
        proc = await asyncio.create_subprocess_exec(
            _FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", "-f", "wav", str(dst),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return data, mime
        if proc.returncode != 0 or not dst.exists():
            return data, mime
        return dst.read_bytes(), "audio/wav"


def wav_duration_ms(wav: bytes) -> int:
    """Duration of a 16 kHz mono 16-bit WAV, or 0 if it is not one."""
    if not (wav.startswith(b"RIFF") and wav[8:12] == b"WAVE"):
        return 0
    try:
        idx = wav.index(b"data") + 8
        return int((len(wav) - idx) / (16000 * 2) * 1000)
    except ValueError:
        return 0
