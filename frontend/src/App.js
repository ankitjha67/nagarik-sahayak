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

function App() {
  const [userId, setUserId] = useState(() => localStorage.getItem("ns_user_id") || null);
  const [phone, setPhone] = useState(() => localStorage.getItem("ns_phone") || null);
  const [language, setLanguage] = useState(() => localStorage.getItem("ns_language") || "hi");

  const handleLogin = (uid, ph) => {
    setUserId(uid);
    setPhone(ph);
    localStorage.setItem("ns_user_id", uid);
    localStorage.setItem("ns_phone", ph);
  };

  const handleLogout = () => {
    setUserId(null);
    setPhone(null);
    localStorage.removeItem("ns_user_id");
    localStorage.removeItem("ns_phone");
    localStorage.removeItem("ns_language");
  };

  const isLoggedIn = !!userId;

  return (
    <div className="App">
      <BrowserRouter>
        <ErrorBoundary>
        <Routes>
          <Route
            path="/"
            element={
              isLoggedIn ? <Navigate to="/home" replace /> : <LoginPage onLogin={handleLogin} />
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
              isLoggedIn ? <SchemesPage language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/exams"
            element={
              isLoggedIn ? <ExamsPage language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/discovery"
            element={
              isLoggedIn ? <DiscoveryPage language={language} /> : <Navigate to="/" replace />
            }
          />
          <Route
            path="/profile"
            element={
              isLoggedIn ? (
                <ProfilePage userId={userId} onLogout={handleLogout} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </ErrorBoundary>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
