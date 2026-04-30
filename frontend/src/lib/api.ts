import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000/api`
    : "http://localhost:8000/api");

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add a request interceptor to add the JWT token to the headers
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const auth = window.localStorage.getItem("mediflow.auth");
      if (auth) {
        const parsed = JSON.parse(auth);
        const token = parsed?.token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Add a response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem("mediflow.auth");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
