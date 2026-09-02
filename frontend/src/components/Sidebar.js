import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { X, BarChart3, ExternalLink, Zap, Globe, GraduationCap, Download } from "lucide-react";

export const Sidebar = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const [analyticsStatus, setAnalyticsStatus] = useState(null);
  const [demoOn, setDemoOn] = useState(false);
  const [toggling, setToggling] = useState(false);
  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    if (isOpen) {
      if (!analyticsStatus) {
        fetch(`${API}/api/analytics/status`)
          .then((r) => r.json())
          .then(setAnalyticsStatus)
          .catch(() => setAnalyticsStatus({ enabled: false, dashboard_url: "https://app.agnost.ai" }));
      }
      fetch(`${API}/api/demo/status`)
        .then((r) => r.json())
        .then((d) => setDemoOn(d.demo_mode))
        .catch(() => {});
    }
  }, [isOpen, analyticsStatus, API]);

  const handleToggle = useCallback(async () => {
    setToggling(true);
    try {
      const res = await fetch(`${API}/api/demo/toggle`, { method: "POST" });
      const d = await res.json();
      setDemoOn(d.demo_mode);
    } catch {}
    setToggling(false);
  }, [API]);

  return (
    <>
      {isOpen && (
        <div
          data-testid="sidebar-overlay"
          role="presentation"
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 transition-opacity"
          onClick={onClose}
        />
      )}

      <div
        data-testid="sidebar-panel"
        role="dialog"
        aria-label="Navigation menu"
        className={`fixed top-0 left-0 h-full w-72 bg-white z-50 shadow-2xl transform transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <span className="text-base font-bold text-[#000080] font-['Mukta']">Menu</span>
          <button
            data-testid="sidebar-close-btn"
            onClick={onClose}
            aria-label="Close menu"
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="px-3 py-4 space-y-1">
          {/* Analytics Dashboard */}
          <a
            data-testid="sidebar-analytics-link"
            href={analyticsStatus?.dashboard_url || "https://app.agnost.ai"}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-3 rounded-xl hover:bg-[#FFF7ED] group transition-colors"
          >
            <div className="w-9 h-9 rounded-lg bg-[#FFF0E0] flex items-center justify-center group-hover:bg-[#FF9933]/20 transition-colors">
              <BarChart3 size={18} className="text-[#FF9933]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-[#000080] font-['Nunito']">Analytics Dashboard</span>
                <ExternalLink size={12} className="text-gray-400 flex-shrink-0" />
              </div>
              <span className="text-xs text-gray-400 font-['Nunito']">Agnost AI</span>
            </div>
            {analyticsStatus?.enabled && (
              <span data-testid="analytics-active-badge" className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
            )}
          </a>

          {/* Demo Mode Toggle */}
          <div
            data-testid="demo-toggle-row"
            className="flex items-center gap-3 px-3 py-3 rounded-xl hover:bg-amber-50 transition-colors"
          >
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors ${demoOn ? "bg-amber-100" : "bg-gray-100"}`}>
              <Zap size={18} className={demoOn ? "text-amber-500" : "text-gray-400"} />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-semibold text-[#000080] font-['Nunito'] block">Demo Mode</span>
              <span className="text-xs text-gray-400 font-['Nunito']">
                {demoOn ? "Stage-ready" : "Off"}
              </span>
            </div>
            <button
              data-testid="demo-toggle-btn"
              onClick={handleToggle}
              disabled={toggling}
              aria-label={demoOn ? "Disable demo mode" : "Enable demo mode"}
              className={`relative w-11 h-6 rounded-full transition-colors duration-300 focus:outline-none ${
                demoOn ? "bg-amber-400" : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-md transition-transform duration-300 ${
                  demoOn ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-100 my-2 mx-3" />

          {/* Discovery Dashboard */}
          <button
            onClick={() => { onClose(); navigate("/discovery"); }}
            className="flex items-center gap-3 px-3 py-3 rounded-xl hover:bg-blue-50 group transition-colors w-full text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
              <Globe size={18} className="text-[#000080]" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-semibold text-[#000080] font-['Nunito'] block">
                Scheme Discovery
              </span>
              <span className="text-xs text-gray-400 font-['Nunito']">
                Crawl portals, view health
              </span>
            </div>
          </button>

          {/* Exams */}
          <button
            onClick={() => { onClose(); navigate("/exams"); }}
            className="flex items-center gap-3 px-3 py-3 rounded-xl hover:bg-purple-50 group transition-colors w-full text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center group-hover:bg-purple-100 transition-colors">
              <GraduationCap size={18} className="text-purple-700" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-semibold text-[#000080] font-['Nunito'] block">
                Exam Alerts
              </span>
              <span className="text-xs text-gray-400 font-['Nunito']">
                Deadlines, admit cards, results
              </span>
            </div>
          </button>
        </nav>

        <div className="absolute bottom-0 left-0 right-0 px-5 py-4 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 font-['Nunito'] text-center">Powered by Agnost AI</p>
        </div>
      </div>
    </>
  );
};
