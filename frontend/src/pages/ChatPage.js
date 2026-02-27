import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import { ChatBubble, TypingIndicator, ToolProgressIndicator } from "../components/ChatBubble";
import { SchemeSelector } from "../components/SchemeSelector";
import { SmartProfiler } from "../components/SmartProfiler";
import { sendMessage, getChatHistory, transcribeAudio, uploadPdf, resetChat } from "../lib/api";
import { toast } from "sonner";
import { SendHorizontal, Mic, MicOff, Loader2, Paperclip } from "lucide-react";

const RECORD_DURATION = 5; // seconds

export default function ChatPage({ userId, language = "hi" }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordCountdown, setRecordCountdown] = useState(0);
  const [initialLoad, setInitialLoad] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sttLang, setSttLang] = useState(() => localStorage.getItem("ns_stt_lang") || "hi");
  const [v2Mode, setV2Mode] = useState("idle"); // idle | selecting | profiling | complete
  const [selectedSchemes, setSelectedSchemes] = useState([]);
  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const countdownRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (userId) {
      getChatHistory(userId)
        .then((r) => {
          setMessages(r.data || []);
          setInitialLoad(false);
        })
        .catch(() => setInitialLoad(false));
    }
  }, [userId]);

  // Handle prefill from HomePage
  useEffect(() => {
    if (location.state?.prefill && !initialLoad) {
      setInput(location.state.prefill);
    }
    if (location.state?.startVoice && !initialLoad) {
      startRecording();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialLoad, location.state]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);

    // Show user message immediately with "sent" status
    const tempUserMsg = {
      id: `temp-${Date.now()}`, user_id: userId, role: "user",
      content: text, status: "sent",
      created_at: new Date().toISOString(), tool_calls: [],
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await sendMessage(userId, text, language);
      const { user_message, bot_message } = res.data;
      // Replace temp msg with real one (status=read) and add bot reply
      setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), user_message, bot_message]);
    } catch {
      // Mark temp as failed
      setMessages((prev) => prev.map((m) => m.id === tempUserMsg.id ? { ...m, status: "sent" } : m));
      toast.error("Message failed to send");
    } finally {
      setLoading(false);
    }
  };

  const startRecording = useCallback(async () => {
    if (isRecording || loading) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (countdownRef.current) clearInterval(countdownRef.current);
        setRecordCountdown(0);
        setIsRecording(false);
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size > 0) {
          await processTranscription(blob);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordCountdown(RECORD_DURATION);
      toast.info(`${RECORD_DURATION}s रिकॉर्डिंग शुरू... बोलें`);

      // Countdown ticker
      let remaining = RECORD_DURATION;
      countdownRef.current = setInterval(() => {
        remaining -= 1;
        setRecordCountdown(remaining);
        if (remaining <= 0) {
          clearInterval(countdownRef.current);
        }
      }, 1000);

      // Auto-stop after 5 seconds
      timerRef.current = setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
          mediaRecorderRef.current.stop();
        }
      }, RECORD_DURATION * 1000);
    } catch (err) {
      toast.error("माइक्रोफोन एक्सेस दें — ब्राउज़र सेटिंग्स में अनुमति चालू करें", { duration: 5000 });
    }
  }, [isRecording, loading]);

  const stopRecording = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  };

  const processTranscription = async (blob) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");
      formData.append("user_id", userId);
      formData.append("language", sttLang);

      const res = await transcribeAudio(formData);
      if (res.data.success) {
        const { user_message, bot_message } = res.data;
        setMessages((prev) => [...prev, user_message, bot_message]);

        const isMock = res.data.is_mock;
        if (isMock) {
          toast.info("Demo mode — mock transcript used");
        } else {
          toast.success(`Sarvam Saaras v3 (${sttLang === "hi" ? "हिंदी" : "English"})`);
        }
      } else {
        toast.error("Transcription failed");
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || "Transcription failed";
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF files are accepted");
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("user_id", userId);
      const res = await uploadPdf(formData);
      if (res.data.success) {
        const confirmMsg = {
          id: `upload-${Date.now()}`, user_id: userId, role: "assistant",
          content: `PDF uploaded successfully: ${res.data.filename}\nYou can now ask me questions about this document.`,
          status: "delivered", created_at: new Date().toISOString(), tool_calls: [],
        };
        setMessages((prev) => [...prev, confirmMsg]);
        toast.success("PDF uploaded successfully");
      }
    } catch {
      toast.error("PDF upload failed");
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleNewChat = async () => {
    try {
      await resetChat(userId);
      setMessages([]);
      setInput("");
      setV2Mode("idle");
      setSelectedSchemes([]);
      toast.success("नई चैट शुरू हो गई!");
    } catch {
      toast.error("Chat reset failed");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div data-testid="chat-page" className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader title="नागरिक सहायक" onMenuClick={() => setSidebarOpen(true)} onNewChat={handleNewChat} />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 max-w-md mx-auto w-full pb-36">
        {/* V2 Flow: Scheme Selection (shown when no messages and idle) */}
        {messages.length === 0 && !initialLoad && v2Mode === "idle" && (
          <div className="animate-fade-in-up">
            <div className="text-center py-4 mb-2">
              <img
                src="/logo.png"
                alt="Nagarik Sahayak"
                className="w-14 h-14 mx-auto mb-2 rounded-xl"
                onError={(e) => { e.target.style.display = "none"; }}
              />
              <h3 className="text-base font-bold text-[#000080] font-['Mukta']">
                नमस्ते! नागरिक सहायक में आपका स्वागत है
              </h3>
              <p className="text-xs text-gray-400 font-['Nunito'] mt-1">
                सरकारी योजनाओं के लिए आवेदन फॉर्म भरने में सहायता
              </p>
            </div>
            <SchemeSelector
              userId={userId}
              onSchemesSelected={(schemes) => {
                setSelectedSchemes(schemes);
                setV2Mode("profiling");
                // Add system message
                setMessages((prev) => [
                  ...prev,
                  {
                    id: `sys-${Date.now()}`,
                    role: "assistant",
                    content: `आपने ${schemes.length} योजना(एं) चुनी हैं:\n${schemes.map((s, i) => `${i + 1}. ${s}`).join("\n")}\n\nअब हम आपकी प्रोफ़ाइल पूरी करेंगे। कृपया नीचे दिए गए सवालों का जवाब दें।`,
                    created_at: new Date().toISOString(),
                  },
                ]);
              }}
            />
            {/* Legacy chat option */}
            <div className="text-center mt-4 pt-3 border-t border-gray-100">
              <p className="text-[10px] text-gray-400 font-['Nunito'] mb-1">या बातचीत से शुरू करें</p>
              <button
                data-testid="start-chat-btn"
                onClick={async () => {
                  setV2Mode("chat");
                  setLoading(true);
                  try {
                    const res = await sendMessage(userId, "namaste", language);
                    setMessages([res.data.user_message, res.data.bot_message]);
                  } catch {}
                  setLoading(false);
                }}
                className="text-xs text-[#000080] font-bold font-['Mukta'] hover:underline"
              >
                बातचीत शुरू करें
              </button>
            </div>
          </div>
        )}

        {/* V2 Smart Profiler */}
        {v2Mode === "profiling" && (
          <div className="mb-4">
            <div className="space-y-3 stagger-children">
              {messages.map((msg) => (
                <ChatBubble key={msg.id} message={msg} />
              ))}
            </div>
            <div className="mt-3">
              <SmartProfiler
                userId={userId}
                schemeNames={selectedSchemes}
                onMessage={(msg) => setMessages((prev) => [...prev, { ...msg, id: `p-${Date.now()}-${Math.random()}` }])}
                onComplete={(data) => {
                  setV2Mode("complete");
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: `done-${Date.now()}`,
                      role: "assistant",
                      content: `${data.count} आवेदन फॉर्म सफलतापूर्वक तैयार हो गए! ऊपर डाउनलोड बटन से डाउनलोड करें।`,
                      created_at: new Date().toISOString(),
                      pdf_urls: data.pdf_urls,
                      user_id: userId,
                    },
                  ]);
                }}
              />
            </div>
          </div>
        )}

        {/* Regular chat messages (legacy or v2 complete) */}
        {(v2Mode === "chat" || v2Mode === "complete") && (
          <div className="space-y-3 stagger-children">
            {messages.map((msg) => (
              <ChatBubble key={msg.id} message={msg} />
            ))}
          </div>
        )}

        {loading && <ToolProgressIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="fixed bottom-14 left-0 right-0 bg-white border-t border-gray-100 px-3 py-2.5 z-30">
        <div className="max-w-md mx-auto flex items-center gap-2">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handleFileUpload}
            data-testid="pdf-file-input"
          />

          {/* Paperclip Button */}
          <button
            data-testid="chat-attach-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || isRecording}
            title="PDF अपलोड करें"
            className="w-10 h-10 rounded-full flex items-center justify-center transition-all flex-shrink-0 bg-gray-100 text-gray-500 hover:bg-[#FFF0E0] hover:text-[#FF9933]"
          >
            <Paperclip size={18} />
          </button>

          {/* Language Toggle for STT */}
          <button
            data-testid="stt-lang-toggle"
            onClick={() => {
              const next = sttLang === "hi" ? "en" : "hi";
              setSttLang(next);
              localStorage.setItem("ns_stt_lang", next);
              toast.info(next === "hi" ? "Voice: हिंदी" : "Voice: English", { duration: 1500 });
            }}
            disabled={loading || isRecording}
            title={sttLang === "hi" ? "Voice language: Hindi — click to switch" : "Voice language: English — click to switch"}
            className="w-10 h-10 rounded-full flex items-center justify-center transition-all flex-shrink-0 bg-[#E6E6F2] text-[#000080] hover:bg-[#D0D0E8] active:scale-95 text-xs font-bold font-['Mukta']"
          >
            {sttLang === "hi" ? "हि" : "EN"}
          </button>

          {/* Mic Button with countdown */}
          <button
            data-testid="chat-mic-btn"
            onClick={isRecording ? stopRecording : startRecording}
            disabled={loading && !isRecording}
            title={isRecording ? "रिकॉर्डिंग बंद करें" : "बोलकर पूछें"}
            className={`relative w-10 h-10 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
              isRecording
                ? "bg-red-500 text-white recording-pulse"
                : "bg-[#FFF0E0] text-[#FF9933] hover:bg-[#FFE0C0] active:scale-95"
            }`}
          >
            {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
            {isRecording && recordCountdown > 0 && (
              <span
                data-testid="mic-countdown"
                className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-white border-2 border-red-500 text-[10px] font-bold text-red-500 flex items-center justify-center"
              >
                {recordCountdown}
              </span>
            )}
          </button>

          {/* Text Input */}
          <input
            data-testid="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="अपना सवाल यहाँ लिखें..."
            disabled={loading || isRecording}
            className="flex-1 h-10 rounded-full bg-gray-50 border border-gray-200 px-4 text-sm font-['Nunito'] placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#FF9933] focus:border-transparent transition-all"
          />

          {/* Send Button */}
          <button
            data-testid="chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className={`w-10 h-10 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
              input.trim()
                ? "bg-[#FF9933] text-white shadow-md hover:bg-[#E68A00] hover:scale-105"
                : "bg-gray-100 text-gray-400"
            }`}
          >
            {loading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <SendHorizontal size={18} />
            )}
          </button>
        </div>
      </div>

      <BottomNav />
    </div>
  );
}
