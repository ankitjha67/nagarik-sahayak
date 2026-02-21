import { IndianFlag } from "./IndianFlag";
import { Menu, RotateCcw } from "lucide-react";

export const AppHeader = ({ title = "नागरिक सहायक", showBack, onBack, onMenuClick, onNewChat }) => (
  <header
    data-testid="app-header"
    className="sticky top-0 z-30 bg-white border-b border-gray-100 px-4 py-3"
  >
    <div className="max-w-md mx-auto flex items-center gap-3">
      {showBack ? (
        <button
          data-testid="header-back-btn"
          onClick={onBack}
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
          className="p-1.5 -ml-1 text-[#000080] hover:bg-gray-50 rounded-lg transition-colors"
        >
          <Menu size={20} />
        </button>
      ) : null}
      <IndianFlag size={30} />
      <h1
        data-testid="header-title"
        className="text-xl font-bold text-[#000080] font-['Mukta'] tracking-tight flex-1"
      >
        {title}
      </h1>
      {onNewChat && (
        <button
          data-testid="new-chat-btn"
          onClick={onNewChat}
          title="नई चैट शुरू करें"
          className="p-2 text-[#000080] hover:bg-[#FFF0E0] hover:text-[#FF9933] rounded-lg transition-all"
        >
          <RotateCcw size={18} />
        </button>
      )}
    </div>
  </header>
);
