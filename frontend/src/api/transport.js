// src/api/transport.js — axios instance + refresh-queue state
// Co-located per scope doc §5 R5 mitigation 1: isRefreshing + failedRequestsQueue
// MUST stay in the same module as the axios instance to prevent thunder-herd.

import axios from 'axios';
import { clearTokens, getAccessToken, getCsrfToken } from './session';

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

// Request interceptor: Add JWT token from the in-memory session helper.
apiClient.interceptors.request.use(
  (config) => {
    config.headers = config.headers ?? {};

    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    const method = (config.method ?? 'get').toLowerCase();
    const isUnsafeMethod = ['post', 'put', 'patch', 'delete'].includes(method);
    const csrfToken = isUnsafeMethod ? getCsrfToken() : null;
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }

    if (
      config.url?.includes('/auth/login') ||
      config.url?.includes('/auth/refresh') ||
      config.url?.includes('/auth/logout')
    ) {
      config.withCredentials = true;
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
        // Wave 7 D.1 shape: {code: "revision_mismatch", message: "..."}).
        // Prefer a human-readable message field if present; fall back to
        // JSON serialization so diagnostics aren't lost as "[object Object]".
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
    // Prefer the request_id from the standardized error body (Wave 2),
    // but fall back to the X-Request-ID response header (Wave 6 T2)
    // when the body is missing one — e.g. non-JSON responses, upstream
    // proxy errors, or handlers that bypass the standardized shape.
    // Axios lower-cases response header names.
    const headerRequestId = error.response?.headers?.['x-request-id'] ?? null;
    error.normalized = {
      detail: normalizedDetail,
      errorCode: responseData?.error_code ?? null,
      requestId: responseData?.request_id ?? headerRequestId,
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
        originalRequest.url?.includes('/auth/refresh') ||
        originalRequest.url?.includes('/auth/logout')
      ) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Another request is already refreshing, queue this one
        return new Promise((resolve, reject) => {
          failedRequestsQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers = originalRequest.headers ?? {};
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;
      let hadAccessToken = false;

      try {
        // Import auth store dynamically to avoid circular dependency
        const { useAuthStore } = await import('@/stores/authStore');
        const authStore = useAuthStore();
        hadAccessToken = !!authStore.accessToken;

        // Attempt to refresh access token
        const newAccessToken = await authStore.refreshAccessToken();

        // Success! Process queued requests with new token
        processQueue(null, newAccessToken);
        isRefreshing = false;

        // Retry original request with new token
        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - clear queue and redirect to login
        processQueue(refreshError, null);
        isRefreshing = false;

        // Clear auth state and preserve return intent only for active sessions.
        window.logService.warn('Token refresh failed, redirecting to login');
        clearTokens();

        if (hadAccessToken) {
          const { buildLoginLocation, default: router } = await import('@/router');
          const currentFullPath =
            router.currentRoute.value?.fullPath ??
            `${window.location.pathname}${window.location.search ?? ''}${window.location.hash ?? ''}`;

          await router.push(buildLoginLocation(currentFullPath));
        }

        return Promise.reject(refreshError);
      }
    }

    // For other errors or if retry failed, just reject
    return Promise.reject(error);
  }
);
