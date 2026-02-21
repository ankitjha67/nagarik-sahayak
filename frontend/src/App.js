import { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import LoginPage from "@/pages/LoginPage";
import HomePage from "@/pages/HomePage";
import ChatPage from "@/pages/ChatPage";
import SchemesPage from "@/pages/SchemesPage";
import ProfilePage from "@/pages/ProfilePage";

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
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
