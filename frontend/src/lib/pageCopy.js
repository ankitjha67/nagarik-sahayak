// Page copy — the interface text that lives in the screens rather than in the
// small, fully-translated core catalogue the backend serves.
//
// Why this is separate from the backend message catalogue. That catalogue
// (i18n/catalog.py) is a deliberately small set of ~40 strings, and a test
// enforces that every one of them exists in all 22 scheduled languages and
// reads differently from English — it is the set the project stands behind.
// The screens carry hundreds more strings. Fabricating all of them into 22
// languages is exactly what that catalogue's design forbids, so page copy
// lives here instead, in the two languages the app can actually write today:
// English (the universal fallback) and Hindi.
//
// The shape is per-key-then-per-language on purpose, so adding a real
// translation later — Tamil, Bengali — is a data change here and nothing in
// the components moves. `tx(key)` (see i18n.js) resolves a key against the
// live language, falling back to English, so a speaker of a language we cannot
// yet write sees readable English rather than Hindi they may not read. That
// fallback is the whole point: before this, these strings were hardcoded
// Hindi and shown to everyone.
//
// What must NOT go here: the privacy notice, the terms, and any statutory
// rights text. Those are legal instruments served from the backend (dpdp/) in
// English and Hindi only — a mistranslated consent notice is a defective
// consent. Keep this file to interface chrome: buttons, labels, toasts,
// headings, empty states.

export const PAGE_COPY = {
  // ── Shared / common ───────────────────────────────────────────────────
  "common.viewAll": { en: "View all", hi: "सभी देखें" },
  "common.retry": { en: "Try again", hi: "फिर से कोशिश करें" },
  "common.loading": { en: "Loading…", hi: "लोड हो रहा है…" },
  "common.close": { en: "Close", hi: "बंद करें" },
  "common.cancel": { en: "Cancel", hi: "रद्द करें" },
  "common.somethingWrong": {
    en: "Something went wrong. Please try again.",
    hi: "कुछ गलत हो गया। कृपया फिर से कोशिश करें।",
  },

  // ── Home screen ───────────────────────────────────────────────────────
  "home.greeting": { en: "Hello! How can we help?", hi: "नमस्ते! कैसे मदद करें?" },
  "home.subtitle": {
    en: "Ask about government schemes, eligibility, or apply for services",
    hi: "सरकारी योजनाओं, पात्रता या सेवाओं के लिए आवेदन के बारे में पूछें",
  },
  "home.quick.schemes": { en: "Schemes", hi: "योजनाएं" },
  "home.quick.eligibility": { en: "Check eligibility", hi: "पात्रता जांचें" },
  "home.quick.help": { en: "Help", hi: "हेल्प" },
  "home.askByVoice": { en: "Ask by voice", hi: "बोलकर पूछें" },
  "home.schemesHeading": { en: "Government schemes", hi: "सरकारी योजनाएं" },
  "home.examAlertsHeading": { en: "Exam alerts", hi: "परीक्षा अलर्ट" },
  "home.goToChat": { en: "Chat", hi: "चैट करें" },
  "home.searchEngineTitle": { en: "Scheme search engine", hi: "योजना खोज इंजन" },
  "home.recentChatsHeading": { en: "Recent conversations", hi: "हाल की बातचीत" },
  "home.noConversations": {
    en: "No conversations yet. Start chatting!",
    hi: "अभी कोई बातचीत नहीं। चैट शुरू करें!",
  },
  "home.daysLeft": { en: "days left", hi: "दिन शेष" },

  // ── Login / OTP ───────────────────────────────────────────────────────
  "login.enterMobile": { en: "Enter your mobile number", hi: "मोबाइल नंबर दर्ज करें" },
  "login.invalidPhone": {
    en: "Please enter a valid 10-digit mobile number",
    hi: "कृपया मान्य 10-अंकों का मोबाइल नंबर दर्ज करें",
  },
  "login.sendOtp": { en: "Send OTP", hi: "OTP भेजें" },
  "login.otpSent": { en: "OTP sent!", hi: "OTP भेजा गया!" },
  "login.sendFailed": { en: "Could not send OTP. Please try again.", hi: "OTP नहीं भेजा जा सका। कृपया फिर से कोशिश करें।" },
  "login.enterOtp": { en: "Enter the OTP", hi: "OTP सत्यापित करें" },
  "login.sentTo": { en: "OTP sent to", hi: "OTP भेजा गया" },
  "login.verify": { en: "Verify", hi: "सत्यापित करें" },
  "login.verified": { en: "Verified! Welcome", hi: "सत्यापित! आपका स्वागत है" },
  "login.invalidOtp": { en: "Invalid OTP", hi: "गलत OTP" },
  "login.verifyFailed": { en: "Verification failed. Please try again.", hi: "सत्यापन विफल रहा। कृपया फिर से कोशिश करें।" },
  "login.changeNumber": { en: "Change number", hi: "नंबर बदलें" },

  // ── Header / chrome ───────────────────────────────────────────────────
  "header.newChat": { en: "Start a new chat", hi: "नई चैट शुरू करें" },
  "header.goBack": { en: "Go back", hi: "पीछे जाएं" },
  "header.openMenu": { en: "Open menu", hi: "मेन्यू खोलें" },

  // ── Profile ───────────────────────────────────────────────────────────
  "profile.notifSaved": { en: "Notification settings saved!", hi: "नोटिफिकेशन सेटिंग सेव हो गई!" },
  "profile.saved": { en: "Profile updated!", hi: "प्रोफाइल अपडेट हो गया!" },
  "profile.namePlaceholder": { en: "Enter your name", hi: "अपना नाम दर्ज करें" },
  "profile.save": { en: "Save", hi: "सेव करें" },
  "profile.saveAlerts": { en: "Save alert settings", hi: "अलर्ट सेव करें" },

  // ── Chat ──────────────────────────────────────────────────────────────
  "chat.recordingStarted": { en: "s recording… please speak", hi: "s रिकॉर्डिंग शुरू… बोलें" },
  "chat.micDenied": {
    en: "Allow microphone access — turn on the permission in your browser settings",
    hi: "माइक्रोफोन एक्सेस दें — ब्राउज़र सेटिंग्स में अनुमति चालू करें",
  },
  "chat.newChatStarted": { en: "New chat started!", hi: "नई चैट शुरू हो गई!" },

  // ── Privacy / consent (UI chrome only; the notice & terms come from the
  //    backend in English and Hindi and are never machine-translated here) ──
  "privacy.consentRecorded": { en: "Consent recorded", hi: "सहमति दर्ज की गई" },
  "privacy.consentWithdrawn": { en: "Consent withdrawn", hi: "सहमति वापस ले ली गई" },
  "privacy.allConsentWithdrawn": { en: "All permissions withdrawn", hi: "सभी अनुमतियाँ वापस ले ली गईं" },
  "privacy.thanksCanApply": {
    en: "Thank you! You can now apply for schemes.",
    hi: "धन्यवाद! अब आप योजनाओं के लिए आवेदन कर सकते हैं।",
  },
  "privacy.detailsErased": { en: "details erased", hi: "विवरण मिटा दिए गए" },
  "privacy.termsAccepted": { en: "Terms accepted", hi: "शर्तें स्वीकार की गईं" },
  "privacy.nomineeRecorded": { en: "Nominee recorded", hi: "नामित व्यक्ति दर्ज किया गया" },
  "privacy.nomineeRemoved": { en: "Nomination removed", hi: "नामांकन हटा दिया गया" },
  "privacy.grievanceLodged": { en: "Your grievance has been lodged", hi: "आपकी शिकायत दर्ज कर ली गई है" },
};
