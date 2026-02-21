import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { ChatBubble, TypingIndicator } from "../components/ChatBubble";
import { sendMessage, getChatHistory, transcribeAudio } from "../lib/api";
import { toast } from "sonner";
import { SendHorizontal, Mic, MicOff, Loader2 } from "lucide-react";

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
  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const countdownRef = useRef(null);

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

    try {
      const res = await sendMessage(userId, text, language);
      const { user_message, bot_message } = res.data;
      setMessages((prev) => [...prev, user_message, bot_message]);
    } catch {
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
    } catch {
      toast.error("Microphone access denied");
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

      const res = await transcribeAudio(formData);
      if (res.data.success) {
        const { user_message, bot_message } = res.data;
        setMessages((prev) => [...prev, user_message, bot_message]);

        const hi = res.data.transcript_hi || "";
        const en = res.data.transcript_en || "";
        if (hi || en) {
          toast.success("Transcribed via Sarvam Saaras v3");
        } else {
          toast.warning("No speech detected");
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

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div data-testid="chat-page" className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader title="नागरिक सहायक" />

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 max-w-md mx-auto w-full pb-36">
        {messages.length === 0 && !initialLoad && (
          <div className="text-center py-12 animate-fade-in-up">
            <div className="w-16 h-16 rounded-full bg-[#FFF0E0] flex items-center justify-center mx-auto mb-4">
              <Mic size={28} className="text-[#FF9933]" />
            </div>
            <h3 className="text-lg font-bold text-[#000080] font-['Mukta'] mb-1">
              बातचीत शुरू करें
            </h3>
            <p className="text-sm text-gray-400 font-['Nunito']">
              Type or tap mic to record 5s voice
            </p>
          </div>
        )}

        <div className="space-y-3 stagger-children">
          {messages.map((msg) => (
            <ChatBubble key={msg.id} message={msg} />
          ))}
        </div>

        {loading && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="fixed bottom-14 left-0 right-0 bg-white border-t border-gray-100 px-3 py-2.5 z-30">
        <div className="max-w-md mx-auto flex items-center gap-2">
          {/* Mic Button with countdown */}
          <button
            data-testid="chat-mic-btn"
            onClick={isRecording ? stopRecording : startRecording}
            disabled={loading && !isRecording}
            className={`relative w-10 h-10 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
              isRecording
                ? "bg-red-500 text-white recording-pulse"
                : "bg-gray-100 text-gray-500 hover:bg-[#FFF0E0] hover:text-[#FF9933]"
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
