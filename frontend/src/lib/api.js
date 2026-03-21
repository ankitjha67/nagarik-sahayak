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

// Response interceptor — handle 401/403
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && (error.response.status === 401 || error.response.status === 403)) {
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
  api.get("/reports/schemes-excel", { responseType: "blob" });
export const downloadExamsExcel = () =>
  api.get("/reports/exams-excel", { responseType: "blob" });
export const getNotificationConfig = () => api.get("/reports/notification-config");
export const sendSchemeAlert = (data) => api.post("/reports/send-alert", data);

export default api;
