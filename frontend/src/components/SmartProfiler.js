import { useState, useEffect, useCallback } from "react";
import {
  smartProfiler, updateUserFullProfile, generateRealFilledForms, verifyFields,
} from "../lib/api";
import api from "../lib/api";
import {
  AlertTriangle, Check, ChevronRight, FileDown, Loader2, Download, RotateCcw,
  ShieldCheck, XCircle,
} from "lucide-react";

export const SmartProfiler = ({ userId, schemeNames, onComplete, onMessage }) => {
  const [profilerState, setProfilerState] = useState(null);
  const [answer, setAnswer] = useState("");
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const [pdfResults, setPdfResults] = useState(null);
  const [error, setError] = useState("");
  const [fieldWarning, setFieldWarning] = useState("");

  const fetchProfilerState = useCallback(async () => {
    try {
      const res = await smartProfiler(userId, schemeNames);
      setProfilerState(res.data);
      if (res.data.allComplete) {
        setShowReview(true);
      }
    } catch (e) {
      setError("प्रोफाइलर लोड नहीं हो सका। पुनः प्रयास करें।");
    }
  }, [userId, schemeNames]);

  useEffect(() => {
    const controller = new AbortController();
    fetchProfilerState();
    return () => controller.abort();
  }, [fetchProfilerState]);

  const handleSubmitAnswer = async () => {
    if (!answer.trim() || !profilerState?.nextQuestion) return;
    setSaving(true);
    setError("");
    setFieldWarning("");
    const pk = profilerState.nextQuestion.profileKey;
    const value = answer.trim();
    try {
      // Check the value before storing it. Catching a mistyped Aadhaar here
      // costs one correction; catching it after the whole form is filled means
      // the applicant is refused at the end with no idea which answer was wrong.
      try {
        const check = await verifyFields({ [pk]: value });
        const forThisField = (check.data.findings || []).filter((f) => f.field === pk);
        const blocking = forThisField.find((f) => f.severity === "error");
        if (blocking) {
          setError(blocking.message_hi || blocking.message_en);
          setSaving(false);
          return;
        }
        const warning = forThisField.find((f) => f.severity === "warning");
        if (warning) {
          // Advisory only — the answer is still saved. Some warnings (a zero
          // income, for instance) are perfectly legitimate for the poorest
          // applicants and must never block them.
          setFieldWarning(warning.message_hi || warning.message_en);
        }
      } catch {
        // Validation is a convenience; if it is unavailable the answer still
        // saves and the server-side gate remains the real check.
      }

      await updateUserFullProfile(userId, { [pk]: value });
      if (onMessage) {
        onMessage({
          role: "user",
          content: answer.trim(),
          created_at: new Date().toISOString(),
          status: "read",
        });
        onMessage({
          role: "assistant",
          content: `"${profilerState.nextQuestion.field.labelHindi}" सहेज लिया गया।`,
          created_at: new Date().toISOString(),
        });
      }
      setAnswer("");
      await fetchProfilerState();
    } catch {
      setError("सहेजने में त्रुटि। पुनः प्रयास करें।");
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateForms = async () => {
    setGenerating(true);
    setError("");
    try {
      const res = await generateRealFilledForms(userId, schemeNames);
      setPdfResults(res.data);
      if (onComplete) onComplete(res.data);
    } catch {
      setError("PDF बनाने में त्रुटि। पुनः प्रयास करें।");
    } finally {
      setGenerating(false);
    }
  };

  if (!profilerState) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={24} className="text-[#FF9933] animate-spin" />
      </div>
    );
  }

  // PDF Results view
  if (pdfResults) {
    const backendUrl = process.env.REACT_APP_BACKEND_URL;
    const refused = pdfResults.refused || [];
    const flagged = pdfResults.flagged_for_review || [];
    const flaggedNames = new Set(flagged.map((f) => f.scheme_name));
    const issuedAny = (pdfResults.pdf_urls || []).length > 0;

    return (
      <div data-testid="pdf-results" className="space-y-3 animate-fade-in-up">
        <div className="text-center mb-3">
          <div
            className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 ${
              issuedAny ? "bg-green-100" : "bg-amber-100"
            }`}
          >
            {issuedAny ? (
              <Check size={24} className="text-green-600" />
            ) : (
              <AlertTriangle size={24} className="text-amber-600" />
            )}
          </div>
          <h3 className="text-sm font-bold text-[#000080] font-['Mukta']">
            {issuedAny ? "आवेदन फॉर्म तैयार हैं!" : "कोई फॉर्म तैयार नहीं हुआ"}
          </h3>
          <p className="text-xs text-gray-500 font-['Nunito']">
            {issuedAny
              ? `${pdfResults.count} फॉर्म - ${pdfResults.profile_fields_used} फ़ील्ड भरे गए`
              : "नीचे दिए गए कारण देखें"}
          </p>
        </div>
        {pdfResults.pdf_urls.map((p, i) => (
          <a
            key={i}
            href={`${backendUrl}${p.pdf_url}`}
            data-testid={`pdf-download-${i}`}
            className="flex items-center gap-3 px-4 py-3 bg-white border border-gray-100 rounded-xl hover:shadow-sm transition-all"
          >
            <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center flex-shrink-0">
              <FileDown size={16} className="text-green-600" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-xs font-bold text-gray-900 font-['Mukta'] block truncate">
                {p.scheme_name_hindi || p.scheme_name}
              </span>
              <span className="text-[10px] text-gray-500 font-['Nunito']">
                {flaggedNames.has(p.scheme_name)
                  ? "सत्यापन हेतु भेजा गया / Sent for verification"
                  : "Pre-filled Application"}
              </span>
            </div>
            {flaggedNames.has(p.scheme_name) && (
              <ShieldCheck size={14} className="text-amber-500 flex-shrink-0" />
            )}
            <Download size={14} className="text-gray-400" />
          </a>
        ))}

        {issuedAny && (
          <DownloadAllButton pdfUrls={pdfResults.pdf_urls} backendUrl={backendUrl} userId={userId} />
        )}

        {/* Forms held for verification. The applicant still receives the form —
            they are told it is being checked, not that they were refused. */}
        {flagged.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <ShieldCheck size={13} className="text-amber-600" />
              <span className="text-[11px] font-bold text-amber-800 font-['Mukta']">
                सत्यापन हेतु भेजा गया / Sent for verification
              </span>
            </div>
            <p className="text-[10px] text-amber-700 font-['Nunito'] leading-relaxed">
              लाभ जारी होने से पहले इन आवेदनों की जाँच की जाएगी। आपका फॉर्म तैयार है।
              <span className="block opacity-80">
                These applications will be checked before the benefit is released.
                Your form is ready to download.
              </span>
            </p>
          </div>
        )}

        {/* Schemes the applicant was refused, each with its own reason. Dropping
            these silently would leave someone wondering why a scheme they chose
            never appeared. */}
        {refused.length > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 space-y-2">
            <div className="flex items-center gap-1.5">
              <XCircle size={13} className="text-red-600" />
              <span className="text-[11px] font-bold text-red-800 font-['Mukta']">
                ये फॉर्म नहीं बन सके / Could not be generated
              </span>
            </div>
            {refused.map((r, i) => (
              <div key={i} className="pl-4">
                <p className="text-[11px] font-semibold text-red-900 font-['Mukta']">
                  {r.scheme_name}
                </p>
                {(r.reasons_hi?.length ? r.reasons_hi : r.reasons_en || []).map((reason, j) => (
                  <p key={j} className="text-[10px] text-red-700 font-['Nunito'] leading-snug">
                    • {reason}
                  </p>
                ))}
                {r.outcome === "incomplete" && (
                  <button
                    onClick={() => { setPdfResults(null); setShowReview(false); }}
                    className="mt-1 text-[10px] font-semibold text-[#000080] underline"
                  >
                    जानकारी पूरी करें / Complete the missing details
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Review & Confirm view
  if (showReview) {
    return (
      <div data-testid="review-confirm" className="space-y-3 animate-fade-in-up">
        <div className="text-center mb-2">
          <h3 className="text-sm font-bold text-[#000080] font-['Mukta']">
            समीक्षा और पुष्टि करें / Review & Confirm
          </h3>
          <p className="text-xs text-gray-500 font-['Nunito']">
            सभी {profilerState.totalFields} फ़ील्ड भरे गए
          </p>
        </div>
        <div className="max-h-64 overflow-y-auto space-y-1 pr-1">
          {profilerState.filled.map((f, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg">
              <Check size={12} className="text-green-500 flex-shrink-0" />
              <span className="text-[11px] text-gray-600 font-['Mukta'] flex-1 truncate">
                {f.labelHindi}
              </span>
              <span className="text-[11px] font-semibold text-gray-900 font-['Nunito'] truncate max-w-[40%]">
                {String(f.currentValue).length > 20 ? String(f.currentValue).slice(0, 20) + "..." : f.currentValue}
              </span>
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <button
            data-testid="edit-profile-btn"
            onClick={() => setShowReview(false)}
            className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-xs font-bold font-['Mukta'] flex items-center justify-center gap-1"
          >
            <RotateCcw size={12} /> संपादित करें
          </button>
          <button
            data-testid="generate-forms-btn"
            onClick={handleGenerateForms}
            disabled={generating}
            className="flex-[2] py-2.5 bg-[#16a34a] hover:bg-[#15803d] text-white rounded-xl text-xs font-bold font-['Mukta'] flex items-center justify-center gap-1 transition-all disabled:bg-gray-400"
          >
            {generating ? (
              <><Loader2 size={14} className="animate-spin" /> PDF बना रहे हैं...</>
            ) : (
              <><FileDown size={14} /> फॉर्म बनाएं और डाउनलोड करें</>
            )}
          </button>
        </div>
        {error && <p className="text-xs text-red-500 font-['Mukta'] text-center">{error}</p>}
      </div>
    );
  }

  // Active Profiling — asking questions
  const progress = profilerState.progress;
  const nextQ = profilerState.nextQuestion;

  if (!nextQ) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={24} className="text-[#FF9933] animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="smart-profiler-active" className="space-y-3 animate-fade-in-up">
      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-[#000080] font-['Mukta'] uppercase tracking-wider">
            प्रोफ़ाइल प्रगति
          </span>
          <span className="text-[10px] font-bold text-[#FF9933] font-['Nunito']">
            {profilerState.filledCount}/{profilerState.totalFields} ({progress}%)
          </span>
        </div>
        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#FF9933] to-[#FF6600] rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Current question */}
      {nextQ && (
        <div className="bg-white border border-gray-100 rounded-xl p-3 shadow-sm">
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-1.5 h-1.5 rounded-full bg-[#FF9933]" />
            <span className="text-[10px] font-bold text-[#000080] font-['Mukta'] uppercase tracking-wider">
              {nextQ.field.section}
            </span>
          </div>
          <p className="text-sm font-bold text-gray-900 font-['Mukta'] mb-1">
            {nextQ.questionHindi}
          </p>
          <p className="text-[11px] text-gray-500 font-['Nunito'] mb-3">
            {nextQ.questionEnglish}
          </p>

          {nextQ.field.type === "select" && nextQ.field.options ? (
            <div className="grid grid-cols-2 gap-1.5 mb-2">
              {nextQ.field.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setAnswer(opt)}
                  className={`px-3 py-2 rounded-lg text-xs font-['Nunito'] font-semibold border transition-all ${
                    answer === opt
                      ? "border-[#000080] bg-[#F0F0F8] text-[#000080]"
                      : "border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          ) : (
            <input
              data-testid="profiler-input"
              type={nextQ.field.type === "number" ? "number" : nextQ.field.type === "email" ? "email" : "text"}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmitAnswer()}
              placeholder={nextQ.field.labelEnglish}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm font-['Nunito'] focus:outline-none focus:ring-2 focus:ring-[#000080]/20 focus:border-[#000080]"
            />
          )}

          <button
            data-testid="profiler-submit-btn"
            onClick={handleSubmitAnswer}
            disabled={!answer.trim() || saving}
            className="w-full mt-2 py-2.5 bg-[#000080] hover:bg-[#000060] disabled:bg-gray-300 text-white rounded-lg text-xs font-bold font-['Mukta'] flex items-center justify-center gap-1 transition-all"
          >
            {saving ? (
              <><Loader2 size={12} className="animate-spin" /> सहेज रहे हैं...</>
            ) : (
              <>आगे बढ़ें <ChevronRight size={14} /></>
            )}
          </button>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-500 font-['Mukta'] text-center flex items-center justify-center gap-1">
          <XCircle size={12} className="flex-shrink-0" />
          {error}
        </p>
      )}
      {/* Advisory: the answer was accepted, but may need supporting proof. */}
      {fieldWarning && !error && (
        <p className="text-[11px] text-amber-600 font-['Mukta'] text-center flex items-center justify-center gap-1">
          <AlertTriangle size={12} className="flex-shrink-0" />
          {fieldWarning}
        </p>
      )}
    </div>
  );
};

// Download All button (reused from ChatBubble concept)
const DownloadAllButton = ({ pdfUrls, backendUrl, userId }) => {
  const [downloading, setDownloading] = useState(false);
  const [done, setDone] = useState(false);

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    for (let i = 0; i < pdfUrls.length; i++) {
      const p = pdfUrls[i];
      try {
        const resp = await fetch(`${backendUrl}${p.pdf_url}`);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${(p.scheme_name || "Form").replace(/\s+/g, "_")}_Form.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      } catch {}
      if (i < pdfUrls.length - 1) await new Promise((r) => setTimeout(r, 500));
    }
    setDone(true);
    setDownloading(false);
    try {
      await api.get(`/download-all?user_id=${userId || ""}&count=${pdfUrls.length}`);
    } catch {}
  };

  return (
    <button
      data-testid="download-all-forms-btn"
      onClick={handleDownload}
      disabled={downloading}
      className={`w-full flex items-center gap-3 px-4 py-3 text-white rounded-xl transition-all shadow-md ${
        done ? "bg-[#16a34a]" : downloading ? "bg-gray-400 cursor-wait" : "bg-[#16a34a] hover:bg-[#15803d] hover:-translate-y-0.5"
      }`}
    >
      <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
        {downloading ? <Loader2 size={18} className="animate-spin" /> : done ? <Check size={18} /> : <FileDown size={18} />}
      </div>
      <div className="flex-1 text-left">
        <span className="text-sm font-bold font-['Mukta'] block">
          {done ? "डाउनलोड पूर्ण!" : downloading ? "डाउनलोड हो रहा है..." : `सभी ${pdfUrls.length} फॉर्म डाउनलोड करें`}
        </span>
      </div>
    </button>
  );
};
