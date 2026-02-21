import { IndianFlag } from "./IndianFlag";

export const AppHeader = ({ title = "नागरिक सहायक", showBack, onBack }) => (
  <header
    data-testid="app-header"
    className="sticky top-0 z-30 bg-white border-b border-gray-100 px-4 py-3"
  >
    <div className="max-w-md mx-auto flex items-center gap-3">
      {showBack && (
        <button
          data-testid="header-back-btn"
          onClick={onBack}
          className="p-1 -ml-1 text-[#000080] hover:bg-gray-50 rounded-full transition-colors"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6"/>
          </svg>
        </button>
      )}
      <IndianFlag size={30} />
      <h1
        data-testid="header-title"
        className="text-xl font-bold text-[#000080] font-['Mukta'] tracking-tight"
      >
        {title}
      </h1>
    </div>
  </header>
);
