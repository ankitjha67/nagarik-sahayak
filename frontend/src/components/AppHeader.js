import { Menu, RotateCcw } from "lucide-react";
import { LanguagePicker } from "./LanguagePicker";
import { useLanguage } from "../lib/i18n";

export const AppHeader = ({ showBack, onBack, onMenuClick, onNewChat }) => {
  const { tx } = useLanguage();
  return (
  <header
    data-testid="app-header"
    className="sticky top-0 z-30 bg-white border-b border-gray-100 px-4 py-2"
  >
    <div className="max-w-md mx-auto flex items-center gap-3">
      {showBack ? (
        <button
          data-testid="header-back-btn"
          onClick={onBack}
          aria-label={tx("header.goBack")}
          className="p-1 -ml-1 text-[#000080] hover:bg-gray-50 rounded-full transition-colors"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6"/>
          </svg>
        </button>
      ) : onMenuClick ? (
        <button
          data-testid="header-menu-btn"
          onClick={onMenuClick}
          aria-label={tx("header.openMenu")}
          className="p-1.5 -ml-1 text-[#000080] hover:bg-gray-50 rounded-lg transition-colors"
        >
          <Menu size={20} />
        </button>
      ) : null}
      <img src="/logo.png" alt="Nagarik Sahayak" className="h-10 w-auto object-contain" />
      <div className="flex-1" />
      {/* In the header on every page rather than buried in settings. Someone who
          cannot read the current language cannot navigate to a settings screen
          to change it. */}
      <LanguagePicker compact />
      {onNewChat && (
        <button
          data-testid="new-chat-btn"
          onClick={onNewChat}
          title={tx("header.newChat")}
          aria-label={tx("header.newChat")}
          className="p-2 text-[#000080] hover:bg-[#FFF0E0] hover:text-[#FF9933] rounded-lg transition-all"
        >
          <RotateCcw size={18} />
        </button>
      )}
    </div>
  </header>
  );
};
