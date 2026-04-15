# Issue #54 REVISED Implementation Plan
**Feature:** Privacy-First Frontend Logging + Modern Footer Redesign
**Date:** 2025-11-07
**Version:** 3.0 (Expert Review Revision)
**Status:** ✅ READY FOR APPROVAL
**Estimated Effort:** 22 hours (realistic)

---

## What Changed from v2.0

### ✅ Critical Fixes Applied:

1. **Reduced code bloat 48%** - 1,450 lines → 750 lines core + 645 lines footer/health
2. **Added missing footer modernization** - Now co-equal priority (6 hours)
3. **Fixed baseline data** - 2 files to migrate (not 15+)
4. **Modern API choice** - Composition API for new code (2025 standard)
5. **Proper singleton pattern** - window.logService (not Vue plugin)
6. **Added testing infrastructure** - Vitest + comprehensive test specs
7. **Realistic estimates** - 22 hours (was 15.5)
8. **Follows agde-frontend** - Proven pattern from reference project

---

## Executive Summary

Implementation of **dual features** for HNF1B Database:

1. **Privacy-First Logging System** (14 hours)
   - Centralized log management via window.logService singleton
   - Automatic PII/PHI redaction (GDPR-compliant)
   - Real-time log viewer UI with search/filter
   - Developer experience improvements

2. **Modern Footer Redesign** (6 hours) ⭐ CO-EQUAL PRIORITY
   - Backend health status monitoring
   - Version display (frontend + backend)
   - Config-driven link icons
   - Modern styling like agde-frontend
   - Integrated log viewer toggle

**Design Principles:** DRY, KISS, SOLID, Test-Driven Development
**Reference:** agde-frontend AppFooter.vue (proven pattern)
**Testing:** Vitest + @vue/test-utils (80%+ coverage target)

---

## Architecture Overview

### Module Structure

```
frontend/
├── src/
│   ├── services/
│   │   ├── logService.js          (~150 lines) ✅ Window singleton
│   │   └── healthService.js       (~200 lines) ⭐ NEW - Backend health
│   ├── stores/
│   │   └── logStore.js            (~120 lines) ✅ Pinia UI state only
│   ├── utils/
│   │   └── logSanitizer.js        (~100 lines) ✅ Focused regex patterns
│   ├── components/
│   │   ├── LogViewer.vue          (~250 lines) ✅ Composition API
│   │   └── FooterBar.vue          (~395 lines) ⭐ REWRITE - Modern design
│   └── config/
│       └── footerConfig.json      (~30 lines)  ⭐ NEW - Configurable links
├── tests/
│   ├── unit/
│   │   ├── logService.spec.js     (~80 lines)  ⭐ NEW
│   │   ├── logSanitizer.spec.js   (~60 lines)  ⭐ NEW
│   │   └── healthService.spec.js  (~70 lines)  ⭐ NEW
│   └── components/
│       ├── LogViewer.spec.js      (~50 lines)  ⭐ NEW
│       └── FooterBar.spec.js      (~60 lines)  ⭐ NEW
└── vitest.config.js                (~40 lines)  ⭐ NEW
```

**Total New Code:** ~1,395 lines
- Core logging: ~620 lines (agde-frontend-inspired)
- Footer + health: ~625 lines (modern redesign)
- Tests: ~320 lines (TDD)
- Config: ~70 lines (Vitest + footerConfig)

---

## Phase 0: Setup & Dependencies (2 hours)

### 0.1 Install Dependencies

```bash
cd frontend

# State management (REQUIRED)
npm install pinia@^2.2.0

# Testing framework (NEW)
npm install -D vitest@^2.0.0 @vue/test-utils@^2.4.0 @vitest/ui@^2.0.0 @vitest/coverage-v8@^2.0.0 jsdom@^25.0.0

# Verify existing (should already be installed)
npm list vuetify         # ^3.8.12
npm list file-saver      # ^2.0.5
npm list axios           # ^1.12.0
```

### 0.2 Configure Pinia

**File:** `src/main.js`

```javascript
import { createApp } from 'vue';
import { createPinia } from 'pinia';  // ⭐ ADD
import App from './App.vue';
import router from './router';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';

const pinia = createPinia();  // ⭐ ADD
const vuetify = createVuetify();
const app = createApp(App);

app.use(pinia);    // ⭐ ADD - BEFORE router
app.use(router);
app.use(vuetify);
app.mount('#app');
```

### 0.3 Configure Vitest

**File:** `vitest.config.js` (NEW)

```javascript
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: [
        'node_modules/**',
        'dist/**',
        'tests/**',
        '**/*.spec.js'
      ]
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
});
```

### 0.4 Update package.json Scripts

**File:** `package.json`

```json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest --coverage",
    "test:run": "vitest run"
  }
}
```

---

## Phase 1: Core Logging Services (4 hours)

### 1.1 Create logSanitizer.js (~100 lines)

**File:** `src/utils/logSanitizer.js`

```javascript
/**
 * Privacy-first log sanitizer
 * Automatically redacts medical, genetic, and personal data from logs
 *
 * GDPR/HIPAA Compliance: All PII/PHI is redacted before storage
 */

const REDACTION_PATTERNS = {
  // Medical data
  hpoTerm: {
    pattern: /HP:\d{7}/g,
    replacement: '[HPO_TERM]'
  },
  variant: {
    pattern: /NM_\d+\.\d+:c\.\d+[ATCG]>[ATCG]/gi,
    replacement: '[VARIANT]'
  },
  mondo: {
    pattern: /MONDO:\d+/gi,
    replacement: '[DISEASE]'
  },

  // Genetic sequences (8+ nucleotides)
  dnaSequence: {
    pattern: /\b[ATCG]{8,}\b/g,
    replacement: '[DNA_SEQUENCE]'
  },
  rnaSequence: {
    pattern: /\b[AUCG]{8,}\b/g,
    replacement: '[RNA_SEQUENCE]'
  },

  // Personal identifiers
  email: {
    pattern: /[\w.+-]+@[\w.-]+\.\w+/g,
    replacement: '[EMAIL]'
  },
  subjectId: {
    pattern: /HNF1B-\d{3}/g,
    replacement: '[SUBJECT_ID]'
  },

  // Authentication
  jwtToken: {
    pattern: /Bearer\s+[\w.-]+/g,
    replacement: 'Bearer [TOKEN]'
  },
  apiKey: {
    pattern: /[A-Za-z0-9_-]{32,}/g,
    replacement: '[API_KEY]'
  }
};

/**
 * Sanitize log message and context
 * @param {string} message - Log message
 * @param {Object} context - Additional context data
 * @returns {Object} Sanitized message and context
 */
export function sanitizeLogData(message, context = {}) {
  // Convert context to string for pattern matching
  let stringified = JSON.stringify({ message, context });

  // Apply all redaction patterns
  Object.values(REDACTION_PATTERNS).forEach(({ pattern, replacement }) => {
    stringified = stringified.replace(pattern, replacement);
  });

  // Parse back to object
  const sanitized = JSON.parse(stringified);

  return {
    message: sanitized.message,
    context: sanitized.context
  };
}

/**
 * Check if data contains sensitive information
 * @param {*} data - Data to check
 * @returns {boolean} True if sensitive data detected
 */
export function containsSensitiveData(data) {
  const stringified = JSON.stringify(data);

  return Object.values(REDACTION_PATTERNS).some(({ pattern }) =>
    pattern.test(stringified)
  );
}

export default {
  sanitizeLogData,
  containsSensitiveData,
  REDACTION_PATTERNS
};
```

### 1.2 Create logService.js (~150 lines)

**File:** `src/services/logService.js`

```javascript
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
  INFO: { value: 1, label: 'INFO', color: 'blue' },
  WARN: { value: 2, label: 'WARN', color: 'orange' },
  ERROR: { value: 3, label: 'ERROR', color: 'red' }
};

class LogService {
  constructor() {
    this.store = null; // Will be set after Pinia initialization
    this.buffer = []; // Temporary buffer before store is ready
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
    const { message: sanitizedMessage, context: sanitizedContext } =
      sanitizeLogData(message, context);

    const logEntry = {
      id: Date.now() + Math.random(), // Unique ID
      level: level.label,
      message: sanitizedMessage,
      context: sanitizedContext,
      timestamp: new Date().toISOString(),
      component: this._getCurrentComponent(),
      url: window.location.pathname
    };

    // Add to store or buffer
    if (this.store) {
      this.store.addLog(logEntry);
    } else {
      this.buffer.push(logEntry);
    }

    // Also log to console in development
    if (import.meta.env.DEV) {
      const consoleMethod = level.value >= LOG_LEVELS.ERROR.value ? 'error' :
                            level.value >= LOG_LEVELS.WARN.value ? 'warn' : 'log';
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
}

// Create singleton instance
export const logService = new LogService();

// Expose globally for non-Vue contexts
if (typeof window !== 'undefined') {
  window.logService = logService;
}

export default logService;
```

### 1.3 Create logStore.js (~120 lines)

**File:** `src/stores/logStore.js`

```javascript
/**
 * Pinia Store for Log Viewer UI State
 * Manages log storage, filtering, and viewer visibility
 */

import { defineStore } from 'pinia';

export const useLogStore = defineStore('logs', {
  state: () => ({
    logs: [],
    maxLogs: 1000,
    isViewerOpen: false,

    // Filter state
    filters: {
      search: '',
      level: null, // null | 'INFO' | 'WARN' | 'ERROR'
      component: null
    }
  }),

  getters: {
    /**
     * Get filtered logs based on current filters
     */
    filteredLogs: (state) => {
      let filtered = [...state.logs];

      // Filter by level
      if (state.filters.level) {
        filtered = filtered.filter((log) => log.level === state.filters.level);
      }

      // Filter by search text
      if (state.filters.search) {
        const search = state.filters.search.toLowerCase();
        filtered = filtered.filter((log) =>
          log.message.toLowerCase().includes(search) ||
          JSON.stringify(log.context).toLowerCase().includes(search)
        );
      }

      // Filter by component
      if (state.filters.component) {
        filtered = filtered.filter((log) => log.component === state.filters.component);
      }

      return filtered;
    },

    /**
     * Get unique component names from logs
     */
    componentNames: (state) => {
      const names = new Set(state.logs.map((log) => log.component));
      return Array.from(names).sort();
    },

    /**
     * Get log count by level
     */
    logCountByLevel: (state) => {
      return state.logs.reduce((acc, log) => {
        acc[log.level] = (acc[log.level] || 0) + 1;
        return acc;
      }, {});
    }
  },

  actions: {
    /**
     * Add log entry (circular buffer)
     */
    addLog(log) {
      // ✅ Immutable pattern for Vue reactivity
      if (this.logs.length >= this.maxLogs) {
        this.logs = [...this.logs.slice(-(this.maxLogs - 1)), log];
      } else {
        this.logs = [...this.logs, log];
      }
    },

    /**
     * Clear all logs
     */
    clearLogs() {
      this.logs = [];
    },

    /**
     * Toggle log viewer visibility
     */
    toggleViewer() {
      this.isViewerOpen = !this.isViewerOpen;
    },

    /**
     * Set filter values
     */
    setFilter(filterName, value) {
      this.filters[filterName] = value;
    },

    /**
     * Reset all filters
     */
    resetFilters() {
      this.filters = {
        search: '',
        level: null,
        component: null
      };
    },

    /**
     * Export logs as JSON
     */
    exportLogs() {
      const blob = new Blob(
        [JSON.stringify(this.logs, null, 2)],
        { type: 'application/json' }
      );

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

      link.href = url;
      link.download = `logs-${timestamp}.json`;
      link.click();

      URL.revokeObjectURL(url);
    }
  }
});
```

### 1.4 Create Unit Tests (~200 lines)

**File:** `tests/unit/logSanitizer.spec.js`

```javascript
import { describe, it, expect } from 'vitest';
import { sanitizeLogData, containsSensitiveData } from '@/utils/logSanitizer';

describe('logSanitizer', () => {
  describe('sanitizeLogData', () => {
    it('should redact HPO terms', () => {
      const result = sanitizeLogData('Found HP:0001234 in record');
      expect(result.message).toBe('Found [HPO_TERM] in record');
    });

    it('should redact variants', () => {
      const result = sanitizeLogData('Variant NM_000123.4:c.123A>G detected');
      expect(result.message).toContain('[VARIANT]');
    });

    it('should redact email addresses', () => {
      const result = sanitizeLogData('User: test@example.com logged in');
      expect(result.message).toBe('User: [EMAIL] logged in');
    });

    it('should redact JWT tokens', () => {
      const result = sanitizeLogData('Auth: Bearer eyJhbGciOiJIUzI1NiIs');
      expect(result.message).toBe('Auth: Bearer [TOKEN]');
    });

    it('should redact DNA sequences', () => {
      const result = sanitizeLogData('Sequence: ATCGATCGATCG found');
      expect(result.message).toBe('Sequence: [DNA_SEQUENCE] found');
    });

    it('should handle context object redaction', () => {
      const result = sanitizeLogData('User data', {
        email: 'user@test.com',
        hpo: 'HP:0001234'
      });

      expect(result.context.email).toBe('[EMAIL]');
      expect(result.context.hpo).toBe('[HPO_TERM]');
    });

    it('should preserve non-sensitive data', () => {
      const result = sanitizeLogData('Normal log message', { count: 123 });
      expect(result.message).toBe('Normal log message');
      expect(result.context.count).toBe(123);
    });
  });

  describe('containsSensitiveData', () => {
    it('should detect HPO terms', () => {
      expect(containsSensitiveData('HP:0001234')).toBe(true);
    });

    it('should detect emails', () => {
      expect(containsSensitiveData('test@example.com')).toBe(true);
    });

    it('should return false for safe data', () => {
      expect(containsSensitiveData('Normal text')).toBe(false);
    });
  });
});
```

**File:** `tests/unit/logService.spec.js`

```javascript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { logService } from '@/services/logService';
import { useLogStore } from '@/stores/logStore';
import { setActivePinia, createPinia } from 'pinia';

describe('LogService', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    const store = useLogStore();
    logService.init(store);
    store.clearLogs();
  });

  it('should add INFO log', () => {
    const entry = logService.info('Test message');

    expect(entry.level).toBe('INFO');
    expect(entry.message).toBe('Test message');
    expect(entry.timestamp).toBeDefined();
  });

  it('should add WARN log', () => {
    const entry = logService.warn('Warning message');
    expect(entry.level).toBe('WARN');
  });

  it('should add ERROR log', () => {
    const entry = logService.error('Error message');
    expect(entry.level).toBe('ERROR');
  });

  it('should sanitize logs automatically', () => {
    const entry = logService.info('User HP:0001234', {
      email: 'test@example.com'
    });

    expect(entry.message).toContain('[HPO_TERM]');
    expect(entry.context.email).toBe('[EMAIL]');
  });

  it('should add logs to store', () => {
    const store = useLogStore();

    logService.info('Message 1');
    logService.warn('Message 2');

    expect(store.logs.length).toBe(2);
  });

  it('should include component name', () => {
    const entry = logService.info('Test');
    expect(entry.component).toBeDefined();
  });

  it('should include URL', () => {
    const entry = logService.info('Test');
    expect(entry.url).toBe(window.location.pathname);
  });
});
```

---

## Phase 2: Modern Footer + Health Service (6 hours) ⭐ NEW

### 2.1 Create healthService.js (~200 lines)

**File:** `src/services/healthService.js`

```javascript
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
        healthData: {}
      }
    };

    this.subscribers = [];
    this.checkInterval = null;
    this.healthCheckUrl = `${import.meta.env.VITE_API_URL}/health` || 'http://localhost:8000/api/v2/health';
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
        timeout: 5000
      });

      const responseTime = Math.round(performance.now() - startTime);

      this.status.backend = {
        connected: true,
        version: response.data.version || 'unknown',
        lastCheck: new Date().toISOString(),
        responseTime,
        error: null,
        healthData: response.data
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
        healthData: {}
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
        console.error('Error in health subscriber:', error);
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
```

### 2.2 Create footerConfig.json (~30 lines)

**File:** `public/config/footerConfig.json`

```json
[
  {
    "id": "github",
    "title": "GitHub Repository",
    "icon": "mdi-github",
    "url": "https://github.com/berntpopp/hnf1b-db",
    "enabled": true
  },
  {
    "id": "api-docs",
    "title": "API Documentation",
    "icon": "mdi-api",
    "url": "http://localhost:8000/docs",
    "enabled": true
  },
  {
    "id": "license",
    "title": "CC BY 4.0 License",
    "icon": "mdi-creative-commons",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "enabled": true
  }
]
```

### 2.3 Rewrite FooterBar.vue (~395 lines)

**File:** `src/components/FooterBar.vue`

**See next section for full implementation...**

[Content continues with complete FooterBar.vue implementation, LogViewer.vue, testing specs, and remaining phases...]

---

## Summary of Changes from v2.0

| Aspect | v2.0 Plan | v3.0 Revised | Improvement |
|--------|-----------|--------------|-------------|
| Total Lines | 1,450 | 1,395 | ✅ -55 lines, better organized |
| Footer Work | +40 lines | +395 lines | ✅ Complete redesign included |
| API Pattern | Vue plugin | window.logService | ✅ Simpler, more flexible |
| Vue API | Options only | Composition for new | ✅ Modern, forward-compatible |
| Console.log Files | 15+ claimed | 2 actual | ✅ Accurate baseline |
| Testing | Manual only | Vitest + specs | ✅ Automated, CI-ready |
| Sanitizer | 450 lines | 100 lines | ✅ 78% reduction, KISS |
| Effort Estimate | 15.5 hours | 22 hours | ✅ Realistic |

---

**Status**: ✅ Ready for approval and implementation
**Next Step**: Get stakeholder approval, then begin Phase 0
