import { useState, useEffect, useCallback } from "react";
import { AppHeader } from "../components/AppHeader";
import { BottomNav } from "../components/BottomNav";
import {
  getPrivacyNotice, getConsent, grantConsent, withdrawConsent,
  getMyData, eraseMyData, lodgeRightsRequest,
} from "../lib/api";
import { toast } from "sonner";
import {
  AlertTriangle, ChevronDown, ChevronRight, Database, Eye, FileText,
  Loader2, Lock, MessageSquareWarning, ShieldCheck, Trash2, Users, XCircle,
} from "lucide-react";

// Plain-language purpose descriptions. The statutory purpose names are precise
// but opaque; a citizen deciding whether to consent needs to understand what
// they are agreeing to, which is the whole point of section 6's "informed".
const PURPOSE_TEXT = {
  scheme_eligibility: {
    hi: "यह जाँचना कि आप किन योजनाओं के लिए पात्र हैं",
    en: "Checking which schemes you qualify for",
    why: "Your age, income and category are compared against each scheme's published conditions.",
  },
  form_completion: {
    hi: "आपके आवेदन फॉर्म भरना",
    en: "Filling in your application forms",
    why: "Your details are written into the government forms you choose.",
  },
  benefit_disbursement: {
    hi: "लाभ आपके बैंक खाते में भेजना",
    en: "Sending the benefit to your bank account",
    why: "Your account and IFSC are needed so the payment reaches you.",
  },
  fraud_prevention: {
    hi: "सार्वजनिक धन के दुरुपयोग को रोकना",
    en: "Preventing misuse of public funds",
    why: "Identifiers are compared as one-way codes against other applications. The numbers themselves are not readable.",
  },
  account_management: {
    hi: "आपका खाता चलाना",
    en: "Running your account",
    why: "Your phone number identifies you when you sign in.",
  },
  service_communication: {
    hi: "समय-सीमा और स्थिति की सूचनाएं भेजना",
    en: "Sending deadline and status alerts",
    why: "Only if you ask for alerts.",
  },
};

// Without these the app cannot do the thing the citizen came for. Presented as
// required rather than hidden, so the choice stays honest.
const ESSENTIAL = ["scheme_eligibility", "form_completion", "account_management"];

function Section({ icon: Icon, title, titleHi, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm mb-3 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-5 py-4 flex items-center gap-3 text-left"
      >
        <div className="w-9 h-9 rounded-xl bg-[#E8EAF6] flex items-center justify-center flex-shrink-0">
          <Icon size={17} className="text-[#000080]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-[#000080] font-['Mukta']">{titleHi}</p>
          <p className="text-[11px] text-gray-500 font-['Nunito']">{title}</p>
        </div>
        <ChevronDown
          size={16}
          className={`text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="px-5 pb-5 border-t border-gray-50 pt-4">{children}</div>}
    </div>
  );
}

export default function PrivacyPage({ userId }) {
  const [notice, setNotice] = useState(null);
  const [consent, setConsent] = useState(null);
  const [myData, setMyData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [grievance, setGrievance] = useState("");
  const [confirmErase, setConfirmErase] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [n, c] = await Promise.all([
      getPrivacyNotice().catch(() => null),
      userId ? getConsent(userId).catch(() => null) : Promise.resolve(null),
    ]);
    if (n) setNotice(n.data);
    if (c) setConsent(c.data);
    setLoading(false);
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  const consented = new Set((consent?.granted || []).map((g) => g.purpose));

  const togglePurpose = async (purpose, on) => {
    setBusy(purpose);
    try {
      if (on) {
        await grantConsent(userId, [purpose]);
        toast.success("सहमति दर्ज की गई");
      } else {
        await withdrawConsent(userId, [purpose]);
        toast.success("सहमति वापस ले ली गई");
      }
      const c = await getConsent(userId);
      setConsent(c.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not update consent");
    } finally {
      setBusy("");
    }
  };

  const acceptEssential = async () => {
    setBusy("all");
    try {
      await grantConsent(userId, ESSENTIAL);
      const c = await getConsent(userId);
      setConsent(c.data);
      toast.success("धन्यवाद! अब आप योजनाओं के लिए आवेदन कर सकते हैं।");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not record consent");
    } finally {
      setBusy("");
    }
  };

  const loadMyData = async () => {
    setBusy("mydata");
    try {
      const r = await getMyData(userId);
      setMyData(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not load your data");
    } finally {
      setBusy("");
    }
  };

  const doErase = async () => {
    setBusy("erase");
    try {
      const r = await eraseMyData(userId, { all: true });
      toast.success(`${r.data.profile_fields || 0} विवरण मिटा दिए गए`);
      setConfirmErase(false);
      setMyData(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Erasure failed");
    } finally {
      setBusy("");
    }
  };

  const sendGrievance = async () => {
    if (!grievance.trim()) return;
    setBusy("grievance");
    try {
      await lodgeRightsRequest(userId, "grievance", { message: grievance.trim() });
      toast.success("आपकी शिकायत दर्ज कर ली गई है");
      setGrievance("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not lodge grievance");
    } finally {
      setBusy("");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[#000080]" />
      </div>
    );
  }

  const hasAnyConsent = consented.size > 0;

  return (
    <div data-testid="privacy-page" className="min-h-screen bg-gray-50 pb-20">
      <AppHeader title="गोपनीयता / Privacy" />

      <div className="max-w-md mx-auto px-4 pt-4">
        {/* First-run prompt. Shown only until consent exists, so it informs
            rather than nags. */}
        {!hasAnyConsent && (
          <div
            data-testid="consent-prompt"
            className="bg-[#FFF0E0] rounded-2xl border border-orange-200 p-5 mb-4 animate-fade-in-up"
          >
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck size={18} className="text-[#FF9933]" />
              <h2 className="text-sm font-bold text-[#000080] font-['Mukta']">
                आपकी अनुमति चाहिए
              </h2>
            </div>
            <p className="text-xs text-gray-700 font-['Nunito'] leading-relaxed mb-3">
              योजनाओं के लिए आवेदन करने हेतु हमें आपके कुछ विवरण चाहिए। आप कभी भी
              यह अनुमति वापस ले सकते हैं।
              <span className="block text-[11px] text-gray-500 mt-1">
                We need some details to apply for schemes on your behalf. You can
                withdraw this permission at any time.
              </span>
            </p>
            <button
              onClick={acceptEssential}
              disabled={busy === "all"}
              data-testid="accept-consent-btn"
              className="w-full py-2.5 rounded-xl bg-[#FF9933] text-white text-sm font-bold disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {busy === "all" ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
              मैं सहमत हूँ / I agree
            </button>
            <p className="text-[10px] text-gray-500 font-['Nunito'] text-center mt-2">
              नीचे प्रत्येक उद्देश्य अलग से चुन सकते हैं।
            </p>
          </div>
        )}

        {/* s6 — consent, per purpose */}
        <Section icon={Lock} titleHi="आपकी अनुमतियाँ" title="Your permissions"
                 defaultOpen>
          <p className="text-[11px] text-gray-500 font-['Nunito'] mb-3">
            प्रत्येक उद्देश्य के लिए अलग अनुमति। कभी भी बदल सकते हैं।
          </p>
          {(consent?.available_purposes || []).map((p) => {
            const text = PURPOSE_TEXT[p.purpose] || {};
            const on = consented.has(p.purpose);
            const essential = ESSENTIAL.includes(p.purpose);
            return (
              <div key={p.purpose} className="py-2.5 border-b border-gray-50 last:border-0">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-gray-800 font-['Mukta']">
                      {text.hi || p.purpose}
                      {essential && (
                        <span className="ml-1.5 text-[9px] text-[#FF9933] font-normal">
                          आवश्यक
                        </span>
                      )}
                    </p>
                    <p className="text-[11px] text-gray-500 font-['Nunito']">{text.en}</p>
                    {text.why && (
                      <p className="text-[10px] text-gray-400 font-['Nunito'] mt-0.5">
                        {text.why}
                      </p>
                    )}
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {p.field_count} विवरण / fields
                    </p>
                  </div>
                  <button
                    onClick={() => togglePurpose(p.purpose, !on)}
                    disabled={busy === p.purpose}
                    aria-label={`${text.en}: ${on ? "on" : "off"}`}
                    data-testid={`consent-toggle-${p.purpose}`}
                    className={`relative w-11 h-6 rounded-full flex-shrink-0 mt-0.5 transition-colors disabled:opacity-50 ${
                      on ? "bg-[#138808]" : "bg-gray-300"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-md transition-transform ${
                        on ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </div>
            );
          })}
          {hasAnyConsent && (
            <button
              onClick={() => withdrawConsent(userId).then(async () => {
                toast.success("सभी अनुमतियाँ वापस ले ली गईं");
                setConsent((await getConsent(userId)).data);
              }).catch(() => toast.error("Could not withdraw"))}
              className="w-full mt-3 py-2 rounded-xl border border-gray-300 text-gray-600 text-xs font-semibold"
            >
              सभी अनुमतियाँ वापस लें / Withdraw all
            </button>
          )}
        </Section>

        {/* s11 — access */}
        <Section icon={Eye} titleHi="मेरा डेटा देखें" title="See what we hold about you">
          {myData ? (
            <div>
              <p className="text-xs text-gray-700 font-['Nunito'] mb-2">
                <strong>{myData.field_count}</strong> विवरण संग्रहीत ·{" "}
                <strong>{myData.applications_count}</strong> आवेदन ·{" "}
                <strong>{myData.chat_messages_count}</strong> संदेश
              </p>
              <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
                {(myData.personal_data_held || []).map((f, i) => (
                  <div key={i} className="flex items-center gap-2 px-2 py-1.5 bg-gray-50 rounded-lg">
                    <Database size={11} className="text-gray-400 flex-shrink-0" />
                    <span className="text-[11px] text-gray-700 font-['Nunito'] flex-1 truncate">
                      {f.field.replace(/_/g, " ")}
                    </span>
                    {f.used_for_decisions && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700">
                        निर्णय
                      </span>
                    )}
                    <span className="text-[9px] text-gray-400">{f.retention_days}d</span>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-gray-500 font-['Nunito'] mt-2">
                "निर्णय" वाले विवरण आपकी पात्रता तय करने में उपयोग होते हैं।
              </p>
            </div>
          ) : (
            <button
              onClick={loadMyData}
              disabled={busy === "mydata"}
              data-testid="load-mydata-btn"
              className="w-full py-2.5 rounded-xl bg-[#000080] text-white text-xs font-semibold disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {busy === "mydata" ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />}
              मेरा डेटा दिखाएं
            </button>
          )}
        </Section>

        {/* s11(1)(c) — who else receives it */}
        <Section icon={Users} titleHi="आपका डेटा किसके साथ साझा होता है"
                 title="Who else receives your data">
          {(notice?.shared_with || []).map((r, i) => (
            <div key={i} className="py-2 border-b border-gray-50 last:border-0">
              <p className="text-xs font-semibold text-gray-800 font-['Nunito']">
                {r.recipient}
              </p>
              <p className="text-[11px] text-gray-600 font-['Nunito']">{r.data}</p>
              <p className="text-[10px] text-gray-400">{r.purpose}</p>
            </div>
          ))}
        </Section>

        {/* s5 — the notice itself */}
        <Section icon={FileText} titleHi="गोपनीयता सूचना" title="Privacy notice">
          <p className="text-xs text-gray-700 font-['Nunito'] leading-relaxed">
            {notice?.summary_hi}
          </p>
          <p className="text-[11px] text-gray-500 font-['Nunito'] leading-relaxed mt-2">
            {notice?.summary_en}
          </p>
          <p className="text-[10px] text-gray-400 mt-2">
            सूचना संस्करण / Notice version: {notice?.notice_version}
          </p>
        </Section>

        {/* s13 — grievance */}
        <Section icon={MessageSquareWarning} titleHi="शिकायत दर्ज करें"
                 title="Raise a grievance">
          <textarea
            value={grievance}
            onChange={(e) => setGrievance(e.target.value)}
            rows={3}
            data-testid="grievance-input"
            placeholder="आपकी शिकायत क्या है?"
            className="w-full px-3 py-2 rounded-xl border border-gray-200 text-xs font-['Nunito'] focus:border-[#000080] focus:ring-1 focus:ring-[#000080] outline-none resize-none"
          />
          <button
            onClick={sendGrievance}
            disabled={busy === "grievance" || !grievance.trim()}
            className="w-full mt-2 py-2.5 rounded-xl bg-[#000080] text-white text-xs font-semibold disabled:opacity-40"
          >
            {busy === "grievance" ? "भेजा जा रहा है…" : "शिकायत भेजें"}
          </button>
          <p className="text-[10px] text-gray-500 font-['Nunito'] mt-2">
            {notice?.grievance?.escalation}
          </p>
        </Section>

        {/* s12 — erasure. Destructive, so it is last and gated behind a
            confirmation that states plainly what will be lost. */}
        <Section icon={Trash2} titleHi="मेरा डेटा मिटाएं" title="Erase my data">
          {!confirmErase ? (
            <>
              <p className="text-xs text-gray-700 font-['Nunito'] leading-relaxed mb-3">
                आपके सभी विवरण, आवेदन फॉर्म और बातचीत मिटा दिए जाएंगे। यह वापस
                नहीं किया जा सकता।
                <span className="block text-[11px] text-gray-500 mt-1">
                  Your details, generated forms and conversations will be deleted.
                  This cannot be undone.
                </span>
              </p>
              <button
                onClick={() => setConfirmErase(true)}
                data-testid="erase-start-btn"
                className="w-full py-2.5 rounded-xl border border-red-300 text-red-600 text-xs font-bold"
              >
                मेरा डेटा मिटाएं
              </button>
            </>
          ) : (
            <div className="rounded-xl bg-red-50 border border-red-200 p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <AlertTriangle size={14} className="text-red-600" />
                <span className="text-xs font-bold text-red-800 font-['Mukta']">
                  क्या आप निश्चित हैं?
                </span>
              </div>
              <p className="text-[11px] text-red-700 font-['Nunito'] mb-3">
                आपका फोन नंबर कानूनी कारणों से रखा जाएगा। बाकी सब मिट जाएगा।
                <span className="block opacity-80">
                  Your phone number is retained for legal reasons. Everything
                  else is removed.
                </span>
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirmErase(false)}
                  className="flex-1 py-2 rounded-xl border border-gray-300 text-gray-700 text-xs font-semibold"
                >
                  रहने दें
                </button>
                <button
                  onClick={doErase}
                  disabled={busy === "erase"}
                  data-testid="erase-confirm-btn"
                  className="flex-1 py-2 rounded-xl bg-red-600 text-white text-xs font-bold disabled:opacity-50 flex items-center justify-center gap-1.5"
                >
                  {busy === "erase" ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
                  हाँ, मिटाएं
                </button>
              </div>
            </div>
          )}
        </Section>
      </div>

      <BottomNav />
    </div>
  );
}
