# Frontend Logging System Implementation Plan (REFACTORED)

**Project:** HNF1B Database
**Date:** 2025-01-22
**Version:** 2.0 (Refactored based on code review)
**Status:** Ready for Implementation
**Estimated Effort:** 14-17 hours

---

## Document Changes from v1.0

### Critical Fixes Applied:
1. ✅ **Options API throughout** (not Composition API)
2. ✅ **Pinia dependency explicitly added** (Phase 0)
3. ✅ **Circular buffer implementation** included
4. ✅ **Array mutation bug** fixed
5. ✅ **FooterBar.vue integration** verified and specified
6. ✅ **Simplified to 3 log levels** (INFO/WARN/ERROR)
7. ✅ **Removed CSV export** (YAGNI)
8. ✅ **Performance optimizations** included

### Alignment with Navigation Modernization:
- ✅ Compatible with upcoming App.vue refactoring
- ✅ FooterBar.vue remains stable (no navigation changes affect it)
- ✅ Uses same Options API pattern as navigation plan
- ✅ No conflicts with responsive layout changes

---

## Executive Summary

Implementation of a **production-ready, privacy-first frontend logging system** for the HNF1B Database. The system provides centralized log management, automatic sensitive data redaction (medical/genetic information), real-time log viewer UI, and comprehensive developer experience improvements.

**Key Simplifications from v1.0:**
- **3 log levels** instead of 5 (INFO, WARN, ERROR)
- **JSON export only** (no CSV)
- **Options API** for all components
- **Performance-optimized** search filtering

**Reference Architecture:** Based on kidney-genetics-db logging system (1,545 lines, 4 core modules)
**Design Principles:** DRY, KISS (simplified), SOLID, Modularization
**Compliance:** GDPR-compliant with automatic PII/PHI redaction

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Phase 0: Pre-Implementation Setup](#2-phase-0-pre-implementation-setup)
3. [Phase 1: Core Modules](#3-phase-1-core-modules)
4. [Phase 2: UI Components](#4-phase-2-ui-components)
5. [Phase 3: Migration](#5-phase-3-migration)
6. [Phase 4: Polish & Documentation](#6-phase-4-polish--documentation)
7. [Testing Strategy](#7-testing-strategy)
8. [Code Examples](#8-code-examples)

---

## 1. Architecture Overview

### 1.1 Module Structure

```
frontend/src/
├── services/
│   └── logService.js          (~320 lines) - Singleton logging service
├── stores/
│   └── logStore.js            (~280 lines) - Pinia store (Options API compatible)
├── utils/
│   └── logSanitizer.js        (~450 lines) - Privacy protection utility
├── components/
│   ├── LogViewer.vue          (~400 lines) - Log viewer drawer (Options API)
│   └── FooterBar.vue          (+40 lines) - Add log icon integration
└── App.vue                    (+60 lines) - Add keyboard shortcut
```

**Total New Code:** ~1,510 lines (35 lines less than v1.0 due to simplifications)

### 1.2 Log Levels (Simplified)

```javascript
const LOG_LEVELS = {
  INFO: 1,   // General informational logs
  WARN: 2,   // Warning conditions
  ERROR: 3   // Error conditions and failures
}
```

**Removed:** DEBUG (use INFO + env check), CRITICAL (use ERROR)

**Rationale:** 99% of frontend logging needs are covered by INFO/WARN/ERROR

### 1.3 Data Flow

```
Component Action
      ↓
this.$log.error('message', { data })
      ↓
logService._log(level, message, data)
      ↓
sanitizeLogEntry(message, data)  [Privacy protection]
      ↓
logStore.addLogEntry(sanitizedEntry)  [Circular buffer]
      ↓
Pinia Reactive State Update
      ↓
LogViewer UI Update (if open)
```

---

## 2. Phase 0: Pre-Implementation Setup

**Duration:** 2 hours
**Prerequisite:** Must complete before Phase 1

### 2.1 Install Dependencies

```bash
cd frontend

# Install Pinia (CRITICAL)
npm install pinia@^2.2.0

# Verify Vuetify 3 (should already be installed)
npm list vuetify
# Expected: vuetify@3.8.12

# Verify file-saver (should already be installed)
npm list file-saver
# Expected: file-saver@2.0.5
```

### 2.2 Configure Pinia in main.js

**File:** `frontend/src/main.js`

**Current:**
```javascript
// src/main.js
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';

const vuetify = createVuetify();
const app = createApp(App);

app.use(router);
app.use(vuetify);
app.mount('#app');
```

**Updated:**
```javascript
// src/main.js
import { createApp } from 'vue';
import { createPinia } from 'pinia';  // ADD
import App from './App.vue';
import router from './router';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';

const pinia = createPinia();  // ADD
const vuetify = createVuetify();
const app = createApp(App);

app.use(pinia);    // ADD - BEFORE router for store initialization
app.use(router);
app.use(vuetify);
app.mount('#app');
```

### 2.3 Verify FooterBar.vue Structure

**File:** `frontend/src/components/FooterBar.vue`

**Current structure verified:**
```vue
<template>
  <v-footer app padless>
    <v-card-text class="text-center">
      <v-btn
        v-for="link in footerLinks"
        :key="link.text"
        icon
        :href="link.href"
        :target="link.target"
      >
        <v-icon size="24px">{{ link.icon }}</v-icon>
      </v-btn>
    </v-card-text>
  </v-footer>
</template>

<script>
export default {
  name: 'FooterBar',
  data() {
    return {
      footerLinks: [
        { text: 'GitHub', icon: 'mdi-github', ... },
        { text: 'API', icon: 'mdi-api', ... },
        { text: 'License', icon: 'mdi-copyright', ... },
      ],
    };
  },
};
</script>
```

✅ **Perfect structure for integration** - will add log icon to footerLinks array

### 2.4 Create Feature Branch

```bash
git checkout -b feature/frontend-logging-system
git push -u origin feature/frontend-logging-system
```

### 2.5 Pre-Implementation Checklist

- [ ] Pinia installed (`npm list pinia` shows v2.2.0+)
- [ ] main.js updated with Pinia initialization
- [ ] FooterBar.vue structure verified
- [ ] Feature branch created
- [ ] Review completed and approved

---

## 3. Phase 1: Core Modules

**Duration:** 5-6 hours
**Deliverables:** logService, logSanitizer, logStore, main.js integration

### 3.1 Log Service (`logService.js`)

**File:** `frontend/src/services/logService.js`
**Lines:** ~320 (simplified from 340)
**Pattern:** Singleton

#### 3.1.1 Core Implementation

```javascript
// frontend/src/services/logService.js

import { sanitizeLogEntry } from '../utils/logSanitizer';

/**
 * Log levels with priority values
 */
const LOG_LEVELS = {
  INFO: 1,
  WARN: 2,
  ERROR: 3
};

/**
 * Singleton logging service
 * Provides centralized logging with automatic sanitization
 */
class LogService {
  constructor() {
    if (LogService.instance) {
      return LogService.instance;
    }

    this.store = null;
    this.minLogLevel = LOG_LEVELS.INFO;
    this.consoleEcho = true;
    this.correlationId = null;
    this.metadata = {};

    // Load config from localStorage
    this._loadConfig();

    LogService.instance = this;
  }

  /**
   * Initialize with Pinia store (called from main.js)
   */
  initStore(store) {
    this.store = store;
  }

  /**
   * Load configuration from localStorage
   * @private
   */
  _loadConfig() {
    try {
      const savedLevel = localStorage.getItem('hnf1b.logging.level');
      const savedEcho = localStorage.getItem('hnf1b.logging.consoleEcho');
      const savedMax = localStorage.getItem('hnf1b.logging.maxEntries');

      if (savedLevel) {
        this.minLogLevel = LOG_LEVELS[savedLevel] || this._getDefaultLogLevel();
      } else {
        this.minLogLevel = this._getDefaultLogLevel();
      }

      if (savedEcho !== null) {
        this.consoleEcho = savedEcho === 'true';
      } else {
        this.consoleEcho = import.meta.env.DEV;
      }

      if (savedMax && this.store) {
        this.store.setMaxEntries(parseInt(savedMax, 10));
      }
    } catch (err) {
      console.error('LogService: Failed to load config from localStorage', err);
    }
  }

  /**
   * Get default log level based on environment
   * @private
   */
  _getDefaultLogLevel() {
    return import.meta.env.DEV ? LOG_LEVELS.INFO : LOG_LEVELS.WARN;
  }

  /**
   * Generate UUID with fallback for older browsers
   * @private
   */
  _generateId() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    // Fallback for non-secure contexts
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Core logging method
   * @private
   */
  _log(level, message, data) {
    // Defensive check: store must be initialized
    if (!this.store) {
      if (import.meta.env.DEV) {
        console.warn('LogService: store not initialized, skipping log');
      }
      return;
    }

    // Check log level threshold
    if (LOG_LEVELS[level] < this.minLogLevel) {
      return;
    }

    // Sanitize before storage (privacy-by-default)
    const sanitized = sanitizeLogEntry(message, data);

    // Create log entry
    const entry = {
      id: this._generateId(),
      timestamp: new Date().toISOString(),
      level,
      message: sanitized.message,
      data: sanitized.data,
      correlationId: this.correlationId,
      metadata: { ...this.metadata },
      url: window.location.href,
      userAgent: navigator.userAgent
    };

    // Optional console echo (dev mode)
    if (this.consoleEcho) {
      const consoleMethod = level === 'ERROR' ? 'error' : level === 'WARN' ? 'warn' : 'log';
      console[consoleMethod](`[${level}] ${message}`, data || '');
    }

    // Add to store
    this.store.addLogEntry(entry);
  }

  // Public API
  info(message, data) {
    this._log('INFO', message, data);
  }

  warn(message, data) {
    this._log('WARN', message, data);
  }

  error(message, data) {
    this._log('ERROR', message, data);
  }

  /**
   * Log API call with timing
   */
  logApiCall(method, url, status, duration, data) {
    const level = status >= 400 ? 'ERROR' : status >= 300 ? 'WARN' : 'INFO';
    this._log(level, `API ${method} ${url} - ${status} (${duration}ms)`, {
      method,
      url,
      status,
      duration,
      ...data
    });
  }

  /**
   * Log performance timing
   */
  logPerformance(operation, startTime, data) {
    const duration = Date.now() - startTime;
    this._log('INFO', `Performance: ${operation} (${duration}ms)`, {
      operation,
      duration,
      ...data
    });
  }

  // Correlation tracking
  setCorrelationId(id) {
    this.correlationId = id;
  }

  clearCorrelationId() {
    this.correlationId = null;
  }

  setMetadata(metadata) {
    this.metadata = { ...this.metadata, ...metadata };
  }

  clearMetadata() {
    this.metadata = {};
  }

  // Configuration
  setMinLogLevel(level) {
    if (LOG_LEVELS[level] !== undefined) {
      this.minLogLevel = LOG_LEVELS[level];
      localStorage.setItem('hnf1b.logging.level', level);
    }
  }

  setConsoleEcho(enabled) {
    this.consoleEcho = enabled;
    localStorage.setItem('hnf1b.logging.consoleEcho', enabled.toString());
  }

  setMaxEntries(count) {
    if (this.store) {
      this.store.setMaxEntries(count);
      localStorage.setItem('hnf1b.logging.maxEntries', count.toString());
    }
  }

  // Utility
  clearLogs() {
    if (this.store) {
      this.store.clearLogs();
    }
  }

  exportLogs() {
    if (this.store) {
      return this.store.exportLogs();
    }
    return { logs: [], metadata: {}, statistics: {} };
  }
}

// Create and export singleton instance
export const logService = new LogService();
export { LOG_LEVELS };
```

### 3.2 Log Sanitizer (`logSanitizer.js`)

**File:** `frontend/src/utils/logSanitizer.js`
**Lines:** ~450
**Pattern:** Pure utility functions

```javascript
// frontend/src/utils/logSanitizer.js

/**
 * Sensitive data key patterns (HNF1B-specific)
 */
const SENSITIVE_KEYS = new Set([
  // Patient identifiers
  'name', 'firstname', 'lastname', 'fullname',
  'dob', 'dateofbirth', 'birthdate',
  'mrn', 'medicalnumber', 'medicalrecordnumber',
  'patientid', 'patient_id', 'subject_id', 'subjectid',
  'email', 'phone', 'address', 'ssn',

  // Phenopackets-specific
  'phenopacket', 'phenopacketid', 'phenopacket_id',
  'subject', 'proband',

  // Medical information
  'diagnosis', 'condition', 'symptom', 'phenotype',
  'hpoterm', 'phenotypicfeature', 'phenotypic_features',

  // Renal-specific (HNF1B disease)
  'kidney_disease', 'renal_disease', 'nephropathy',
  'cakut', 'rcad', 'mckd', 'hyperuricemia',
  'diabetes', 'mody', 'pancreatic',

  // Treatment
  'medication', 'prescription', 'drug', 'treatment', 'procedure',
  'dialysis', 'transplant', 'biopsy',

  // Genetic data
  'hnf1b', 'hnf1b_variant', 'tcf2',
  'variant', 'mutation', 'genotype', 'allele',
  'chromosome', 'dna', 'rna', 'protein',
  'hgvs', 'vrs', 'genomic', 'transcript',
  'nucleotide', 'amino_acid', 'codon',
  'snp', 'cnv', 'deletion', 'duplication', 'inversion',
  'copy_number', 'structural_variant',
  'rsid', 'clinvar', 'dbsnp', 'cosmic', 'gnomad',

  // Authentication/Security
  'token', 'accesstoken', 'access_token', 'authtoken', 'auth_token',
  'jwt', 'bearer', 'refreshtoken', 'refresh_token',
  'password', 'passwd', 'pwd', 'secret',
  'apikey', 'api_key', 'key', 'privatekey', 'private_key'
]);

/**
 * Pattern-based redaction rules
 */
const SENSITIVE_PATTERNS = [
  { pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, label: '[REDACTED_EMAIL]' },
  { pattern: /\b(?:\+?[1-9]\d{0,2}[\s.-]?)?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}\b/g, label: '[REDACTED_PHONE]' },
  { pattern: /\b\d{3}-?\d{2}-?\d{4}\b/g, label: '[REDACTED_SSN]' },
  { pattern: /\b[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b/g, label: '[REDACTED_TOKEN]' },

  // HGVS DNA variants
  { pattern: /\bc\.\d+[ACGT]>[ACGT]\b/gi, label: '[REDACTED_VARIANT]' },
  { pattern: /\bc\.\d+_\d+del[ACGT]*\b/gi, label: '[REDACTED_VARIANT]' },
  { pattern: /\bc\.\d+_\d+ins[ACGT]+\b/gi, label: '[REDACTED_VARIANT]' },
  { pattern: /\bc\.\d+_\d+dup[ACGT]*\b/gi, label: '[REDACTED_VARIANT]' },

  // HGVS Protein variants
  { pattern: /\bp\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}\b/g, label: '[REDACTED_VARIANT]' },
  { pattern: /\bp\.[A-Z][a-z]{2}\d+\*/g, label: '[REDACTED_VARIANT]' },

  // Genomic coordinates
  { pattern: /\bchr[0-9XYMxy]{1,2}:\d+-\d+\b/g, label: '[REDACTED_COORDINATE]' },

  // RefSeq IDs
  { pattern: /\b(NM|NP|NG|NR|XM|XP)_\d+\.\d+\b/g, label: '[REDACTED_GENE_ID]' },

  // VRS IDs
  { pattern: /\bga4gh:[A-Z]{2,3}\.[A-Za-z0-9_-]+\b/g, label: '[REDACTED_VRS_ID]' },

  // rs IDs
  { pattern: /\brs\d{6,}\b/g, label: '[REDACTED_RS_ID]' }
];

/**
 * Check if a key is sensitive (case-insensitive)
 */
function isSensitiveKey(key) {
  return SENSITIVE_KEYS.has(key.toLowerCase());
}

/**
 * Apply pattern-based redaction to string
 */
function redactPatterns(str) {
  if (typeof str !== 'string') return str;

  let result = str;
  for (const { pattern, label } of SENSITIVE_PATTERNS) {
    result = result.replace(pattern, label);
  }
  return result;
}

/**
 * Recursively sanitize object
 * @param {any} obj - Object to sanitize
 * @param {number} depth - Current recursion depth
 * @param {number} maxDepth - Maximum recursion depth
 * @returns {any} Sanitized copy
 */
export function sanitizeForLogging(obj, depth = 0, maxDepth = 5) {
  // Max depth protection
  if (depth > maxDepth) {
    return '[MAX_DEPTH_EXCEEDED]';
  }

  // Null/undefined
  if (obj === null || obj === undefined) {
    return obj;
  }

  // Primitives
  if (typeof obj !== 'object') {
    // Redact patterns in strings
    if (typeof obj === 'string') {
      return redactPatterns(obj);
    }
    return obj;
  }

  // Arrays
  if (Array.isArray(obj)) {
    return obj.map(item => sanitizeForLogging(item, depth + 1, maxDepth));
  }

  // Objects
  const sanitized = {};
  for (const [key, value] of Object.entries(obj)) {
    // Redact sensitive keys
    if (isSensitiveKey(key)) {
      sanitized[key] = '[REDACTED_SENSITIVE]';
    } else {
      sanitized[key] = sanitizeForLogging(value, depth + 1, maxDepth);
    }
  }

  return sanitized;
}

/**
 * Sanitize log entry (message + data)
 * @param {string} message - Log message
 * @param {any} data - Additional data
 * @returns {{ message: string, data: any }}
 */
export function sanitizeLogEntry(message, data) {
  return {
    message: redactPatterns(message),
    data: sanitizeForLogging(data)
  };
}

/**
 * Quick check if value contains sensitive data
 * @param {any} value
 * @returns {boolean}
 */
export function containsSensitiveData(value) {
  if (typeof value === 'string') {
    for (const { pattern } of SENSITIVE_PATTERNS) {
      if (pattern.test(value)) {
        return true;
      }
    }
  }

  if (typeof value === 'object' && value !== null) {
    for (const key of Object.keys(value)) {
      if (isSensitiveKey(key)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Get redaction summary (development only)
 */
export function getRedactionSummary(obj) {
  const summary = {
    sensitiveKeys: [],
    redactedValues: 0,
    patterns: []
  };

  function traverse(value, path = '') {
    if (typeof value === 'object' && value !== null) {
      for (const [key, val] of Object.entries(value)) {
        if (isSensitiveKey(key)) {
          summary.sensitiveKeys.push(path ? `${path}.${key}` : key);
          summary.redactedValues++;
        }
        traverse(val, path ? `${path}.${key}` : key);
      }
    } else if (typeof value === 'string') {
      for (const { pattern, label } of SENSITIVE_PATTERNS) {
        if (pattern.test(value)) {
          summary.patterns.push({ pattern: pattern.source, label, path });
          summary.redactedValues++;
        }
      }
    }
  }

  traverse(obj);
  return summary;
}
```

### 3.3 Log Store (`logStore.js`)

**File:** `frontend/src/stores/logStore.js`
**Lines:** ~280 (simplified from 325)
**Pattern:** Pinia Setup Store (Options API compatible)

```javascript
// frontend/src/stores/logStore.js

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useLogStore = defineStore('log', () => {
  // State
  const logs = ref([]);
  const isViewerVisible = ref(false);
  const maxEntries = ref(100);
  const searchQuery = ref('');
  const levelFilter = ref([]);

  const stats = ref({
    totalLogsReceived: 0,
    totalLogsDropped: 0,
    lastLogTime: null,
    sessionStartTime: new Date().toISOString()
  });

  // Computed - Counts
  const logCount = computed(() => logs.value.length);

  const errorCount = computed(() => {
    return logs.value.filter(log => log.level === 'ERROR').length;
  });

  const warningCount = computed(() => {
    return logs.value.filter(log => log.level === 'WARN').length;
  });

  const infoCount = computed(() => {
    return logs.value.filter(log => log.level === 'INFO').length;
  });

  // Computed - Grouping
  const logsByLevel = computed(() => {
    const groups = { INFO: 0, WARN: 0, ERROR: 0 };
    logs.value.forEach(log => {
      if (groups[log.level] !== undefined) {
        groups[log.level]++;
      }
    });
    return groups;
  });

  const recentErrors = computed(() => {
    return logs.value
      .filter(log => log.level === 'ERROR')
      .slice(-5)
      .reverse();
  });

  // Computed - Filtering (PERFORMANCE OPTIMIZED)
  const filteredLogs = computed(() => {
    let filtered = logs.value;

    // Level filter
    if (levelFilter.value.length > 0) {
      filtered = filtered.filter(log => levelFilter.value.includes(log.level));
    }

    // Search filter (OPTIMIZED - uses cached search string)
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase();
      filtered = filtered.filter(log => {
        // Search in message
        if (log.message.toLowerCase().includes(query)) {
          return true;
        }
        // Search in cached data string
        if (log._searchCache && log._searchCache.includes(query)) {
          return true;
        }
        return false;
      });
    }

    // Return reversed COPY (not mutation!) - FIXED BUG
    return [...filtered].reverse();
  });

  // Computed - Memory
  const memoryUsage = computed(() => {
    const bytes = JSON.stringify(logs.value).length;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  });

  // Actions - Core operations
  function addLogEntry(entry, maxEntriesOverride) {
    // Add search cache for performance
    const augmentedEntry = {
      ...entry,
      _searchCache: entry.data ? JSON.stringify(entry.data).toLowerCase() : ''
    };

    logs.value.push(augmentedEntry);
    stats.value.totalLogsReceived++;

    // Circular buffer implementation (CRITICAL FIX)
    const limit = maxEntriesOverride || maxEntries.value;
    if (logs.value.length > limit) {
      const dropped = logs.value.splice(0, logs.value.length - limit);
      stats.value.totalLogsDropped += dropped.length;
    }

    stats.value.lastLogTime = entry.timestamp;
  }

  function clearLogs() {
    logs.value = [];
    stats.value.totalLogsReceived = 0;
    stats.value.totalLogsDropped = 0;
    stats.value.lastLogTime = null;
  }

  function trimLogs(newMaxEntries) {
    if (logs.value.length > newMaxEntries) {
      const dropped = logs.value.splice(0, logs.value.length - newMaxEntries);
      stats.value.totalLogsDropped += dropped.length;
    }
  }

  // Actions - UI control
  function showViewer() {
    isViewerVisible.value = true;
  }

  function hideViewer() {
    isViewerVisible.value = false;
  }

  function toggleViewer() {
    isViewerVisible.value = !isViewerVisible.value;
  }

  // Actions - Filtering
  function setSearchQuery(query) {
    searchQuery.value = query;
  }

  function setLevelFilter(levels) {
    levelFilter.value = levels;
  }

  function clearFilters() {
    searchQuery.value = '';
    levelFilter.value = [];
  }

  // Actions - Configuration
  function setMaxEntries(value) {
    maxEntries.value = value;
    trimLogs(value);
  }

  // Actions - Querying
  function getLogById(id) {
    return logs.value.find(log => log.id === id);
  }

  function getLogsByCorrelationId(correlationId) {
    return logs.value.filter(log => log.correlationId === correlationId);
  }

  function getLogsByTimeRange(startTime, endTime) {
    const start = new Date(startTime).getTime();
    const end = new Date(endTime).getTime();

    return logs.value.filter(log => {
      const timestamp = new Date(log.timestamp).getTime();
      return timestamp >= start && timestamp <= end;
    });
  }

  function getStatistics() {
    return {
      ...stats.value,
      currentLogCount: logs.value.length,
      byLevel: logsByLevel.value,
      memoryUsage: memoryUsage.value
    };
  }

  // Actions - Export (JSON ONLY - CSV removed for KISS)
  function exportLogs(options = {}) {
    const {
      includeMetadata = true,
      onlyFiltered = false
    } = options;

    const logsToExport = onlyFiltered ? filteredLogs.value : logs.value;

    const exportData = {
      logs: logsToExport
    };

    if (includeMetadata) {
      exportData.metadata = {
        application: 'HNF1B Database',
        version: '2.0.0',
        exportedAt: new Date().toISOString(),
        environment: import.meta.env.MODE
      };

      exportData.session = {
        startTime: stats.value.sessionStartTime,
        duration: calculateDuration(stats.value.sessionStartTime),
        totalLogsReceived: stats.value.totalLogsReceived,
        totalLogsDropped: stats.value.totalLogsDropped,
        currentLogCount: logs.value.length
      };

      exportData.statistics = {
        byLevel: logsByLevel.value,
        memoryUsage: memoryUsage.value
      };
    }

    return exportData;
  }

  // Helper for duration calculation
  function calculateDuration(startTime) {
    const start = new Date(startTime).getTime();
    const now = Date.now();
    const diffMs = now - start;

    const hours = Math.floor(diffMs / 3600000);
    const minutes = Math.floor((diffMs % 3600000) / 60000);
    const seconds = Math.floor((diffMs % 60000) / 1000);

    return `${hours}h ${minutes}m ${seconds}s`;
  }

  return {
    // State
    logs,
    isViewerVisible,
    maxEntries,
    searchQuery,
    levelFilter,
    stats,

    // Computed
    logCount,
    errorCount,
    warningCount,
    infoCount,
    logsByLevel,
    recentErrors,
    filteredLogs,
    memoryUsage,

    // Actions
    addLogEntry,
    clearLogs,
    trimLogs,
    showViewer,
    hideViewer,
    toggleViewer,
    setSearchQuery,
    setLevelFilter,
    clearFilters,
    setMaxEntries,
    getLogById,
    getLogsByCorrelationId,
    getLogsByTimeRange,
    getStatistics,
    exportLogs
  };
});
```

### 3.4 Initialize in main.js

**File:** `frontend/src/main.js`

**Add after Pinia initialization:**

```javascript
// frontend/src/main.js

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';

// Import logging
import { logService } from './services/logService';
import { useLogStore } from './stores/logStore';

const pinia = createPinia();
const vuetify = createVuetify();
const app = createApp(App);

app.use(pinia);
app.use(router);
app.use(vuetify);

// Initialize logging system
const logStore = useLogStore();
logService.initStore(logStore);

// Make globally available
app.config.globalProperties.$log = logService;
window.logService = logService;

// Global error handler
app.config.errorHandler = (err, instance, info) => {
  logService.error('Unhandled Vue Error', {
    error: err.message,
    stack: err.stack,
    componentName: instance?.$options?.name || 'Unknown',
    info,
    url: window.location.href
  });

  // Re-throw in development
  if (import.meta.env.DEV) {
    throw err;
  }
};

// Unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  logService.error('Unhandled Promise Rejection', {
    reason: event.reason?.message || event.reason,
    stack: event.reason?.stack,
    url: window.location.href
  });

  if (import.meta.env.DEV) {
    console.error('Unhandled promise rejection:', event.reason);
  }
});

app.mount('#app');

// Log startup
logService.info('HNF1B Database application started', {
  environment: import.meta.env.MODE,
  url: window.location.href
});
```

---

## 4. Phase 2: UI Components

**Duration:** 4-5 hours
**Deliverables:** LogViewer.vue, FooterBar integration, App.vue keyboard shortcut

### 4.1 Log Viewer Component

**File:** `frontend/src/components/LogViewer.vue`
**Lines:** ~400
**Pattern:** Vue SFC with Options API

```vue
<template>
  <v-navigation-drawer
    v-model="logStore.isViewerVisible"
    location="right"
    width="600"
    temporary
    class="log-viewer"
  >
    <!-- Toolbar -->
    <v-toolbar color="primary" dark density="compact">
      <v-toolbar-title>
        Log Viewer
        <v-chip size="small" class="ml-2">{{ logStore.logCount }}</v-chip>
      </v-toolbar-title>
      <v-spacer />
      <v-btn icon="mdi-download" @click="downloadLogs" />
      <v-btn icon="mdi-delete" @click="confirmClearLogs" />
      <v-btn icon="mdi-close" @click="logStore.hideViewer" />
    </v-toolbar>

    <!-- Filter Controls -->
    <v-container>
      <!-- Search -->
      <v-text-field
        v-model="localSearchQuery"
        prepend-inner-icon="mdi-magnify"
        label="Search logs"
        clearable
        density="compact"
        variant="outlined"
        @update:model-value="updateSearch"
      />

      <!-- Level Filter -->
      <v-select
        v-model="localLevelFilter"
        :items="['INFO', 'WARN', 'ERROR']"
        label="Filter by level"
        multiple
        chips
        density="compact"
        variant="outlined"
        @update:model-value="updateLevelFilter"
      />

      <!-- Max Entries -->
      <v-select
        v-model="localMaxEntries"
        :items="[20, 50, 100, 200, 500]"
        label="Max entries"
        density="compact"
        variant="outlined"
        @update:model-value="updateMaxEntries"
      />

      <!-- Statistics Chips -->
      <v-chip-group>
        <v-chip v-if="logStore.errorCount > 0" color="error">
          ERROR: {{ logStore.errorCount }}
        </v-chip>
        <v-chip v-if="logStore.warningCount > 0" color="warning">
          WARN: {{ logStore.warningCount }}
        </v-chip>
        <v-chip color="info">
          INFO: {{ logStore.infoCount }}
        </v-chip>
        <v-chip color="grey">
          Memory: {{ logStore.memoryUsage }}
        </v-chip>
      </v-chip-group>
    </v-container>

    <!-- Log Entries -->
    <v-container class="log-entries">
      <!-- Log Cards -->
      <v-card
        v-for="log in logStore.filteredLogs"
        :key="log.id"
        :color="getLogColor(log.level)"
        class="log-entry mb-2"
        elevation="2"
      >
        <!-- Header -->
        <v-card-title class="py-2">
          <v-chip :color="getLogColor(log.level)" size="small" variant="elevated">
            {{ log.level }}
          </v-chip>
          <span class="text-caption ml-2">{{ formatTimestamp(log.timestamp) }}</span>
          <v-chip
            v-if="log.correlationId"
            size="small"
            variant="outlined"
            class="ml-2"
          >
            {{ log.correlationId.substring(0, 8) }}
          </v-chip>
          <v-spacer />
          <v-btn
            icon="mdi-content-copy"
            size="small"
            variant="text"
            @click="copyLogEntry(log)"
          />
        </v-card-title>

        <!-- Message -->
        <v-card-text>
          <div class="log-message">{{ log.message }}</div>

          <!-- Additional Data (if exists) -->
          <v-expansion-panels v-if="log.data" class="mt-2">
            <v-expansion-panel>
              <v-expansion-panel-title>Additional Data</v-expansion-panel-title>
              <v-expansion-panel-text>
                <pre class="log-data-content">{{ formatLogData(log.data) }}</pre>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
      </v-card>

      <!-- Empty State -->
      <v-alert v-if="logStore.filteredLogs.length === 0" type="info" variant="tonal">
        No logs to display
      </v-alert>
    </v-container>
  </v-navigation-drawer>
</template>

<script>
import { useLogStore } from '@/stores/logStore';

export default {
  name: 'LogViewer',

  setup() {
    const logStore = useLogStore();
    return { logStore };
  },

  data() {
    return {
      localSearchQuery: '',
      localLevelFilter: [],
      localMaxEntries: 100
    };
  },

  mounted() {
    // Initialize local state from store
    this.localSearchQuery = this.logStore.searchQuery;
    this.localLevelFilter = [...this.logStore.levelFilter];
    this.localMaxEntries = this.logStore.maxEntries;
  },

  methods: {
    updateSearch(value) {
      this.logStore.setSearchQuery(value || '');
    },

    updateLevelFilter(levels) {
      this.logStore.setLevelFilter(levels);
    },

    updateMaxEntries(newValue) {
      this.logStore.setMaxEntries(newValue);
      // Save to localStorage
      localStorage.setItem('hnf1b.logging.maxEntries', newValue.toString());
    },

    async downloadLogs() {
      try {
        const exportData = this.logStore.exportLogs({
          includeMetadata: true,
          onlyFiltered: false
        });

        // Use file-saver (default export - FIXED)
        const FileSaver = await import('file-saver');
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
          type: 'application/json'
        });

        const filename = `hnf1b-logs-${new Date().toISOString()}.json`;
        FileSaver.default.saveAs(blob, filename);
      } catch (err) {
        console.error('Failed to export logs:', err);
        alert('Failed to export logs. See console for details.');
      }
    },

    confirmClearLogs() {
      if (confirm('Clear all logs? This cannot be undone.')) {
        this.logStore.clearLogs();
      }
    },

    copyLogEntry(log) {
      const text = JSON.stringify(log, null, 2);
      navigator.clipboard.writeText(text).then(
        () => {
          // Optional: show success message
          console.log('Log entry copied to clipboard');
        },
        (err) => {
          console.error('Failed to copy:', err);
        }
      );
    },

    formatTimestamp(timestamp) {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3
      });
    },

    formatLogData(data) {
      return JSON.stringify(data, null, 2);
    },

    getLogColor(level) {
      const colors = {
        INFO: 'blue-lighten-4',
        WARN: 'orange-lighten-3',
        ERROR: 'red-lighten-3'
      };
      return colors[level] || 'grey-lighten-2';
    }
  }
};
</script>

<style scoped>
.log-viewer {
  z-index: 1000;
}

.log-entries {
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}

.log-entry {
  transition: transform 0.2s, box-shadow 0.2s;
}

.log-entry:hover {
  transform: translateX(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}

.log-message {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.875rem;
  word-break: break-word;
  white-space: pre-wrap;
}

.log-data-content {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.75rem;
  background: rgba(0, 0, 0, 0.05);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 300px;
}
</style>
```

### 4.2 FooterBar Integration

**File:** `frontend/src/components/FooterBar.vue`

**Add log viewer icon to existing footer:**

```vue
<template>
  <v-footer app padless class="elevation-3">
    <v-card-text class="text-center">
      <!-- Existing links -->
      <v-btn
        v-for="link in footerLinks"
        :key="link.text"
        icon
        :href="link.href"
        :target="link.target"
        text
      >
        <v-icon size="24px">{{ link.icon }}</v-icon>
      </v-btn>

      <!-- ADD: Spacer to push log icon to right -->
      <v-spacer />

      <!-- ADD: Log Viewer Icon with Error Badge -->
      <v-btn
        icon
        text
        :title="`Open Log Viewer (Ctrl+Shift+L) - ${logStore.errorCount} errors`"
        @click="logStore.showViewer"
      >
        <v-badge
          :content="logStore.errorCount"
          :model-value="logStore.errorCount > 0"
          color="error"
          dot
        >
          <v-icon size="24px">mdi-text-box-search-outline</v-icon>
        </v-badge>
      </v-btn>
    </v-card-text>
  </v-footer>
</template>

<script>
import { useLogStore } from '@/stores/logStore';  // ADD

export default {
  name: 'FooterBar',

  setup() {  // ADD
    const logStore = useLogStore();
    return { logStore };
  },

  data() {
    return {
      footerLinks: [
        {
          text: 'GitHub',
          icon: 'mdi-github',
          href: 'https://github.com/berntpopp/HNF1B-db',
          target: '_blank',
        },
        {
          text: 'API',
          icon: 'mdi-api',
          href: '/API',
          target: '_self',
        },
        {
          text: 'License',
          icon: 'mdi-copyright',
          href: 'https://creativecommons.org/licenses/by/4.0/',
          target: '_blank',
        },
      ],
    };
  },
};
</script>

<style scoped>
/* Add any additional footer styling here if needed */
</style>
```

### 4.3 App.vue Integration

**File:** `frontend/src/App.vue`

**Add LogViewer component and keyboard shortcut:**

```vue
<template>
  <v-app>
    <AppBar />
    <v-main>
      <router-view />
    </v-main>
    <FooterBar />

    <!-- ADD: Log Viewer Component -->
    <LogViewer />
  </v-app>
</template>

<script>
import AppBar from './components/AppBar.vue';
import FooterBar from './components/FooterBar.vue';
import LogViewer from './components/LogViewer.vue';  // ADD
import { useLogStore } from './stores/logStore';      // ADD

export default {
  name: 'App',

  components: {
    AppBar,
    FooterBar,
    LogViewer  // ADD
  },

  setup() {  // ADD
    const logStore = useLogStore();
    return { logStore };
  },

  mounted() {  // ADD
    window.addEventListener('keydown', this.handleKeyPress);
  },

  beforeUnmount() {  // ADD
    window.removeEventListener('keydown', this.handleKeyPress);
  },

  methods: {  // ADD
    handleKeyPress(event) {
      // Ctrl+Shift+L to toggle log viewer
      if (event.ctrlKey && event.shiftKey && event.key === 'L') {
        event.preventDefault();
        this.logStore.toggleViewer();
      }
    }
  }
};
</script>
```

---

## 5. Phase 3: Migration

**Duration:** 2-3 hours
**Deliverables:** API interceptor logging, component migration, ESLint rules

### 5.1 API Interceptor Integration

**File:** `frontend/src/api/index.js`

**Add logging to request/response interceptors:**

```javascript
// ADD at top of file
import { logService } from '@/services/logService';

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Existing token injection
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // ADD: Logging with correlation ID
    const correlationId = logService._generateId ? logService._generateId() : Date.now().toString();
    config.metadata = { correlationId, startTime: Date.now() };

    logService.setCorrelationId(correlationId);
    logService.info(`API Request: ${config.method.toUpperCase()} ${config.url}`, {
      method: config.method,
      url: config.url,
      params: config.params
    });

    return config;
  },
  (error) => {
    logService.error('API Request Error', { error: error.message });
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    // ADD: Log successful response
    const { correlationId, startTime } = response.config.metadata || {};
    const duration = startTime ? Date.now() - startTime : 0;

    logService.logApiCall(
      response.config.method.toUpperCase(),
      response.config.url,
      response.status,
      duration,
      {
        dataSize: JSON.stringify(response.data).length
      }
    );

    logService.clearCorrelationId();

    return response;
  },
  (error) => {
    // Existing 401 redirect
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }

    // ADD: Log error response
    const { correlationId, startTime } = error.config?.metadata || {};
    const duration = startTime ? Date.now() - startTime : 0;

    logService.error('API Response Error', {
      method: error.config?.method,
      url: error.config?.url,
      status: error.response?.status,
      statusText: error.response?.statusText,
      duration,
      errorMessage: error.message
    });

    logService.clearCorrelationId();

    return Promise.reject(error);
  }
);
```

### 5.2 Component Migration

**Example migration (Phenopackets.vue):**

**Before:**
```javascript
try {
  const response = await getPhenopackets({ skip: 0, limit: 10 });
  phenopackets.value = response.data.items;
} catch (error) {
  console.error('Error fetching phenopackets:', error);  // OLD
  showError.value = true;
}
```

**After:**
```javascript
try {
  const response = await getPhenopackets({ skip: 0, limit: 10 });
  phenopackets.value = response.data.items;
  this.$log.info('Phenopackets loaded', {  // NEW
    count: response.data.items.length
  });
} catch (error) {
  this.$log.error('Error fetching phenopackets', {  // NEW
    error: error.message,
    stack: error.stack
  });
  showError.value = true;
}
```

### 5.3 Files to Migrate (17 total)

1. `views/Phenopackets.vue`
2. `views/Publications.vue`
3. `views/PagePhenopacket.vue`
4. `views/PageVariant.vue`
5. `views/SearchResults.vue`
6. `views/Login.vue`
7. `views/Home.vue`
8. `views/User.vue`
9. `views/Variants.vue`
10. `views/Individuals.vue`
11. `views/AggregationsDashboard.vue`
12. `components/phenopacket/MetadataCard.vue`
13. `components/analyses/ProteinLinearPlot.vue`
14. `components/SearchCard.vue`
15. `api/index.js` (already done above)
16. `main.js` (already done in Phase 1)
17. `App.vue` (already done in Phase 2)

### 5.4 Add Logout Log Clearing

**File:** `frontend/src/utils/auth.js` (or wherever logout is defined)

```javascript
import { logService } from '@/services/logService';

export function logout() {
  removeToken();
  logService.clearLogs();  // ADD: Clear logs on logout
  logService.info('User logged out');
  window.location.href = '/login';
}
```

### 5.5 ESLint Configuration

**File:** `frontend/eslint.config.js` or `frontend/.eslintrc.js`

```javascript
// If using ESLint 9 (flat config):
export default [
  {
    rules: {
      'no-console': ['error', { allow: ['assert'] }]
    }
  }
];

// If using older ESLint (< 9):
module.exports = {
  rules: {
    'no-console': ['error', { allow: ['assert'] }]
  }
};
```

---

## 6. Phase 4: Polish & Documentation

**Duration:** 2-3 hours
**Deliverables:** Documentation, JSDoc comments, final testing

### 6.1 Add JSDoc Comments

**Example (logService.js):**

```javascript
/**
 * Log an informational message
 *
 * @param {string} message - Log message
 * @param {Object} [data] - Additional context data (will be sanitized)
 * @returns {void}
 *
 * @example
 * logService.info('Phenopackets loaded', { count: 20 })
 */
info(message, data) {
  this._log('INFO', message, data);
}
```

### 6.2 Update README.md

**Add section to `frontend/README.md`:**

```markdown
## Frontend Logging System

### Quick Start

The logging system provides centralized, privacy-aware logging with a built-in viewer.

**Basic Usage:**
```javascript
// In Vue components
this.$log.info('Action completed', { count: 10 })
this.$log.warn('Warning condition', { details: '...' })
this.$log.error('Error occurred', { error: err.message })

// In non-component code
import { logService } from '@/services/logService'
logService.info('Message', { data })
```

**Open Log Viewer:**
- Click log icon in footer (bottom right)
- Press `Ctrl+Shift+L`

**Features:**
- ✅ Automatic sensitive data redaction (medical/genetic data)
- ✅ Search and filter logs
- ✅ Export to JSON
- ✅ Real-time error badge
- ✅ Performance tracking

### Configuration

```javascript
// Set log level (INFO, WARN, ERROR)
logService.setMinLogLevel('WARN')  // Production: only warnings and errors

// Set max entries (20-500)
logService.setMaxEntries(100)

// Enable/disable console echo
logService.setConsoleEcho(false)  // Production: disable
```

### Privacy & Security

All logs are automatically sanitized before storage:
- Patient identifiers (IDs, emails, names)
- Genetic data (HGVS notation, VRS IDs, variants)
- Medical information (diagnoses, medications)
- Authentication tokens (JWT, passwords)

Exported logs are safe to share for debugging.
```

---

## 7. Testing Strategy

### 7.1 Manual Testing Checklist

| Test Case | Steps | Expected Result | Status |
|-----------|-------|----------------|--------|
| **Basic Logging** | `window.logService.info('test')` in console | Log appears in viewer | ⬜ |
| **Error Badge** | `window.logService.error('test')` 3 times | Badge shows "3" | ⬜ |
| **Drawer Opens** | Click footer icon | Right drawer opens | ⬜ |
| **Keyboard Shortcut** | Press Ctrl+Shift+L | Drawer toggles | ⬜ |
| **Level Filter** | Filter by ERROR | Only errors shown | ⬜ |
| **Search** | Search "phenopacket" | Matching logs shown | ⬜ |
| **Clear Logs** | Click clear button | All logs removed | ⬜ |
| **Export JSON** | Click download | JSON file downloads | ⬜ |
| **Sanitization** | Log email: `test@example.com` | Email redacted | ⬜ |
| **Max Entries** | Add 150 logs (max 100) | Only 100 retained | ⬜ |
| **API Logging** | Navigate to /phenopackets | Request/response logged | ⬜ |
| **Logout Clears** | Logout | Logs cleared | ⬜ |

### 7.2 Integration Tests

```javascript
// Browser console tests

// Test 1: Basic logging
window.logService.info('Test message')
window.logService.warn('Test warning')
window.logService.error('Test error')

// Test 2: Sanitization
window.logService.info('User email is test@example.com')
window.logService.info('Variant c.123A>G detected')

// Test 3: Export
const exported = window.logService.exportLogs()
console.log(exported)

// Test 4: Verify sanitization
console.log(exported.logs[0].message)  // Should show [REDACTED_EMAIL]
```

### 7.3 Performance Testing

```javascript
// Test circular buffer performance
console.time('Add 200 logs')
for (let i = 0; i < 200; i++) {
  window.logService.info(`Log entry ${i}`, { index: i })
}
console.timeEnd('Add 200 logs')

// Check memory
console.log(window.logService.exportLogs().statistics.memoryUsage)
```

---

## 8. Code Examples

### 8.1 Common Logging Patterns

```javascript
// Success logging
this.$log.info('Operation completed', {
  operation: 'loadPhenopackets',
  count: response.data.length
})

// Warning logging
this.$log.warn('Deprecated API used', {
  function: 'oldGetIndividuals',
  replacement: 'getPhenopackets'
})

// Error logging
this.$log.error('Failed to save', {
  error: err.message,
  stack: err.stack,
  data: formData
})

// Performance tracking
const start = Date.now()
// ... operation ...
this.$log.logPerformance('Data processing', start, {
  recordCount: data.length
})

// API logging (automatic in interceptor)
// Just make API calls normally:
await getPhenopackets({ skip: 0, limit: 10 })
// Automatically logs:
// INFO: API Request: GET /api/v2/phenopackets/
// INFO: API GET /api/v2/phenopackets/ - 200 (145ms)
```

### 8.2 Correlation Tracking

```javascript
// Track related operations
const correlationId = 'batch-import-' + Date.now()
this.$log.setCorrelationId(correlationId)

this.$log.info('Starting batch import', { fileCount: 10 })
for (const file of files) {
  this.$log.info('Processing file', { filename: file.name })
}
this.$log.info('Batch import complete')

this.$log.clearCorrelationId()

// All logs now have same correlationId, can be filtered together
```

---

## 9. Implementation Timeline

### Week 1: Foundation & UI

**Day 1 (2 hours):**
- Phase 0: Pre-implementation setup
- Install Pinia, update main.js
- Create feature branch

**Day 2 (6 hours):**
- Phase 1: Implement logService.js
- Phase 1: Implement logSanitizer.js
- Phase 1: Implement logStore.js
- Test basic logging

**Day 3 (5 hours):**
- Phase 2: Implement LogViewer.vue
- Phase 2: Update FooterBar.vue
- Phase 2: Update App.vue
- Test UI

### Week 2: Migration & Polish

**Day 4 (3 hours):**
- Phase 3: API interceptor integration
- Phase 3: Migrate 8-10 components

**Day 5 (2 hours):**
- Phase 3: Migrate remaining components
- Phase 3: Add ESLint rules

**Day 6 (3 hours):**
- Phase 4: Add JSDoc comments
- Phase 4: Update documentation
- Phase 4: Final testing
- Code review

**Total: 21 hours** (includes buffer)

---

## 10. Success Criteria

### Implementation Complete When:

1. ✅ All 4 core modules implemented
2. ✅ Pinia properly installed and configured
3. ✅ Zero raw `console.log` calls in code
4. ✅ LogViewer accessible via footer + keyboard
5. ✅ Error badge updates reactively
6. ✅ All 17 components migrated
7. ✅ API logging automatic
8. ✅ Logout clears logs
9. ✅ ESLint `no-console` rule active
10. ✅ Documentation complete
11. ✅ All manual tests passing
12. ✅ Code review approved

---

## 11. Rollback Plan

If critical issues found:

```bash
# Option 1: Revert feature branch
git checkout main
git branch -D feature/frontend-logging-system

# Option 2: Keep infrastructure, disable UI
# Comment out in App.vue:
# <LogViewer />

# Comment out in FooterBar.vue:
# Log viewer icon section

# Option 3: Selective revert
git revert <commit-hash>  # Revert specific commits
```

---

## Appendix A: Differences from v1.0

| Aspect | v1.0 | v2.0 (This Plan) |
|--------|------|------------------|
| **API Pattern** | Composition API (`<script setup>`) | Options API |
| **Log Levels** | 5 (DEBUG/INFO/WARN/ERROR/CRITICAL) | 3 (INFO/WARN/ERROR) |
| **Export Formats** | JSON + CSV | JSON only |
| **App.vue Integration** | `<script setup>` with composables | Options API with `setup()` |
| **Pinia Setup** | Assumed installed | Explicit installation in Phase 0 |
| **Circular Buffer** | Mentioned but not shown | Fully implemented |
| **Array Mutation** | Bug (`.reverse()`) | Fixed (`[...].reverse()`) |
| **Search Performance** | Slow (JSON.stringify) | Optimized (cached search string) |
| **file-saver Import** | Named import (wrong) | Default import (correct) |
| **UUID Fallback** | Missing | Included |
| **Total Lines** | 1,545 | 1,510 (simplified) |
| **Estimated Effort** | 16-20 hours | 14-17 hours |

---

## Appendix B: Quick Reference

### Import Paths

```javascript
// Services
import { logService } from '@/services/logService'

// Stores
import { useLogStore } from '@/stores/logStore'

// Utils
import { sanitizeLogEntry } from '@/utils/logSanitizer'
```

### Global Access

```javascript
// In Vue components
this.$log.info('message')

// Anywhere in code
window.logService.info('message')
```

### LocalStorage Keys

```
hnf1b.logging.level          // 'INFO' | 'WARN' | 'ERROR'
hnf1b.logging.consoleEcho    // 'true' | 'false'
hnf1b.logging.maxEntries     // '20' to '500'
```

---

**Document Version:** 2.0 (Refactored)
**Last Updated:** 2025-01-22
**Author:** Claude Code (AI Assistant)
**Based On:** Code review findings and navigation modernization alignment
**Status:** Ready for Implementation
