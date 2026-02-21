import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  headers: { "Content-Type": "application/json" },
});

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

// Voice
export const sendVoice = (formData) =>
  api.post("/chat/voice", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

export default api;
