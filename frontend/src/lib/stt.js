// Speech capture that works on every platform the app runs on.
//
// Two modes:
//   "server"  - record with MediaRecorder in whatever container this browser
//               supports (WebM/Opus on Chrome and Android, MP4/AAC on iPhone
//               Safari, OGG on Firefox) and send the bytes; the server picks
//               an engine (Bhashini, Whisper, Groq, OpenAI, …) with fallback.
//   "browser" - use the Web Speech API on the device, where it exists, and
//               send only the recognised text (nothing leaves the phone but
//               the words).
//
// Nothing here assumes a vendor; the server tells us what it has.

const CANDIDATE_MIMES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",            // Safari / iOS
  "audio/aac",
  "audio/wav",
];

export const recordingSupported = () =>
  typeof window !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

export const browserSpeechSupported = () =>
  typeof window !== "undefined" && !!(window.SpeechRecognition || window.webkitSpeechRecognition);

// The first container this browser can actually produce. Returns "" when the
// browser has MediaRecorder but will not say (older Safari): recording then
// starts with no mimeType and the blob's own type is used.
export const pickRecordingMime = () => {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  return CANDIDATE_MIMES.find((m) => MediaRecorder.isTypeSupported(m)) || "";
};

export const extensionFor = (mime) => {
  const m = (mime || "").split(";")[0];
  return ({ "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/aac": "aac",
            "audio/wav": "wav", "audio/mpeg": "mp3" })[m] || "bin";
};

// BCP-47 tag for the Web Speech API from the app's short code.
export const speechLang = (code) => {
  const c = (code || "hi").split("-")[0];
  return c === "en" ? "en-IN" : `${c}-IN`;
};

/**
 * Start a recording. Resolves with { stop(): Promise<{blob, mime}> } or
 * rejects when the microphone is refused. The caller owns the timer.
 */
export const startRecording = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = pickRecordingMime();
  const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
  const stopped = new Promise((resolve) => {
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const type = recorder.mimeType || mime || (chunks[0] && chunks[0].type) || "application/octet-stream";
      resolve({ blob: new Blob(chunks, { type }), mime: type });
    };
  });
  recorder.start();
  return {
    mime: recorder.mimeType || mime,
    isRecording: () => recorder.state === "recording",
    stop: () => { if (recorder.state === "recording") recorder.stop(); return stopped; },
  };
};

/**
 * Recognise speech on the device. Resolves with the transcript text, or
 * rejects with an Error whose .code is "unsupported" | "no-speech" |
 * "not-allowed" | "network" | "aborted".
 */
export const recogniseOnDevice = (langCode, { maxSeconds = 8 } = {}) =>
  new Promise((resolve, reject) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { const e = new Error("unsupported"); e.code = "unsupported"; return reject(e); }
    const rec = new SR();
    rec.lang = speechLang(langCode);
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    let done = false;
    const finish = (fn, v) => { if (!done) { done = true; clearTimeout(timer); fn(v); } };
    const timer = setTimeout(() => { try { rec.stop(); } catch { /* ignore */ } }, maxSeconds * 1000);
    rec.onresult = (ev) => {
      const text = Array.from(ev.results).map((r) => r[0]?.transcript || "").join(" ").trim();
      finish(resolve, text);
    };
    rec.onerror = (ev) => { const e = new Error(ev.error || "error"); e.code = ev.error || "error"; finish(reject, e); };
    rec.onend = () => { const e = new Error("no-speech"); e.code = "no-speech"; finish(reject, e); };
    try { rec.start(); } catch (err) { const e = new Error("not-allowed"); e.code = "not-allowed"; finish(reject, e); }
  });

// Per-viewer preference: which mode to use. Stored locally; a convenience only.
export const getSttMode = () => { try { return localStorage.getItem("ns_stt_mode") || "server"; } catch { return "server"; } };
export const setSttMode = (mode) => { try { localStorage.setItem("ns_stt_mode", mode); } catch { /* ignore */ } };
export const getSttProvider = () => { try { return localStorage.getItem("ns_stt_provider") || ""; } catch { return ""; } };
export const setSttProvider = (key) => { try { localStorage.setItem("ns_stt_provider", key || ""); } catch { /* ignore */ } };
