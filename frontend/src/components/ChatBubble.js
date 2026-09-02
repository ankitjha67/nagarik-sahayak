import { useState, useRef, useEffect, useCallback } from "react";
import { CheckCheck, Check as CheckIcon, FileSearch, FileText, Check, X, Languages, Play, Pause, ShieldCheck, ShieldX, Download, FileDown, Loader2, Search, ClipboardCheck, FileOutput, Volume2, VolumeX, Share2 } from "lucide-react";
import api from "../lib/api";

function escapeHtml(str) {
  if (typeof str !== "string") return str;
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

const EligibilityCard = ({ result }) => {
  const isEligible = result.eligible;
  return (
    <div
      data-testid={`eligibility-card-${isEligible ? "eligible" : "ineligible"}`}
      className={`rounded-lg border px-3 py-2.5 ${
        isEligible ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        {isEligible ? (
          <ShieldCheck size={15} className="text-green-600 flex-shrink-0" />
        ) : (
          <ShieldX size={15} className="text-red-500 flex-shrink-0" />
        )}
        <span className={`text-xs font-bold font-['Mukta'] ${isEligible ? "text-green-800" : "text-red-800"}`}>
          {result.scheme_hi || result.scheme}
        </span>
        <span className={`ml-auto text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
          isEligible ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
        }`}>
          {isEligible ? "पात्र" : "अपात्र"}
        </span>
      </div>
      <p className="text-[11px] text-gray-600 font-['Nunito'] leading-relaxed">{result.reason}</p>
      {isEligible && result.benefit && (
        <p className="text-[11px] text-green-700 font-['Nunito'] font-semibold mt-1">Benefit: {result.benefit}</p>
      )}
    </div>
  );
};

const ToolCallTrace = ({ toolCall }) => (
  <div data-testid="mcp-tool-trace" className="mb-2.5 rounded-xl border border-[#E6E6F2] bg-[#F8F8FC] overflow-hidden">
    <div className="flex items-center gap-2 px-3 py-1.5 bg-[#E6E6F2] border-b border-[#D4D4E8]">
      <FileSearch size={13} className="text-[#000080]" />
      <span className="text-[11px] font-bold text-[#000080] font-['Mukta'] tracking-wide uppercase">
        MCP Tool: {toolCall.tool_name}
      </span>
    </div>
    <div className="px-3 py-2 space-y-1">
      <p className="text-[10px] font-semibold text-gray-500 font-['Nunito'] uppercase tracking-wider">Documents scanned</p>
      {toolCall.documents_scanned?.map((doc, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <FileText size={12} className="text-[#FF9933] flex-shrink-0" />
          <span className="text-[11px] text-gray-600 font-['Nunito']">{doc}</span>
        </div>
      ))}
    </div>
    {toolCall.results && toolCall.results.length > 0 && (
      <div className="px-3 py-2 border-t border-[#E6E6F2] space-y-2">
        <p className="text-[10px] font-semibold text-gray-500 font-['Nunito'] uppercase tracking-wider">Eligibility results</p>
        {toolCall.results.map((r, i) => (
          <EligibilityCard key={i} result={r} />
        ))}
      </div>
    )}
    {(!toolCall.results || toolCall.results.length === 0) && (
      <div className="px-3 py-1.5 border-t border-[#E6E6F2] flex items-center gap-1.5">
        {toolCall.match_found ? (
          <>
            <div className="w-4 h-4 rounded-full bg-green-100 flex items-center justify-center">
              <Check size={10} className="text-green-600" />
            </div>
            <span className="text-[11px] font-semibold text-green-700 font-['Nunito']">Match found</span>
          </>
        ) : (
          <>
            <div className="w-4 h-4 rounded-full bg-red-100 flex items-center justify-center">
              <X size={10} className="text-red-500" />
            </div>
            <span className="text-[11px] font-semibold text-red-600 font-['Nunito']">No match in documents</span>
          </>
        )}
      </div>
    )}
  </div>
);

const TranscriptionBlock = ({ message }) => {
  const hi = message.transcript_hi || "";
  const en = message.transcript_en || "";
  const audioUrl = message.audio_url || "";
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.onended = null;
        audioRef.current.onerror = null;
        audioRef.current = null;
      }
    };
  }, []);

  const togglePlay = () => {
    if (!audioUrl) return;
    const backendUrl = process.env.REACT_APP_BACKEND_URL;
    const fullUrl = `${backendUrl}${audioUrl}`;
    if (!audioRef.current) {
      audioRef.current = new Audio(fullUrl);
      audioRef.current.onended = () => setPlaying(false);
      audioRef.current.onerror = () => setPlaying(false);
    }
    if (playing) {
      audioRef.current.pause();
      setPlaying(false);
    } else {
      audioRef.current.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  };

  return (
    <div data-testid="transcription-block" className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <Languages size={14} className="text-[#FF9933]" />
          <span className="text-[10px] font-bold text-[#FF9933] font-['Mukta'] uppercase tracking-wider">
            Voice Transcription — Sarvam Saaras v3
          </span>
        </div>
        {audioUrl && (
          <button
            data-testid="audio-playback-btn"
            onClick={togglePlay}
            className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${
              playing ? "bg-[#000080] text-white" : "bg-[#FFF0E0] text-[#FF9933] hover:bg-[#FFE4C4]"
            }`}
          >
            {playing ? <Pause size={12} /> : <Play size={12} className="ml-0.5" />}
          </button>
        )}
      </div>
      {hi && (
        <div data-testid="transcript-hindi" className="rounded-lg bg-[#FFF8F0] border border-orange-100 px-3 py-2">
          <span className="text-[10px] font-bold text-[#000080] font-['Mukta'] uppercase tracking-wider block mb-0.5">Hindi</span>
          <p className="text-sm text-gray-800 leading-relaxed font-['Mukta']">{hi}</p>
        </div>
      )}
      {en && (
        <div data-testid="transcript-english" className="rounded-lg bg-[#F0F0F8] border border-[#D4D4E8] px-3 py-2">
          <span className="text-[10px] font-bold text-[#000080] font-['Nunito'] uppercase tracking-wider block mb-0.5">English</span>
          <p className="text-sm text-gray-800 leading-relaxed font-['Nunito']">{en}</p>
        </div>
      )}
    </div>
  );
};

/* Hindi Voice Reply — uses browser SpeechSynthesis (works offline) */
const HindiVoiceBtn = ({ text }) => {
  const [speaking, setSpeaking] = useState(false);
  const utterRef = useRef(null);

  const toggle = useCallback(() => {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const plain = text.replace(/\[.*?\]/g, "").replace(/\n+/g, " ").trim();
    if (!plain) return;
    const utter = new SpeechSynthesisUtterance(plain);
    utter.lang = "hi-IN";
    utter.rate = 0.95;
    utter.pitch = 1;
    // Try to pick a Hindi voice
    const voices = window.speechSynthesis.getVoices();
    const hiVoice = voices.find((v) => v.lang.startsWith("hi"));
    if (hiVoice) utter.voice = hiVoice;
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    utterRef.current = utter;
    window.speechSynthesis.speak(utter);
    setSpeaking(true);
  }, [text, speaking]);

  useEffect(() => {
    return () => window.speechSynthesis.cancel();
  }, []);

  return (
    <button
      data-testid="hindi-voice-btn"
      onClick={toggle}
      className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${
        speaking
          ? "bg-[#000080] text-white voice-pulse"
          : "bg-[#F0F0F8] text-[#000080] hover:bg-[#E6E6F2]"
      }`}
      title={speaking ? "Stop" : "सुनें (Hindi)"}
    >
      {speaking ? <VolumeX size={13} /> : <Volume2 size={13} />}
    </button>
  );
};

/* Animated Double Ticks */
const TickStatus = ({ status }) => {
  const isRead = status === "read";
  const isDelivered = status === "delivered" || isRead;

  return (
    <span data-testid={`tick-${isRead ? "blue" : "grey"}`} className="inline-flex items-center">
      {isDelivered ? (
        <CheckCheck
          size={14}
          className={`transition-all duration-500 ${
            isRead ? "text-[#000080] tick-read-anim" : "text-gray-400 tick-deliver-anim"
          }`}
        />
      ) : (
        <CheckIcon
          size={14}
          className="text-gray-400 tick-sent-anim"
        />
      )}
    </span>
  );
};

/* WhatsApp Share Button — copies share text to clipboard */
const WhatsAppShareBtn = ({ pdfUrl, schemeName }) => {
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    const text = `Mera Nagarik Sahayak report! Eligible for ${schemeName}. Download PDF: ${pdfUrl}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: "Nagarik Sahayak Report", text, url: pdfUrl });
        return;
      } catch {}
    }
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  return (
    <button
      data-testid="whatsapp-share-btn"
      onClick={handleShare}
      className={`w-full flex items-center gap-2 px-4 py-2.5 text-white rounded-xl transition-all hover:-translate-y-0.5 shadow-md ${copied ? "bg-[#128C7E]" : "bg-[#25D366] hover:bg-[#1DA851]"}`}
    >
      <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 flex-shrink-0">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
        <path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.5.5 0 00.612.612l4.458-1.495A11.952 11.952 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.37 0-4.567-.702-6.413-1.907l-.446-.28-3.092 1.036 1.036-3.092-.28-.446A9.955 9.955 0 012 12C2 6.486 6.486 2 12 2s10 4.486 10 10-4.486 10-10 10z" />
      </svg>
      <div>
        <span className="text-xs font-bold font-['Mukta'] block">{copied ? "कॉपी हो गया! WhatsApp में पेस्ट करें" : "WhatsApp पर शेयर करें"}</span>
        <span className="text-[10px] opacity-75 font-['Nunito']">{copied ? "Copied! Paste in WhatsApp" : "Copy share text to clipboard"}</span>
      </div>
      {copied ? <CheckCheck size={14} className="ml-auto" /> : <Share2 size={14} className="ml-auto" />}
    </button>
  );
};

const MultiPdfDownloadBlock = ({ pdfUrls, userId, backendUrl }) => {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    setError("");
    setDone(false);

    // Extract PDF IDs for zip fallback
    const pdfIds = pdfUrls.map((p) => {
      const parts = (p.pdf_url || "").split("/");
      return parts[parts.length - 1] || "";
    }).filter(Boolean);

    try {
      // Strategy: fetch each PDF as blob and trigger download via <a> with stagger
      let successCount = 0;
      for (let i = 0; i < pdfUrls.length; i++) {
        const pdfItem = pdfUrls[i];
        const url = `${backendUrl}${pdfItem.pdf_url}`;
        const fileName = `${(pdfItem.scheme_name || "Form").replace(/\s+/g, "_")}_Form.pdf`;
        try {
          const resp = await fetch(url);
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const blob = await resp.blob();
          const blobUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = blobUrl;
          link.download = fileName;
          link.style.display = "none";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(blobUrl);
          successCount++;
        } catch {
          // Individual file failed — continue, will fallback to zip
        }
        // 500ms stagger between downloads
        if (i < pdfUrls.length - 1) {
          await new Promise((r) => setTimeout(r, 500));
        }
      }

      if (successCount === pdfUrls.length) {
        // All downloaded successfully
        setDone(true);
        // Track success
        try {
          await api.get(`/download-all?user_id=${userId || ""}&count=${pdfUrls.length}`);
        } catch {}
      } else {
        // Some failed — fallback to zip download
        const zipUrl = `${backendUrl}/api/download-all-zip?pdf_ids=${encodeURIComponent(pdfIds.join(","))}&user_id=${encodeURIComponent(userId || "")}`;
        try {
          const resp = await fetch(zipUrl);
          if (!resp.ok) throw new Error(`ZIP HTTP ${resp.status}`);
          const blob = await resp.blob();
          const blobUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = blobUrl;
          link.download = "Nagarik_Sahayak_Forms.zip";
          link.style.display = "none";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(blobUrl);
          setDone(true);
        } catch {
          setError("डाउनलोड विफल हुआ। कृपया पुनः प्रयास करें।");
          // Track error
          try {
            await api.get(`/download-all?user_id=${userId || ""}&count=0`);
          } catch {}
        }
      }
    } catch {
      setError("नेटवर्क त्रुटि। कृपया इंटरनेट जांचें और पुनः प्रयास करें।");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="mt-2.5 space-y-2">
      <button
        data-testid="pdf-download-all-btn"
        onClick={handleDownload}
        disabled={downloading}
        className={`w-full flex items-center gap-3 px-4 py-3 text-white rounded-xl transition-all shadow-md ${
          done
            ? "bg-[#16a34a]"
            : downloading
            ? "bg-gray-400 cursor-wait"
            : "bg-[#16a34a] hover:bg-[#15803d] hover:-translate-y-0.5"
        }`}
      >
        <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
          {downloading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : done ? (
            <Check size={18} />
          ) : (
            <FileDown size={18} />
          )}
        </div>
        <div className="flex-1 text-left">
          <span className="text-sm font-bold font-['Mukta'] block">
            {done ? "डाउनलोड पूर्ण!" : downloading ? "डाउनलोड हो रहा है..." : `सभी ${pdfUrls.length} फॉर्म डाउनलोड करें`}
          </span>
          <ul className="mt-0.5">
            {pdfUrls.map((p, i) => (
              <li key={i} className="text-[10px] opacity-90 font-['Nunito'] leading-tight">
                {i + 1}. {p.scheme_name}
              </li>
            ))}
          </ul>
        </div>
        {!downloading && !done && <Download size={16} className="flex-shrink-0 opacity-80" />}
      </button>
      {error && (
        <p data-testid="download-error-msg" className="text-xs text-red-600 font-['Mukta'] px-1">{error}</p>
      )}
      <WhatsAppShareBtn pdfUrl={`${backendUrl}${pdfUrls[0].pdf_url}`} schemeName={
        pdfUrls.map(p => p.scheme_name).join(", ")
      } />
    </div>
  );
};

export const ChatBubble = ({ message }) => {
  const isUser = message.role === "user";
  const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;
  const isTranscription = message.type === "transcription";
  const hasPdf = !!message.pdf_url;
  const isPdfReport = message.type === "pdf_report";
  const backendUrl = process.env.REACT_APP_BACKEND_URL;

  return (
    <div
      data-testid={`chat-bubble-${message.role}`}
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in-up`}
    >
      <div
        className={`relative max-w-[85%] px-4 py-2.5 ${
          isUser
            ? "bg-[#FFF0E0] rounded-2xl rounded-tr-sm border border-orange-100"
            : "bg-white rounded-2xl rounded-tl-sm border border-gray-100 shadow-sm"
        }`}
      >
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#FF9933]" />
            <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">नागरिक सहायक</span>
            <div className="ml-auto">
              <HindiVoiceBtn text={message.content} />
            </div>
          </div>
        )}

        {hasToolCalls && message.tool_calls.map((tc, i) => <ToolCallTrace key={i} toolCall={tc} />)}

        {isTranscription ? (
          <TranscriptionBlock message={message} />
        ) : (
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-line font-['Nunito']">{escapeHtml(message.content)}</p>
        )}

        {/* PDF Download — ALL eligible forms at once */}
        {message.pdf_urls && message.pdf_urls.length > 0 ? (
          <MultiPdfDownloadBlock pdfUrls={message.pdf_urls} userId={message.user_id} backendUrl={backendUrl} />
        ) : (hasPdf || isPdfReport) && message.pdf_url ? (
          <div className="mt-2.5 space-y-2">
            <a
              href={`${backendUrl}${message.pdf_url}`}
              data-testid="pdf-download-btn"
              className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-[#FF9933] to-[#FF8000] hover:from-[#FF8800] hover:to-[#E67300] text-white rounded-xl transition-all hover:-translate-y-0.5 shadow-md"
            >
              <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
                <FileDown size={18} />
              </div>
              <div>
                <span className="text-sm font-bold font-['Mukta'] block">PDF डाउनलोड करें</span>
                <span className="text-[10px] opacity-90 font-['Nunito']">Pre-filled Application Form</span>
              </div>
              <Download size={16} className="ml-auto opacity-80" />
            </a>
            <WhatsAppShareBtn pdfUrl={`${backendUrl}${message.pdf_url}`} schemeName={
              message.eligibility_results?.find(r => r.eligible)?.scheme || "Government Scheme"
            } />
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-1 mt-1">
          <span className="text-[10px] text-gray-400">{formatTime(message.created_at)}</span>
          {isUser && <TickStatus status={message.status} />}
        </div>
      </div>
    </div>
  );
};

function formatTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
}

export const TypingIndicator = () => (
  <div data-testid="typing-indicator" className="flex justify-start animate-fade-in-up">
    <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-gray-100 shadow-sm">
      <div className="flex items-center gap-1.5 mb-1">
        <div className="w-1.5 h-1.5 rounded-full bg-[#FF9933]" />
        <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">नागरिक सहायक</span>
      </div>
      <div className="flex gap-1.5 py-1">
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
      </div>
    </div>
  </div>
);

const TOOL_STEPS = [
  { icon: Search, text: "Reading Vidyasiri Scholarship PDF...", textHi: "विद्यासिरी छात्रवृत्ति PDF पढ़ रहे हैं..." },
  { icon: ClipboardCheck, text: "Checking eligibility criteria...", textHi: "पात्रता मानदंड जांच रहे हैं..." },
  { icon: FileOutput, text: "Generating filled application form...", textHi: "भरा हुआ आवेदन फॉर्म तैयार कर रहे हैं..." },
];

export const ToolProgressIndicator = () => {
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    const timers = TOOL_STEPS.map((_, i) =>
      setTimeout(() => setVisibleCount(i + 1), i * 650)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div data-testid="tool-progress-indicator" className="flex justify-start animate-fade-in-up">
      <div className="relative max-w-[85%] bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-gray-100 shadow-sm overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-[2px] tool-shimmer-bar" />
        <div className="flex items-center gap-1.5 mb-2.5">
          <div className="w-1.5 h-1.5 rounded-full bg-[#FF9933]" />
          <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">नागरिक सहायक</span>
          <Loader2 size={12} className="ml-1 text-[#FF9933] animate-spin" />
          <span data-testid="agent-thinking-text" className="text-[10px] text-[#FF9933] font-semibold font-['Mukta'] ml-0.5">Agent is thinking...</span>
        </div>
        <div className="space-y-2">
          {TOOL_STEPS.map((step, i) => {
            const Icon = step.icon;
            const visible = i < visibleCount;
            const isLatest = i === visibleCount - 1;
            return (
              <div
                key={i}
                data-testid={`tool-step-${i}`}
                className={`flex items-center gap-2.5 transition-all duration-500 ${
                  visible ? "tool-step-enter opacity-100" : "opacity-0 h-0 overflow-hidden"
                }`}
              >
                <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors duration-300 ${
                  isLatest ? "bg-[#FF9933]/15 tool-icon-pulse" : "bg-[#E6E6F2]"
                }`}>
                  {isLatest ? <Loader2 size={13} className="text-[#FF9933] animate-spin" /> : <Icon size={13} className="text-[#000080]" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-['Nunito'] leading-tight transition-colors duration-300 ${isLatest ? "text-gray-800 font-semibold" : "text-gray-400"}`}>
                    {step.textHi}
                  </p>
                  <p className={`text-[10px] font-['Nunito'] leading-tight transition-colors duration-300 ${isLatest ? "text-gray-500" : "text-gray-300"}`}>
                    {step.text}
                  </p>
                </div>
                {!isLatest && visible && <Check size={13} className="text-green-500 flex-shrink-0 tool-check-pop" />}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
