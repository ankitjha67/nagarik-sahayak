import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor — attach user_id from localStorage
api.interceptors.request.use((config) => {
  const userId = localStorage.getItem("ns_user_id");
  if (userId) {
    config.headers["X-User-Id"] = userId;
  }
  return config;
});

// Endpoints that carry their own credentials and legitimately return 403 when
// those are wrong. A rejected reviewer password must surface as an error on the
// reviewer screen, not silently destroy the citizen's session and redirect them
// to the login page.
const SELF_AUTHENTICATING = ["/review/", "/forms/refresh", "/forms/seed", "/demo/toggle"];

// Response interceptor — handle 401/403
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || "";
    const selfAuth = SELF_AUTHENTICATING.some((p) => url.includes(p));
    if (!selfAuth && (status === 401 || status === 403)) {
      localStorage.removeItem("ns_user_id");
      localStorage.removeItem("ns_phone");
      localStorage.removeItem("ns_language");
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

// Cancel token helper using AbortController
export const createCancelToken = () => {
  const controller = new AbortController();
  return { signal: controller.signal, cancel: () => controller.abort() };
};

// Auth
export const sendOTP = (phone) => api.post("/auth/send-otp", { phone });
export const verifyOTP = (phone, otp) => api.post("/auth/verify-otp", { phone, otp });

// Profile
export const getProfile = (userId) => api.get(`/profile/${userId}`);
export const updateProfile = (userId, data) => api.put(`/profile/${userId}`, data);

// Schemes
export const getSchemes = () => api.get("/schemes");
export const getScheme = (id) => api.get(`/schemes/${id}`);

// Chat
export const sendMessage = (userId, content, language = "hi") =>
  api.post("/chat", { user_id: userId, content, language });
export const getChatHistory = (userId) => api.get(`/chat/history/${userId}`);

// Voice (legacy)
export const sendVoice = (formData) =>
  api.post("/chat/voice", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

// Sarvam Transcribe
export const transcribeAudio = (formData) =>
  api.post("/transcribe", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

// MCP Tools
export const getMcpTools = () => api.get("/mcp/tools");
export const searchSchemes = (query) => api.post("/search-schemes", { query });
export const eligibilityCheck = (data) => api.post("/eligibility-check", data);

// PDF
export const generatePdf = (data) => api.post("/generate-pdf", data);

// Upload PDF
export const uploadPdf = (formData) =>
  api.post("/upload-pdf", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

// Reset Chat
export const resetChat = (userId) => api.post("/chat/reset", { user_id: userId });

// ── V2.0 APIs ──

export const getV2Schemes = () => api.get("/v2/schemes");

export const getFormTemplate = (schemeName) =>
  api.get(`/v2/form-template/${encodeURIComponent(schemeName)}`);

export const getFormTemplates = () => api.get("/v2/form-templates");

export const getUserFullProfile = (userId) => api.get(`/v2/user-profile/${userId}`);

export const updateUserFullProfile = (userId, fields) =>
  api.post(`/v2/user-profile/${userId}`, { fields });

export const smartProfiler = (userId, schemeNames) =>
  api.post("/v2/smart-profiler", { user_id: userId, scheme_names: schemeNames });

export const generateRealFilledForms = (userId, schemeNames) =>
  api.post("/v2/generate-filled-forms", { user_id: userId, scheme_names: schemeNames });

// Upload PDF and extract form fields (new scheme onboarding)
export const uploadAndExtract = (formData) =>
  api.post("/upload-and-extract", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000, // 2 min — extraction can take time
  });

// ── V3 Discovery APIs ──

export const getDiscoveryStatus = () => api.get("/discovery/status");
export const triggerDiscoveryCrawl = (portalNames) =>
  api.post("/discovery/crawl", portalNames ? { portal_names: portalNames } : {});
export const getDiscoveryPortals = () => api.get("/discovery/portals");
export const getPortalHealth = () => api.get("/discovery/portal-health");
export const getDiscoveryStats = () => api.get("/discovery/stats");

// ── V3 Exam APIs ──

export const getExams = (params = {}) =>
  api.get("/exams", { params });
export const getExamAlerts = (daysAhead = 30) =>
  api.get("/exams/alerts", { params: { days_ahead: daysAhead } });
export const getExamCategories = () => api.get("/exams/categories");
export const getExamStats = () => api.get("/exams/stats");
export const getExamDetail = (examId) => api.get(`/exams/${examId}`);

// ── V3 Report APIs ──

export const downloadSchemesExcel = () =>
  api.get("/reports/schemes-excel", { responseType: "blob", timeout: 120000 });
export const downloadExamsExcel = () =>
  api.get("/reports/exams-excel", { responseType: "blob", timeout: 120000 });
export const getNotificationConfig = () => api.get("/reports/notification-config");
export const sendSchemeAlert = (data) => api.post("/reports/send-alert", data);

// ── Discovered Schemes (V3 crawler DB) ──

export const getDiscoveredSchemes = (params = {}) =>
  api.get("/discovery/schemes", { params });
export const resetPortalHealth = (portalName) =>
  api.post(`/discovery/portal-health/${encodeURIComponent(portalName)}/reset`);

// ── Real Government Forms ──

export const getFormCatalog = () => api.get("/forms/catalog");
export const getFormCatalogDetail = (schemeName) =>
  api.get(`/forms/catalog/${encodeURIComponent(schemeName)}`);
export const getFormLinkHealth = () => api.get("/forms/link-health", { timeout: 120000 });
export const seedFormCatalog = (overwrite = false) =>
  api.post("/forms/seed", { overwrite });
// Live extraction downloads + OCRs a government PDF, so it needs a long timeout.
export const extractLiveForm = (pdfUrl, schemeHint = "", saveToDb = false) =>
  api.post(
    "/forms/extract-live",
    { pdf_url: pdfUrl, scheme_hint: schemeHint, save_to_db: saveToDb },
    { timeout: 180000 }
  );

// ── DPDP Act: notice, consent, and data principal rights ──

export const getPrivacyNotice = () => api.get("/dpdp/notice");
export const getConsent = (userId) => api.get(`/dpdp/consent/${userId}`);
export const grantConsent = (userId, purposes, opts = {}) =>
  api.post(`/dpdp/consent/${userId}`, {
    purposes,
    language: opts.language || "hi",
    parental_consent: !!opts.parentalConsent,
  });
export const withdrawConsent = (userId, purposes) =>
  api.post(`/dpdp/consent/${userId}/withdraw`, purposes ? { purposes } : {});
export const getMyData = (userId) => api.get(`/dpdp/my-data/${userId}`);
export const eraseMyData = (userId, body) => api.post(`/dpdp/erase/${userId}`, body);
export const lodgeRightsRequest = (userId, requestType, details) =>
  api.post(`/dpdp/request/${userId}`, { request_type: requestType, details });

// ── Terms of service and s14 nomination ──

export const getTerms = () => api.get("/dpdp/terms");
export const getTermsStatus = (userId) => api.get(`/dpdp/terms/status/${userId}`);
export const acceptTerms = (userId, version) =>
  api.post(`/dpdp/terms/accept/${userId}`, { version });
export const getNominee = (userId) => api.get(`/dpdp/nominee/${userId}`);
export const setNominee = (userId, nominee) =>
  api.post(`/dpdp/nominee/${userId}`, nominee);
export const removeNominee = (userId) => api.delete(`/dpdp/nominee/${userId}`);

// ── Reviewer queue ──
// Reviewer credentials are passed per-call rather than stored on the shared
// axios instance, so an ordinary citizen session can never accidentally carry
// them. `creds` is {adminSecret, reviewerId}.

const reviewHeaders = (creds) => ({
  "X-Admin-Secret": creds?.adminSecret || "",
  "X-Reviewer-Id": creds?.reviewerId || "",
});

export const getReviewQueue = (creds, { status = "pending", limit = 50, offset = 0 } = {}) =>
  api.get("/review/queue", { params: { status, limit, offset }, headers: reviewHeaders(creds) });
export const getReviewCase = (creds, caseId) =>
  api.get(`/review/case/${caseId}`, { headers: reviewHeaders(creds) });
export const decideReviewCase = (creds, caseId, decision, note = "") =>
  api.post(`/review/case/${caseId}/decide`, { decision, note }, { headers: reviewHeaders(creds) });
export const reopenReviewCase = (creds, caseId, note = "") =>
  api.post(`/review/case/${caseId}/reopen`, { note }, { headers: reviewHeaders(creds) });
export const getMyReviewCases = (userId) => api.get(`/review/my-cases/${userId}`);

// ── Verification: field validity, eligibility, abuse screening ──

export const verifyFields = (profile, schemeName) =>
  api.post("/verify/fields", { profile, scheme_name: schemeName });
export const verifyEligibility = (profile, schemeName) =>
  api.post("/verify/eligibility", { profile, scheme_name: schemeName });
export const verifyApplication = (profile, schemeName, userId) =>
  api.post("/verify/application", {
    profile, scheme_name: schemeName, user_id: userId,
  });
export const screenAllSchemes = (profile, userId) =>
  api.post("/verify/screen-all", { profile, user_id: userId }, { timeout: 60000 });

// ── Notification Preferences & Exam Subscriptions ──

export const getNotificationPreferences = (userId) =>
  api.get(`/notifications/preferences/${userId}`);
export const updateNotificationPreferences = (userId, prefs) =>
  api.put(`/notifications/preferences/${userId}`, prefs);
export const getExamSubscriptions = (userId) =>
  api.get(`/notifications/subscriptions/${userId}`);
export const subscribeToExam = (userId, data) =>
  api.post(`/notifications/subscriptions/${userId}`, data);
export const unsubscribeFromExam = (userId, subscriptionId) =>
  api.delete(`/notifications/subscriptions/${userId}/${subscriptionId}`);

// ── Languages ──
// Public: a person is entitled to read the interface in their own language
// before signing in, so none of these carries a user header requirement.

export const getLanguages = () => api.get("/i18n/languages");
export const getLanguageBundle = (code) => api.get(`/i18n/bundle/${code}`);
export const suggestLanguage = (state) =>
  api.get("/i18n/suggest", { params: state ? { state } : {} });
export const getLanguageCoverage = () => api.get("/i18n/coverage");

// ── KYC / identity verification ──
// None of these is a precondition for applying. They raise confidence in an
// identity, which speeds a claim; the Aadhaar Act s7 proviso means a benefit
// cannot be refused for want of authentication.

export const getKycMethods = (onlyAvailable = false) =>
  api.get("/kyc/methods", { params: { only_available: onlyAvailable } });
export const getKycMethod = (key) => api.get(`/kyc/methods/${key}`);
export const verifyAadhaarOfflineXml = (profile, fileBase64, shareCode) =>
  api.post("/kyc/aadhaar/offline-xml", { profile, fileBase64, shareCode },
           { timeout: 30000 });
export const verifyAadhaarSecureQr = (profile, qr) =>
  api.post("/kyc/aadhaar/secure-qr", { profile, qr });
export const recordAttestation = (payload) => api.post("/kyc/attestation", payload);
export const recordSelfDeclaration = (profile) =>
  api.post("/kyc/self-declaration", { profile });
export const getKycStatus = (outcomes) => api.post("/kyc/status", { outcomes });
export const getKycSchemeGap = (outcomes, schemeName) =>
  api.post("/kyc/scheme-gap", { outcomes, schemeName });

// ── Scheme catalog, filtered by level and State ──
// Passing a state returns that State's schemes *and* every Central scheme; a
// resident of Bihar can claim both.

export const getFormCatalog = ({ level, state } = {}) =>
  api.get("/forms/catalog", { params: { ...(level && { level }), ...(state && { state }) } });
export const getCatalogStates = () => api.get("/forms/catalog-states");

export default api;
