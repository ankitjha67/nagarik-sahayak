import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import { getChatHistory, getSchemes, getExamAlerts, getDiscoveryStats } from "../lib/api";
import { Mic, MessageCircle, BookOpen, ChevronRight, Sparkles, GraduationCap, Clock, Globe, Search as SearchIcon } from "lucide-react";

export default function HomePage({ userId }) {
  const navigate = useNavigate();
  const [recentChats, setRecentChats] = useState([]);
  const [schemes, setSchemes] = useState([]);
  const [examAlerts, setExamAlerts] = useState([]);
  const [discoveryStats, setDiscoveryStats] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (userId) {
      getChatHistory(userId).then((r) => {
        const msgs = r.data || [];
        setRecentChats(msgs.slice(-5).reverse());
      }).catch(() => {});
      getSchemes().then((r) => setSchemes(r.data || [])).catch(() => {});
      getExamAlerts(14).then((r) => setExamAlerts((r.data.alerts || []).slice(0, 3))).catch(() => {});
      getDiscoveryStats().then((r) => setDiscoveryStats(r.data)).catch(() => {});
    }
  }, [userId]);

  const handleMicClick = () => {
    navigate("/chat", { state: { startVoice: true } });
  };

  return (
    <div data-testid="home-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader onMenuClick={() => setSidebarOpen(true)} />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="max-w-md mx-auto px-4 pt-4">
        {/* Welcome Banner */}
        <div
          data-testid="welcome-banner"
          className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm mb-5 animate-fade-in-up"
        >
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#FFF0E0] flex items-center justify-center flex-shrink-0">
              <Sparkles size={20} className="text-[#FF9933]" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#000080] font-['Mukta']">
                नमस्ते! कैसे मदद करें?
              </h2>
              <p className="text-sm text-gray-500 font-['Nunito'] mt-0.5">
                Ask about government schemes, eligibility, or apply for services
              </p>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex gap-2 mt-4">
            {["योजनाएं", "पात्रता जांचें", "हेल्प"].map((label) => (
              <button
                key={label}
                data-testid={`quick-action-${label}`}
                onClick={() =>
                  navigate("/chat", { state: { prefill: label } })
                }
                className="px-3 py-1.5 rounded-full bg-[#FFF0E0] text-[#000080] text-xs font-semibold font-['Mukta'] border border-orange-100 hover:bg-[#FFE4C4] transition-colors"
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Mic FAB - Centered */}
        <div className="flex flex-col items-center mb-6 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          <button
            data-testid="mic-button"
            onClick={handleMicClick}
            className="w-20 h-20 rounded-full flex items-center justify-center shadow-xl transition-all duration-200 hover:scale-105 active:scale-95 bg-[#FF9933] mic-pulse"
          >
            <Mic size={32} className="text-white" strokeWidth={2.5} />
          </button>
          <p className="text-xs text-gray-400 mt-2 font-['Mukta']">
            बोलकर पूछें
          </p>
        </div>

        {/* Schemes Quick View */}
        <div className="mb-5 animate-fade-in-up" style={{ animationDelay: "0.15s" }}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-[#000080] font-['Mukta']">
              सरकारी योजनाएं
            </h3>
            <button
              data-testid="view-all-schemes-btn"
              onClick={() => navigate("/schemes")}
              className="text-xs text-[#FF9933] font-semibold flex items-center gap-0.5 hover:underline"
            >
              सभी देखें <ChevronRight size={14} />
            </button>
          </div>

          <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 no-scrollbar">
            {schemes.map((scheme) => (
              <button
                key={scheme.id}
                data-testid={`scheme-card-${scheme.id}`}
                onClick={() => navigate("/schemes")}
                className="flex-shrink-0 w-44 bg-white rounded-xl p-4 border border-gray-100 shadow-sm hover:shadow-md transition-all text-left"
              >
                <div className="w-8 h-8 rounded-lg bg-[#FFF0E0] flex items-center justify-center mb-2">
                  <BookOpen size={16} className="text-[#FF9933]" />
                </div>
                <p className="text-sm font-bold text-[#000080] font-['Mukta'] line-clamp-2 leading-tight">
                  {scheme.title_hi}
                </p>
                <p className="text-[11px] text-gray-400 mt-1 font-['Nunito'] line-clamp-1">
                  {scheme.title}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Exam Alerts */}
        {examAlerts.length > 0 && (
          <div className="mb-5 animate-fade-in-up" style={{ animationDelay: "0.17s" }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-bold text-[#000080] font-['Mukta']">
                परीक्षा अलर्ट
              </h3>
              <button
                onClick={() => navigate("/exams")}
                className="text-xs text-[#FF9933] font-semibold flex items-center gap-0.5 hover:underline"
              >
                सभी देखें <ChevronRight size={14} />
              </button>
            </div>
            <div className="space-y-2">
              {examAlerts.map((alert, idx) => (
                <button
                  key={idx}
                  onClick={() => navigate("/exams")}
                  className={`w-full text-left rounded-xl p-3 border transition-all hover:shadow-sm ${
                    alert.urgency === "critical" ? "bg-red-50 border-red-200" :
                    alert.urgency === "high" ? "bg-orange-50 border-orange-200" :
                    "bg-blue-50 border-blue-200"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Clock size={14} className={
                      alert.urgency === "critical" ? "text-red-600" :
                      alert.urgency === "high" ? "text-orange-600" :
                      "text-blue-600"
                    } />
                    <span className="text-sm font-semibold text-gray-800 font-['Mukta'] truncate">
                      {alert.exam_name}
                    </span>
                    {alert.days_left != null && (
                      <span className={`text-[10px] font-bold ml-auto flex-shrink-0 ${
                        alert.urgency === "critical" ? "text-red-700" : "text-orange-700"
                      }`}>
                        {alert.days_left}d left
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-0.5 ml-6">{alert.message_hi}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Discovery Stats */}
        {discoveryStats && discoveryStats.total_schemes > 0 && (
          <div className="mb-5 animate-fade-in-up" style={{ animationDelay: "0.19s" }}>
            <button
              onClick={() => navigate("/discovery")}
              className="w-full bg-gradient-to-r from-[#000080] to-[#1a1aab] rounded-xl p-4 text-white text-left hover:opacity-95 transition-opacity"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
                  <Globe size={20} />
                </div>
                <div>
                  <p className="text-sm font-bold font-['Mukta']">योजना खोज इंजन</p>
                  <p className="text-xs opacity-80 font-['Nunito']">
                    {discoveryStats.total_schemes} schemes from {Object.keys(discoveryStats.by_sector || {}).length} sectors
                  </p>
                </div>
                <ChevronRight size={18} className="ml-auto opacity-60" />
              </div>
            </button>
          </div>
        )}

        {/* Recent Chat */}
        <div className="animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-[#000080] font-['Mukta']">
              हाल की बातचीत
            </h3>
            <button
              data-testid="view-chat-btn"
              onClick={() => navigate("/chat")}
              className="text-xs text-[#FF9933] font-semibold flex items-center gap-0.5 hover:underline"
            >
              चैट करें <ChevronRight size={14} />
            </button>
          </div>

          {recentChats.length === 0 ? (
            <div className="bg-white rounded-xl p-6 border border-gray-100 text-center">
              <MessageCircle size={28} className="text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-400 font-['Nunito']">
                No conversations yet. Start chatting!
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentChats.map((msg) => (
                <button
                  key={msg.id}
                  data-testid={`recent-chat-${msg.id}`}
                  onClick={() => navigate("/chat")}
                  className="w-full bg-white rounded-xl p-3 border border-gray-100 text-left hover:shadow-sm transition-all flex items-center gap-3"
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      msg.role === "user"
                        ? "bg-[#FFF0E0]"
                        : "bg-[#E6E6F2]"
                    }`}
                  >
                    <MessageCircle
                      size={14}
                      className={
                        msg.role === "user"
                          ? "text-[#FF9933]"
                          : "text-[#000080]"
                      }
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 truncate font-['Nunito']">
                      {msg.content}
                    </p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {new Date(msg.created_at).toLocaleString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        day: "numeric",
                        month: "short",
                      })}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <BottomNav />
    </div>
  );
}
