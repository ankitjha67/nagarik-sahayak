import { useState, useEffect } from "react";
import { X, BarChart3, ExternalLink } from "lucide-react";

export const Sidebar = ({ isOpen, onClose }) => {
  const [analyticsStatus, setAnalyticsStatus] = useState(null);

  useEffect(() => {
    if (isOpen && !analyticsStatus) {
      const API = process.env.REACT_APP_BACKEND_URL;
      fetch(`${API}/api/analytics/status`)
        .then((r) => r.json())
        .then(setAnalyticsStatus)
        .catch(() => setAnalyticsStatus({ enabled: false, dashboard_url: "https://app.agnost.ai" }));
    }
  }, [isOpen, analyticsStatus]);

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          data-testid="sidebar-overlay"
          className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <div
        data-testid="sidebar-panel"
        className={`fixed top-0 left-0 h-full w-72 bg-white z-50 shadow-2xl transform transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <span className="text-base font-bold text-[#000080] font-['Mukta']">
            Menu
          </span>
          <button
            data-testid="sidebar-close-btn"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Nav items */}
        <nav className="px-3 py-4 space-y-1">
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
                <span className="text-sm font-semibold text-[#000080] font-['Nunito']">
                  Analytics Dashboard
                </span>
                <ExternalLink size={12} className="text-gray-400 flex-shrink-0" />
              </div>
              <span className="text-xs text-gray-400 font-['Nunito']">
                Agnost AI &middot; Tool tracking
              </span>
            </div>
            {analyticsStatus?.enabled && (
              <span
                data-testid="analytics-active-badge"
                className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0"
              />
            )}
          </a>
        </nav>

        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 px-5 py-4 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 font-['Nunito'] text-center">
            Powered by Agnost AI
          </p>
        </div>
      </div>
    </>
  );
};
