import axios, {
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { "Content-Type": "application/json" },
});

// Request: attach access token
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response: unwrap envelope + 401 refresh & retry
apiClient.interceptors.response.use(
  (response) => {
    // 204 No Content — no body to unwrap
    if (response.status === 204) return response;
    // Unwrap standard envelope: { is_successful, status_code, message, data }
    if (response.data?.data !== undefined) {
      return { ...response, data: response.data.data };
    }
    return response;
  },
  async (error) => {
    const original = error.config as RetryableConfig;

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;

      const refreshToken =
        typeof window !== "undefined"
          ? localStorage.getItem("refresh_token")
          : null;

      if (!refreshToken) {
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("user");
          localStorage.removeItem("active_coop_id");
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }

      try {
        // Direct axios call — bypasses our interceptors to avoid loop
        const { data } = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/api/auth/refresh`,
          { refresh_token: refreshToken },
        );
        // The raw response has the envelope; unwrap manually
        const tokens = data.data;
        localStorage.setItem("access_token", tokens.access_token);
        localStorage.setItem("refresh_token", tokens.refresh_token);

        original.headers.Authorization = `Bearer ${tokens.access_token}`;
        return apiClient(original);
      } catch {
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("user");
          localStorage.removeItem("active_coop_id");
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
