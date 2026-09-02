import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getLanguageBundle, getLanguages } from "./api";

// English strings, bundled. The app must render in a usable language before the
// first network round-trip completes and must keep rendering if that round-trip
// fails — a citizen on a weak connection should see the interface, not a spinner
// where the navigation ought to be.
const FALLBACK = {
  "app.name": "Nagarik Sahayak",
  "app.tagline": "Government schemes, made simple",
  "nav.schemes": "Schemes",
  "nav.profile": "My Profile",
  "nav.documents": "Documents",
  "nav.privacy": "Privacy and Rights",
  "nav.help": "Help",
  "action.continue": "Continue",
  "action.back": "Back",
  "action.submit": "Submit",
  "action.save": "Save",
  "action.download": "Download",
  "action.upload": "Upload",
  "action.verify_identity": "Verify your identity",
  "action.skip": "Skip for now",
  "status.eligible": "You may be eligible",
  "status.not_eligible": "You do not meet this scheme's conditions",
  "status.incomplete": "More information is needed",
  "status.under_review": "An officer is checking this",
  "status.verified": "Verified",
  "status.not_verified": "Not verified",
  "label.name": "Full name",
  "label.date_of_birth": "Date of birth",
  "label.mobile": "Mobile number",
  "label.district": "District",
  "label.state": "State",
  "label.annual_income": "Annual family income",
  "msg.no_fee": "This service is free. Never pay anyone to use it.",
  "msg.not_government":
    "This app is not run by the government. It helps you prepare your application; you must submit it yourself.",
  "msg.aadhaar_optional":
    "Aadhaar is one option among several. A voter ID, ration card or job card also works.",
  "msg.language_unavailable":
    "This is not yet available in your language, so it is being shown in English.",
  "msg.error_generic": "Something went wrong. Your information is safe. Please try again.",
  "rights.summary": "You can see, correct or delete your information at any time.",
  "help.call_helpline": "Call the helpline",
};

const STORAGE_KEY = "ns_language";

const LanguageContext = createContext(null);

export function LanguageProvider({ children, initial }) {
  const [code, setCode] = useState(
    () => initial || localStorage.getItem(STORAGE_KEY) || "hi"
  );
  const [bundle, setBundle] = useState({ strings: FALLBACK, fallbacks: [] });
  const [languages, setLanguages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getLanguageBundle(code)
      .then((res) => {
        if (cancelled) return;
        setBundle(res.data);
      })
      .catch(() => {
        // Keep whatever is already rendered. Replacing a working interface with
        // an error because a translation file did not load would be a worse
        // outcome than showing the previous language.
        if (!cancelled) setBundle((b) => b);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [code]);

  useEffect(() => {
    getLanguages()
      .then((res) => setLanguages(res.data.languages || []))
      .catch(() => setLanguages([]));
  }, []);

  // Tell the browser and every assistive technology which language and
  // direction the page is in. Without this a screen reader pronounces Tamil
  // with English phonemes, and Urdu lays out left-to-right.
  useEffect(() => {
    const meta = bundle.language || {};
    document.documentElement.lang = meta.code || code;
    document.documentElement.dir = meta.direction === "rtl" ? "rtl" : "ltr";
  }, [bundle, code]);

  const change = useCallback((next) => {
    setCode(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const value = useMemo(() => {
    const strings = bundle.strings || FALLBACK;
    const fallbacks = new Set(bundle.fallbacks || []);
    return {
      code,
      setLanguage: change,
      languages,
      loading,
      meta: bundle.language || null,
      // True when any string on this page is English standing in for the
      // requested language. Surfaced so the UI can say so rather than letting
      // the reader assume the app decided English is their language.
      hasFallbacks: (bundle.fallbacks || []).length > 0,
      fallbackNotice: bundle.fallbackNotice || "",
      t: (key) => strings[key] ?? FALLBACK[key] ?? key,
      isFallback: (key) => fallbacks.has(key),
    };
  }, [bundle, code, change, languages, loading]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    // Used outside the provider — return a working English shim rather than
    // throwing, so one misplaced component cannot blank the whole page.
    return {
      code: "en",
      setLanguage: () => {},
      languages: [],
      loading: false,
      meta: null,
      hasFallbacks: false,
      fallbackNotice: "",
      t: (key) => FALLBACK[key] ?? key,
      isFallback: () => false,
    };
  }
  return ctx;
}

export function useT() {
  return useLanguage().t;
}

export { FALLBACK as ENGLISH_STRINGS };
