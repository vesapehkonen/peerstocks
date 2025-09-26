import axios from "axios";

// CRA reads env vars prefixed with REACT_APP_ at build time
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export default api;
