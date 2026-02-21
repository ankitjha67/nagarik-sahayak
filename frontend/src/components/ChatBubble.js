import { useState, useRef } from "react";
import { CheckCheck, FileSearch, FileText, Check, X, Languages, Play, Pause } from "lucide-react";

const ToolCallTrace = ({ toolCall }) => (
  <div
    data-testid="mcp-tool-trace"
    className="mb-2.5 rounded-xl border border-[#E6E6F2] bg-[#F8F8FC] overflow-hidden"
  >
    {/* Tool header */}
    <div className="flex items-center gap-2 px-3 py-1.5 bg-[#E6E6F2] border-b border-[#D4D4E8]">
      <FileSearch size={13} className="text-[#000080]" />
      <span className="text-[11px] font-bold text-[#000080] font-['Mukta'] tracking-wide uppercase">
        MCP Tool: {toolCall.tool_name}
      </span>
    </div>

    {/* Scanned documents */}
    <div className="px-3 py-2 space-y-1">
      <p className="text-[10px] font-semibold text-gray-500 font-['Nunito'] uppercase tracking-wider">
        Documents scanned
      </p>
      {toolCall.documents_scanned?.map((doc, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <FileText size={12} className="text-[#FF9933] flex-shrink-0" />
          <span className="text-[11px] text-gray-600 font-['Nunito']">{doc}</span>
        </div>
      ))}
    </div>

    {/* Match result */}
    <div className="px-3 py-1.5 border-t border-[#E6E6F2] flex items-center gap-1.5">
      {toolCall.match_found ? (
        <>
          <div className="w-4 h-4 rounded-full bg-green-100 flex items-center justify-center">
            <Check size={10} className="text-green-600" />
          </div>
          <span className="text-[11px] font-semibold text-green-700 font-['Nunito']">
            Match found
          </span>
        </>
      ) : (
        <>
          <div className="w-4 h-4 rounded-full bg-red-100 flex items-center justify-center">
            <X size={10} className="text-red-500" />
          </div>
          <span className="text-[11px] font-semibold text-red-600 font-['Nunito']">
            No match in documents
          </span>
        </>
      )}
    </div>
  </div>
);

const TranscriptionBlock = ({ message }) => {
  const hi = message.transcript_hi || "";
  const en = message.transcript_en || "";
  const audioUrl = message.audio_url || "";
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

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
              playing
                ? "bg-[#000080] text-white"
                : "bg-[#FFF0E0] text-[#FF9933] hover:bg-[#FFE4C4]"
            }`}
          >
            {playing ? <Pause size={12} /> : <Play size={12} className="ml-0.5" />}
          </button>
        )}
      </div>

      {hi && (
        <div data-testid="transcript-hindi" className="rounded-lg bg-[#FFF8F0] border border-orange-100 px-3 py-2">
          <span className="text-[10px] font-bold text-[#000080] font-['Mukta'] uppercase tracking-wider block mb-0.5">
            Hindi
          </span>
          <p className="text-sm text-gray-800 leading-relaxed font-['Mukta']">{hi}</p>
        </div>
      )}

      {en && (
        <div data-testid="transcript-english" className="rounded-lg bg-[#F0F0F8] border border-[#D4D4E8] px-3 py-2">
          <span className="text-[10px] font-bold text-[#000080] font-['Nunito'] uppercase tracking-wider block mb-0.5">
            English
          </span>
          <p className="text-sm text-gray-800 leading-relaxed font-['Nunito']">{en}</p>
        </div>
      )}
    </div>
  );
};

export const ChatBubble = ({ message }) => {
  const isUser = message.role === "user";
  const isRead = message.status === "read";
  const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;
  const isTranscription = message.type === "transcription";

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
            <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">
              नागरिक सहायक
            </span>
          </div>
        )}

        {/* MCP Tool Call Trace */}
        {hasToolCalls &&
          message.tool_calls.map((tc, i) => (
            <ToolCallTrace key={i} toolCall={tc} />
          ))}

        {/* Transcription dual-language block */}
        {isTranscription ? (
          <TranscriptionBlock message={message} />
        ) : (
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-line font-['Nunito']">
            {message.content}
          </p>
        )}

        <div className="flex items-center justify-end gap-1 mt-1">
          <span className="text-[10px] text-gray-400">
            {formatTime(message.created_at)}
          </span>
          {isUser && (
            <CheckCheck
              size={14}
              data-testid={`tick-${isRead ? "blue" : "grey"}`}
              className={`${
                isRead ? "text-[#000080]" : "text-gray-400"
              } transition-colors`}
            />
          )}
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
        <span className="text-[11px] font-semibold text-[#000080] font-['Mukta']">
          नागरिक सहायक
        </span>
      </div>
      <div className="flex gap-1.5 py-1">
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
        <div className="w-2 h-2 rounded-full bg-gray-400 typing-dot" />
      </div>
    </div>
  </div>
);
