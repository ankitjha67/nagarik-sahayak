import { useState, useEffect, Component } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import LoginPage from "@/pages/LoginPage";
import HomePage from "@/pages/HomePage";
import ChatPage from "@/pages/ChatPage";
import SchemesPage from "@/pages/SchemesPage";
import ExamsPage from "@/pages/ExamsPage";
import DiscoveryPage from "@/pages/DiscoveryPage";
import ProfilePage from "@/pages/ProfilePage";
import ReviewPage from "@/pages/ReviewPage";
import PrivacyPage from "@/pages/PrivacyPage";
import IdentityPage from "@/pages/IdentityPage";
import { LanguageProvider, useLanguage } from "@/lib/i18n";
import { FallbackBanner } from "@/components/LanguagePicker";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center px-6 bg-gray-50">
          <h1 className="text-xl font-bold text-red-600 mb-2">कुछ गलत हो गया</h1>
          <p className="text-sm text-gray-600 mb-4">Something went wrong. Please try again.</p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.href = "/";
            }}
            className="px-4 py-2 bg-[#FF9933] text-white rounded-lg font-semibold"
          >
            होम पेज पर जाएं
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// The routes live in their own component *inside* the LanguageProvider so the
// `language` each page receives is the provider's live value, not a copy frozen
// at mount. Before this split, App held its own `language` state that the
// language picker never updated — the picker changes the provider, not App — so
// switching language left every page keyed on the prop stuck in the old
// language until a full reload. Reading it from the provider here fixes every
// page at once.
function AppRoutes({ userId, onLogin, onLogout }) {
  const { code: language } = useLanguage();
  const isLoggedIn = !!userId;

  return (
    <BrowserRouter>
        {/* WCAG 2.4.1 — lets keyboard and screen-reader users bypass the
            header rather than tabbing through it on every page. */}
        <a href="#main-content" className="skip-to-content">
          मुख्य सामग्री पर जाएं / Skip to main content
        </a>
        <FallbackBanner />
        <ErrorBoundary>
        <main id="main-content">
        <Routes>
          <Route
            path="/"
            element={
              isLoggedIn ? <Navigate to="/home" replace /> : <LoginPage onLogin={onLogin} />
            }
          />
          <Route
            path="/home"
            element={
              isLoggedIn ? <HomePage userId={userId} language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/chat"
            element={
              isLoggedIn ? <ChatPage userId={userId} language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/schemes"
            element={
              isLoggedIn ? <SchemesPage userId={userId} language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/exams"
            element={
              isLoggedIn ? <ExamsPage userId={userId} language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/discovery"
            element={
              isLoggedIn ? <DiscoveryPage language={language} /> : <Navigate to="/" replace />
            }
          />
          {/* Reviewer console. Not behind the citizen login: reviewers are
              departmental staff who authenticate with their own credentials,
              and may never have a citizen account at all. */}
          <Route path="/review" element={<ReviewPage />} />
          <Route
            path="/privacy"
            element={
              isLoggedIn ? <PrivacyPage userId={userId} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/identity"
            element={
              isLoggedIn ? <IdentityPage userId={userId} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/profile"
            element={
              isLoggedIn ? (
                <ProfilePage userId={userId} onLogout={onLogout} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </main>
        </ErrorBoundary>
      </BrowserRouter>
  );
}

function App() {
  const [userId, setUserId] = useState(() => localStorage.getItem("ns_user_id") || null);
  // Phone is kept in localStorage for the auth flow; App no longer holds it in
  // state because nothing rendered here reads it.
  const initialLanguage = localStorage.getItem("ns_language") || "hi";

  const handleLogin = (uid, ph) => {
    setUserId(uid);
    localStorage.setItem("ns_user_id", uid);
    localStorage.setItem("ns_phone", ph);
  };

  const handleLogout = () => {
    setUserId(null);
    localStorage.removeItem("ns_user_id");
    localStorage.removeItem("ns_phone");
    localStorage.removeItem("ns_language");
  };

  return (
    <div className="App">
      {/* The language provider wraps the router, not each page: the chosen
          language sets document.documentElement.lang and dir, which must hold
          across navigation or a screen reader re-guesses the language on every
          route change. AppRoutes lives inside it so each page gets the live
          language, not a copy frozen at mount. */}
      <LanguageProvider initial={initialLanguage}>
        <AppRoutes userId={userId} onLogin={handleLogin} onLogout={handleLogout} />
      </LanguageProvider>
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
