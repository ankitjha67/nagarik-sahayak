import { useEffect, useRef, useState, useCallback } from "react";
import { X, Check, FileText, Share2, Loader2, Info } from "lucide-react";
import { getSchemeDocuments } from "../lib/api";

// "What to carry to the counter." The form-filling engine says what to write;
// this says what to bring. A missing enclosure is the commonest reason an
// application is turned away, after the citizen has already spent a day and a
// fare to reach the office — so the documents are listed in one place, in their
// language, with the reason for each, and the ticks are remembered on the
// device so the list survives being closed, reopened, and used offline on the
// day of travel.

// Ticks live only in this browser, keyed per scheme. Which papers a citizen has
// gathered is their own working note, not evidence the application needs, so it
// never leaves the device — the same reasoning as kycStore.
const tickKey = (schemeName) => `ns_docs_ticked:${schemeName}`;

function loadTicked(schemeName) {
  try {
    const raw = localStorage.getItem(tickKey(schemeName));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? new Set(parsed) : new Set();
  } catch {
    return new Set();
  }
}

function saveTicked(schemeName, set) {
  try {
    localStorage.setItem(tickKey(schemeName), JSON.stringify([...set]));
  } catch {
    /* private window or storage blocked — the list still works this session */
  }
}

export function DocumentChecklist({ schemeName, schemeTitle, isHindi, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [ticked, setTicked] = useState(() => loadTicked(schemeName));
  const closeRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getSchemeDocuments(schemeName)
      .then((r) => !cancelled && setData(r.data))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [schemeName]);

  // Escape closes the sheet, and focus moves to the close button on open, so a
  // keyboard or screen-reader user is not stranded behind the backdrop.
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const toggle = useCallback(
    (key) => {
      setTicked((prev) => {
        const next = new Set(prev);
        next.has(key) ? next.delete(key) : next.add(key);
        saveTicked(schemeName, next);
        return next;
      });
    },
    [schemeName]
  );

  const docs = data?.documents || [];
  const readyCount = docs.filter((d) => ticked.has(d.key)).length;

  const shareOnWhatsApp = () => {
    const title = isHindi ? data.schemeNameHindi || schemeTitle : schemeTitle;
    const header = isHindi
      ? `${title} — काउंटर पर ले जाने योग्य दस्तावेज़:`
      : `${title} — documents to carry:`;
    const lines = docs.map((d) => {
      const name = isHindi ? d.nameHindi : d.nameEnglish;
      const mark = ticked.has(d.key) ? "✅" : "▢";
      return `${mark} ${name}`;
    });
    const footer = isHindi ? data.noticeHindi : data.noticeEnglish;
    const text = `${header}\n\n${lines.join("\n")}\n\n${footer}`;
    // wa.me opens WhatsApp with the text pre-filled; the citizen chooses who to
    // send it to (often themselves or a family member who holds the papers).
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label={isHindi ? "ले जाने योग्य दस्तावेज़" : "Documents to carry"}
    >
      {/* Backdrop */}
      <button
        aria-label={isHindi ? "बंद करें" : "Close"}
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
        tabIndex={-1}
      />

      {/* Sheet */}
      <div className="relative w-full max-w-md bg-white rounded-t-2xl sm:rounded-2xl max-h-[85vh] flex flex-col shadow-2xl animate-fade-in-up">
        {/* Header */}
        <div className="flex items-start gap-3 p-5 border-b border-gray-100">
          <div className="w-10 h-10 rounded-xl bg-[#FFF0E0] flex items-center justify-center flex-shrink-0">
            <FileText size={20} className="text-[#FF9933]" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold text-[#000080] font-['Mukta'] leading-tight">
              {isHindi ? "काउंटर पर क्या ले जाएं" : "What to carry to the counter"}
            </h2>
            <p className="text-xs text-gray-500 font-['Nunito'] mt-0.5 line-clamp-1">
              {schemeTitle}
            </p>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label={isHindi ? "बंद करें" : "Close"}
            className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {error && (
            <p className="text-sm text-gray-500 text-center py-6 font-['Nunito']">
              {isHindi
                ? "दस्तावेज़ सूची अभी उपलब्ध नहीं है।"
                : "The document list is not available yet."}
            </p>
          )}

          {!data && !error && (
            <div className="flex justify-center py-8">
              <Loader2 className="animate-spin text-[#FF9933]" size={24} />
            </div>
          )}

          {data && (
            <>
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-semibold text-gray-700 font-['Mukta']">
                  {isHindi
                    ? `${readyCount} / ${docs.length} तैयार`
                    : `${readyCount} of ${docs.length} ready`}
                </span>
                <div className="h-2 w-28 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#138808] transition-all duration-300"
                    style={{ width: `${docs.length ? (readyCount / docs.length) * 100 : 0}%` }}
                  />
                </div>
              </div>

              <ul className="space-y-2">
                {docs.map((d) => {
                  const on = ticked.has(d.key);
                  return (
                    <li key={d.key}>
                      <button
                        onClick={() => toggle(d.key)}
                        aria-pressed={on}
                        className={`w-full text-left rounded-xl border p-3 flex items-start gap-3 transition-colors ${
                          on
                            ? "bg-green-50 border-green-200"
                            : "bg-white border-gray-200 hover:border-gray-300"
                        }`}
                      >
                        <span
                          className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 mt-0.5 ${
                            on
                              ? "bg-[#138808] border-[#138808]"
                              : "border-gray-300"
                          }`}
                        >
                          {on && <Check size={14} className="text-white" strokeWidth={3} />}
                        </span>
                        <span className="flex-1 min-w-0">
                          <span className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`text-sm font-bold font-['Mukta'] ${
                                on ? "text-green-800 line-through" : "text-gray-800"
                              }`}
                            >
                              {isHindi ? d.nameHindi : d.nameEnglish}
                            </span>
                            {!d.mandatory && (
                              <span className="text-[10px] font-semibold text-gray-400 border border-gray-200 rounded px-1">
                                {isHindi ? "यदि लागू हो" : "if applicable"}
                              </span>
                            )}
                          </span>
                          <span className="block text-[11px] text-gray-500 font-['Nunito'] mt-0.5 leading-snug">
                            {isHindi ? d.reasonHindi : d.reasonEnglish}
                          </span>
                          {d.alternatives?.length > 0 && (
                            <span className="block text-[11px] text-[#000080] font-['Nunito'] mt-1 leading-snug">
                              {isHindi ? "या: " : "Or: "}
                              {d.alternatives.join(", ")}
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>

              {/* The plain, honest notice — said once, where it will be read. */}
              <div className="mt-4 rounded-lg bg-blue-50 border border-blue-100 p-3 flex gap-2">
                <Info size={14} className="text-blue-500 flex-shrink-0 mt-0.5" />
                <p className="text-[11px] text-blue-800 font-['Nunito'] leading-snug">
                  {isHindi ? data.noticeHindi : data.noticeEnglish}
                </p>
              </div>
            </>
          )}
        </div>

        {/* Footer — share */}
        {data && (
          <div className="p-4 border-t border-gray-100">
            <button
              onClick={shareOnWhatsApp}
              data-testid="share-checklist-whatsapp"
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#25D366] text-white rounded-xl font-semibold font-['Mukta'] hover:brightness-95 transition-all"
            >
              <Share2 size={18} />
              {isHindi ? "WhatsApp पर भेजें" : "Share on WhatsApp"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
