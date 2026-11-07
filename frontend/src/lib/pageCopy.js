// Page copy - the interface text that lives in the screens rather than in the
// small, fully-translated core catalogue the backend serves.
//
// Why this is separate from the backend message catalogue. That catalogue
// (i18n/catalog.py) is a deliberately small set of ~40 strings, and a test
// enforces that every one of them exists in all 22 scheduled languages and
// reads differently from English - it is the set the project stands behind.
// The screens carry hundreds more strings. Fabricating all of them into 22
// languages is exactly what that catalogue's design forbids, so page copy
// lives here instead, in the two languages the app can actually write today:
// English (the universal fallback) and Hindi.
//
// The shape is per-key-then-per-language on purpose, so adding a real
// translation later - Tamil, Bengali - is a data change here and nothing in
// the components moves. `tx(key)` (see i18n.js) resolves a key against the
// live language, falling back to English, so a speaker of a language we cannot
// yet write sees readable English rather than Hindi they may not read. That
// fallback is the whole point: before this, these strings were hardcoded
// Hindi and shown to everyone.
//
// What must NOT go here: the privacy notice, the terms, and any statutory
// rights text. Those are legal instruments served from the backend (dpdp/) in
// English and Hindi only - a mistranslated consent notice is a defective
// consent. Keep this file to interface chrome: buttons, labels, toasts,
// headings, empty states.

export const PAGE_COPY = {
  // ── Shared / common ───────────────────────────────────────────────────
  "common.viewAll": { en: "View all", hi: "सभी देखें" },

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
    en: "Allow microphone access - turn on the permission in your browser settings",
    hi: "माइक्रोफोन एक्सेस दें - ब्राउज़र सेटिंग्स में अनुमति चालू करें",
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

  // ── Eligibility (short badges) ────────────────────────────────────────
  "status.eligibleShort": { en: "Eligible", hi: "पात्र" },
  "status.notEligibleShort": { en: "Not eligible", hi: "अपात्र" },

  // ── Downloads (chat forms, profiler) ──────────────────────────────────
  "download.failed": { en: "Download failed. Please try again.", hi: "डाउनलोड विफल हुआ। कृपया पुनः प्रयास करें।" },
  "download.networkError": { en: "Network error. Please check your internet and try again.", hi: "नेटवर्क त्रुटि। कृपया इंटरनेट जांचें और पुनः प्रयास करें।" },
  "download.done": { en: "Download complete!", hi: "डाउनलोड पूर्ण!" },
  "download.inProgress": { en: "Downloading…", hi: "डाउनलोड हो रहा है…" },
  "download.allPrefix": { en: "Download all", hi: "सभी" },
  "download.allSuffix": { en: "forms", hi: "फॉर्म डाउनलोड करें" },

  // ── Smart profiler ────────────────────────────────────────────────────
  "profiler.loadFailed": { en: "Could not load the profiler. Please try again.", hi: "प्रोफाइलर लोड नहीं हो सका। पुनः प्रयास करें।" },
  "profiler.saveError": { en: "Error while saving. Please try again.", hi: "सहेजने में त्रुटि। पुनः प्रयास करें।" },
  "profiler.formsReady": { en: "Application forms are ready!", hi: "आवेदन फॉर्म तैयार हैं!" },
  "profiler.noForms": { en: "No forms could be prepared", hi: "कोई फॉर्म तैयार नहीं हुआ" },
  "profiler.seeReasons": { en: "See the reasons below", hi: "नीचे दिए गए कारण देखें" },

  // ── Chat input ────────────────────────────────────────────────────────
  "chat.noFormPrepared": { en: "No form could be prepared. See the reasons below.", hi: "कोई फॉर्म तैयार नहीं हो सका। कारण नीचे देखें।" },
  "chat.stopRecording": { en: "Stop recording", hi: "रिकॉर्डिंग बंद करें" },
  "chat.welcome": { en: "Hello! Welcome to Nagarik Sahayak", hi: "नमस्ते! नागरिक सहायक में आपका स्वागत है" },
  "chat.welcomeSub": { en: "Help filling application forms for government schemes", hi: "सरकारी योजनाओं के लिए आवेदन फॉर्म भरने में सहायता" },
  "chat.startConversation": { en: "Start a conversation", hi: "बातचीत शुरू करें" },
  "chat.orStartTalking": { en: "Or start by talking", hi: "या बातचीत से शुरू करें" },
  "chat.uploadPdf": { en: "Upload PDF", hi: "PDF अपलोड करें" },
  "chat.selectedSchemes": {
    en: "You have selected {n} scheme(s):",
    hi: "आपने {n} योजना(एं) चुनी हैं:",
  },
  "chat.nowCompleteProfile": {
    en: "Now we'll complete your profile. Please answer the questions below.",
    hi: "अब हम आपकी प्रोफ़ाइल पूरी करेंगे। कृपया नीचे दिए गए सवालों का जवाब दें।",
  },
  "chat.formRefusedCount": {
    en: "A form could not be generated for {n} scheme(s) - see the reasons below.",
    hi: "{n} योजना के लिए फॉर्म नहीं बन सका - कारण नीचे देखें।",
  },
  "chat.flaggedCount": {
    en: "{n} application(s) sent for verification.",
    hi: "{n} आवेदन सत्यापन हेतु भेजा गया है।",
  },
  "chat.inputPlaceholder": { en: "Type your question here…", hi: "अपना सवाल यहाँ लिखें…" },
  "chat.formsReadyCount": {
    en: "{n} application forms are ready! Use the download button above.",
    hi: "{n} आवेदन फॉर्म तैयार हो गए! ऊपर डाउनलोड बटन से डाउनलोड करें।",
  },

  // ── Scheme selector ───────────────────────────────────────────────────
  "selector.chooseToApply": { en: "Choose one or more schemes to apply for", hi: "एक या अधिक योजनाएं चुनें जिनके लिए आवेदन करना है" },
  "selector.startApplication": { en: "Start application", hi: "आवेदन शुरू करें" },
  "selector.applyForN": { en: "Apply for {n} schemes", hi: "{n} योजनाओं के लिए आवेदन करें" },

  // ── Privacy screen chrome (headings & buttons, not the legal notice) ──
  "privacy.whatGrievance": { en: "What is your grievance?", hi: "आपकी शिकायत क्या है?" },
  "privacy.sending": { en: "Sending…", hi: "भेजा जा रहा है…" },
  "privacy.sendGrievance": { en: "Send grievance", hi: "शिकायत भेजें" },
  "privacy.nomineeActive": { en: "Active - this person can use your rights now", hi: "सक्रिय - यह व्यक्ति अभी आपके अधिकारों का उपयोग कर सकता है" },
  "privacy.saving": { en: "Saving…", hi: "सहेजा जा रहा है…" },
  "privacy.nominate": { en: "Nominate", hi: "नामित करें" },
  "privacy.eraseMyData": { en: "Erase my data", hi: "मेरा डेटा मिटाएं" },
  "privacy.decisionHelp": {
    en: "Details marked “Decision” are used to decide your eligibility.",
    hi: "“निर्णय” वाले विवरण आपकी पात्रता तय करने में उपयोग होते हैं।",
  },
  "privacy.consentNeeded": { en: "We need your permission", hi: "आपकी अनुमति चाहिए" },
  "privacy.consentExplain": {
    en: "To apply for schemes we need some of your details. You can",
    hi: "योजनाओं के लिए आवेदन करने हेतु हमें आपके कुछ विवरण चाहिए। आप कभी भी",
  },
  "privacy.canWithdraw": { en: "withdraw this permission at any time.", hi: "यह अनुमति वापस ले सकते हैं।" },
  "privacy.chooseEachPurpose": { en: "You can choose each purpose separately below.", hi: "नीचे प्रत्येक उद्देश्य अलग से चुन सकते हैं।" },
  "privacy.separatePermission": { en: "A separate permission for each purpose. Change it any time.", hi: "प्रत्येक उद्देश्य के लिए अलग अनुमति। कभी भी बदल सकते हैं।" },
  "privacy.required": { en: "Required", hi: "आवश्यक" },
  "privacy.storedFields": { en: "details stored", hi: "विवरण संग्रहीत" },
  "privacy.applications": { en: "applications", hi: "आवेदन" },
  "privacy.messages": { en: "messages", hi: "संदेश" },
  "privacy.decisionBadge": { en: "Decision", hi: "निर्णय" },
  "privacy.showMyData": { en: "Show my data", hi: "मेरा डेटा दिखाएं" },
  "privacy.versionAccepted": { en: "accepted", hi: "स्वीकृत" },
  "privacy.versionPrefix": { en: "Version", hi: "संस्करण" },
  "privacy.nomineeExplain": {
    en: "You can nominate someone to use your rights if you die or become incapacitated.",
    hi: "आप किसी को नामित कर सकते हैं जो आपकी मृत्यु या अक्षमता की स्थिति में आपके अधिकारों का उपयोग कर सके।",
  },
  "privacy.eraseWarning": {
    en: "All your details, application forms and conversations will be deleted. This cannot be undone.",
    hi: "आपके सभी विवरण, आवेदन फॉर्म और बातचीत मिटा दिए जाएंगे। यह वापस नहीं किया जा सकता।",
  },
  "privacy.areYouSure": { en: "Are you sure?", hi: "क्या आप निश्चित हैं?" },
  "privacy.phoneRetained": {
    en: "Your phone number will be kept for legal reasons. Everything else will be erased.",
    hi: "आपका फोन नंबर कानूनी कारणों से रखा जाएगा। बाकी सब मिट जाएगा।",
  },
  "privacy.keepIt": { en: "Keep it", hi: "रहने दें" },
  "privacy.yesErase": { en: "Yes, erase", hi: "हाँ, मिटाएं" },

  // ── Chat message chrome ───────────────────────────────────────────────
  "app.name": { en: "Nagarik Sahayak", hi: "नागरिक सहायक" },
  "chat.listen": { en: "Listen", hi: "सुनें" },
  "chat.copiedPaste": { en: "Copied! Paste it in WhatsApp", hi: "कॉपी हो गया! WhatsApp में पेस्ट करें" },
  "chat.shareWhatsApp": { en: "Share on WhatsApp", hi: "WhatsApp पर शेयर करें" },
  "download.pdf": { en: "Download PDF", hi: "PDF डाउनलोड करें" },

  // ── Smart profiler (continued) ────────────────────────────────────────
  "profiler.pdfError": { en: "Error while generating the PDF. Please try again.", hi: "PDF बनाने में त्रुटि। पुनः प्रयास करें।" },
  "profiler.allFieldsFilled": { en: "All {n} fields filled", hi: "सभी {n} फ़ील्ड भरे गए" },
  "profiler.generatingPdf": { en: "Generating PDF…", hi: "PDF बना रहे हैं…" },
  "profiler.generateDownload": { en: "Generate & download forms", hi: "फॉर्म बनाएं और डाउनलोड करें" },
  "profiler.progress": { en: "Profile progress", hi: "प्रोफ़ाइल प्रगति" },
  "common.edit": { en: "Edit", hi: "संपादित करें" },
  "common.saving": { en: "Saving…", hi: "सहेज रहे हैं…" },
  "common.continue": { en: "Continue", hi: "आगे बढ़ें" },
};
