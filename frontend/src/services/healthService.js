/**
 * Backend Health Monitoring Service
 *
 * Tracks backend connectivity and system health with optimizations:
 * - Uses lightweight /health endpoint (not /aggregate/summary)
 * - Page Visibility API to pause polling when tab is hidden (bfcache friendly)
 * - Adaptive polling: faster when recovering, slower when stable
 *
 * Based on agde-frontend healthService pattern with performance improvements.
 */

import axios from 'axios';

/** Polling intervals in milliseconds */
const INTERVALS = {
  /** Normal polling when connected */
  NORMAL: 60000, // 60 seconds (reduced from 30s)
  /** Fast polling when recovering from disconnect */
  RECOVERY: 10000, // 10 seconds
  /** Slow polling when tab is hidden */
  BACKGROUND: 120000, // 2 minutes
};

/** Maximum retries before giving up */
const MAX_RETRIES = 3;

/** Request timeout in milliseconds */
const REQUEST_TIMEOUT = 5000;

class HealthService {
  constructor() {
    this.status = {
      backend: {
        connected: false,
        version: null,
        lastCheck: null,
        responseTime: null,
        error: null,
      },
    };

    this.subscribers = new Set();
    this.checkInterval = null;
    this.isTabVisible = true;
    this.consecutiveFailures = 0;

    // Use lightweight /health endpoint (goes through Vite proxy in dev)
    // Always use relative URL to avoid CORS issues
    this.healthCheckUrl = '/health';

    // Bind methods for event listeners
    this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
  }

  /**
   * Start periodic health checks with visibility-aware polling.
   * @param {number} intervalMs - Initial polling interval (default: 60s)
   */
  startMonitoring(intervalMs = INTERVALS.NORMAL) {
    // Setup Page Visibility API listener (bfcache friendly)
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.handleVisibilityChange);
      this.isTabVisible = document.visibilityState === 'visible';
    }

    // Initial check
    this.checkBackendHealth();

    // Start periodic checks with adaptive interval
    this.scheduleNextCheck(intervalMs);
  }

  /**
   * Stop health checks and cleanup.
   */
  stopMonitoring() {
    if (this.checkInterval) {
      clearTimeout(this.checkInterval);
      this.checkInterval = null;
    }

    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    }
  }

  /**
   * Handle tab visibility changes.
   * Pauses/resumes polling based on tab visibility (bfcache optimization).
   */
  handleVisibilityChange() {
    const wasVisible = this.isTabVisible;
    this.isTabVisible = document.visibilityState === 'visible';

    if (this.isTabVisible && !wasVisible) {
      // Tab became visible - do immediate check and resume normal polling
      window.logService?.debug('Health monitoring resumed (tab visible)');
      this.checkBackendHealth();
      this.scheduleNextCheck(this.getCurrentInterval());
    } else if (!this.isTabVisible && wasVisible) {
      // Tab became hidden - switch to slower background polling
      window.logService?.debug('Health monitoring slowed (tab hidden)');
      this.scheduleNextCheck(INTERVALS.BACKGROUND);
    }
  }

  /**
   * Get the appropriate polling interval based on current state.
   * @returns {number} Interval in milliseconds
   */
  getCurrentInterval() {
    if (!this.isTabVisible) {
      return INTERVALS.BACKGROUND;
    }
    if (this.consecutiveFailures > 0) {
      return INTERVALS.RECOVERY;
    }
    return INTERVALS.NORMAL;
  }

  /**
   * Schedule the next health check.
   * @param {number} delay - Delay in milliseconds
   */
  scheduleNextCheck(delay) {
    if (this.checkInterval) {
      clearTimeout(this.checkInterval);
    }

    this.checkInterval = setTimeout(async () => {
      await this.checkBackendHealth();
      this.scheduleNextCheck(this.getCurrentInterval());
    }, delay);
  }

  /**
   * Check backend health via lightweight /health endpoint.
   * @returns {Promise<boolean>} True if healthy
   */
  async checkBackendHealth() {
    const startTime = performance.now();

    try {
      const response = await axios.get(this.healthCheckUrl, {
        timeout: REQUEST_TIMEOUT,
      });

      const responseTime = Math.round(performance.now() - startTime);

      this.status.backend = {
        connected: true,
        version: response.data.version || 'v2',
        lastCheck: new Date().toISOString(),
        responseTime,
        error: null,
      };

      // Reset failure counter on success
      this.consecutiveFailures = 0;

      this.notifySubscribers();
      return true;
    } catch (error) {
      const responseTime = Math.round(performance.now() - startTime);

      this.status.backend = {
        connected: false,
        version: null,
        lastCheck: new Date().toISOString(),
        responseTime,
        error: error.message || 'Connection failed',
      };

      this.consecutiveFailures++;

      this.notifySubscribers();
      return false;
    }
  }

  /**
   * Check with retry logic and exponential backoff.
   * @param {number} maxRetries - Maximum retry attempts
   * @returns {Promise<boolean>} True if any attempt succeeded
   */
  async checkBackendHealthWithRetry(maxRetries = MAX_RETRIES) {
    for (let i = 0; i < maxRetries; i++) {
      const success = await this.checkBackendHealth();
      if (success) return true;

      // Exponential backoff before retry
      if (i < maxRetries - 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000 * (i + 1)));
      }
    }
    return false;
  }

  /**
   * Get current health status.
   * @returns {Object} Current status object
   */
  getStatus() {
    return this.status;
  }

  /**
   * Subscribe to status changes.
   * @param {Function} callback - Called with status on changes
   * @returns {Function} Unsubscribe function
   */
  subscribe(callback) {
    this.subscribers.add(callback);

    // Return unsubscribe function
    return () => {
      this.subscribers.delete(callback);
    };
  }

  /**
   * Notify all subscribers of status change.
   */
  notifySubscribers() {
    this.subscribers.forEach((callback) => {
      try {
        callback(this.status);
      } catch (error) {
        window.logService?.error('Health subscriber callback failed', {
          error: error.message,
          subscriberCount: this.subscribers.size,
        });
      }
    });
  }
}

// Create singleton instance
export const healthService = new HealthService();

// Start monitoring on import (browser environment only)
if (typeof window !== 'undefined') {
  healthService.startMonitoring(INTERVALS.NORMAL);
}

export default healthService;
