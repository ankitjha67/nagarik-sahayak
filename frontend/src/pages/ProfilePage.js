import { useState, useEffect } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import { getProfile, updateProfile } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import { UserCircle2, Phone, Globe, LogOut, Save, Loader2 } from "lucide-react";

export default function ProfilePage({ userId, onLogout }) {
  const [profile, setProfile] = useState(null);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("hi");
  const [saving, setSaving] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (userId) {
      getProfile(userId)
        .then((r) => {
          setProfile(r.data);
          setName(r.data.name || "");
          setLanguage(r.data.language || "hi");
        })
        .catch(() => {});
    }
  }, [userId]);

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const res = await updateProfile(userId, { name, language });
      setProfile(res.data);
      toast.success("प्रोफाइल अपडेट हो गया!");
    } catch {
      toast.error("Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="profile-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader title="प्रोफाइल" onMenuClick={() => setSidebarOpen(true)} />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="max-w-md mx-auto px-4 pt-6">
        {/* Avatar Section */}
        <div className="text-center mb-6 animate-fade-in-up">
          <div className="w-20 h-20 rounded-full bg-[#E6E6F2] flex items-center justify-center mx-auto mb-3">
            <UserCircle2 size={40} className="text-[#000080]" />
          </div>
          <p className="text-sm text-gray-400 font-['Nunito']">
            {profile?.phone ? `+91 ${profile.phone}` : "Loading..."}
          </p>
        </div>

        {/* Profile Form */}
        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm space-y-5 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          {/* Name */}
          <div>
            <label className="text-sm font-semibold text-gray-700 font-['Mukta'] flex items-center gap-2 mb-2">
              <UserCircle2 size={16} className="text-[#FF9933]" />
              नाम / Name
            </label>
            <Input
              data-testid="profile-name-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="अपना नाम दर्ज करें"
              className="h-11 rounded-xl border-gray-200 font-['Nunito']"
            />
          </div>

          {/* Phone (Read-only) */}
          <div>
            <label className="text-sm font-semibold text-gray-700 font-['Mukta'] flex items-center gap-2 mb-2">
              <Phone size={16} className="text-[#FF9933]" />
              फोन नंबर / Phone
            </label>
            <Input
              data-testid="profile-phone-display"
              type="text"
              value={profile?.phone ? `+91 ${profile.phone}` : ""}
              disabled
              className="h-11 rounded-xl border-gray-200 bg-gray-50 text-gray-500 font-['Nunito']"
            />
          </div>

          {/* Language */}
          <div>
            <label className="text-sm font-semibold text-gray-700 font-['Mukta'] flex items-center gap-2 mb-2">
              <Globe size={16} className="text-[#FF9933]" />
              भाषा / Language
            </label>
            <div className="flex gap-3">
              <button
                data-testid="lang-hindi-btn"
                onClick={() => setLanguage("hi")}
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold font-['Mukta'] border transition-all ${
                  language === "hi"
                    ? "bg-[#FFF0E0] border-[#FF9933] text-[#000080]"
                    : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                }`}
              >
                हिन्दी
              </button>
              <button
                data-testid="lang-english-btn"
                onClick={() => setLanguage("en")}
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold font-['Nunito'] border transition-all ${
                  language === "en"
                    ? "bg-[#FFF0E0] border-[#FF9933] text-[#000080]"
                    : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                }`}
              >
                English
              </button>
            </div>
          </div>

          {/* Save Button */}
          <Button
            data-testid="profile-save-btn"
            onClick={handleSave}
            disabled={saving}
            className="w-full h-11 rounded-full bg-[#FF9933] hover:bg-[#E68A00] text-white font-semibold shadow-md shadow-orange-100 transition-all"
          >
            {saving ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <>
                <Save size={16} />
                सेव करें
              </>
            )}
          </Button>
        </div>

        {/* Logout */}
        <button
          data-testid="logout-btn"
          onClick={onLogout}
          className="mt-6 mx-auto flex items-center gap-2 text-sm text-red-500 font-medium hover:text-red-600 transition-colors font-['Nunito']"
        >
          <LogOut size={16} />
          लॉग आउट / Logout
        </button>

        {/* App Info */}
        <div className="mt-8 text-center animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
          <p className="text-xs text-gray-300 font-['Nunito']">
            Nagarik Sahayak v1.0.0
          </p>
          <p className="text-[10px] text-gray-300 font-['Nunito'] mt-0.5">
            Digital India Initiative
          </p>
        </div>
      </div>

      <BottomNav />
    </div>
  );
}
