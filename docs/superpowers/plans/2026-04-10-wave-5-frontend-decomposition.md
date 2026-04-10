# Wave 5: Frontend Decomposition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every frontend file in `frontend/src/` under 500 LOC. Split the 6 giant components + 11 medium files identified in the re-baseline. Extract composables for reusable logic. Fix the broken zoom bug and the broken variant search as side effects of the relevant component splits.

**Architecture:** Composition-API-first extraction. For each giant component, pull stateful logic into `useXxx()` composables, pure transforms into `utils/` modules, and UI-specific sub-sections into smaller components. The top-level component becomes layout + orchestration only.

**Tech Stack:** Vue 3 (Composition API), Vuetify 3, D3, NGL Viewer, Chart.js, Vitest, Vue Test Utils.

**Parent spec:** `docs/superpowers/specs/2026-04-10-codebase-refactor-roadmap-design.md` (Wave 5 section)

**Prerequisites:**
- Waves 1-4 complete.
- **Critical:** Wave 2's characterization tests are the primary safety net. Every component decomposition in this wave asserts the characterization tests still pass **unchanged** after the split.
- Wave 4's standardized error response shape simplifies the api/index.js split.

---

## Context

All Wave 1 conventions apply. Branch: `chore/wave-5-frontend-decomposition`. Composables follow the convention `useXxx.js` (or `.ts` if the project converts to TypeScript later — currently JavaScript).

**Rules of thumb for composable extraction:**
- Composables return an object of refs, computed values, and functions.
- Composables do not import UI components.
- Composables can be tested without mounting a Vue tree (use `setup()`-style tests).
- Pure utilities (no reactivity, no Vue imports) go in `utils/` instead of composables.

**Rules of thumb for component extraction:**
- Each extracted sub-component owns a clearly named slice of the template (a section, a card, a row).
- Passing data via props is fine; avoid creating new provide/inject unless it eliminates a lot of prop drilling.
- `v-model` emits are acceptable for two-way bindings but should be typed/documented.

**Files to decompose (17 total over 500 LOC):**

Priority group (6 files, biggest first):
| File | LOC | Safety net | Wave 5 task |
|------|:---:|-----------|:-----------:|
| HNF1BGeneVisualization.vue | 1,421 | Wave 2 char spec | Task 6 |
| ProteinStructure3D.vue | 1,130 | Wave 2 char spec | Task 7 |
| HNF1BProteinVisualization.vue | 1,063 | Wave 2 upgraded char spec | Task 8 |
| PageVariant.vue | 1,032 | Wave 2 char spec | Task 5 |
| api/index.js | 953 | Existing auth/API tests | Task 2 |
| AdminDashboard.vue | 905 | Wave 2 char spec | Task 4 |

Catch-up group (11 files):
| File | LOC | Planned split | Wave 5 task |
|------|:---:|---------------|:-----------:|
| PagePublication.vue | 704 | Task 9a |
| AggregationsDashboard.vue | 693 | Task 9b |
| PagePhenopacket.vue | 682 | Task 9c |
| VariantComparisonChart.vue | 649 | Task 9d |
| useSeoMeta.js | 621 | Task 9e |
| Phenopackets.vue | 590 | Task 9f |
| InterpretationsCard.vue | 557 | Task 9g |
| Variants.vue | 544 | Task 9h |
| User.vue | 522 | Task 9i |
| VariantAnnotator.vue | 509 | Task 9j |
| Home.vue | 503 | Task 9k |

**Order:** Tasks 1-8 (biggest files, safety-net-backed) first. Task 9a-9k (medium files) after.

---

## Task 1: Extract `useSyncTask` composable (unblocks AdminDashboard split)

**Files:**
- Create: `frontend/src/composables/useSyncTask.js`
- Create: `frontend/tests/unit/composables/useSyncTask.spec.js`

The 4 polling flows in `AdminDashboard.vue:669-831` are identical modulo the start/status function pair. Pulling them into a single composable eliminates ~150 LOC of duplication and makes AdminDashboard splittable.

- [ ] **Step 1: Write the composable tests first**

Create `frontend/tests/unit/composables/useSyncTask.spec.js`:

```javascript
/**
 * Tests for the useSyncTask composable.
 *
 * Uses vitest fake timers to drive the polling loop without waiting
 * real time.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useSyncTask } from '@/composables/useSyncTask';

describe('useSyncTask', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns idle state initially', () => {
    const task = useSyncTask({
      startFn: vi.fn(),
      statusFn: vi.fn(),
      pollInterval: 1000,
    });
    expect(task.status.value).toBe('idle');
    expect(task.isRunning.value).toBe(false);
  });

  it('start() calls startFn and polls statusFn', async () => {
    const startFn = vi.fn().mockResolvedValue({ task_id: 'T1' });
    const statusFn = vi.fn().mockResolvedValue({ status: 'running', progress: 25 });

    const task = useSyncTask({ startFn, statusFn, pollInterval: 1000 });
    await task.start();

    expect(startFn).toHaveBeenCalled();
    expect(task.isRunning.value).toBe(true);

    // Advance fake timers to trigger polling
    await vi.advanceTimersByTimeAsync(1000);
    expect(statusFn).toHaveBeenCalledWith('T1');
  });

  it('stops polling when statusFn returns completed status', async () => {
    const startFn = vi.fn().mockResolvedValue({ task_id: 'T2' });
    const statusFn = vi
      .fn()
      .mockResolvedValueOnce({ status: 'running', progress: 50 })
      .mockResolvedValueOnce({ status: 'completed', progress: 100 });

    const onComplete = vi.fn();
    const task = useSyncTask({
      startFn,
      statusFn,
      pollInterval: 1000,
      onComplete,
    });
    await task.start();

    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1000);

    expect(task.isRunning.value).toBe(false);
    expect(task.status.value).toBe('completed');
    expect(onComplete).toHaveBeenCalled();
  });

  it('captures error when startFn throws', async () => {
    const startFn = vi.fn().mockRejectedValue(new Error('network down'));
    const statusFn = vi.fn();

    const task = useSyncTask({ startFn, statusFn, pollInterval: 1000 });
    await task.start();

    expect(task.status.value).toBe('failed');
    expect(task.error.value).toContain('network down');
  });
});
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd frontend && npx vitest run tests/unit/composables/useSyncTask.spec.js
```

Expected: FAIL (module not found).

- [ ] **Step 3: Create the composable**

Create `frontend/src/composables/useSyncTask.js`:

```javascript
/**
 * useSyncTask — polling-based sync operation composable.
 *
 * Collapses the 4 duplicated sync polling flows in AdminDashboard.vue
 * into a single reusable abstraction.
 *
 * @param {Object} options
 * @param {() => Promise<{task_id: string}>} options.startFn - Starts the sync; returns task_id.
 * @param {(taskId: string) => Promise<{status: string, progress: number}>} options.statusFn - Polls status.
 * @param {number} options.pollInterval - Milliseconds between polls.
 * @param {(result: any) => void} [options.onComplete] - Called on successful completion.
 * @param {(error: Error) => void} [options.onError] - Called on failure.
 */
import { ref, computed } from 'vue';

const COMPLETED_STATES = new Set(['completed', 'success', 'done']);
const FAILED_STATES = new Set(['failed', 'error']);

export function useSyncTask({
  startFn,
  statusFn,
  pollInterval = 2000,
  onComplete = () => {},
  onError = () => {},
}) {
  const status = ref('idle'); // idle | running | completed | failed
  const progress = ref(0);
  const error = ref(null);
  const taskId = ref(null);
  const _intervalHandle = ref(null);

  const isRunning = computed(() => status.value === 'running');

  async function start() {
    status.value = 'running';
    progress.value = 0;
    error.value = null;

    try {
      const result = await startFn();
      taskId.value = result?.task_id || null;
      if (!taskId.value) {
        // startFn completed synchronously
        status.value = 'completed';
        progress.value = 100;
        onComplete(result);
        return;
      }
      _startPolling();
    } catch (err) {
      status.value = 'failed';
      error.value = err.message || String(err);
      onError(err);
    }
  }

  function stop() {
    if (_intervalHandle.value) {
      clearInterval(_intervalHandle.value);
      _intervalHandle.value = null;
    }
    status.value = 'idle';
  }

  function _startPolling() {
    _intervalHandle.value = setInterval(async () => {
      if (!taskId.value) {
        _stopPolling();
        return;
      }
      try {
        const result = await statusFn(taskId.value);
        progress.value = result?.progress || 0;
        const resultStatus = String(result?.status || '').toLowerCase();
        if (COMPLETED_STATES.has(resultStatus)) {
          status.value = 'completed';
          progress.value = 100;
          onComplete(result);
          _stopPolling();
        } else if (FAILED_STATES.has(resultStatus)) {
          status.value = 'failed';
          error.value = result?.error || 'Task failed';
          onError(new Error(error.value));
          _stopPolling();
        }
      } catch (err) {
        status.value = 'failed';
        error.value = err.message || String(err);
        onError(err);
        _stopPolling();
      }
    }, pollInterval);
  }

  function _stopPolling() {
    if (_intervalHandle.value) {
      clearInterval(_intervalHandle.value);
      _intervalHandle.value = null;
    }
  }

  return {
    status,
    progress,
    error,
    taskId,
    isRunning,
    start,
    stop,
  };
}
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run tests/unit/composables/useSyncTask.spec.js
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSyncTask.js frontend/tests/unit/composables/useSyncTask.spec.js
git commit -m "feat(frontend): add useSyncTask composable

Extracts the polling-with-start/status pattern used 4 times in
AdminDashboard.vue into a reusable composable. Unblocks Wave 5
Task 4 (AdminDashboard split).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Split api/index.js into http + session + endpoints modules

**Files:**
- Create: `frontend/src/api/http.js`
- Create: `frontend/src/api/session.js`
- Create: `frontend/src/api/endpoints/phenopackets.js`
- Create: `frontend/src/api/endpoints/variants.js`
- Create: `frontend/src/api/endpoints/publications.js`
- Create: `frontend/src/api/endpoints/aggregations.js`
- Create: `frontend/src/api/endpoints/search.js`
- Create: `frontend/src/api/endpoints/auth.js`
- Create: `frontend/src/api/endpoints/admin.js`
- Create: `frontend/src/api/endpoints/reference.js`
- Create: `frontend/src/api/endpoints/ontology.js`
- Modify: `frontend/src/api/index.js` (shrinks to a barrel re-export file)

- [ ] **Step 1: Read api/index.js to map its contents**

```bash
wc -l frontend/src/api/index.js
grep -n "^export\|^const.*api\|axios\.\|interceptors" frontend/src/api/index.js | head -60
```

Identify:
- The axios instance creation (→ http.js)
- The request/response interceptors for auth refresh (→ session.js)
- The endpoint function exports grouped by domain (→ endpoints/*.js)

- [ ] **Step 2: Create http.js with the axios instance**

Create `frontend/src/api/http.js`:

```javascript
/**
 * Base axios instance for the HNF1B API.
 *
 * Just the HTTP transport — no auth interceptors, no error handlers.
 * Those live in session.js and main-error-handler.js respectively.
 */
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api/v2';

export const http = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

export { API_URL };
```

- [ ] **Step 3: Create session.js with auth interceptors**

Create `frontend/src/api/session.js`:

```javascript
/**
 * Auth session handling: JWT storage, refresh queue, token injection.
 *
 * Wraps the http instance from http.js with request/response
 * interceptors. Imports the auth store lazily to break the circular
 * dependency that used to require dynamic import() in api/index.js.
 */
import { http } from './http';

const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

let isRefreshing = false;
let failedQueue = [];

function processQueue(error, token = null) {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(accessToken, refreshToken) {
  localStorage.setItem(TOKEN_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// Request interceptor: inject token
http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: refresh on 401
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url.includes('/auth/refresh')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return http(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = getRefreshToken();
        const { data } = await http.post('/auth/refresh', { refresh_token: refreshToken });
        setTokens(data.access_token, data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return http(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  },
);

export { http };
```

- [ ] **Step 4: Split endpoints by domain**

For each domain module, copy the relevant endpoint functions from `api/index.js` into its own file. Example for phenopackets:

Create `frontend/src/api/endpoints/phenopackets.js`:

```javascript
/**
 * Phenopacket CRUD and search endpoints.
 */
import { http } from '../http';

export async function getPhenopackets(params = {}) {
  const { data } = await http.get('/phenopackets/', { params });
  return data;
}

export async function getPhenopacketById(id) {
  const { data } = await http.get(`/phenopackets/${id}`);
  return data;
}

export async function createPhenopacket(payload) {
  const { data } = await http.post('/phenopackets/', payload);
  return data;
}

export async function updatePhenopacket(id, patch) {
  const { data } = await http.patch(`/phenopackets/${id}`, patch);
  return data;
}

export async function deletePhenopacket(id) {
  await http.delete(`/phenopackets/${id}`);
}

export async function searchPhenopackets(query, params = {}) {
  const { data } = await http.post('/phenopackets/search', { query, ...params });
  return data;
}
```

Repeat for `variants.js`, `publications.js`, `aggregations.js`, `search.js`, `auth.js`, `admin.js`, `reference.js`, `ontology.js`. Use the function names already exported by the current `api/index.js` — do **not** rename anything (that would break the rest of the app).

- [ ] **Step 5: Shrink api/index.js to a barrel re-export**

Replace the entire contents of `frontend/src/api/index.js` with:

```javascript
/**
 * API barrel file.
 *
 * Re-exports everything so existing consumers using
 * `import { getPhenopackets } from '@/api';` keep working. The
 * actual implementations live in the http/session/endpoints
 * modules.
 */
export * from './http';
export * from './session';
export * from './endpoints/phenopackets';
export * from './endpoints/variants';
export * from './endpoints/publications';
export * from './endpoints/aggregations';
export * from './endpoints/search';
export * from './endpoints/auth';
export * from './endpoints/admin';
export * from './endpoints/reference';
export * from './endpoints/ontology';
```

- [ ] **Step 6: Run the full frontend test suite**

```bash
cd frontend && make check
```

Expected: all green. If any component fails because an expected export is missing, check the endpoint file for a typo in the function name.

- [ ] **Step 7: Build to catch import errors**

```bash
cd frontend && npm run build
```

Expected: clean build. Vite will catch any broken import path.

- [ ] **Step 8: Verify file sizes**

```bash
find frontend/src/api -name "*.js" -exec wc -l {} \;
```

Expected: every file under 500 LOC. `endpoints/` files should each be under 150 LOC.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/
git commit -m "$(cat <<'EOF'
refactor(frontend): split api/index.js into http, session, endpoints

Decomposes the 953-LOC api/index.js into:
  api/
    http.js                    (axios instance only)
    session.js                 (JWT interceptors + refresh queue)
    endpoints/
      phenopackets.js
      variants.js
      publications.js
      aggregations.js
      search.js
      auth.js
      admin.js
      reference.js
      ontology.js
    index.js                   (barrel re-export)

All existing consumers keep working via the barrel. The circular
dependency workaround (dynamic import()) is no longer needed — the
new module boundaries break the cycle naturally.

Closes P2 #4 from the 2026-04-09 review.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Consolidate frontend auth ownership into authStore

**Files:**
- Modify: `frontend/src/stores/authStore.js` (becomes single source of truth)
- Modify: `frontend/src/router/index.js` (reads only from store)
- Modify: `frontend/src/api/session.js` (emits events the store listens to; no direct localStorage access from router or components)

The current auth state is scattered across `api/index.js` (now `api/session.js`), `stores/authStore.js`, and `router/index.js`. Consolidate into a single ownership model.

- [ ] **Step 1: Read the current state locations**

```bash
grep -rn "localStorage\|access_token\|refresh_token" frontend/src/api/ frontend/src/stores/ frontend/src/router/
```

Map what each file currently reads/writes.

- [ ] **Step 2: Make authStore the single source of truth**

Edit `frontend/src/stores/authStore.js`. The store should own:
- `accessToken` (ref, initialized from localStorage)
- `refreshToken` (ref, initialized from localStorage)
- `user` (ref, fetched on login)
- `isAuthenticated` (computed)
- `login()`, `logout()`, `setTokens()`, `clearTokens()` actions

Remove any direct localStorage reads from components and the router. All access goes through the store.

- [ ] **Step 3: Update router guards to read from the store**

Edit `frontend/src/router/index.js`. The global `beforeEach` guard should call:

```javascript
import { useAuthStore } from '@/stores/authStore';

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login' });
  } else {
    next();
  }
});
```

No direct `localStorage.getItem` calls in the router.

- [ ] **Step 4: Update session.js to talk to the store via events**

Edit `frontend/src/api/session.js`. Instead of direct `localStorage` access, publish custom DOM events that the store listens to:

```javascript
// In session.js:
function emitTokenRefreshed(tokens) {
  window.dispatchEvent(
    new CustomEvent('auth:token-refreshed', { detail: tokens })
  );
}

function emitAuthCleared() {
  window.dispatchEvent(new CustomEvent('auth:cleared'));
}
```

Then in the store init, add listeners:

```javascript
// In authStore.js:
window.addEventListener('auth:token-refreshed', (e) => {
  accessToken.value = e.detail.access_token;
  refreshToken.value = e.detail.refresh_token;
});
window.addEventListener('auth:cleared', () => {
  accessToken.value = null;
  refreshToken.value = null;
});
```

**Simpler alternative:** if event-based coordination feels heavyweight, keep `session.js` calling store actions directly via a lazy Pinia import. The point is: localStorage reads should happen in exactly one place (the store initializer).

- [ ] **Step 5: Add tests for the consolidated store**

Extend `frontend/tests/unit/stores/authStore.spec.js` (should already exist) with tests for:
- Store initializes tokens from localStorage on creation
- `login(credentials)` sets tokens and user
- `logout()` clears everything
- `isAuthenticated` reflects the token state

- [ ] **Step 6: Run tests + build**

```bash
cd frontend && make check && npm run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/authStore.js frontend/src/router/index.js frontend/src/api/session.js frontend/tests/unit/stores/authStore.spec.js
git commit -m "$(cat <<'EOF'
refactor(frontend): consolidate auth ownership in authStore

Makes stores/authStore.js the single source of truth for auth
state. Router guards read only from the store; session.js talks to
the store via events/actions instead of direct localStorage access.
Eliminates the three-way state duplication flagged in the 2026-04-09
review (P3 #15).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Split AdminDashboard.vue using useSyncTask

**Files:**
- Modify: `frontend/src/views/AdminDashboard.vue` (shrink to layout + composition)
- Create: `frontend/src/views/admin/SyncOperationsSection.vue`
- Create: `frontend/src/views/admin/SystemStatusSection.vue`
- Create: `frontend/src/views/admin/RecentActivitySection.vue`

- [ ] **Step 1: Identify the 4 sync flows**

```bash
sed -n '669,831p' frontend/src/views/AdminDashboard.vue
```

These 163 lines contain 4 nearly-identical sync flows. Extract them into `SyncOperationsSection.vue` using the `useSyncTask` composable from Task 1.

- [ ] **Step 2: Create SyncOperationsSection.vue**

Create `frontend/src/views/admin/SyncOperationsSection.vue`:

```vue
<template>
  <v-card class="pa-4">
    <v-card-title>Sync Operations</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <SyncOperationCard
            title="Publications"
            :progress="publicationsTask.progress"
            :status="publicationsTask.status"
            :error="publicationsTask.error"
            @start="publicationsTask.start"
          />
        </v-col>
        <v-col cols="12" md="6">
          <SyncOperationCard
            title="Variants"
            :progress="variantsTask.progress"
            :status="variantsTask.status"
            :error="variantsTask.error"
            @start="variantsTask.start"
          />
        </v-col>
        <v-col cols="12" md="6">
          <SyncOperationCard
            title="Reference Data"
            :progress="referenceTask.progress"
            :status="referenceTask.status"
            :error="referenceTask.error"
            @start="referenceTask.start"
          />
        </v-col>
        <v-col cols="12" md="6">
          <SyncOperationCard
            title="Phenopackets"
            :progress="phenopacketsTask.progress"
            :status="phenopacketsTask.status"
            :error="phenopacketsTask.error"
            @start="phenopacketsTask.start"
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { useSyncTask } from '@/composables/useSyncTask';
import {
  syncPublications,
  syncVariants,
  syncReferenceData,
  syncPhenopackets,
  getSyncTaskStatus,
} from '@/api';
import SyncOperationCard from './SyncOperationCard.vue';

const publicationsTask = useSyncTask({
  startFn: syncPublications,
  statusFn: getSyncTaskStatus,
  pollInterval: 2000,
});
const variantsTask = useSyncTask({
  startFn: syncVariants,
  statusFn: getSyncTaskStatus,
  pollInterval: 2000,
});
const referenceTask = useSyncTask({
  startFn: syncReferenceData,
  statusFn: getSyncTaskStatus,
  pollInterval: 2000,
});
const phenopacketsTask = useSyncTask({
  startFn: syncPhenopackets,
  statusFn: getSyncTaskStatus,
  pollInterval: 2000,
});
</script>
```

Also create the small `SyncOperationCard.vue` sibling component (one card with title, progress bar, start button, error display).

- [ ] **Step 3: Create the other two sections**

`SystemStatusSection.vue`: reads `getSystemStatus()` on mount, shows database/redis/vep status cards.

`RecentActivitySection.vue`: shows the audit log / recent activity panel.

Each should be under 200 LOC.

- [ ] **Step 4: Shrink AdminDashboard.vue**

Replace the template with a top-level layout composing the three sections:

```vue
<template>
  <v-container>
    <h1>Admin Dashboard</h1>
    <SyncOperationsSection class="mb-4" />
    <SystemStatusSection class="mb-4" />
    <RecentActivitySection />
  </v-container>
</template>

<script setup>
import SyncOperationsSection from './admin/SyncOperationsSection.vue';
import SystemStatusSection from './admin/SystemStatusSection.vue';
import RecentActivitySection from './admin/RecentActivitySection.vue';
</script>
```

Target: `AdminDashboard.vue` under 100 LOC.

- [ ] **Step 5: Run Wave 2 AdminDashboard characterization test UNCHANGED**

```bash
cd frontend && npx vitest run tests/unit/views/AdminDashboard.spec.js
```

Expected: all tests pass with the spec file unchanged. This proves the split preserved observable behavior.

- [ ] **Step 6: Run full frontend check**

```bash
cd frontend && make check && npm run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/AdminDashboard.vue frontend/src/views/admin/
git commit -m "refactor(frontend): split AdminDashboard.vue into sections

Uses the useSyncTask composable to collapse 4 duplicated polling
flows. Splits the 905-LOC AdminDashboard.vue into:
  AdminDashboard.vue             (layout only, <100 LOC)
  admin/SyncOperationsSection.vue
  admin/SystemStatusSection.vue
  admin/RecentActivitySection.vue
  admin/SyncOperationCard.vue    (reusable sync card)

Wave 2 characterization test passes unchanged.

Closes P2 #8 and part of P3 #10.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Split PageVariant.vue

**Files:**
- Modify: `frontend/src/views/PageVariant.vue` (layout + tab routing, <200 LOC)
- Create: `frontend/src/composables/useVariantPage.js`
- Create: `frontend/src/views/variant/VariantDetailsTab.vue`
- Create: `frontend/src/views/variant/VariantAnnotationTab.vue`
- Create: `frontend/src/views/variant/VariantPublicationsTab.vue`
- Create: `frontend/src/views/variant/VariantVisualizationTab.vue`

- [ ] **Step 1: Extract useVariantPage composable**

Create `frontend/src/composables/useVariantPage.js`:

```javascript
/**
 * Composable for PageVariant.vue's data lifecycle.
 *
 * Owns: variant fetch, related phenopackets fetch, publications fetch,
 * SEO meta setup, clipboard actions. No UI concerns.
 */
import { ref, computed, watch } from 'vue';
import {
  getVariantById,
  getVariantPhenopackets,
  getVariantPublications,
} from '@/api';
import { useSeoMeta } from '@/composables/useSeoMeta';

export function useVariantPage(variantIdRef) {
  const variant = ref(null);
  const phenopackets = ref([]);
  const publications = ref([]);
  const loading = ref(false);
  const error = ref(null);

  const geneSymbol = computed(() => variant.value?.gene_symbol || '');

  async function loadAll() {
    loading.value = true;
    error.value = null;
    try {
      variant.value = await getVariantById(variantIdRef.value);
      const [phenosResp, pubsResp] = await Promise.all([
        getVariantPhenopackets(variantIdRef.value),
        getVariantPublications(variantIdRef.value),
      ]);
      phenopackets.value = phenosResp.data || [];
      publications.value = pubsResp.data || [];
    } catch (err) {
      error.value = err.message;
      window.logService?.error('Failed to load variant page', {
        variantId: variantIdRef.value,
      });
    } finally {
      loading.value = false;
    }
  }

  useSeoMeta({
    title: computed(() => `${variant.value?.hgvs_c || 'Variant'} — HNF1B-DB`),
    description: computed(() => `Variant details for ${variant.value?.hgvs_c}`),
  });

  watch(variantIdRef, loadAll, { immediate: true });

  return { variant, phenopackets, publications, loading, error, geneSymbol };
}
```

- [ ] **Step 2: Extract the tab components**

Each tab component is a small focused view that receives props from PageVariant:

`VariantDetailsTab.vue` — shows HGVS notations, gene context, ACMG classification, population frequencies.
`VariantAnnotationTab.vue` — shows VEP annotation (consequence, impact, CADD, predictions).
`VariantPublicationsTab.vue` — renders `publications` prop as a list.
`VariantVisualizationTab.vue` — embeds the gene/protein visualization components filtered to this variant.

Each under 200 LOC.

- [ ] **Step 3: Rewrite PageVariant.vue as thin orchestrator**

```vue
<template>
  <v-container v-if="!loading && variant">
    <h1>{{ variant.hgvs_c }}</h1>
    <v-tabs v-model="activeTab">
      <v-tab value="details">Details</v-tab>
      <v-tab value="annotation">Annotation</v-tab>
      <v-tab value="publications">Publications ({{ publications.length }})</v-tab>
      <v-tab value="visualization">Visualization</v-tab>
    </v-tabs>
    <v-window v-model="activeTab">
      <v-window-item value="details">
        <VariantDetailsTab :variant="variant" :phenopackets="phenopackets" />
      </v-window-item>
      <v-window-item value="annotation">
        <VariantAnnotationTab :variant="variant" />
      </v-window-item>
      <v-window-item value="publications">
        <VariantPublicationsTab :publications="publications" />
      </v-window-item>
      <v-window-item value="visualization">
        <VariantVisualizationTab :variant="variant" />
      </v-window-item>
    </v-window>
  </v-container>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useVariantPage } from '@/composables/useVariantPage';
import VariantDetailsTab from './variant/VariantDetailsTab.vue';
import VariantAnnotationTab from './variant/VariantAnnotationTab.vue';
import VariantPublicationsTab from './variant/VariantPublicationsTab.vue';
import VariantVisualizationTab from './variant/VariantVisualizationTab.vue';

const route = useRoute();
const variantId = computed(() => route.params.id);
const { variant, phenopackets, publications, loading } = useVariantPage(variantId);
const activeTab = ref('details');
</script>
```

- [ ] **Step 4: Run characterization spec unchanged**

```bash
cd frontend && npx vitest run tests/unit/views/PageVariant.spec.js
```

Expected: passes unchanged.

- [ ] **Step 5: Run full check + build**

```bash
cd frontend && make check && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/PageVariant.vue frontend/src/views/variant/ frontend/src/composables/useVariantPage.js
git commit -m "refactor(frontend): split PageVariant.vue into composable + tab components

Extracts data lifecycle into useVariantPage composable. Splits tab
content into 4 focused components under views/variant/. The top-level
PageVariant.vue becomes layout + tab routing only (~80 LOC, down
from 1,032 LOC).

Wave 2 characterization test passes unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Split HNF1BGeneVisualization.vue — and fix the zoom bug

**Files:**
- Modify: `frontend/src/components/gene/HNF1BGeneVisualization.vue` (orchestration + template only)
- Create: `frontend/src/composables/useGenePlotScales.js`
- Create: `frontend/src/composables/useGenePlotZoom.js`
- Create: `frontend/src/composables/useVariantFiltering.js`
- Create: `frontend/src/composables/useTooltip.js`
- Create: `frontend/src/utils/d3/geneAxis.js`
- Create: `frontend/src/utils/d3/variantMarkers.js`
- Create: `frontend/src/utils/d3/exonTracks.js`

- [ ] **Step 1: Read the component's structure**

```bash
grep -n "^const\|^function\|^watch\|^computed\|^onMounted" frontend/src/components/gene/HNF1BGeneVisualization.vue | head -40
```

Identify the major responsibilities: scales (x/y D3 scales), zoom (D3 zoom behavior), variant filtering, tooltip rendering, SVG axis rendering, marker rendering, exon track rendering.

- [ ] **Step 2: Extract pure D3 utilities first**

Create `frontend/src/utils/d3/geneAxis.js`:

```javascript
/**
 * Pure D3 utilities for rendering the gene-coordinate axis.
 *
 * No Vue reactivity — takes a selection and a scale, mutates the
 * selection. Testable with a single happy-dom <svg> element.
 */
import * as d3 from 'd3';

export function renderGeneAxis(selection, scale, options = {}) {
  const axis = d3.axisBottom(scale).ticks(options.ticks || 10);
  selection.call(axis);
  return selection;
}

export function formatGenePosition(bp) {
  if (bp >= 1_000_000) return `${(bp / 1_000_000).toFixed(2)}Mb`;
  if (bp >= 1_000) return `${(bp / 1_000).toFixed(1)}kb`;
  return `${bp}bp`;
}
```

Repeat for `variantMarkers.js` (pure functions that take a D3 selection + data and append/update markers) and `exonTracks.js`.

- [ ] **Step 3: Extract composables**

Create `useGenePlotScales.js`:

```javascript
import { computed, ref } from 'vue';
import * as d3 from 'd3';

export function useGenePlotScales(variantsRef, widthRef, heightRef) {
  const xDomain = computed(() => {
    if (!variantsRef.value?.length) return [0, 1];
    return d3.extent(variantsRef.value, (v) => v.position);
  });
  const xScale = computed(() =>
    d3.scaleLinear().domain(xDomain.value).range([0, widthRef.value]),
  );
  // ... etc
  return { xScale, xDomain };
}
```

Create `useGenePlotZoom.js`:

```javascript
import { ref, onMounted, onBeforeUnmount } from 'vue';
import * as d3 from 'd3';

/**
 * Encapsulates D3 zoom behavior.
 *
 * IMPORTANT: This composable fixes the zoom bug flagged in the
 * 2026-04-09 review. The old implementation attached the zoom
 * handler to the wrong selection (the outer SVG instead of the
 * inner transformable group) which is why zoom controls rendered
 * but didn't work. The fix: apply transforms to a dedicated
 * <g class="zoomable"> element.
 */
export function useGenePlotZoom(svgRef, groupRef, options = {}) {
  const currentTransform = ref(d3.zoomIdentity);
  let zoomBehavior;

  onMounted(() => {
    if (!svgRef.value || !groupRef.value) return;
    zoomBehavior = d3
      .zoom()
      .scaleExtent(options.scaleExtent || [1, 10])
      .on('zoom', (event) => {
        currentTransform.value = event.transform;
        d3.select(groupRef.value).attr('transform', event.transform);
      });
    d3.select(svgRef.value).call(zoomBehavior);
  });

  function zoomIn() {
    if (zoomBehavior && svgRef.value) {
      d3.select(svgRef.value).transition().call(zoomBehavior.scaleBy, 1.5);
    }
  }

  function zoomOut() {
    if (zoomBehavior && svgRef.value) {
      d3.select(svgRef.value).transition().call(zoomBehavior.scaleBy, 0.66);
    }
  }

  function resetZoom() {
    if (zoomBehavior && svgRef.value) {
      d3.select(svgRef.value).transition().call(zoomBehavior.transform, d3.zoomIdentity);
    }
  }

  onBeforeUnmount(() => {
    if (svgRef.value && zoomBehavior) {
      d3.select(svgRef.value).on('.zoom', null);
    }
  });

  return { currentTransform, zoomIn, zoomOut, resetZoom };
}
```

Create `useVariantFiltering.js` (filter variants by consequence, ACMG class, etc.) and `useTooltip.js` (manage tooltip visibility and content).

- [ ] **Step 4: Rewrite HNF1BGeneVisualization.vue**

Shrink the component to:
- `<script setup>`: import composables, create refs, wire them together.
- `<template>`: the SVG structure with a `ref="svg"` and `ref="zoomableGroup"`.
- `<style>`: any remaining scoped styles.

Target: under 400 LOC.

- [ ] **Step 5: Run characterization spec including the zoom `it.fails` test**

```bash
cd frontend && npx vitest run tests/unit/components/gene/HNF1BGeneVisualization.spec.js
```

Expected: the 4 non-zoom characterization tests still pass. The `it.fails` zoom test now **passes unexpectedly** (because the bug is fixed) — vitest will report this as a failure because `.fails` tests are expected to fail.

Remove the `.fails` suffix from the zoom test. It should now be a normal passing test:

```javascript
it('zoom in button increases the visible scale', async () => {
  // ... same body
});
```

Run again. All 5 tests pass.

- [ ] **Step 6: Verify file sizes**

```bash
wc -l frontend/src/components/gene/HNF1BGeneVisualization.vue \
      frontend/src/composables/useGenePlot*.js \
      frontend/src/composables/useVariantFiltering.js \
      frontend/src/composables/useTooltip.js \
      frontend/src/utils/d3/*.js
```

Expected: every file under 500 LOC, most under 200 LOC.

- [ ] **Step 7: Manual smoke test (recommended)**

```bash
cd frontend && npm run dev
```

Navigate to a page that embeds `HNF1BGeneVisualization`. Verify variants render and, critically, that zoom controls actually zoom. Kill the dev server.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/gene/HNF1BGeneVisualization.vue frontend/src/composables/useGenePlot*.js frontend/src/composables/useVariantFiltering.js frontend/src/composables/useTooltip.js frontend/src/utils/d3/ frontend/tests/unit/components/gene/HNF1BGeneVisualization.spec.js
git commit -m "$(cat <<'EOF'
refactor(frontend): split HNF1BGeneVisualization.vue and fix zoom bug

Decomposes the 1,421-LOC gene visualization component into:
  HNF1BGeneVisualization.vue   (orchestration + template, <400 LOC)
  composables/useGenePlotScales.js
  composables/useGenePlotZoom.js
  composables/useVariantFiltering.js
  composables/useTooltip.js
  utils/d3/geneAxis.js
  utils/d3/variantMarkers.js
  utils/d3/exonTracks.js

The zoom bug flagged in the 2026-04-09 review (#92) is fixed as a
side effect of useGenePlotZoom: the old implementation attached the
zoom handler to the outer SVG instead of a dedicated transformable
<g> element. The Wave 2 characterization zoom test flips from
it.fails to it and passes.

Closes P3 #10 for HNF1BGeneVisualization and issue #92.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Split ProteinStructure3D.vue

**Files:**
- Modify: `frontend/src/components/gene/ProteinStructure3D.vue`
- Create: `frontend/src/composables/useNGLViewer.js`
- Create: `frontend/src/components/gene/ProteinViewerControls.vue`

- [ ] **Step 1: Extract NGL integration into useNGLViewer**

Create `frontend/src/composables/useNGLViewer.js`:

```javascript
/**
 * NGL Viewer composable.
 *
 * Owns the lifecycle of a NGL Stage: creation, loading, disposal,
 * representation changes. The component passes a container ref and
 * the composable handles the rest.
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import * as NGL from 'ngl';

export function useNGLViewer(containerRef, pdbIdRef, options = {}) {
  const stage = ref(null);
  const loading = ref(false);
  const error = ref(null);

  async function load(pdbId) {
    if (!stage.value) return;
    loading.value = true;
    error.value = null;
    try {
      stage.value.removeAllComponents();
      const component = await stage.value.loadFile(`rcsb://${pdbId}`);
      component.addRepresentation(options.defaultRepresentation || 'cartoon');
      component.autoView();
    } catch (err) {
      error.value = err.message;
      window.logService?.error('NGL load failed', { pdbId, err: err.message });
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    if (!containerRef.value) return;
    stage.value = new NGL.Stage(containerRef.value, {
      backgroundColor: options.backgroundColor || 'white',
    });
    if (pdbIdRef.value) load(pdbIdRef.value);
  });

  watch(pdbIdRef, (newId) => newId && load(newId));

  onBeforeUnmount(() => {
    if (stage.value) stage.value.dispose();
  });

  function setRepresentation(representation) {
    if (!stage.value) return;
    const components = stage.value.compList || [];
    components.forEach((comp) => {
      comp.removeAllRepresentations();
      comp.addRepresentation(representation);
    });
  }

  return { stage, loading, error, setRepresentation };
}
```

- [ ] **Step 2: Extract UI controls into ProteinViewerControls.vue**

A small presentation-only component with a representation selector, reset-view button, screenshot button, emits events the parent handles.

- [ ] **Step 3: Rewrite ProteinStructure3D.vue**

Shrink to orchestration. Also fix the `console.warn` hijacking flagged in the review — replace with `logService.warn` calls using a proper error boundary around the NGL operations.

- [ ] **Step 4: Run characterization spec + checks**

```bash
cd frontend && npx vitest run tests/unit/components/gene/ProteinStructure3D.spec.js && make check
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/gene/ProteinStructure3D.vue frontend/src/composables/useNGLViewer.js frontend/src/components/gene/ProteinViewerControls.vue
git commit -m "refactor(frontend): split ProteinStructure3D.vue with useNGLViewer composable

Extracts NGL Stage lifecycle into useNGLViewer composable and UI
controls into ProteinViewerControls.vue. Component shrinks from
1,130 LOC to <400 LOC. Fixes the console.warn hijacking pattern
(review #5 medium) by routing warnings through logService.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Split HNF1BProteinVisualization.vue

**Files:**
- Modify: `frontend/src/components/gene/HNF1BProteinVisualization.vue`
- Create: `frontend/src/composables/useProteinPlotScales.js`
- Create: `frontend/src/composables/useDomainHighlighting.js`
- Create: `frontend/src/utils/d3/proteinAxis.js`
- Create: `frontend/src/utils/d3/domainBars.js`

- [ ] **Step 1: Follow the HNF1BGeneVisualization pattern**

Apply the same composable-extraction approach used in Task 6. The protein visualization has different specifics (residue positions instead of genomic coordinates, protein domains instead of exons) but the same Vue/D3 integration shape.

- [ ] **Step 2: Run characterization spec (the upgraded one from Wave 2)**

```bash
cd frontend && npx vitest run tests/unit/components/HNF1BProteinVisualization.spec.js
```

Expected: all tests (both domain-data and characterization) pass unchanged.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/gene/HNF1BProteinVisualization.vue frontend/src/composables/useProteinPlotScales.js frontend/src/composables/useDomainHighlighting.js frontend/src/utils/d3/proteinAxis.js frontend/src/utils/d3/domainBars.js
git commit -m "refactor(frontend): split HNF1BProteinVisualization.vue

Applies the same composable + d3 util pattern as the gene
visualization split in Task 6. Component shrinks from 1,063 LOC to
<400 LOC. Wave 2 characterization spec passes unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Decompose the 11 medium-oversized files

Each sub-task is its own PR. Same pattern: extract composable(s), extract sub-components, shrink the top-level file, run tests, commit.

### Task 9a: PagePublication.vue (704 LOC)

- [ ] Extract `usePublicationPage(pubId)` composable (data + SEO).
- [ ] Extract `PublicationCitationCard.vue` and `PublicationAbstractCard.vue`.
- [ ] Shrink `PagePublication.vue` to layout. Target < 200 LOC.
- [ ] Add a thin render test for the extracted components.
- [ ] Commit: `refactor(frontend): split PagePublication.vue into composable + cards`.

### Task 9b: AggregationsDashboard.vue (693 LOC)

- [ ] Extract one section component per aggregation tab:
  - `DemographicsSection.vue`
  - `ClinicalFeaturesSection.vue`
  - `VariantsSection.vue`
  - `PublicationsSection.vue`
  - `SurvivalSection.vue`
- [ ] `AggregationsDashboard.vue` becomes layout + tab routing.
- [ ] Commit: `refactor(frontend): split AggregationsDashboard.vue into section components`.

### Task 9c: PagePhenopacket.vue (682 LOC)

- [ ] Extract `usePhenopacketPage(id)` composable.
- [ ] Extract tab content components: `PhenopacketSubjectTab.vue`, `PhenopacketFeaturesTab.vue`, `PhenopacketInterpretationsTab.vue`, `PhenopacketVariantsTab.vue`.
- [ ] Commit: `refactor(frontend): split PagePhenopacket.vue into composable + tabs`.

### Task 9d: VariantComparisonChart.vue (649 LOC)

- [ ] Extract organ-system keyword map to `frontend/src/data/organSystemKeywords.js` (fixes review anti-pattern).
- [ ] Extract `useComparisonChartData` composable (transforms raw aggregation data into chart-ready shape).
- [ ] Extract `chartTransformers.js` pure utilities under `frontend/src/utils/chart/`.
- [ ] Remove `document.createElement` direct DOM manipulation — use Vue template refs.
- [ ] Commit: `refactor(frontend): split VariantComparisonChart and fix direct DOM manipulation`.

### Task 9e: useSeoMeta.js (621 LOC)

- [ ] Split the composable into thinner pieces:
  - `useSeoMeta.js` — orchestration, accepts options, calls the below helpers
  - `seoStructuredData.js` — JSON-LD generation functions
  - `seoBreadcrumbs.js` — breadcrumb builders
  - `seoDefaults.js` — static default meta values
- [ ] All three helpers are pure functions — easy to unit test.
- [ ] Commit: `refactor(frontend): split useSeoMeta.js into orchestration + pure helpers`.

### Task 9f: Phenopackets.vue (590 LOC)

- [ ] Extract `usePhenopacketList` composable (data + pagination + filters).
- [ ] Extract `PhenopacketListFilters.vue` facet panel.
- [ ] Commit: `refactor(frontend): split Phenopackets.vue into list composable + filter panel`.

### Task 9g: InterpretationsCard.vue (557 LOC)

- [ ] Extract `InterpretationRow.vue` (one genomic interpretation).
- [ ] Extract `useInterpretationFormatting.js` composable for the formatting helpers.
- [ ] Commit: `refactor(frontend): split InterpretationsCard into row component + formatting composable`.

### Task 9h: Variants.vue (544 LOC) — and fix the broken search

- [ ] **Investigate the broken variant search first.** The review notes it's non-functional. Read the current search implementation. Likely cause: wrong query parameter name, or client-side filtering that silently fails.
- [ ] Extract `useVariantList` composable (data + pagination + search + sort).
- [ ] Extract `VariantListFilters.vue` component.
- [ ] Fix the search bug as part of the extraction — the composable should call the search endpoint correctly and propagate results to the list.
- [ ] Add a test for the fix: `frontend/tests/unit/composables/useVariantList.spec.js` asserting search results update when the query changes.
- [ ] Commit: `refactor(frontend): split Variants.vue and fix broken variant search`.

### Task 9i: User.vue (522 LOC)

- [ ] Extract `UserProfileForm.vue`, `UserPasswordChangeForm.vue`, `UserActivityList.vue`.
- [ ] Commit: `refactor(frontend): split User.vue into profile/password/activity sub-components`.

### Task 9j: VariantAnnotator.vue (509 LOC)

- [ ] Extract `useVariantAnnotation` composable (API calls + result processing).
- [ ] Extract `AnnotationResultCard.vue`.
- [ ] Wave 6 will add a dedicated component test; none needed here.
- [ ] Commit: `refactor(frontend): split VariantAnnotator.vue into composable + result card`.

### Task 9k: Home.vue (503 LOC)

- [ ] Lightest split. Extract hero, stats, and features sections into small focused components:
  - `HomeHero.vue`
  - `HomeStatsBanner.vue`
  - `HomeFeaturesGrid.vue`
- [ ] Commit: `refactor(frontend): split Home.vue into hero, stats, and features sections`.

---

## Task 10: Wave 5 exit verification

- [ ] **Step 1: Verify all Wave 2 characterization tests still pass unchanged**

```bash
cd frontend && npx vitest run tests/unit/views/PageVariant.spec.js tests/unit/components/gene/ tests/unit/views/AdminDashboard.spec.js tests/unit/views/FAQ.spec.js tests/unit/components/HNF1BProteinVisualization.spec.js
```

Expected: all pass. The `git diff` against the Wave 2 commit of those files should show **no changes** (except for `HNF1BGeneVisualization.spec.js` where the zoom test flipped from `it.fails` to `it`).

- [ ] **Step 2: Measure all frontend files**

```bash
find frontend/src -name "*.vue" -o -name "*.js" -exec wc -l {} \; | awk '$1 > 500 {print}' | sort -rn
```

Expected: at most 3 files over 500 LOC, each with an entry in `docs/refactor/tech-debt.md`.

- [ ] **Step 3: Run the full frontend suite + build**

```bash
cd frontend && make check && npm run build
```

Expected: all green.

- [ ] **Step 4: Verify v-html audit**

```bash
grep -rn "v-html" frontend/src --include="*.vue"
```

Expected: only matches in FAQ.vue and About.vue, both using the sanitize() utility from Wave 1.

- [ ] **Step 5: Smoke test the zoom fix (manual)**

```bash
cd frontend && npm run dev
```

Navigate to a page with `HNF1BGeneVisualization`, use zoom buttons, verify actually zooms. Kill server.

- [ ] **Step 6: Write exit note**

Create `docs/refactor/wave-5-exit.md` summarizing: all 17 file splits, the zoom bug fix, the variant search fix, test count changes, entries added to tech-debt.md.

- [ ] **Step 7: Commit**

```bash
git add docs/refactor/wave-5-exit.md
git commit -m "docs: add Wave 5 exit note

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

**Wave 5 is done when all Task 1-10 items (including 9a-9k sub-tasks) are checked off and the exit note is committed.**

---

## Self-Review Notes

- **Spec coverage:** useSyncTask (Task 1), api/index.js split (Task 2), auth consolidation (Task 3), AdminDashboard split (Task 4), PageVariant split (Task 5), HNF1BGeneVisualization split + zoom fix (Task 6), ProteinStructure3D split (Task 7), HNF1BProteinVisualization split (Task 8), 11 medium files (Task 9a-9k). Every Wave 5 item from the spec is addressed.
- **Safety net:** every giant component split references the Wave 2 characterization test and asserts it passes unchanged.
- **Bug fixes as side effects:** zoom bug (Task 6), variant search (Task 9h), DOM manipulation anti-pattern (Task 9d), console.warn hijacking (Task 7), organ system keyword map (Task 9d).
- **Placeholder scan:** Tasks 9a-9k are terse by design — the pattern is established in Tasks 1-8 and 9 sub-tasks follow it mechanically. No `<fill in>` except the exit note template.
- **Type/name consistency:** `useSyncTask`, `useVariantPage`, `useGenePlotZoom`, etc., all used consistently between their creation tasks and the components that import them.
- **Risk callout:** Task 9h (variant search fix) is the highest-risk item in Wave 5 because it introduces a behavioral fix, not just a refactor. Test coverage is explicit in that task.
