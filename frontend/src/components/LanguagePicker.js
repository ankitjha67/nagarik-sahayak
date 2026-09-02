import { useMemo, useState } from "react";
import { AlertTriangle, Check, ChevronDown, Globe, Info } from "lucide-react";
import { useLanguage } from "../lib/i18n";

// Every language is listed in its own script. A picker that offers "Bengali" to
// somebody who reads বাংলা is a picker they cannot use, which defeats the point
// of having one.
//
// Every language carries a badge saying how far it can be trusted. All 22
// scheduled languages now have text, but "Draft" and "Unchecked" mean different
// things and the badge is the only place a reader learns which one they are
// getting. A language with no entries at all would still be listed and marked
// "Not yet available" rather than hidden — a Santali speaker who finds their
// language absent concludes the app does not know Santali exists.

function QualityBadge({ quality, percent }) {
  if (quality === "source") {
    return (
      <span className="text-[11px] px-1.5 py-0.5 rounded bg-green-100 text-green-800">
        Original
      </span>
    );
  }
  if (quality === "reviewed") {
    return (
      <span className="text-[11px] px-1.5 py-0.5 rounded bg-green-100 text-green-800">
        Reviewed
      </span>
    );
  }
  if (quality === "draft") {
    return (
      <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
        Draft · {percent}%
      </span>
    );
  }
  if (quality === "low_confidence") {
    return (
      <span className="text-[11px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-900">
        Unchecked
      </span>
    );
  }
  return (
    <span className="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
      Not yet available
    </span>
  );
}

export function LanguagePicker({ compact = false }) {
  const { code, setLanguage, languages, meta } = useLanguage();
  const [open, setOpen] = useState(false);

  const { available, unavailable } = useMemo(() => {
    const list = languages || [];
    return {
      available: list.filter((l) => l.quality !== "missing"),
      unavailable: list.filter((l) => l.quality === "missing"),
    };
  }, [languages]);

  const current = meta || (languages || []).find((l) => l.code === code);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="Choose language / भाषा चुनें"
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 bg-white text-sm font-medium hover:bg-gray-50"
      >
        <Globe className="w-4 h-4 text-gray-500" aria-hidden="true" />
        <span>{current?.endonym || code}</span>
        {!compact && <ChevronDown className="w-4 h-4 text-gray-400" aria-hidden="true" />}
      </button>

      {open && (
        <>
          {/* Click-away layer. Rendered before the panel so the panel stays on
              top, and marked hidden from assistive technology since Escape and
              the toggle button already close the menu. */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            role="listbox"
            aria-label="Languages"
            className="absolute right-0 z-50 mt-2 w-80 max-h-[70vh] overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-xl"
            onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          >
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Available now
              </p>
            </div>
            {available.map((lang) => (
              <button
                key={lang.code}
                type="button"
                role="option"
                aria-selected={lang.code === code}
                onClick={() => {
                  setLanguage(lang.code);
                  setOpen(false);
                }}
                dir={lang.direction}
                className={`w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-gray-50 ${
                  lang.code === code ? "bg-orange-50" : ""
                }`}
              >
                <span className="min-w-0">
                  <span className="block text-base font-medium truncate">{lang.endonym}</span>
                  <span className="block text-xs text-gray-500 truncate" dir="ltr">
                    {lang.name}
                    {lang.regions?.length ? ` · ${lang.regions.slice(0, 2).join(", ")}` : ""}
                  </span>
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  <QualityBadge quality={lang.quality} percent={lang.percent} />
                  {lang.code === code && (
                    <Check className="w-4 h-4 text-orange-600" aria-hidden="true" />
                  )}
                </span>
              </button>
            ))}

            {unavailable.length > 0 && (
              <>
                <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Not yet translated
                  </p>
                  <p className="text-[11px] text-gray-500 mt-1 leading-relaxed">
                    {unavailable[0]?.reason ||
                      "These are listed so the gap is visible and can be filled."}
                  </p>
                </div>
                {unavailable.map((lang) => (
                  <div
                    key={lang.code}
                    dir={lang.direction}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 opacity-60"
                  >
                    <span className="min-w-0">
                      <span className="block text-sm truncate">{lang.endonym}</span>
                      <span className="block text-xs text-gray-500 truncate" dir="ltr">
                        {lang.name}
                      </span>
                    </span>
                    <QualityBadge quality={lang.quality} percent={0} />
                  </div>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Shown when the current page is partly or wholly English because the chosen
 * language has no translation. Saying so is the point: without it the interface
 * silently asserts that English is this person's language.
 */
export function FallbackBanner() {
  const {
    hasFallbacks, fallbackNotice, lowConfidence, qualityWarning,
    qualityWarningHindi, meta,
  } = useLanguage();

  // Two different messages, never merged. A fallback says "this is not your
  // language". A quality warning says "this is your language, but nobody who
  // speaks it has checked it." Collapsing them would lose the distinction that
  // tells the reader what to do next.
  if (hasFallbacks) {
    return (
      <div
        role="status"
        className="flex items-start gap-2 px-4 py-2.5 bg-amber-50 border-b border-amber-200 text-[13px] text-amber-900"
      >
        <Info className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <span>
          {fallbackNotice ||
            "This is not yet available in your language, so it is being shown in English."}
          {meta?.endonym ? ` (${meta.endonym})` : ""}
        </span>
      </div>
    );
  }

  if (lowConfidence) {
    return (
      <div
        role="status"
        className="flex items-start gap-2 px-4 py-2.5 bg-orange-50 border-b border-orange-200 text-[13px] text-orange-900"
      >
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <span>
          <span className="block">{qualityWarning}</span>
          {qualityWarningHindi && (
            <span className="block mt-0.5 opacity-90" lang="hi">
              {qualityWarningHindi}
            </span>
          )}
        </span>
      </div>
    );
  }

  return null;
}

export default LanguagePicker;
