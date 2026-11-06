"""Speech to text, behind one interface, on any platform.

The app must not depend on one vendor, one SDK, or one operating system. So:

* every engine is an `SttProvider` with the same `transcribe()`;
* engines talk plain HTTPS through httpx (no vendor SDKs to install), or run
  locally when their optional package is present (faster-whisper, Vosk), or
  are the browser itself (Web Speech API sends text, not audio);
* the registry picks an engine by language and availability, and falls back
  down an ordered chain when one fails, so a dead key never silences a
  citizen;
* audio is normalised with ffmpeg when present (WebM/Opus from Chrome, MP4/AAC
  from iPhones, OGG, WAV, MP3 all become 16 kHz mono WAV) and passed through
  unchanged when not.

Free engines: bhashini (GoI), whisper_local, vosk, openai_compatible (any
self-hosted Whisper server), groq (free tier). Frontier engines: openai,
deepgram, assemblyai, google, azure, gemini, sarvam.
"""
