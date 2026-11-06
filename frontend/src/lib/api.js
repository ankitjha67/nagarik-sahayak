import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  headers: { "Content-Type": "application/json" },
});

// ── Session ──
// The server issues a short-lived signed access token and an opaque refresh
// token that rotates on every use. Both live in localStorage for this
// single-page client; the access token is attached to every request and
// silently refreshed once on a 401 before the session is treated as gone.

const KEYS = { access: "ns_access", refresh: "ns_refresh", role: "ns_role", user: "ns_user_id", phone: "ns_phone" };

const safeGet = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const safeSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } };
const safeDel = (k) => { try { localStorage.removeItem(k); } catch { /* storage unavailable */ } };

export const storeSession = ({ access_token, refresh_token, role, user_id, phone }) => {
  if (access_token) safeSet(KEYS.access, access_token);
  if (refresh_token) safeSet(KEYS.refresh, refresh_token);
  if (role) safeSet(KEYS.role, role);
  if (user_id) safeSet(KEYS.user, user_id);
  if (phone) safeSet(KEYS.phone, phone);
};

export const clearSession = () => {
  Object.values(KEYS).forEach(safeDel);
  safeDel("ns_language");
};

export const sessionRole = () => safeGet(KEYS.role) || "citizen";
export const hasSession = () => !!safeGet(KEYS.access);

// Request interceptor — attach the bearer token
api.interceptors.request.use((config) => {
  const token = safeGet(KEYS.access);
  if (token) config.headers["Authorization"] = `Bearer ${token}`;
  return config;
});

// Endpoints that carry their own credentials and legitimately return 403 when
// those are wrong. A rejected reviewer password must surface as an error on the
// reviewer screen, not silently destroy the citizen's session and redirect them
// to the login page.
const SELF_AUTHENTICATING = ["/review/", "/forms/refresh", "/forms/seed", "/demo/toggle", "/auth/"];

let refreshing = null;
const refreshAccessToken = async () => {
  const refresh = safeGet(KEYS.refresh);
  if (!refresh) throw new Error("no refresh token");
  if (!refreshing) {
    refreshing = axios
      .post(`${API}/auth/refresh`, { refresh_token: refresh })
      .then((r) => { storeSession(r.data); return r.data.access_token; })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
};

const endSession = () => {
  clearSession();
  window.location.href = "/";
};

// Response interceptor — refresh once on 401, otherwise end the session
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status;
    const config = error.config || {};
    const url = config.url || "";
    const selfAuth = SELF_AUTHENTICATING.some((p) => url.includes(p));
    if (selfAuth) return Promise.reject(error);

    if (status === 401 && !config._retried && safeGet(KEYS.refresh)) {
      config._retried = true;
      try {
        const token = await refreshAccessToken();
        config.headers = { ...(config.headers || {}), Authorization: `Bearer ${token}` };
        return api.request(config);
      } catch {
        endSession();
        return Promise.reject(error);
      }
    }
    if (status === 401) endSession();
    // 403 means "not yours": the session is fine, the caller shows the message.
    return Promise.reject(error);
  }
);

export const logoutServer = async () => {
  try { await api.post("/auth/logout"); } catch { /* already gone */ }
  clearSession();
};
export const refreshSession = () => api.post("/auth/refresh", { refresh_token: safeGet(KEYS.refresh) });
export const whoAmI = () => api.get("/auth/me");

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

// Voice turn in the chat: audio (any container) or on-device text. The server
// picks a speech engine with fallback; `provider` may name one explicitly.
export const transcribeAudio = (formData) =>
  api.post("/transcribe", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 90000,
  });

// ── Speech to text, provider-agnostic ──
export const getSttProviders = (language = "hi") =>
  api.get("/stt/providers", { params: { language } });
export const sttTranscribe = (formData) =>
  api.post("/stt/transcribe", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 90000,
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
// getFormCatalog is defined once, further down, in its parameterised form
// (level/state filtering) — it was declared a second time here as well, and two
// `export const` of one name in a module is a SyntaxError that fails the whole
// build. The parameterised version is a superset: called with no arguments it
// behaves exactly as this plain one did.

export const getFormCatalogDetail = (schemeName) =>
  api.get(`/forms/catalog/${encodeURIComponent(schemeName)}`);
// "What to carry to the counter" — the documents a scheme's form implies,
// bilingual, with the reason for each and the alternatives the law allows.
export const getSchemeDocuments = (schemeName) =>
  api.get(`/forms/catalog/${encodeURIComponent(schemeName)}/documents`);
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
// `kycOutcomes` are whatever the /kyc endpoints returned for this citizen.
// Passing none is normal and never counts against them — under the Aadhaar Act
// s7 proviso a benefit cannot be refused for want of authentication. Passing
// them can only lower the friction an honest applicant meets.
export const verifyApplication = (profile, schemeName, userId, kycOutcomes = []) =>
  api.post("/verify/application", {
    profile, scheme_name: schemeName, user_id: userId,
    kyc_outcomes: kycOutcomes,
  });
export const screenAllSchemes = (profile, userId, kycOutcomes = []) =>
  api.post("/verify/screen-all",
           { profile, user_id: userId, kyc_outcomes: kycOutcomes },
           { timeout: 60000 });

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
