import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BASE}/api`;

export const tz = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch (e) {
    return "";
  }
};

const client = axios.create({ baseURL: API, timeout: 45000 });

export const getWall = () => client.get("/wall", { params: { tz: tz() } }).then((r) => r.data);

export const getMessage = (id) =>
  client.get(`/message/${id}`, { params: { tz: tz() } }).then((r) => r.data);

export const getMessages = (sort) =>
  client.get("/messages", { params: { sort, tz: tz() } }).then((r) => r.data);

export const createOrder = (payload) =>
  client.post("/create-order", payload, { params: { tz: tz() } }).then((r) => r.data);

export const verifyPayment = (payload) =>
  client.post("/verify-payment", payload).then((r) => r.data);

export const paymentFailed = (payload) =>
  client.post("/payment-failed", payload).then((r) => r.data).catch(() => null);

export const adminLogin = (password) =>
  client.post("/admin/login", { password }).then((r) => r.data);

const hdr = (pw) => ({ headers: { "X-Admin-Password": pw } });

export const adminState = (pw) => client.get("/admin/state", hdr(pw)).then((r) => r.data);
export const adminPost = (pw, path, body) =>
  client.post(path, body || {}, hdr(pw)).then((r) => r.data);

export const errText = (e, fallback) =>
  e?.response?.data?.detail || e?.message || fallback || "The wall is not answering.";

export const ogUrl = (id) => `${API}/og/${id}.png`;
export const shareUrl = (id) => `${API}/m/${id}`;
