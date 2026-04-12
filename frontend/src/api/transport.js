// src/api/transport.js — axios instance + refresh-queue state
// Co-located per scope doc §5 R5 mitigation 1: isRefreshing + failedRequestsQueue
// MUST stay in the same module as the axios instance to prevent thunder-herd.

import axios from 'axios';
import { getAccessToken } from './session';

export const apiClient = axios.create({
  // Use Vite proxy in development (avoids CORS), direct URL in production
  baseURL: import.meta.env.VITE_API_URL || '/api/v2',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent infinite refresh loops
let isRefreshing = false;
// Queue for failed requests during token refresh
let failedRequestsQueue = [];

/**
 * Process queued requests after token refresh.
 * @param {Error|null} error - Error if refresh failed
 * @param {string|null} token - New access token if refresh succeeded
 */
function processQueue(error, token = null) {
  failedRequestsQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve(token);
    }
  });
  failedRequestsQueue = [];
}

// Request interceptor: Add JWT token from localStorage
// Note: We use localStorage directly here for performance (synchronous)
// The auth store manages the same tokens and keeps them in sync
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle token refresh on 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Normalize standardized backend error shape (Wave 2 T11):
    //   { detail, error_code, request_id }
    // Backwards-compatible fallback for legacy FastAPI errors which only
    // had { detail } (string or array). Attaches `error.normalized` so
    // downstream callers can read a uniform shape.
    const responseData = error.response?.data;
    let normalizedDetail = error.message;
    if (responseData) {
      if (typeof responseData.detail === 'string') {
        normalizedDetail = responseData.detail;
      } else if (Array.isArray(responseData.detail)) {
        // Legacy FastAPI validation error shape (list of {loc, msg, type})
        normalizedDetail = responseData.detail
          .map((item) =>
            item && typeof item === 'object' && 'msg' in item ? item.msg : String(item)
          )
          .join('; ');
      } else if (responseData.detail && typeof responseData.detail === 'object') {
        // Structured dict details preserved by the backend handler (e.g.,
        // {error: "conflict", current_revision: 5} from the update-conflict
        // endpoint). Prefer a human-readable message field if present; fall
        // back to JSON serialization so diagnostics aren't lost as
        // "[object Object]".
        const d = responseData.detail;
        if (typeof d.message === 'string') {
          normalizedDetail = d.message;
        } else if (typeof d.error === 'string') {
          normalizedDetail = d.error;
        } else {
          try {
            normalizedDetail = JSON.stringify(d);
          } catch {
            normalizedDetail = String(d);
          }
        }
      } else if (responseData.detail != null) {
        normalizedDetail = String(responseData.detail);
      }
    }
    error.normalized = {
      detail: normalizedDetail,
      errorCode: responseData?.error_code ?? null,
      requestId: responseData?.request_id ?? null,
    };

    // Log normalized error (logService redacts sensitive fields automatically)
    if (window.logService && error.response) {
      window.logService.error('API request failed', {
        status: error.response.status,
        url: originalRequest?.url,
        detail: error.normalized.detail,
        errorCode: error.normalized.errorCode,
        requestId: error.normalized.requestId,
      });
    }

    // If 401 and not already retrying, attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Skip refresh for auth endpoints to prevent infinite loops
      if (
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/refresh')
      ) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Another request is already refreshing, queue this one
        return new Promise((resolve, reject) => {
          failedRequestsQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Import auth store dynamically to avoid circular dependency
        const { useAuthStore } = await import('@/stores/authStore');
        const authStore = useAuthStore();

        // Attempt to refresh access token
        const newAccessToken = await authStore.refreshAccessToken();

        // Success! Process queued requests with new token
        processQueue(null, newAccessToken);
        isRefreshing = false;

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - clear queue and redirect to login
        processQueue(refreshError, null);
        isRefreshing = false;

        // Clear auth state and redirect
        window.logService.warn('Token refresh failed, redirecting to login');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        // Only redirect if not already on login page
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }

        return Promise.reject(refreshError);
      }
    }

    // For other errors or if retry failed, just reject
    return Promise.reject(error);
  }
);
