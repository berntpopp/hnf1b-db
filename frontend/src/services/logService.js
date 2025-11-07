/**
 * Frontend Logging Service (Singleton)
 * Privacy-first logging with automatic PII/PHI redaction
 *
 * Usage:
 *   window.logService.info('User logged in', { userId: 123 });
 *   window.logService.error('API call failed', { error });
 */

import { sanitizeLogData } from '@/utils/logSanitizer';

const LOG_LEVELS = {
  DEBUG: { value: 0, label: 'DEBUG', color: 'grey' },
  INFO: { value: 1, label: 'INFO', color: 'blue' },
  WARN: { value: 2, label: 'WARN', color: 'orange' },
  ERROR: { value: 3, label: 'ERROR', color: 'red' },
};

class LogService {
  constructor() {
    this.store = null; // Will be set after Pinia initialization
    this.buffer = []; // Temporary buffer before store is ready
    this.minLevel = LOG_LEVELS.INFO.value; // Default: only INFO and above
    this.consoleEnabled = false; // Console logging OFF by default (use LogViewer)
  }

  /**
   * Initialize with Pinia store
   * Called from main.js after Pinia setup
   */
  init(store) {
    this.store = store;

    // Flush buffered logs to store
    this.buffer.forEach((log) => this.store.addLog(log));
    this.buffer = [];
  }

  /**
   * Generic log method
   * @private
   */
  _log(level, message, context = {}) {
    // Sanitize for privacy
    const { message: sanitizedMessage, context: sanitizedContext } = sanitizeLogData(
      message,
      context
    );

    const logEntry = {
      id: Date.now() + Math.random(), // Unique ID
      level: level.label,
      levelValue: level.value,
      message: sanitizedMessage,
      context: sanitizedContext,
      timestamp: new Date().toISOString(),
      component: this._getCurrentComponent(),
      url: window.location.pathname,
    };

    // Add to store or buffer (always capture all logs)
    if (this.store) {
      this.store.addLog(logEntry);
    } else {
      this.buffer.push(logEntry);
    }

    // Console logging: OFF by default, configurable
    // Only log if explicitly enabled AND level meets minimum threshold
    if (this.consoleEnabled && level.value >= this.minLevel) {
      const consoleMethod =
        level.value >= LOG_LEVELS.ERROR.value
          ? 'error'
          : level.value >= LOG_LEVELS.WARN.value
            ? 'warn'
            : 'log';
      console[consoleMethod](`[${level.label}]`, message, context);
    }

    return logEntry;
  }

  /**
   * Get current Vue component name (if available)
   * @private
   */
  _getCurrentComponent() {
    // Try to get from Vue DevTools context
    if (window.__VUE_DEVTOOLS_GLOBAL_HOOK__?.appRecords?.[0]) {
      const app = window.__VUE_DEVTOOLS_GLOBAL_HOOK__.appRecords[0];
      const currentComponent = app?.app?._instance?.type?.name;
      return currentComponent || 'Unknown';
    }
    return 'Unknown';
  }

  /**
   * Public API
   */
  debug(message, context) {
    return this._log(LOG_LEVELS.DEBUG, message, context);
  }

  info(message, context) {
    return this._log(LOG_LEVELS.INFO, message, context);
  }

  warn(message, context) {
    return this._log(LOG_LEVELS.WARN, message, context);
  }

  error(message, context) {
    return this._log(LOG_LEVELS.ERROR, message, context);
  }

  /**
   * Get log level enum (for external use)
   */
  getLevels() {
    return LOG_LEVELS;
  }

  /**
   * Set minimum log level (logs below this level won't be shown)
   * @param {string} levelName - 'DEBUG', 'INFO', 'WARN', 'ERROR'
   */
  setMinLevel(levelName) {
    const level = LOG_LEVELS[levelName];
    if (level) {
      this.minLevel = level.value;
      if (this.store) {
        this.store.setMinLevel(level.value);
      }
    }
  }

  /**
   * Enable/disable console logging
   * @param {boolean} enabled - true to enable console logs, false to disable
   */
  setConsoleEnabled(enabled) {
    this.consoleEnabled = enabled;
  }

  /**
   * Get current console logging state
   */
  getConsoleEnabled() {
    return this.consoleEnabled;
  }
}

// Create singleton instance
export const logService = new LogService();

// Expose globally for non-Vue contexts
if (typeof window !== 'undefined') {
  window.logService = logService;
}

export default logService;
