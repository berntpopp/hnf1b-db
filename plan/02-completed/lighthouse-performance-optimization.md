# Lighthouse Performance Optimization Plan

## Executive Summary

Based on Lighthouse diagnostics and codebase analysis, this plan addresses:
- **Minify JavaScript**: Est savings 1,558 KiB (dev mode artifact - production already minified)
- **Reduce unused JavaScript**: Est savings 849 KiB
- **Back/forward cache**: 1 failure reason
- **Minify CSS**: Est savings 27 KiB
- **Reduce unused CSS**: Est savings 145 KiB
- **Enormous network payloads**: Total 4,706 KiB
- **Long main-thread tasks**: 4 long tasks

## Current Build Analysis

| Chunk | Uncompressed | Brotli | Status |
|-------|-------------|--------|--------|
| ngl-viewer | 776 KB | 178 KB | Lazy-loaded ✓ |
| vendor | 492 KB | 104 KB | **Needs optimization** |
| vuetify-core | 268 KB | 68 KB | Expected (full UI lib) |
| charts | 192 KB | 54 KB | Lazy-loaded ✓ |
| d3-modules | 78 KB | 22 KB | Lazy-loaded ✓ |
| vuetify-data | 31 KB | 8 KB | Lazy-loaded ✓ |

---

## Phase 1: Quick Wins (Est. -50-80 KB)

### 1.1 Remove Unused Dependencies

**vee-validate** - Declared but never imported (grep found 0 matches)
```bash
npm uninstall vee-validate
# Saves: ~25 KB (tree-shaken but still bundled metadata)
```

**@mdi/js** - Installed but not used (using @mdi/font instead)
```bash
npm uninstall @mdi/js
# Saves: ~800 KB from node_modules (not bundled, but cleaner deps)
```

### 1.2 Replace lodash-es with just-debounce-it

Current: `lodash-es` used in only 2 files for `debounce`:
- `src/composables/useAutosave.js:24`
- `src/composables/useHPOAutocomplete.js:15`

**Action**: Replace with `just-debounce-it` (already in package.json):

```javascript
// Before
import { debounce } from 'lodash-es';

// After
import debounce from 'just-debounce-it';
```

Then remove lodash-es:
```bash
npm uninstall lodash-es
# Saves: ~4 KB brotli (lodash-es partial import)
```

### 1.3 Optimize MDI Icon Font Loading

Current: Loading full icon font (~396 KB woff2)
Options:
1. **Keep current** - Simple, all icons available
2. **Subset font** - Complex, maintenance burden
3. **Switch to @mdi/js SVG icons** - Tree-shakeable but requires refactoring all 44 files

**Recommendation**: Keep @mdi/font for now. The font-display: swap is already implemented.
Future: Consider subsetting if icon count is limited.

---

## Phase 2: CSS Optimization (Est. -100-145 KB)

### 2.1 Analyze Unused CSS

Vuetify includes all component styles. Options:

**Option A: PurgeCSS (Complex)**
```javascript
// vite.config.js
import purgecss from '@fullhuman/postcss-purgecss'

// Risk: May remove dynamically-used classes
// Requires extensive safelist configuration
```

**Option B: Vuetify Sass Variables (Recommended)**
Customize Vuetify to exclude unused component styles:

```javascript
// vite.config.js
vuetify({
  autoImport: true,
  styles: {
    configFile: 'src/styles/vuetify-settings.scss'
  }
})
```

```scss
// src/styles/vuetify-settings.scss
// Disable unused component styles
$rating-disabled: true;
$slider-disabled: true;
// etc.
```

### 2.2 Critical CSS Extraction

Already implemented in `index.html`:
```html
<style>
  #app { min-height: 100vh; }
  #app:empty { visibility: hidden; }
</style>
```

**Additional**: Extract above-the-fold CSS for Home page hero section.

---

## Phase 3: JavaScript Optimization (Est. -200-400 KB)

### 3.1 Lazy Load Heavy Aggregations Components

`AggregationsDashboard` is 86 KB brotli. Split into:

```javascript
// Current: All charts load together
// Proposed: Lazy load individual chart components

const KaplanMeierChart = defineAsyncComponent(() =>
  import('@/components/analyses/KaplanMeierChart.vue')
);

const PublicationsTimelineChart = defineAsyncComponent(() =>
  import('@/components/analyses/PublicationsTimelineChart.vue')
);
```

### 3.2 Split Vendor Chunk Further

Current vendor chunk (492 KB) contains mixed dependencies.

```javascript
// vite.config.js - Enhanced manualChunks
manualChunks(id) {
  // Existing splits...

  // NEW: Split date-fns
  if (id.includes('date-fns')) return 'date-fns';

  // NEW: Split yup validation
  if (id.includes('yup')) return 'validation';

  // NEW: Split file-saver (only used in downloads)
  if (id.includes('file-saver')) return 'file-utils';
}
```

### 3.3 Dynamic Import for Non-Critical Features

```javascript
// Log viewer - only loaded when user opens it
const LogViewer = defineAsyncComponent(() =>
  import('@/components/LogViewer.vue')
);

// Search card - can be deferred
const SearchCard = defineAsyncComponent({
  loader: () => import('@/components/SearchCard.vue'),
  delay: 200
});
```

---

## Phase 4: Back/Forward Cache (bfcache)

### 4.1 Identify Blockers

Common bfcache blockers:
- `beforeunload` event listeners
- `unload` event listeners
- Open WebSocket/EventSource connections
- In-progress `fetch()` requests
- `Cache-Control: no-store` responses

**Action**: Audit for these patterns:

```javascript
// Check for unload listeners
grep -r "beforeunload\|addEventListener.*unload" src/

// Check for WebSocket usage
grep -r "WebSocket\|EventSource" src/
```

### 4.2 Fix: Remove Unload Listeners

If found, convert to `pagehide` with `persisted` check:

```javascript
// Before (blocks bfcache)
window.addEventListener('beforeunload', cleanup);

// After (bfcache compatible)
window.addEventListener('pagehide', (event) => {
  if (!event.persisted) {
    cleanup();
  }
});
```

### 4.3 Fix: Properly Close Connections

```javascript
// In component unmount
onUnmounted(() => {
  // Close any open connections
  abortController.abort();
});
```

---

## Phase 5: Long Main-Thread Tasks

### 5.1 Defer Non-Critical JavaScript

```javascript
// main.js - Defer auth initialization
const authStore = useAuthStore();

// Use requestIdleCallback for non-critical init
if ('requestIdleCallback' in window) {
  requestIdleCallback(() => {
    authStore.initialize();
  });
} else {
  setTimeout(() => authStore.initialize(), 0);
}
```

### 5.2 Web Workers for Heavy Computation

For D3 data processing:

```javascript
// workers/dataProcessor.worker.js
self.onmessage = (e) => {
  const processed = heavyDataProcessing(e.data);
  self.postMessage(processed);
};

// Component
const worker = new Worker(new URL('./workers/dataProcessor.worker.js', import.meta.url));
```

### 5.3 Virtualize Long Lists

Already using VDataTable with virtual scrolling. Ensure:
```vue
<v-data-table
  :items="items"
  :virtual="items.length > 100"
  :item-height="48"
/>
```

---

## Phase 6: Network Payload Optimization

### 6.1 Image Optimization

If images exist, add:
```javascript
// vite.config.js
import imagemin from 'vite-plugin-imagemin';

plugins: [
  imagemin({
    webp: { quality: 80 },
    avif: { quality: 65 }
  })
]
```

### 6.2 Font Subsetting (Future)

For MDI icons, identify used icons:
```bash
grep -roh "mdi-[a-z-]*" src/ | sort -u > used-icons.txt
```

Then create subset using fonttools:
```bash
pyftsubset materialdesignicons.woff2 --unicodes-file=used-icons.txt
```

### 6.3 Preload Critical Assets

Already in `index.html`:
```html
<link rel="preconnect" href="https://api.hnf1b.org" crossorigin />
```

Add preload for critical chunks:
```html
<link rel="modulepreload" href="/assets/vue-core-[hash].js" />
<link rel="modulepreload" href="/assets/vuetify-core-[hash].js" />
```

---

## Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Remove vee-validate | 5 min | Low |
| 2 | Remove @mdi/js | 5 min | Low |
| 3 | Replace lodash-es | 15 min | Medium |
| 4 | Fix bfcache blockers | 30 min | High (UX) |
| 5 | Lazy load Aggregations | 1 hr | Medium |
| 6 | Split vendor chunk | 30 min | Medium |
| 7 | Vuetify Sass optimization | 2 hr | High |
| 8 | Web Workers for D3 | 3 hr | Medium |

---

## Monitoring

### Bundle Size CI Check

Already configured with `chunkSizeWarningLimit: 300`.

Add GitHub Action:
```yaml
- name: Check bundle size
  run: |
    npm run build
    # Fail if any chunk > 300KB uncompressed
```

### Lighthouse CI

```yaml
- name: Lighthouse CI
  uses: treosh/lighthouse-ci-action@v11
  with:
    configPath: './lighthouserc.json'
```

---

## Expected Results

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Total JS | ~2.5 MB | ~2.0 MB | Unused deps, splitting |
| Total CSS | ~750 KB | ~600 KB | Vuetify optimization |
| FCP | 9.3s | <3s | Critical path optimization |
| LCP | 14.8s | <4s | Lazy loading, preloading |
| bfcache | Blocked | Enabled | Remove blockers |

---

## Notes

1. **Dev vs Production**: The "Minify JavaScript" warning (1,558 KiB) is likely from running Lighthouse on dev server. Production builds are already minified with Terser.

2. **Vuetify Trade-off**: Full Vuetify is ~270 KB brotli. Manual tree-shaking requires explicit imports everywhere. Current auto-import is the recommended approach.

3. **NGL Viewer**: 178 KB brotli is unavoidable for 3D protein visualization. Already correctly lazy-loaded.
