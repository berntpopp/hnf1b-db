/**
 * Backend Health Monitoring Service
 * Tracks backend connectivity, version, and system health
 *
 * Based on agde-frontend healthService pattern
 */

import axios from 'axios';

class HealthService {
  constructor() {
    this.status = {
      backend: {
        connected: false,
        version: null,
        lastCheck: null,
        responseTime: null,
        error: null,
        healthData: {},
      },
    };

    this.subscribers = [];
    this.checkInterval = null;

    // Use summary endpoint as health check until backend implements /health
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v2';
    this.healthCheckUrl = `${apiUrl}/phenopackets/aggregate/summary`;
  }

  /**
   * Start periodic health checks
   */
  startMonitoring(intervalMs = 30000) {
    // Initial check
    this.checkBackendHealth();

    // Periodic checks
    this.checkInterval = setInterval(() => {
      this.checkBackendHealth();
    }, intervalMs);
  }

  /**
   * Stop health checks
   */
  stopMonitoring() {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  /**
   * Check backend health
   */
  async checkBackendHealth() {
    const startTime = performance.now();

    try {
      const response = await axios.get(this.healthCheckUrl, {
        timeout: 5000,
      });

      const responseTime = Math.round(performance.now() - startTime);

      this.status.backend = {
        connected: true,
        version: response.data.version || 'v2',
        lastCheck: new Date().toISOString(),
        responseTime,
        error: null,
        healthData: response.data,
      };

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
        healthData: {},
      };

      this.notifySubscribers();
      return false;
    }
  }

  /**
   * Check with retry logic
   */
  async checkBackendHealthWithRetry(maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
      const success = await this.checkBackendHealth();
      if (success) return true;

      // Wait before retry (exponential backoff)
      if (i < maxRetries - 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000 * (i + 1)));
      }
    }
    return false;
  }

  /**
   * Get current status
   */
  getStatus() {
    return this.status;
  }

  /**
   * Subscribe to status changes
   */
  subscribe(callback) {
    this.subscribers.push(callback);

    // Return unsubscribe function
    return () => {
      this.subscribers = this.subscribers.filter((cb) => cb !== callback);
    };
  }

  /**
   * Notify all subscribers
   */
  notifySubscribers() {
    this.subscribers.forEach((callback) => {
      try {
        callback(this.status);
      } catch (error) {
        window.logService.error('Health subscriber callback failed', {
          error: error.message,
          subscriberCount: this.subscribers.length,
        });
      }
    });
  }
}

// Create singleton
export const healthService = new HealthService();

// Start monitoring on import (can be disabled if needed)
if (typeof window !== 'undefined') {
  healthService.startMonitoring(30000); // Check every 30 seconds
}

export default healthService;
