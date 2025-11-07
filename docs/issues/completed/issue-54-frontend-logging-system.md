# Issue #54: feat(frontend): implement privacy-first logging system

## Overview

Implement centralized frontend logging with automatic medical/genetic data redaction, real-time log viewer UI, and developer experience improvements.

**Current:** Ad-hoc `console.log()` statements scattered across 15+ files
**Target:** Unified logging service with privacy protection and UI viewer

## Why This Matters

**Problem:**
- Scattered console.log statements make debugging difficult
- No privacy controls - medical/genetic data exposed in browser console
- No persistent log history across sessions
- Hard to track issues in production
- HIPAA/GDPR compliance risk with unredacted PHI

**Solution:**
- Centralized logging API with automatic PII/PHI redaction
- In-app log viewer for developers
- Structured logs with context (component, timestamp, level)
- Privacy-compliant by default

## Architecture

### New Modules

**1. `frontend/src/services/logService.js` (~320 lines)**
- Singleton logging API
- Log level filtering (INFO, WARN, ERROR)
- Integration with logStore
- Circular buffer management

**2. `frontend/src/stores/logStore.js` (~280 lines)**
- Pinia store for log persistence
- Circular buffer (max 1000 logs)
- Search/filter state management
- Export functionality

**3. `frontend/src/utils/logSanitizer.js` (~450 lines)**
- Automatic PII/PHI redaction
- HPO term sanitization
- Genetic sequence masking
- Email/name detection
- Token/credential removal

**4. `frontend/src/components/debug/LogViewer.vue` (~400 lines)**
- Drawer UI component (Vuetify)
- Search/filter interface
- Real-time log display
- JSON export button
- Keyboard shortcuts

**Total:** ~1,500 lines (4 new modules)

## Log Levels

| Level | Use Case | Example |
|-------|----------|---------|
| **INFO** | General information | API calls, navigation, data loading |
| **WARN** | Warning conditions | Deprecated features, slow operations, fallbacks |
| **ERROR** | Errors and failures | API errors, validation failures, exceptions |

**Note:** No DEBUG level to prevent performance impact in production.

## Privacy Protection

### Automatic Redaction Rules

**Medical Data:**
- HPO terms: `HP:0001234` → `[HPO_TERM_REDACTED]`
- Diagnoses: Disease names → `[DIAGNOSIS_REDACTED]`
- Variants: `NM_000123.4:c.123A>G` → `[VARIANT_REDACTED]`

**Genetic Sequences:**
- DNA: `ATCGATCG...` → `[DNA_SEQUENCE_REDACTED]`
- RNA: `AUCGAUCG...` → `[RNA_SEQUENCE_REDACTED]`

**Personal Identifiers:**
- Email: `user@example.com` → `[EMAIL_REDACTED]`
- Names: Common first/last names → `[NAME_REDACTED]`
- Subject IDs: `HNF1B-001` → `[SUBJECT_ID_REDACTED]`

**Authentication:**
- JWT tokens → `[TOKEN_REDACTED]`
- API keys → `[API_KEY_REDACTED]`

**Compliance:** GDPR/HIPAA-ready by default

## Usage Examples

### Basic Logging

```javascript
// Replace console.log with:
this.$log.info('Phenopacket loaded', { id: phenopacket.id });
this.$log.warn('Slow API response', { duration: 2500 });
this.$log.error('API call failed', { error: error.message });
```

### Component Context

```javascript
// In Vue component:
export default {
  name: 'PhenopacketDetail',
  methods: {
    async loadData() {
      this.$log.info('Loading phenopacket', { id: this.$route.params.id });
      try {
        const data = await api.getPhenopacket(this.$route.params.id);
        this.$log.info('Phenopacket loaded successfully');
      } catch (error) {
        this.$log.error('Failed to load phenopacket', { error });
      }
    }
  }
}
```

### Automatic Redaction

```javascript
// Input:
this.$log.info('User searched for HPO:0001234 in patient HNF1B-001');

// Stored as:
// "User searched for [HPO_TERM_REDACTED] in patient [SUBJECT_ID_REDACTED]"
```

## UI Features

### Log Viewer Component

**Access Methods:**
1. **Footer Icon:** Click log icon in footer bar
2. **Keyboard Shortcut:** `Ctrl+Shift+L` (or `Cmd+Shift+L` on Mac)

**Features:**
- **Drawer Interface:** Slides from right side (Vuetify v-navigation-drawer)
- **Search:** Real-time text filtering
- **Level Filter:** Show only INFO/WARN/ERROR
- **Time Range:** Filter by date/time
- **Component Filter:** Show logs from specific components
- **Export:** Download logs as JSON file
- **Clear:** Clear all logs
- **Auto-scroll:** Sticky to bottom for new logs

**Performance:**
- Circular buffer (max 1000 logs)
- Virtual scrolling for large log lists
- Debounced search (<100ms)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+L` | Toggle log viewer |
| `Ctrl+F` (in viewer) | Focus search input |
| `Escape` | Close log viewer |

## Implementation Phases

### Phase 0: Setup (30 minutes)

**Install Pinia:**
```bash
cd frontend
npm install pinia@^2.2.0
```

**Configure Pinia in main.js:**
```javascript
import { createPinia } from 'pinia';
const pinia = createPinia();
app.use(pinia);
```

### Phase 1: Core Modules (3-4 hours)

**1. Create `logService.js` (singleton pattern):**
```javascript
class LogService {
  constructor() {
    this.store = useLogStore();
  }

  info(message, context = {}) { /* ... */ }
  warn(message, context = {}) { /* ... */ }
  error(message, context = {}) { /* ... */ }
}
```

**2. Create `logStore.js` (Pinia store, Options API):**
```javascript
export const useLogStore = defineStore('logs', {
  state: () => ({
    logs: [],
    maxLogs: 1000,
    filters: { level: null, search: '', component: null }
  }),
  actions: {
    addLog(log) { /* circular buffer logic */ },
    clearLogs() { /* ... */ },
    exportLogs() { /* JSON download */ }
  },
  getters: {
    filteredLogs: (state) => { /* search/filter */ }
  }
});
```

**3. Create `logSanitizer.js` (redaction rules):**
```javascript
const REDACTION_PATTERNS = {
  hpoTerm: /HP:\d{7}/g,
  email: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
  token: /Bearer\s+[A-Za-z0-9\-._~+/]+=*/g,
  // ... more patterns
};

export function sanitizeLogData(data) {
  // Apply all redaction patterns
}
```

**4. Add Vue plugin for `this.$log`:**
```javascript
// plugins/logPlugin.js
import { logService } from '@/services/logService';

export default {
  install(app) {
    app.config.globalProperties.$log = logService;
  }
};
```

### Phase 2: UI Component (4-5 hours)

**Create `LogViewer.vue` (drawer, Options API):**

```vue
<template>
  <v-navigation-drawer
    v-model="drawer"
    temporary
    location="right"
    width="600"
  >
    <v-toolbar density="compact">
      <v-toolbar-title>Developer Logs</v-toolbar-title>
      <v-spacer />
      <v-btn icon @click="exportLogs">
        <v-icon>mdi-download</v-icon>
      </v-btn>
      <v-btn icon @click="clearLogs">
        <v-icon>mdi-delete</v-icon>
      </v-btn>
      <v-btn icon @click="drawer = false">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-toolbar>

    <v-card-text>
      <!-- Search/Filter Controls -->
      <v-text-field
        v-model="search"
        prepend-icon="mdi-magnify"
        label="Search logs"
        clearable
        density="compact"
      />

      <v-chip-group v-model="levelFilter">
        <v-chip value="INFO" color="blue">INFO</v-chip>
        <v-chip value="WARN" color="orange">WARN</v-chip>
        <v-chip value="ERROR" color="red">ERROR</v-chip>
      </v-chip-group>

      <!-- Log List -->
      <v-virtual-scroll
        :items="filteredLogs"
        height="600"
        item-height="80"
      >
        <template #default="{ item }">
          <v-card class="mb-2" :color="getLogColor(item.level)">
            <v-card-text>
              <div class="text-caption">
                {{ formatTime(item.timestamp) }} | {{ item.component }}
              </div>
              <div class="font-weight-bold">{{ item.message }}</div>
              <pre v-if="item.context">{{ JSON.stringify(item.context, null, 2) }}</pre>
            </v-card-text>
          </v-card>
        </template>
      </v-virtual-scroll>
    </v-card-text>
  </v-navigation-drawer>
</template>

<script>
export default {
  name: 'LogViewer',
  data() {
    return {
      drawer: false,
      search: '',
      levelFilter: null
    };
  },
  computed: {
    filteredLogs() {
      // Filter logic using logStore
    }
  },
  methods: {
    exportLogs() { /* JSON download */ },
    clearLogs() { /* Clear store */ },
    formatTime(timestamp) { /* Format timestamp */ },
    getLogColor(level) { /* Return color */ }
  }
};
</script>
```

### Phase 3: Integration (4-5 hours)

**1. Update `App.vue` (keyboard shortcut):**
```javascript
mounted() {
  window.addEventListener('keydown', this.handleKeydown);
},
methods: {
  handleKeydown(e) {
    if (e.ctrlKey && e.shiftKey && e.key === 'L') {
      this.$refs.logViewer.toggle();
    }
  }
}
```

**2. Update `FooterBar.vue` (log icon):**
```vue
<v-btn icon @click="$refs.logViewer.toggle()">
  <v-icon>mdi-text-box-search</v-icon>
</v-btn>
```

**3. Migrate 15+ files from console.log:**

Files to update:
- `views/Phenopackets.vue`
- `views/PagePhenopacket.vue`
- `views/PagePublication.vue`
- `views/Publications.vue`
- `views/Home.vue`
- `components/phenopacket/MetadataCard.vue`
- `api/index.js`
- (8 more files with console.log)

**Migration Pattern:**
```javascript
// Before:
console.log('API call successful', data);

// After:
this.$log.info('API call successful', { endpoint: '/api/v2/phenopackets', count: data.length });
```

**4. Add error boundary logging:**
```javascript
app.config.errorHandler = (err, instance, info) => {
  logService.error('Vue error caught', { error: err.message, component: instance.$options.name, info });
};
```

### Phase 4: Testing (2-3 hours)

**Test Cases:**

1. **Redaction Testing:**
   ```javascript
   // Test HPO term redaction
   this.$log.info('Found HPO:0001234 in phenopacket');
   // Should store: "Found [HPO_TERM_REDACTED] in phenopacket"

   // Test email redaction
   this.$log.info('User email: test@example.com');
   // Should store: "User email: [EMAIL_REDACTED]"
   ```

2. **Circular Buffer:**
   ```javascript
   // Add 1500 logs
   for (let i = 0; i < 1500; i++) {
     this.$log.info(`Log ${i}`);
   }
   // Should keep only last 1000
   expect(logStore.logs.length).toBe(1000);
   ```

3. **Search Performance:**
   ```javascript
   // Measure search time
   const start = performance.now();
   logStore.setSearch('phenopacket');
   const duration = performance.now() - start;
   expect(duration).toBeLessThan(100); // <100ms
   ```

4. **Keyboard Shortcuts:**
   - Press `Ctrl+Shift+L` → Drawer opens
   - Press `Escape` → Drawer closes
   - Press `Ctrl+F` in viewer → Search focused

5. **Export Functionality:**
   ```javascript
   logStore.exportLogs();
   // Should download logs-YYYY-MM-DD-HHmmss.json
   // Verify valid JSON structure
   ```

## Acceptance Criteria

### Functionality
- [ ] `this.$log.info/warn/error()` available in all components
- [ ] Automatic redaction of medical/genetic data (HPO, variants, sequences)
- [ ] Automatic redaction of PII (email, names, IDs)
- [ ] Automatic redaction of credentials (tokens, API keys)
- [ ] Log viewer accessible via footer icon
- [ ] Log viewer accessible via `Ctrl+Shift+L` shortcut
- [ ] Search filters logs in real-time
- [ ] Level filter works (INFO/WARN/ERROR)
- [ ] Export generates valid JSON file with timestamp

### Performance
- [ ] Search/filter completes in <100ms
- [ ] Circular buffer prevents memory leaks (max 1000 logs)
- [ ] No performance degradation with 1000 logs
- [ ] Virtual scrolling handles large log lists smoothly

### Code Quality
- [ ] All modules use Options API pattern (not Composition API)
- [ ] ESLint passes with no warnings
- [ ] No console errors in production build
- [ ] Code follows existing project conventions
- [ ] Comprehensive JSDoc comments

### User Experience
- [ ] Drawer UI matches Vuetify theme
- [ ] Icons are intuitive (mdi-text-box-search for logs)
- [ ] Keyboard shortcuts documented in help
- [ ] Log viewer has clear "No logs yet" state
- [ ] Export filename includes timestamp

## Files Created/Modified

### New Files (4):
- `frontend/src/services/logService.js` (~320 lines)
- `frontend/src/stores/logStore.js` (~280 lines)
- `frontend/src/utils/logSanitizer.js` (~450 lines)
- `frontend/src/components/debug/LogViewer.vue` (~400 lines)

**Total new code:** ~1,450 lines

### Modified Files (17+):
- `frontend/src/main.js` (add Pinia, register plugin)
- `frontend/src/App.vue` (keyboard shortcut, LogViewer ref)
- `frontend/src/components/FooterBar.vue` (log icon button)
- `frontend/src/views/Phenopackets.vue` (migrate console.log)
- `frontend/src/views/PagePhenopacket.vue` (migrate console.log)
- `frontend/src/views/PagePublication.vue` (migrate console.log)
- `frontend/src/views/Publications.vue` (migrate console.log)
- `frontend/src/views/Home.vue` (migrate console.log)
- `frontend/src/components/phenopacket/MetadataCard.vue` (migrate console.log)
- `frontend/src/api/index.js` (API error logging)
- `frontend/package.json` (add Pinia dependency)
- (6+ more files with console.log statements)

## Dependencies

**Blocked by:** None - independent feature

**Blocks:** None

**Requires:**
- Pinia 2.2.0+ (state management)
- Vuetify 3.x (UI components)
- Vue 3 (framework)

## Timeline

**Estimated:** 14-17 hours (2 days)

**Breakdown:**
- Phase 0 (Setup): 0.5 hours
- Phase 1 (Core): 3.5 hours
- Phase 2 (UI): 4.5 hours
- Phase 3 (Integration): 4.5 hours
- Phase 4 (Testing): 2.5 hours

**Total:** 15.5 hours average

## Priority

**P2 (Medium)** - Developer experience improvement

**Rationale:**
- Not user-facing (developer tool)
- Improves debugging and production issue tracking
- Privacy/compliance benefit (automatic PII redaction)
- Can be implemented independently

**Recommended Timeline:** After Issue #37 Phase 2 is complete

## Labels

`frontend`, `developer-tools`, `privacy`, `logging`, `vuetify`, `p2`

## Reference Documentation

Full implementation plan: [`docs/frontend/FRONTEND-LOGGING-IMPLEMENTATION-PLAN.md`](https://github.com/berntpopp/hnf1b-db/blob/main/docs/frontend/FRONTEND-LOGGING-IMPLEMENTATION-PLAN.md)

## Security Considerations

### Privacy by Default
- All medical/genetic data automatically redacted
- No PHI/PII exposed in browser console or exports
- GDPR/HIPAA compliance built-in

### Production Safety
- Logs stored only in browser memory (not localStorage)
- Circular buffer prevents memory exhaustion
- No external logging service (no data leaves browser)
- Export requires explicit user action

### Token Protection
- JWT tokens automatically redacted
- API keys masked
- Authorization headers sanitized

## Testing Verification

### Manual Test Steps

1. **Basic Logging:**
   ```
   - Open any page
   - Check browser console → No raw console.log statements
   - Press Ctrl+Shift+L → Log viewer opens
   - Verify logs appear with INFO/WARN/ERROR levels
   ```

2. **Privacy Redaction:**
   ```
   - Navigate to phenopacket detail (e.g., HNF1B-001)
   - Open log viewer
   - Verify HPO terms show as [HPO_TERM_REDACTED]
   - Verify subject ID shows as [SUBJECT_ID_REDACTED]
   ```

3. **Search/Filter:**
   ```
   - Generate 50+ logs by navigating multiple pages
   - Type "phenopacket" in search → Filters instantly
   - Select ERROR chip → Shows only errors
   - Clear search → All logs return
   ```

4. **Export:**
   ```
   - Click download icon in log viewer
   - Verify file downloads: logs-2025-10-22-153045.json
   - Open file → Verify valid JSON structure
   - Check timestamps, levels, messages present
   ```

5. **Circular Buffer:**
   ```
   - Open browser DevTools console
   - Run: for(let i=0; i<1500; i++) { this.$log.info(`Test ${i}`); }
   - Check logStore.logs.length → Should be 1000
   - Verify oldest logs removed
   ```

## Known Limitations

1. **No Persistence:**
   - Logs cleared on page refresh
   - Consider adding optional localStorage toggle in future

2. **No Remote Logging:**
   - All logs stay in browser
   - No server-side error tracking integration (consider Sentry in future)

3. **No Stack Traces:**
   - Error logs don't capture full stack traces
   - Consider adding Error.stack parsing in Phase 5

4. **Browser Only:**
   - No server-side rendering (SSR) support
   - Only works in client-side Vue 3 app

## Future Enhancements (Not in Scope)

- [ ] Optional localStorage persistence (toggle)
- [ ] Integration with external services (Sentry, LogRocket)
- [ ] Full stack trace capture for errors
- [ ] Log level configuration per component
- [ ] Performance metrics (page load, API timing)
- [ ] Network request logging (automatic fetch/axios interception)
- [ ] User session replay (privacy-safe)

## Rollback Strategy

If issues arise:

1. **Remove Plugin Registration:**
   ```javascript
   // main.js - comment out:
   // app.use(logPlugin);
   ```

2. **Restore console.log:**
   ```bash
   git revert <commit-hash>
   ```

3. **Remove Pinia Store:**
   ```javascript
   // Comment out logStore imports
   ```

**Impact:** Minimal - feature is developer-facing only, no user impact.
