# HNF1B Database SEO Audit Response

**Date:** 2025-12-13
**Based on:** SEO audit report analysis

---

## Executive Summary

The audit reveals **one fundamental problem** causing most issues: **SPA (Single Page Application) rendering**. The site's Vue.js architecture means search engines see minimal HTML content (838% rendering difference), leading to:
- Low text content (176 words visible)
- 1% text-to-code ratio (vs. 10%+ recommended)
- Thin content perception
- Soft 404 errors (200 status on error pages)

### Priority Matrix

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| 🔴 Critical | SPA rendering / thin content | Very High | High |
| 🔴 Critical | 404 returns 200 status | High | Low |
| 🟠 High | Title tag too short | Medium | Low |
| 🟠 High | Missing H2-H6 headers | Medium | Low |
| 🟡 Medium | Meta description length | Low | Low |
| 🟡 Medium | Mobile PageSpeed (44) | Medium | Medium |
| 🟢 Low | Analytics missing | Low | Low |
| 🟢 Low | Social profiles | Very Low | Low |

---

## Critical Issues & Solutions

### 1. SPA Rendering Problem (Root Cause)

**Problem:** Crawlers see 176 words instead of actual content. Text-to-code ratio is 1%.

**Why it happens:** Vue.js renders content client-side via JavaScript. Search engines see only the initial HTML shell.

**Solutions (in order of recommendation):**

#### Option A: Prerendering (Recommended for this project)

Generate static HTML for key routes at build time.

```bash
npm install vite-plugin-prerender
```

```javascript
// vite.config.js
import { prerender } from 'vite-plugin-prerender';

export default defineConfig({
  plugins: [
    prerender({
      routes: [
        '/',
        '/phenopackets',
        '/variants',
        '/publications',
        '/aggregations',
        '/about',
        '/faq'
      ]
    })
  ]
});
```

**Pros:** Simple, no infrastructure changes, works with static hosting
**Cons:** Doesn't work for dynamic routes (individual variant pages)

#### Option B: Dynamic Rendering with Prerender.io

Use a service that detects crawlers and serves pre-rendered HTML.

```nginx
# nginx.conf - Detect crawlers and proxy to prerender service
location / {
    set $prerender 0;
    if ($http_user_agent ~* "googlebot|bingbot|yandex|baiduspider") {
        set $prerender 1;
    }
    if ($prerender = 1) {
        rewrite .* /render/$scheme://$host$request_uri break;
        proxy_pass https://service.prerender.io;
    }
    try_files $uri $uri/ /index.html;
}
```

**Pros:** Works for all routes including dynamic ones
**Cons:** Requires subscription ($15-99/month), adds latency for bots

#### Option C: Nuxt.js Migration (Most Comprehensive)

Migrate to Nuxt 3 for full SSR/SSG support.

```bash
# New project structure
npx nuxi init hnf1b-nuxt
# Migrate components and pages
```

**Pros:** Best SEO, fastest performance, hybrid rendering
**Cons:** Significant refactoring effort (weeks)

**Recommendation:** Start with **Option A** (prerendering) for static pages, add **Option B** (Prerender.io) for dynamic routes.

---

### 2. 404 Page Returns 200 Status Code

**Problem:** `/not-found-page` returns HTTP 200 instead of 404, wasting crawl budget.

**Solution:** Configure nginx to return true 404 for the catch-all route.

```javascript
// router/index.js - Add catch-all route
{
  path: '/:pathMatch(.*)*',
  name: 'NotFound',
  component: () => import('@/views/NotFound.vue'),
  meta: {
    title: 'Page Not Found',
    is404: true
  }
}
```

```nginx
# nginx.conf - Return real 404 for specific path
location = /404 {
    internal;
    return 404;
}

location / {
    try_files $uri $uri/ /index.html;

    # If requesting /404-trigger, return real 404
    if ($request_uri ~* "^/404-trigger") {
        return 404;
    }
}
```

```javascript
// NotFound.vue - Trigger server 404 for crawlers
onMounted(() => {
  // For crawlers, redirect to trigger real 404
  const isBot = /googlebot|bingbot/i.test(navigator.userAgent);
  if (isBot) {
    window.location.href = '/404-trigger';
  }
});
```

---

### 3. Title Tag Too Short (21 chars)

**Current:** `Home | HNF1B Database` (21 chars)
**Recommended:** 35-65 characters

**Fix in `index.html`:**

```html
<!-- Before -->
<title>Home | HNF1B Database</title>

<!-- After -->
<title>HNF1B Database - Clinical Variants & Phenotypes for MODY5/RCAD</title>
```

Length: 62 characters ✓

**Alternative titles:**
- `HNF1B Gene Database - 800+ Phenopackets, Variants & Publications` (64 chars)
- `HNF1B Variant Database - MODY5 & RCAD Clinical Data Registry` (60 chars)

---

### 4. Missing H2-H6 Header Tags

**Problem:** Only H1 detected, no hierarchical structure.

**Solution:** Add visible header structure to Home.vue:

```vue
<template>
  <div>
    <h1>HNF1B Database</h1>

    <section>
      <h2>Explore Clinical Data</h2>
      <!-- Stats cards -->
    </section>

    <section>
      <h2>Gene & Protein Visualization</h2>
      <!-- Visualization tabs -->

      <h3>Gene Structure</h3>
      <h3>Protein Domains</h3>
      <h3>3D Structure</h3>
    </section>

    <section>
      <h2>Latest Publications</h2>
      <!-- Publication list -->
    </section>
  </div>
</template>
```

**Target structure:**
```
H1: HNF1B Database (1)
  H2: Explore Clinical Data
  H2: Gene & Protein Visualization
    H3: Gene Structure
    H3: Protein Domains
    H3: 3D Structure
  H2: Latest Publications
```

---

### 5. Meta Description Too Long (185 chars)

**Current:** 185 characters
**Recommended:** 120-160 characters

**Fix in `index.html`:**

```html
<!-- Before (185 chars) -->
<meta name="description" content="Comprehensive database of HNF1B gene variants and associated phenotypes. Search 800+ phenopackets with clinical features, genetic variants, and publications for HNF1B-related disorders.">

<!-- After (156 chars) -->
<meta name="description" content="Search 800+ HNF1B clinical cases with phenotypes, genetic variants, and publications. The definitive resource for MODY5 and RCAD research.">
```

---

### 6. Mobile PageSpeed (44/100)

**Issues identified:**
- First Contentful Paint: 6.44s (should be <1.8s)
- Largest Contentful Paint: 7.49s (should be <2.5s)
- Speed Index: 6.44s

**Quick wins:**

```javascript
// vite.config.js - Code splitting improvements
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'vuetify': ['vuetify'],
          'd3': ['d3'],
          'ngl': ['ngl'] // 3D viewer is heavy
        }
      }
    }
  }
});
```

```html
<!-- index.html - Preload critical resources -->
<link rel="preload" href="/fonts/inter.woff2" as="font" crossorigin>
<link rel="preconnect" href="https://api.hnf1b.org">

<!-- Defer non-critical CSS -->
<link rel="preload" href="/assets/vuetify.css" as="style" onload="this.rel='stylesheet'">
```

```vue
<!-- Lazy load heavy components -->
<script setup>
const ProteinStructure3D = defineAsyncComponent(() =>
  import('@/components/gene/ProteinStructure3D.vue')
);
</script>
```

---

## Medium Priority Improvements

### 7. Add Analytics

```html
<!-- index.html - Plausible (privacy-friendly) -->
<script defer data-domain="hnf1b.org" src="https://plausible.io/js/script.js"></script>
```

Or Google Analytics 4:
```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

### 8. Open Graph Tags Not Detected

The audit says OG tags weren't found, but we have them. This is likely because they're in the initial HTML but the crawler checked the rendered content.

**Verify they're in index.html (not dynamically injected):**
```html
<meta property="og:title" content="HNF1B Database - Clinical Variants & Phenotypes">
<meta property="og:description" content="Search 800+ HNF1B clinical cases...">
<meta property="og:image" content="https://hnf1b.org/og-image.png">
<meta property="og:url" content="https://hnf1b.org/">
<meta property="og:type" content="website">
```

### 9. Increase Page Text Content

Add visible descriptive text to the homepage:

```vue
<!-- Home.vue - Add intro section -->
<section class="intro-section py-6">
  <v-container>
    <h2 class="text-h5 mb-4">About the HNF1B Database</h2>
    <p class="text-body-1">
      The HNF1B Database is the most comprehensive resource for clinical and genetic
      data related to HNF1B-associated disorders, including MODY5 (Maturity-Onset
      Diabetes of the Young type 5) and RCAD (Renal Cysts and Diabetes syndrome).
    </p>
    <p class="text-body-1">
      Our database contains over 800 phenopackets with detailed clinical phenotypes,
      198 curated genetic variants with pathogenicity classifications, and references
      to 141 peer-reviewed publications. All data follows the GA4GH Phenopackets v2
      standard for interoperability.
    </p>
  </v-container>
</section>
```

---

## Low Priority / Future Improvements

### 10. Social Profiles
- Create profiles on: Twitter/X, LinkedIn, GitHub (already have)
- Add social links to footer with proper Schema.org markup

### 11. Local Business Schema
Not applicable - this is a research database, not a local business.

### 12. Link Building Strategy
- Submit to genetic database directories (OMIM, GeneCards resources)
- Publish a methods paper citing the database
- Reach out to MODY5/RCAD patient advocacy groups

---

## Implementation Roadmap

### Phase 1: Quick Wins (This Week)
- [ ] Update title tag (62 chars)
- [ ] Shorten meta description (156 chars)
- [ ] Add H2/H3 headers to Home.vue
- [ ] Add introductory text content
- [ ] Configure true 404 status

### Phase 2: Performance (Next Week)
- [ ] Implement code splitting
- [ ] Add resource preloading
- [ ] Lazy load 3D viewer component
- [ ] Add analytics (Plausible or GA4)

### Phase 3: Prerendering (Week 3)
- [ ] Install vite-plugin-prerender
- [ ] Configure prerendering for static routes
- [ ] Test with Google Search Console URL Inspection
- [ ] Consider Prerender.io for dynamic routes

### Phase 4: Monitoring (Ongoing)
- [ ] Set up Google Search Console
- [ ] Monitor Core Web Vitals
- [ ] Track indexed pages growth
- [ ] Monitor keyword rankings

---

## Expected Impact

| Metric | Current | Target (3 months) |
|--------|---------|-------------------|
| Text-to-code ratio | 1% | >10% |
| Mobile PageSpeed | 44 | >70 |
| Indexed pages | ~10 | 500+ |
| Title length | 21 | 62 |
| H2-H6 tags | 0 | 5+ |

---

## References

- [Vue.js SEO-Friendly SPAs: Tips & Prerender Example](https://snipcart.com/blog/vue-js-seo-prerender-example)
- [How To Properly Serve 404 Errors on SPAs](https://thegray.company/blog/single-page-application-spas-404s-seo)
- [Vue.js SEO in 2025: Why You Still Need SSR](https://dev.to/hmzas/vuejs-seo-in-2025-why-you-still-need-server-side-rendering-ssr-12b9)
- [SPA SEO: Optimize Your Single-Page App for Google](https://snipcart.com/blog/spa-seo)
- [Technical SEO Guide to Server-Side Rendering](https://gracker.ai/seo-101/server-side-rendering-spa-seo)
- [How to Fix 404 Errors on SPAs](https://prerender.io/blog/fix-404-errors-on-spas/)
