import { useState, useEffect } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import { Sidebar } from "../components/Sidebar";
import {
  getProfile, updateProfile,
  getNotificationPreferences, updateNotificationPreferences,
  getMyReviewCases,
} from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  UserCircle2, Phone, Globe, LogOut, Save, Loader2, Bell, Mail,
  ShieldCheck, Clock, CheckCircle2, XCircle,
} from "lucide-react";

function PrefToggle({ label, labelHi, checked, onChange }) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <p className="text-sm font-semibold text-gray-700 font-['Mukta']">{labelHi}</p>
        <p className="text-[11px] text-gray-400 font-['Nunito']">{label}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        aria-label={`${label}: ${checked ? "on" : "off"}`}
        className={`relative w-11 h-6 rounded-full transition-colors duration-300 focus:outline-none ${
          checked ? "bg-[#FF9933]" : "bg-gray-300"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-md transition-transform duration-300 ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

export default function ProfilePage({ userId, onLogout }) {
  const [profile, setProfile] = useState(null);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("hi");
  const [saving, setSaving] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [prefs, setPrefs] = useState({
    scheme_deadline_alerts: false,
    exam_deadline_alerts: false,
    new_scheme_alerts: false,
    email: "",
  });
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [reviewCases, setReviewCases] = useState([]);

  useEffect(() => {
    if (userId) {
      getProfile(userId)
        .then((r) => {
          setProfile(r.data);
          setName(r.data.name || "");
          setLanguage(r.data.language || "hi");
        })
        .catch(() => {});
      // Applications held for verification. Someone whose benefit is delayed is
      // entitled to know that a check is under way rather than assuming silence
      // means refusal.
      getMyReviewCases(userId)
        .then((r) => setReviewCases(r.data.cases || []))
        .catch(() => {});
      getNotificationPreferences(userId)
        .then((r) => setPrefs({
          scheme_deadline_alerts: !!r.data.scheme_deadline_alerts,
          exam_deadline_alerts: !!r.data.exam_deadline_alerts,
          new_scheme_alerts: !!r.data.new_scheme_alerts,
          email: r.data.email || "",
        }))
        .catch(() => {});
    }
  }, [userId]);

  const handleSavePrefs = async () => {
    setSavingPrefs(true);
    try {
      await updateNotificationPreferences(userId, prefs);
      toast.success("नोटिफिकेशन सेटिंग सेव हो गई!");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to save preferences");
    } finally {
      setSavingPrefs(false);
    }
  };

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

        {/* Verification status */}
        {reviewCases.length > 0 && (
          <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm mt-5 animate-fade-in-up">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck size={16} className="text-[#FF9933]" />
              <h3 className="text-sm font-bold text-[#000080] font-['Mukta']">
                सत्यापन स्थिति / Verification Status
              </h3>
            </div>
            <div className="space-y-2">
              {reviewCases.map((c, i) => {
                const cfg = {
                  pending: { Icon: Clock, cls: "bg-amber-50 border-amber-200 text-amber-800" },
                  approved: { Icon: CheckCircle2, cls: "bg-green-50 border-green-200 text-green-800" },
                  rejected: { Icon: XCircle, cls: "bg-red-50 border-red-200 text-red-800" },
                }[c.status] || { Icon: Clock, cls: "bg-gray-50 border-gray-200 text-gray-700" };
                const { Icon, cls } = cfg;
                return (
                  <div key={i} className={`rounded-xl border p-3 ${cls}`}>
                    <div className="flex items-start gap-2">
                      <Icon size={14} className="mt-0.5 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-xs font-bold font-['Mukta'] truncate">
                          {c.scheme}
                        </p>
                        <p className="text-[11px] font-['Nunito'] opacity-90 mt-0.5">
                          {c.message_hi}
                        </p>
                        <p className="text-[10px] font-['Nunito'] opacity-70">
                          {c.message_en}
                        </p>
                        {/* Only rejections carry a note; an approval needs none. */}
                        {c.note && (
                          <p className="text-[10px] font-['Nunito'] mt-1 pt-1 border-t border-current/20">
                            कारण / Reason: {c.note}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Notification Preferences */}
        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm mt-5 animate-fade-in-up" style={{ animationDelay: "0.15s" }}>
          <div className="flex items-center gap-2 mb-3">
            <Bell size={16} className="text-[#FF9933]" />
            <h3 className="text-sm font-bold text-[#000080] font-['Mukta']">
              अलर्ट सेटिंग / Alert Settings
            </h3>
          </div>

          <PrefToggle
            label="Scheme deadline alerts"
            labelHi="योजना डेडलाइन अलर्ट"
            checked={prefs.scheme_deadline_alerts}
            onChange={(v) => setPrefs((p) => ({ ...p, scheme_deadline_alerts: v }))}
          />
          <PrefToggle
            label="Exam deadline alerts"
            labelHi="परीक्षा डेडलाइन अलर्ट"
            checked={prefs.exam_deadline_alerts}
            onChange={(v) => setPrefs((p) => ({ ...p, exam_deadline_alerts: v }))}
          />
          <PrefToggle
            label="New scheme notifications"
            labelHi="नई योजना सूचनाएं"
            checked={prefs.new_scheme_alerts}
            onChange={(v) => setPrefs((p) => ({ ...p, new_scheme_alerts: v }))}
          />

          {/* Alert Email */}
          <div className="mt-3">
            <label className="text-sm font-semibold text-gray-700 font-['Mukta'] flex items-center gap-2 mb-2">
              <Mail size={14} className="text-[#FF9933]" />
              अलर्ट ईमेल / Alert Email
            </label>
            <Input
              type="email"
              value={prefs.email}
              onChange={(e) => setPrefs((p) => ({ ...p, email: e.target.value }))}
              placeholder="email@example.com"
              className="h-10 rounded-xl border-gray-200 font-['Nunito']"
            />
          </div>

          <Button
            onClick={handleSavePrefs}
            disabled={savingPrefs}
            className="w-full h-10 mt-4 rounded-full bg-[#000080] hover:bg-[#000060] text-white font-semibold transition-all"
          >
            {savingPrefs ? (
              <Loader2 className="animate-spin" size={16} />
            ) : (
              <>
                <Save size={14} />
                अलर्ट सेव करें
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
