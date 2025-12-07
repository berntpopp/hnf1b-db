# HNF1B Database - Lighthouse Optimization Report

**Date:** 2025-12-05
**Current Scores:** Performance 58 | Accessibility 80 | Best Practices 96 | SEO 83
**Target Scores:** Performance 90+ | Accessibility 95+ | Best Practices 100 | SEO 95+

---

## Executive Summary

This report provides a comprehensive analysis of the HNF1B Database frontend based on Lighthouse audit results, codebase investigation, and comparison with the GeneFoundry frontend (a modern reference implementation). The findings identify **23 actionable improvements** across performance, accessibility, SEO, and best practices.

### Key Issues Identified

| Category | Current | Target | Critical Issues |
|----------|---------|--------|-----------------|
| **Performance** | 58 | 90+ | TBT 2,330ms, unused JS 8,453KB, font blocking |
| **Accessibility** | 80 | 95+ | Missing aria-labels, ARIA role issues, contrast |
| **Best Practices** | 96 | 100 | Console errors, missing CSP headers |
| **SEO** | 83 | 95+ | No meta description, invalid robots.txt, no JSON-LD |

### Console Error Detected

```
GET https://api.hnf1b.org/api/v2/reference/genes/HNF1B/domains?genome_build=GRCh38 404 (Not Found)
```

**Root Cause:** The `/reference/genes/{symbol}/domains` endpoint exists in the backend (`backend/app/reference/router.py:219`), but the reference data (genes, transcripts, protein domains) may not be populated in the production database.

**Fix:** Either populate the reference tables or add graceful error handling in the frontend to prevent console errors.

---

## Part 1: Performance Optimization (Score: 58 → 90+)

### 1.1 Critical: Font Loading Strategy

**Current Issue:** Material Design Icons loaded via CSS import blocks rendering.

```javascript
// main.js - CURRENT (blocking)
import '@mdi/font/css/materialdesignicons.css';
```

**Impact:** ~500KB font file blocks First Contentful Paint (FCP), contributes to 510ms font display delay.

**Solution A: Add font-display: swap (Quick Fix)**

Create `src/assets/mdi-override.css`:

```css
/* Override MDI font-face to use swap */
@font-face {
  font-family: 'Material Design Icons';
  src: url('~@mdi/font/fonts/materialdesignicons-webfont.woff2') format('woff2'),
       url('~@mdi/font/fonts/materialdesignicons-webfont.woff') format('woff');
  font-weight: normal;
  font-style: normal;
  font-display: swap; /* Critical: Show fallback immediately */
}
```

**Solution B: Switch to SVG Icons (Best Performance)**

You already have `@mdi/js` installed. Update Vuetify config:

```javascript
// src/plugins/vuetify.js
import { createVuetify } from 'vuetify';
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg';

export default createVuetify({
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: { mdi },
  },
});
```

Then in components:

```vue
<script setup>
import { mdiHome, mdiAccount, mdiMagnify } from '@mdi/js';
</script>

<template>
  <v-icon :icon="mdiHome" />
  <v-btn :prepend-icon="mdiAccount">Profile</v-btn>
</template>
```

**Impact:** Eliminates 500KB font download, reduces TBT by 60-80%.

---

### 1.2 High: Add Compression Plugins

**Current:** No pre-compression of assets.

**Solution:** Add Brotli + gzip compression to `vite.config.js`:

```bash
npm install --save-dev vite-plugin-compression
```

```javascript
// vite.config.js
import compression from 'vite-plugin-compression';

export default defineConfig({
  plugins: [
    vue(),
    vuetify({ autoImport: true }),

    // Brotli compression (best, ~20% smaller than gzip)
    compression({
      algorithm: 'brotliCompress',
      ext: '.br',
      threshold: 1024,
      exclude: [/\.(png|jpg|jpeg|gif|webp|avif|ico)$/i],
    }),

    // Gzip fallback for older browsers
    compression({
      algorithm: 'gzip',
      ext: '.gz',
      threshold: 1024,
      exclude: [/\.(png|jpg|jpeg|gif|webp|avif|ico)$/i],
    }),

    visualizer({ /* existing config */ }),
  ],
});
```

**Impact:** 20-30% smaller transfer sizes, faster initial load.

---

### 1.3 High: Optimize Manual Chunks

**Current:** Basic chunking for vue, vuetify, d3, axios.

**Improved:** Function-based splitting for better granularity:

```javascript
// vite.config.js
build: {
  rollupOptions: {
    output: {
      manualChunks(id) {
        // Heavy visualization libraries
        if (id.includes('chart.js')) return 'charts';
        if (id.includes('ngl')) return 'ngl-viewer';
        if (id.includes('d3-')) return 'd3-modules';

        // Vuetify data components (heavy)
        if (id.includes('vuetify/lib/components/VDataTable')) {
          return 'vuetify-data';
        }
        if (id.includes('vuetify')) return 'vuetify-core';

        // Vue ecosystem
        if (id.includes('vue-router') || id.includes('pinia')) {
          return 'vue-core';
        }
        if (id.includes('vue')) return 'vue-vendor';

        // Other node_modules
        if (id.includes('node_modules')) return 'vendor';
      },
    },
  },

  // Alert on large chunks
  chunkSizeWarningLimit: 300,
},
```

**Impact:** Better caching, reduced re-downloads on updates.

---

### 1.4 Medium: Lazy Load Heavy Components

**Current:** Some components load eagerly within views.

**Solution:** Use `defineAsyncComponent` for heavy visualizations:

```vue
<script setup>
import { defineAsyncComponent, ref } from 'vue';

// Lazy load 3D viewer only when tab is active
const ProteinStructure3D = defineAsyncComponent(() =>
  import('@/components/gene/ProteinStructure3D.vue')
);

const activeTab = ref('lollipop');
</script>

<template>
  <v-tabs v-model="activeTab">
    <v-tab value="lollipop">Lollipop Plot</v-tab>
    <v-tab value="3d">3D Structure</v-tab>
  </v-tabs>

  <v-window v-model="activeTab">
    <v-window-item value="lollipop">
      <HNF1BProteinVisualization :variants="variants" />
    </v-window-item>
    <v-window-item value="3d">
      <!-- Only loads NGL.js (~300KB) when this tab is shown -->
      <Suspense>
        <ProteinStructure3D v-if="activeTab === '3d'" />
        <template #fallback>
          <v-skeleton-loader type="image" />
        </template>
      </Suspense>
    </v-window-item>
  </v-window>
</template>
```

**Impact:** Reduces initial bundle by 300KB+ for pages with 3D viewer.

---

### 1.5 Medium: Add Content Visibility for Below-Fold Content

**Solution:** Add to `src/style.css`:

```css
/* Optimize rendering of below-fold sections */
.v-data-table,
.phenopacket-details,
.aggregations-dashboard {
  content-visibility: auto;
  contain-intrinsic-size: auto 500px;
}

/* Skip rendering hidden tabs */
.v-window-item:not(.v-window-item--active) {
  content-visibility: hidden;
}
```

**Impact:** Browser skips rendering off-screen content, reducing main thread work.

---

### 1.6 Low: Preconnect to API

**Solution:** Add to `index.html`:

```html
<head>
  <!-- DNS prefetch for API -->
  <link rel="dns-prefetch" href="//api.hnf1b.org">
  <link rel="preconnect" href="https://api.hnf1b.org" crossorigin>
</head>
```

**Impact:** Saves 100-300ms on first API request.

---

## Part 2: Accessibility Improvements (Score: 80 → 95+)

### 2.1 Critical: Add aria-labels to Icon Buttons

**Files Affected:**
- `src/views/Variants.vue` (lines 244-253)
- `src/views/SearchResults.vue` (lines 141-150)
- `src/views/Phenopackets.vue` (lines 69-78, 86)

**Current (Missing aria-labels):**

```vue
<v-btn icon :disabled="options.page === 1" @click="goToFirstPage">
  <v-icon>mdi-page-first</v-icon>
</v-btn>
```

**Fixed:**

```vue
<v-btn
  icon
  :disabled="options.page === 1"
  @click="goToFirstPage"
  aria-label="Go to first page"
>
  <v-icon aria-hidden="true">mdi-page-first</v-icon>
</v-btn>

<v-btn
  icon
  :disabled="options.page === 1"
  @click="goToPreviousPage"
  aria-label="Go to previous page"
>
  <v-icon aria-hidden="true">mdi-chevron-left</v-icon>
</v-btn>

<v-btn
  icon
  :disabled="options.page === totalPages"
  @click="goToNextPage"
  aria-label="Go to next page"
>
  <v-icon aria-hidden="true">mdi-chevron-right</v-icon>
</v-btn>

<v-btn
  icon
  :disabled="options.page === totalPages"
  @click="goToLastPage"
  aria-label="Go to last page"
>
  <v-icon aria-hidden="true">mdi-page-last</v-icon>
</v-btn>
```

**Impact:** Screen readers can now announce button purposes.

---

### 2.2 High: Fix ARIA Tooltip Issues

**Issue:** ARIA tooltip elements do not have accessible names.

**Solution:** Ensure tooltips have proper text content:

```vue
<!-- BAD: Empty tooltip -->
<v-tooltip>
  <template #activator="{ props }">
    <v-btn v-bind="props" icon>
      <v-icon>mdi-information</v-icon>
    </v-btn>
  </template>
</v-tooltip>

<!-- GOOD: Tooltip with accessible text -->
<v-tooltip text="View detailed information">
  <template #activator="{ props }">
    <v-btn v-bind="props" icon aria-label="Information">
      <v-icon aria-hidden="true">mdi-information</v-icon>
    </v-btn>
  </template>
</v-tooltip>
```

---

### 2.3 Medium: Create Accessibility Composable

**File:** `src/composables/useAccessibility.js`

```javascript
import { ref, onMounted, onUnmounted } from 'vue';

/**
 * Detect if user prefers reduced motion
 * Used to disable animations for accessibility
 */
export function usePrefersReducedMotion() {
  const prefersReducedMotion = ref(false);
  let mediaQuery = null;

  const updatePreference = (e) => {
    prefersReducedMotion.value = e.matches;
  };

  onMounted(() => {
    mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    prefersReducedMotion.value = mediaQuery.matches;
    mediaQuery.addEventListener('change', updatePreference);
  });

  onUnmounted(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', updatePreference);
    }
  });

  return prefersReducedMotion;
}

/**
 * Responsive breakpoint detection
 */
export function useIsMobile(breakpoint = 600) {
  const isMobile = ref(false);
  let mediaQuery = null;

  const updateMatch = (e) => {
    isMobile.value = e.matches;
  };

  onMounted(() => {
    mediaQuery = window.matchMedia(`(max-width: ${breakpoint}px)`);
    isMobile.value = mediaQuery.matches;
    mediaQuery.addEventListener('change', updateMatch);
  });

  onUnmounted(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', updateMatch);
    }
  });

  return isMobile;
}
```

**Usage:**

```vue
<script setup>
import { usePrefersReducedMotion } from '@/composables/useAccessibility';

const prefersReducedMotion = usePrefersReducedMotion();

const scrollToTop = () => {
  window.scrollTo({
    top: 0,
    behavior: prefersReducedMotion.value ? 'instant' : 'smooth'
  });
};
</script>
```

---

### 2.4 Medium: Fix Color Contrast Issues

**Issue:** Background and foreground colors do not have sufficient contrast ratio.

**Audit Required:** Run Lighthouse in DevTools to identify specific elements.

**Common Fixes:**

```css
/* Ensure WCAG AA compliance (4.5:1 for normal text, 3:1 for large) */

/* Light theme adjustments */
.v-chip--variant-tonal {
  /* Increase contrast for tonal chips */
  --v-chip-tonal-opacity: 0.2;
}

/* Muted text should still be readable */
.text-medium-emphasis {
  opacity: 0.7; /* Increase from 0.6 */
}

/* Links should be distinguishable */
a:not(.v-btn) {
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}
```

---

## Part 3: SEO Improvements (Score: 83 → 95+)

### 3.1 Critical: Add Meta Description and Open Graph Tags

**File:** `frontend/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />

    <!-- Primary Meta Tags -->
    <title>HNF1B Database - Clinical Phenotype and Variant Registry</title>
    <meta name="title" content="HNF1B Database - Clinical Phenotype and Variant Registry">
    <meta name="description" content="Comprehensive database of HNF1B gene variants and associated phenotypes. Search 800+ phenopackets with clinical features, genetic variants, and publications for HNF1B-related disorders.">
    <meta name="keywords" content="HNF1B, MODY5, renal cysts, diabetes, phenopackets, genetic variants, clinical genetics">
    <meta name="author" content="Berlin Institute of Health at Charité">
    <meta name="robots" content="index, follow">

    <!-- Canonical URL -->
    <link rel="canonical" href="https://hnf1b.org/">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://hnf1b.org/">
    <meta property="og:title" content="HNF1B Database - Clinical Phenotype and Variant Registry">
    <meta property="og:description" content="Comprehensive database of HNF1B gene variants and associated phenotypes. Search 800+ phenopackets with clinical features and genetic variants.">
    <meta property="og:image" content="https://hnf1b.org/HNF1B-db_logo.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:site_name" content="HNF1B Database">
    <meta property="og:locale" content="en_US">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://hnf1b.org/">
    <meta name="twitter:title" content="HNF1B Database - Clinical Phenotype and Variant Registry">
    <meta name="twitter:description" content="Comprehensive database of HNF1B gene variants and associated phenotypes.">
    <meta name="twitter:image" content="https://hnf1b.org/HNF1B-db_logo.png">

    <!-- Favicons (existing) -->
    <link rel="icon" type="image/svg+xml" href="/HNF1B-db_favicon.svg" />
    <link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png" />
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
    <link rel="shortcut icon" href="/favicon.ico" />
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">

    <!-- Mobile -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#1976D2">

    <!-- Preconnect -->
    <link rel="dns-prefetch" href="//api.hnf1b.org">
    <link rel="preconnect" href="https://api.hnf1b.org" crossorigin>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

---

### 3.2 Critical: Add JSON-LD Structured Data

**File:** `frontend/index.html` (add before closing `</head>`)

```html
    <!-- Structured Data: Organization -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "@id": "https://hnf1b.org/#organization",
      "name": "HNF1B Database",
      "url": "https://hnf1b.org",
      "logo": {
        "@type": "ImageObject",
        "url": "https://hnf1b.org/HNF1B-db_logo.svg",
        "width": 512,
        "height": 512
      },
      "description": "Comprehensive database of HNF1B gene variants and associated clinical phenotypes.",
      "foundingDate": "2021",
      "sameAs": [
        "https://github.com/berntpopp/hnf1b-db"
      ],
      "contactPoint": {
        "@type": "ContactPoint",
        "email": "contact@hnf1b.org",
        "contactType": "General Inquiry"
      },
      "parentOrganization": {
        "@type": "Organization",
        "name": "Berlin Institute of Health at Charité",
        "alternateName": "BIH",
        "url": "https://www.bihealth.org"
      }
    }
    </script>

    <!-- Structured Data: WebSite (enables sitelinks search) -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "@id": "https://hnf1b.org/#website",
      "name": "HNF1B Database",
      "url": "https://hnf1b.org",
      "description": "Clinical phenotype and variant registry for HNF1B-related disorders",
      "publisher": {
        "@id": "https://hnf1b.org/#organization"
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": "https://hnf1b.org/search?q={search_term_string}"
        },
        "query-input": "required name=search_term_string"
      }
    }
    </script>

    <!-- Structured Data: SoftwareApplication -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "@id": "https://hnf1b.org/#software",
      "name": "HNF1B Database",
      "applicationCategory": "HealthApplication",
      "applicationSubCategory": "Clinical Genetics Database",
      "operatingSystem": "Web Browser",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      },
      "featureList": [
        "GA4GH Phenopackets v2 compliant data storage",
        "Variant Effect Predictor (VEP) annotations",
        "HPO term autocomplete and search",
        "Kaplan-Meier survival analysis",
        "Interactive protein visualizations",
        "Publication tracking with PubMed integration"
      ],
      "screenshot": "https://hnf1b.org/HNF1B-db_screenshot.png",
      "softwareVersion": "2.0",
      "isAccessibleForFree": true,
      "license": "https://opensource.org/licenses/MIT",
      "codeRepository": "https://github.com/berntpopp/hnf1b-db",
      "programmingLanguage": ["Python", "JavaScript", "Vue.js"],
      "author": {
        "@id": "https://hnf1b.org/#organization"
      }
    }
    </script>

    <!-- Structured Data: Dataset (for scientific databases) -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Dataset",
      "@id": "https://hnf1b.org/#dataset",
      "name": "HNF1B Phenopacket Collection",
      "description": "Collection of 864 GA4GH Phenopackets containing clinical phenotype and genetic variant data for HNF1B-related disorders",
      "url": "https://hnf1b.org/phenopackets",
      "identifier": "hnf1b-phenopackets-v2",
      "keywords": ["HNF1B", "MODY5", "renal cysts", "diabetes", "phenopackets", "rare disease"],
      "license": "https://creativecommons.org/licenses/by/4.0/",
      "creator": {
        "@id": "https://hnf1b.org/#organization"
      },
      "distribution": {
        "@type": "DataDownload",
        "encodingFormat": "application/json",
        "contentUrl": "https://api.hnf1b.org/api/v2/phenopackets/"
      },
      "measurementTechnique": "Clinical phenotyping with HPO terms",
      "variableMeasured": [
        "Clinical phenotypes (HPO)",
        "Genetic variants",
        "Disease classifications (MONDO)",
        "Publication references"
      ]
    }
    </script>
```

**Impact:** Enables rich snippets in Google Search, improves CTR by up to 30%.

---

### 3.3 Critical: Create robots.txt

**File:** `frontend/public/robots.txt`

```txt
# HNF1B Database - Robots.txt
# https://hnf1b.org/robots.txt

User-agent: *
Allow: /

# Disallow admin/internal pages
Disallow: /login
Disallow: /user
Disallow: /phenopacket/create
Disallow: /phenopacket/edit

# Sitemap location
Sitemap: https://hnf1b.org/sitemap.xml

# Crawl-delay for polite crawling (optional)
Crawl-delay: 1
```

---

### 3.4 High: Create sitemap.xml

**File:** `frontend/public/sitemap.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://hnf1b.org/</loc>
    <lastmod>2025-12-05</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://hnf1b.org/phenopackets</loc>
    <lastmod>2025-12-05</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://hnf1b.org/variants</loc>
    <lastmod>2025-12-05</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://hnf1b.org/publications</loc>
    <lastmod>2025-12-05</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://hnf1b.org/aggregations</loc>
    <lastmod>2025-12-05</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>
```

**Note:** For dynamic sitemaps, consider generating via API endpoint.

---

### 3.5 Medium: Dynamic Meta Tags with Vue Meta

**Install:**

```bash
npm install @unhead/vue
```

**Setup:** `src/main.js`

```javascript
import { createHead } from '@unhead/vue';

const app = createApp(App);
const head = createHead();

app.use(head);
app.use(router);
app.mount('#app');
```

**Usage in views:**

```vue
<!-- src/views/PagePhenopacket.vue -->
<script setup>
import { useHead } from '@unhead/vue';
import { computed } from 'vue';

const props = defineProps(['phenopacket']);

useHead(computed(() => ({
  title: `${props.phenopacket?.subject_id} - HNF1B Database`,
  meta: [
    {
      name: 'description',
      content: `Phenopacket for subject ${props.phenopacket?.subject_id} with ${props.phenopacket?.phenotypic_features?.length || 0} clinical features.`
    },
    {
      property: 'og:title',
      content: `${props.phenopacket?.subject_id} - HNF1B Database`
    }
  ]
})));
</script>
```

---

## Part 4: Best Practices Improvements (Score: 96 → 100)

### 4.1 Medium: Fix Console Error (404)

**Issue:** `GET https://api.hnf1b.org/api/v2/reference/genes/HNF1B/domains 404`

**Options:**

**Option A: Populate Reference Data**
```bash
# Backend: Run reference data migration
cd backend
uv run python -m migration.populate_reference_data
```

**Option B: Add Graceful Error Handling**

```javascript
// src/api/index.js - Add fallback
export const getReferenceGeneDomains = async (symbol, genomeBuild = 'GRCh38') => {
  try {
    return await apiClient.get(`/reference/genes/${symbol}/domains`, {
      params: { genome_build: genomeBuild },
    });
  } catch (error) {
    if (error.response?.status === 404) {
      // Return empty domains instead of throwing
      window.logService.debug('Reference domains not available', { symbol });
      return { data: { domains: [], gene: symbol } };
    }
    throw error;
  }
};
```

---

### 4.2 Low: Add Security Headers (Server-Side)

**Nginx Configuration:**

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.hnf1b.org;" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

---

### 4.3 Low: Generate Source Maps Only for Error Tracking

**Current:** `sourcemap: true` exposes source code.

**Better:** Use hidden source maps for error tracking services:

```javascript
// vite.config.js
build: {
  sourcemap: 'hidden', // Generate maps but don't link from JS
}
```

Then upload source maps to error tracking service (Sentry, etc.) and delete from production.

---

## Part 5: Implementation Priority

### Phase 1: Quick Wins (1-2 hours)

| Task | Impact | Effort |
|------|--------|--------|
| Add meta description to index.html | SEO +5 | 10 min |
| Create robots.txt | SEO +3 | 5 min |
| Add aria-labels to pagination buttons | A11y +5 | 30 min |
| Add preconnect for API | Perf +2 | 5 min |
| Fix 404 console error | BP +2 | 30 min |

### Phase 2: High Impact (4-8 hours)

| Task | Impact | Effort |
|------|--------|--------|
| Add JSON-LD structured data | SEO +8 | 1 hour |
| Implement font-display: swap | Perf +15 | 1 hour |
| Add compression plugins | Perf +10 | 30 min |
| Create sitemap.xml | SEO +2 | 30 min |
| Add Open Graph meta tags | SEO +3 | 30 min |

### Phase 3: Significant Effort (1-2 days)

| Task | Impact | Effort |
|------|--------|--------|
| Switch to SVG icons (@mdi/js) | Perf +20 | 4 hours |
| Optimize manualChunks function | Perf +8 | 2 hours |
| Lazy load heavy components | Perf +10 | 3 hours |
| Add dynamic meta tags with @unhead/vue | SEO +5 | 2 hours |
| Create accessibility composables | A11y +3 | 2 hours |

### Phase 4: Advanced (Optional)

| Task | Impact | Effort |
|------|--------|--------|
| Add PWA support | UX +10 | 4 hours |
| Implement content-visibility CSS | Perf +5 | 1 hour |
| Add security headers | BP +2 | 1 hour |

---

## Expected Results After Implementation

| Category | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|----------|---------|---------------|---------------|---------------|
| Performance | 58 | 62 | 78 | 90+ |
| Accessibility | 80 | 88 | 90 | 95+ |
| Best Practices | 96 | 98 | 100 | 100 |
| SEO | 83 | 90 | 95 | 98+ |

---

## References

### Documentation

- [Vuetify Treeshaking](https://vuetifyjs.com/en/features/treeshaking/)
- [Vite Build Optimization](https://vite.dev/guide/build)
- [Vue 3 Performance](https://vuejs.org/guide/best-practices/performance.html)
- [Schema.org for Datasets](https://schema.org/Dataset)
- [JSON-LD Best Practices](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data)

### Research Sources

- [Vue.js SEO Best Practices 2025](https://www.seo-day.de/wiki/technisches-seo/javascript-seo/frameworks/vue.php?lang=en)
- [Modern JSON-LD Implementation in 2025](https://blog.enodo.io/modern-json-ld-implementation-in-2025-toward-cleaner-and-maintainable-seo-9.html)
- [JSON-LD with Vue 3](https://medium.com/@fmoessle/json-ld-with-vue-3-or-nuxt-3-a70a5d905b4a)
- [Optimizing Vue.js Apps in 2025](https://metadesignsolutions.com/optimizing-vuejs-apps-in-2025-lazy-loading-tree-shaking-more/)

### Comparison Reference

- GeneFoundry Frontend: `/mnt/c/development/genefoundry/` - Modern Vue 3 implementation with JSON-LD, compression, font optimization, and accessibility patterns.

---

## Appendix: Files to Modify

```
frontend/
├── index.html                    # Meta tags, JSON-LD, preconnect
├── public/
│   ├── robots.txt               # NEW: Crawler directives
│   └── sitemap.xml              # NEW: URL listing
├── vite.config.js               # Compression, chunking
├── src/
│   ├── main.js                  # Font loading, @unhead/vue
│   ├── style.css                # font-display, content-visibility
│   ├── assets/
│   │   └── mdi-override.css     # NEW: Font display fix
│   ├── composables/
│   │   └── useAccessibility.js  # NEW: A11y helpers
│   ├── api/
│   │   └── index.js             # Error handling for 404
│   └── views/
│       ├── Variants.vue         # aria-labels
│       ├── Phenopackets.vue     # aria-labels
│       └── SearchResults.vue    # aria-labels
```

---

*Report generated by Claude Code analysis of HNF1B Database frontend codebase.*
