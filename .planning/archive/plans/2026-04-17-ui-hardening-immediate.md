# UI Hardening Immediate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all Critical + High findings from the 2026-04-17 UI/UX review, plus M10/M12/L6, in one Playwright-verified PR off `main`.

**Architecture:** All changes are frontend-only (Vue 3 / Vuetify 4 / Pinia). Each finding maps to a single commit. Shared components land first (`ExternalLink`, `AppDataTable` heading prop) so per-view changes pull from them. The one finding with unverified root cause (C1 `/aggregations`) begins with a reproduction step before any code change.

**Tech Stack:** Vue 3.5, Vuetify 4.0, Tiptap v3, Pinia, Vite 7, Vitest 4, Playwright 1.57, axios.

---

## Spec

- `.planning/specs/2026-04-17-ui-hardening-immediate-design.md` (committed at `efd98b0`)
- Source review: `.planning/reviews/2026-04-17-ui-ux-design-review.md`

## Branch State

- Branch: `ui-hardening-immediate` (created off fresh `main` at `1bde64b`).
- First commit already landed: `efd98b0 docs(planning): add UI hardening spec and refresh reviews` — contains spec + refreshed reviews + new UI/UX review.
- All subsequent commits in this plan are additive on top of `efd98b0`.

## House Conventions

- Frontend tests: `cd frontend && npm run test` (Vitest) or `make test` under `frontend/`.
- Frontend lint: `cd frontend && npm run lint:check` (verify) or `npm run lint` (fix + write).
- Frontend format: `cd frontend && npm run format:check` (verify) or `npm run format` (fix).
- Frontend e2e: `cd frontend && npx playwright test` (Playwright config at `frontend/playwright.config.js`; base URL `http://localhost:5173`).
- Backend smoke: `make test` from repo root.
- Dev servers: `make backend` + `make frontend` in two terminals; frontend listens on `:5173`, backend on `:8000`.
- Unit test tree: `frontend/tests/unit/{components,stores,views,composables,api,...}/`.
- E2E tree: `frontend/tests/e2e/*.spec.js`; shared helpers in `frontend/tests/e2e/helpers/`.
- Commit style: conventional commits; every commit must keep CI green.
- Never log via `console.log`; use `window.logService.{debug,info,warn,error}`.

## Pre-Flight

### Task 0: Verify branch state

**Files:**
- Modify: none

- [ ] **Step 1 — confirm branch + tree clean**

```bash
cd ~/development/hnf1b-db
git branch --show-current
git status --short
git log --oneline -3
```

Expected:

- current branch: `ui-hardening-immediate`
- no uncommitted changes
- `efd98b0 docs(planning): add UI hardening spec and refresh reviews` is HEAD

- [ ] **Step 2 — confirm frontend deps installed**

```bash
cd ~/development/hnf1b-db/frontend
npm ci
npx playwright install --with-deps chromium
```

Expected: deps install cleanly; Playwright browser present.

---

## Task 1 — ExternalLink Component + Unit Test (H1, shared)

**Commit message:** `feat(frontend): add ExternalLink wrapper enforcing rel=noopener noreferrer (H1)`

**Files:**
- Create: `frontend/src/components/common/ExternalLink.vue`
- Create: `frontend/tests/unit/components/common/ExternalLink.spec.js`

- [ ] **Step 1 — write the failing unit test**

Create `frontend/tests/unit/components/common/ExternalLink.spec.js`:

```js
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ExternalLink from '@/components/common/ExternalLink.vue';

describe('ExternalLink', () => {
  it('renders an anchor with target=_blank and rel=noopener noreferrer', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Link text' },
    });
    const a = wrapper.get('a');
    expect(a.attributes('href')).toBe('https://example.com/a');
    expect(a.attributes('target')).toBe('_blank');
    expect(a.attributes('rel')).toBe('noopener noreferrer');
    expect(a.text()).toContain('Link text');
  });

  it('includes an mdi-open-in-new icon by default', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Link text' },
    });
    expect(wrapper.find('.mdi-open-in-new').exists()).toBe(true);
  });

  it('suppresses the icon when showIcon=false', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a', showIcon: false },
      slots: { default: 'Link text' },
    });
    expect(wrapper.find('.mdi-open-in-new').exists()).toBe(false);
  });

  it('applies aria-label when provided', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a', ariaLabel: 'Open example docs' },
      slots: { default: 'Docs' },
    });
    expect(wrapper.get('a').attributes('aria-label')).toBe('Open example docs');
  });

  it('exposes a visually-hidden "opens in new tab" suffix for screen readers', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Docs' },
    });
    const sr = wrapper.find('.sr-only');
    expect(sr.exists()).toBe(true);
    expect(sr.text()).toMatch(/opens in new tab/i);
  });
});
```

- [ ] **Step 2 — run test to confirm failure**

```bash
cd frontend
npx vitest run tests/unit/components/common/ExternalLink.spec.js
```

Expected: FAIL — `Failed to resolve component: ExternalLink` (file does not exist).

- [ ] **Step 3 — implement ExternalLink.vue**

Create `frontend/src/components/common/ExternalLink.vue`:

```vue
<template>
  <a
    :href="href"
    target="_blank"
    rel="noopener noreferrer"
    :aria-label="ariaLabel || undefined"
    class="external-link"
  >
    <slot />
    <v-icon
      v-if="showIcon"
      class="external-link__icon mdi-open-in-new"
      size="x-small"
      aria-hidden="true"
    >
      mdi-open-in-new
    </v-icon>
    <span class="sr-only">(opens in new tab)</span>
  </a>
</template>

<script setup>
defineProps({
  href: { type: String, required: true },
  ariaLabel: { type: String, default: '' },
  showIcon: { type: Boolean, default: true },
});
</script>

<style scoped>
.external-link {
  color: inherit;
  text-decoration: none;
}
.external-link:hover {
  text-decoration: underline;
}
.external-link__icon {
  margin-left: 4px;
  vertical-align: -2px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
```

- [ ] **Step 4 — run test to confirm pass**

```bash
cd frontend
npx vitest run tests/unit/components/common/ExternalLink.spec.js
```

Expected: PASS (5 tests).

- [ ] **Step 5 — run lint**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors. If lint auto-fixable, run `npm run lint` then re-check.

- [ ] **Step 6 — commit**

```bash
git add frontend/src/components/common/ExternalLink.vue \
        frontend/tests/unit/components/common/ExternalLink.spec.js
git commit -m "$(cat <<'EOF'
feat(frontend): add ExternalLink wrapper enforcing rel=noopener noreferrer (H1)

Provides a shared anchor component that guarantees target=_blank links
carry rel="noopener noreferrer" and a visually-hidden "opens in new tab"
hint for screen readers. Replaces ad-hoc anchors across Publications,
PagePublication, PageVariant, About, and FAQ in subsequent commits.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md H1
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Apply ExternalLink + add rel on v-btn hrefs (H1 sweep)

**Commit message:** `fix(frontend): add rel=noopener noreferrer to all external anchors (H1)`

**Files:**
- Modify: `frontend/src/views/Publications.vue` (lines 95-107, 112-124 — v-btn hrefs)
- Modify: `frontend/src/views/PagePublication.vue` (lines 54, 116)
- Modify: `frontend/src/views/PageVariant.vue` (lines 213, 238, 263, 291, 304, 317, 330, 343, 358, 371)
- Modify: `frontend/src/views/About.vue` (lines 166, 191)
- Modify: `frontend/src/views/FAQ.vue` (lines 196, 260)
- Create: `frontend/tests/e2e/ui-hardening-a11y.spec.js` (partial — rel sweep only; other assertions added later)

- [ ] **Step 1 — write the failing Playwright spec (rel sweep only)**

Create `frontend/tests/e2e/ui-hardening-a11y.spec.js`:

```js
import { test, expect } from '@playwright/test';

/**
 * Every anchor with target="_blank" must carry rel containing both
 * "noopener" and "noreferrer". Covers H1 from the 2026-04-17 review.
 */
const PAGES_WITH_EXTERNAL_LINKS = [
  '/publications',
  '/about',
  '/faq',
];

async function assertExternalLinkRels(page) {
  const anchors = await page.locator('a[target="_blank"]').all();
  expect(anchors.length, 'expected at least one external anchor').toBeGreaterThan(0);
  for (const a of anchors) {
    const rel = (await a.getAttribute('rel')) || '';
    const href = await a.getAttribute('href');
    expect(rel, `anchor ${href} must include noopener`).toContain('noopener');
    expect(rel, `anchor ${href} must include noreferrer`).toContain('noreferrer');
  }
}

for (const path of PAGES_WITH_EXTERNAL_LINKS) {
  test(`external anchors on ${path} carry rel=noopener noreferrer`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    await assertExternalLinkRels(page);
  });
}

test('external anchors on a publication detail page carry rel', async ({ page }) => {
  await page.goto('/publications');
  await page.waitForLoadState('networkidle');
  const firstPmidChip = page.locator('a.v-chip[href*="/publications/"]').first();
  await firstPmidChip.waitFor({ state: 'visible' });
  await firstPmidChip.click();
  await page.waitForLoadState('networkidle');
  await assertExternalLinkRels(page);
});
```

- [ ] **Step 2 — run spec to confirm failure**

```bash
cd frontend
# Dev servers must be running: `make backend` + `make frontend` in two terminals.
npx playwright test tests/e2e/ui-hardening-a11y.spec.js
```

Expected: FAIL — at least one page reports an anchor with missing/partial `rel`.

- [ ] **Step 3 — fix v-btn external anchors in Publications.vue**

In `frontend/src/views/Publications.vue`, edit the two `v-btn` hrefs. Add `rel="noopener noreferrer"` to each:

```vue
<v-btn
  v-bind="props"
  :href="`https://pubmed.ncbi.nlm.nih.gov/${extractPmidNumber(item.pmid)}`"
  target="_blank"
  rel="noopener noreferrer"
  icon
  size="x-small"
  variant="text"
  color="orange-darken-2"
  aria-label="View on PubMed"
>
```

And:

```vue
<v-btn
  v-bind="props"
  :href="`https://doi.org/${item.doi}`"
  target="_blank"
  rel="noopener noreferrer"
  icon
  size="x-small"
  variant="text"
  color="blue-darken-2"
  aria-label="View DOI"
>
```

- [ ] **Step 4 — fix PagePublication.vue**

In `frontend/src/views/PagePublication.vue` replace each of the two `target="_blank"` anchors at lines ~54 and ~116 with an `<ExternalLink>` wrapper. Import the component at top of `<script setup>`:

```js
import ExternalLink from '@/components/common/ExternalLink.vue';
```

Example replacement for the PMID link (actual markup may differ; preserve existing label/icon contents inside the `<slot />`):

```vue
<ExternalLink
  :href="`https://pubmed.ncbi.nlm.nih.gov/${extractPmidNumber(publication.pmid)}`"
  aria-label="View on PubMed (opens new tab)"
>
  PubMed
</ExternalLink>
```

For the DOI link:

```vue
<ExternalLink
  :href="`https://doi.org/${publication.doi}`"
  aria-label="View DOI (opens new tab)"
>
  {{ publication.doi }}
</ExternalLink>
```

If the existing site uses a `v-btn` with `href`, prefer keeping `v-btn` styling and just adding `rel="noopener noreferrer"` — matching the Publications.vue pattern from Step 3 — rather than swapping to `ExternalLink`. The goal is the attribute; the component is sugar.

- [ ] **Step 5 — fix PageVariant.vue (10 occurrences)**

In `frontend/src/views/PageVariant.vue`, at each of lines 213, 238, 263, 291, 304, 317, 330, 343, 358, 371, add `rel="noopener noreferrer"` to the anchor/`v-btn` tag. If the site is a plain `<a>`, prefer wrapping with `<ExternalLink>`; if it is a `v-btn`, just add the attribute. Import `ExternalLink` at top of `<script setup>` if any replacement uses it:

```js
import ExternalLink from '@/components/common/ExternalLink.vue';
```

- [ ] **Step 6 — fix About.vue (line 166, line 191)**

In `frontend/src/views/About.vue`:

- Line 166: replace the plain `<a target="_blank">` with `<ExternalLink>`.
- Line 191: upgrade existing `rel="noopener"` to `rel="noopener noreferrer"` on the License anchor.

- [ ] **Step 7 — fix FAQ.vue (lines 196, 260)**

In `frontend/src/views/FAQ.vue`, wrap both anchors with `<ExternalLink>` (import at top of `<script setup>`).

- [ ] **Step 8 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 9 — re-run Playwright spec**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js
```

Expected: PASS on all four defined tests.

- [ ] **Step 10 — commit**

```bash
git add frontend/src/views/Publications.vue \
        frontend/src/views/PagePublication.vue \
        frontend/src/views/PageVariant.vue \
        frontend/src/views/About.vue \
        frontend/src/views/FAQ.vue \
        frontend/tests/e2e/ui-hardening-a11y.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): add rel=noopener noreferrer to all external anchors (H1)

Applies rel="noopener noreferrer" to every target=_blank anchor/v-btn
across Publications, PagePublication, PageVariant, About, and FAQ.
Uses the new ExternalLink wrapper for plain anchors; preserves v-btn
styling for table-cell external-link icons by adding the attribute
inline.

Adds tests/e2e/ui-hardening-a11y.spec.js covering the rel sweep on
/publications, /about, /faq, and a publication detail page.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md H1
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Router redirect + dual-state fix (C2)

**Commit message:** `fix(frontend): route /phenopackets/new to /create and dedupe loading state (C2)`

**Files:**
- Modify: `frontend/src/router/index.js` (add redirect before `/phenopackets/:phenopacket_id`)
- Modify: `frontend/src/views/PagePhenopacket.vue` (dedupe loading+error render at ~line 94-98)
- Create: `frontend/tests/e2e/ui-hardening-critical.spec.js`

- [ ] **Step 1 — write the failing Playwright spec**

Create `frontend/tests/e2e/ui-hardening-critical.spec.js`:

```js
import { test, expect } from '@playwright/test';

test.describe('Critical findings', () => {
  test('/phenopackets/new redirects to /phenopackets/create', async ({ page }) => {
    await page.goto('/phenopackets/new');
    await page.waitForURL('**/phenopackets/create', { timeout: 5000 });
    await expect(page).toHaveURL(/\/phenopackets\/create$/);
    await expect(page.locator('h1')).toBeVisible();
  });

  test('nonexistent phenopacket id shows error alert without spinner', async ({ page }) => {
    await page.goto('/phenopackets/definitely-not-a-real-id-zzz');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.v-alert[class*="error"]')).toBeVisible();
    // Loading spinner must NOT be visible when an error is shown.
    await expect(page.locator('.v-progress-circular')).toHaveCount(0);
  });
});
```

- [ ] **Step 2 — run spec to confirm failure**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-critical.spec.js -g "redirects|nonexistent"
```

Expected: FAIL — redirect never resolves; dual-state test sees a spinner alongside the error alert.

- [ ] **Step 3 — add router redirect**

In `frontend/src/router/index.js`, insert the redirect entry **immediately before** the `/phenopackets/:phenopacket_id` route (around line 37). The route ordering matters because vue-router matches top-to-bottom and `/:phenopacket_id` would otherwise catch `/new`:

```js
  {
    path: '/phenopackets/create',
    name: 'CreatePhenopacket',
    component: () =>
      import(
        /* webpackChunkName: "phenopacket-create-edit" */ '../views/PhenopacketCreateEdit.vue'
      ),
    meta: { title: 'Create Phenopacket', requiresAuth: true },
  },
  {
    path: '/phenopackets/:phenopacket_id/edit',
    name: 'EditPhenopacket',
    component: () =>
      import(
        /* webpackChunkName: "phenopacket-create-edit" */ '../views/PhenopacketCreateEdit.vue'
      ),
    meta: { title: 'Edit Phenopacket', requiresAuth: true },
  },
  // /new is a common curator guess — alias to the real create route.
  { path: '/phenopackets/new', redirect: '/phenopackets/create' },
  {
    path: '/phenopackets/:phenopacket_id',
    name: 'PagePhenopacket',
    component: () =>
      import(/* webpackChunkName: "page-phenopacket" */ '../views/PagePhenopacket.vue'),
    meta: { title: 'Phenopacket Details' },
  },
```

- [ ] **Step 4 — fix dual-state render in PagePhenopacket.vue**

Open `frontend/src/views/PagePhenopacket.vue`. Locate the error and loading template blocks (error alert near line 94-98, loading spinner nearby). Guard the loading state with `v-if="loading && !error"` so the two become mutually exclusive. The error block stays as `v-if="error"`. Example:

```vue
<!-- Error State -->
<v-alert v-if="error" type="error" variant="tonal" prominent class="mb-6">
  <v-alert-title>Error Loading Phenopacket</v-alert-title>
  {{ error }}
</v-alert>

<!-- Loading State — hidden when an error is present -->
<div v-else-if="loading" class="text-center py-10">
  <v-progress-circular indeterminate color="primary" />
  <p class="mt-2">Loading phenopacket…</p>
</div>
```

If the existing template uses `v-if="loading"` (without `v-else`), change the spinner block to `v-else-if="loading"` so the error always wins. Do not remove the loading block — it remains the primary UX for the normal path.

- [ ] **Step 5 — run Playwright spec to confirm pass**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-critical.spec.js -g "redirects|nonexistent"
```

Expected: PASS on both tests.

- [ ] **Step 6 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 7 — commit**

```bash
git add frontend/src/router/index.js \
        frontend/src/views/PagePhenopacket.vue \
        frontend/tests/e2e/ui-hardening-critical.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): route /phenopackets/new to /create and dedupe loading state (C2)

Adds a permanent redirect from /phenopackets/new to /phenopackets/create
so the common curator guess lands on the real create page. The dynamic
:phenopacket_id route previously swallowed "new" as an ID and rendered
both a loading spinner and an "Error Loading Phenopacket: Phenopacket
'new' not found" alert simultaneously; guard the loading state with
v-else-if so an error always wins.

Adds tests/e2e/ui-hardening-critical.spec.js covering the redirect and
the dual-state dedup.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md C2
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — AppDataTable titleTag prop + h1 on list/create pages (H2)

**Commit message:** `fix(frontend): render list and create page titles as real h1 (H2)`

**Files:**
- Modify: `frontend/src/components/common/AppDataTable.vue` (title title-bar markup)
- Modify: `frontend/src/views/Phenopackets.vue` (AppDataTable usage — no change needed if default is `h1`)
- Modify: `frontend/src/views/Publications.vue` (same)
- Modify: `frontend/src/views/Variants.vue` (same)
- Modify: `frontend/src/views/PhenopacketCreateEdit.vue` (swap v-card-title for h1)
- Create: `frontend/tests/unit/components/common/AppDataTable.spec.js`
- Modify: `frontend/tests/e2e/ui-hardening-a11y.spec.js` (add h1 presence tests)

- [ ] **Step 1 — write failing unit test for AppDataTable titleTag**

Create `frontend/tests/unit/components/common/AppDataTable.spec.js`:

```js
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import AppDataTable from '@/components/common/AppDataTable.vue';

describe('AppDataTable', () => {
  it('renders title as an h1 by default', () => {
    const wrapper = mount(AppDataTable, {
      props: { title: 'Registry', headers: [], items: [] },
    });
    const h1 = wrapper.find('h1');
    expect(h1.exists()).toBe(true);
    expect(h1.text()).toBe('Registry');
  });

  it('respects titleTag override', () => {
    const wrapper = mount(AppDataTable, {
      props: { title: 'Sub-Registry', titleTag: 'h2', headers: [], items: [] },
    });
    expect(wrapper.find('h2').exists()).toBe(true);
    expect(wrapper.find('h2').text()).toBe('Sub-Registry');
  });

  it('does not render a title element when title prop is absent', () => {
    const wrapper = mount(AppDataTable, {
      props: { headers: [], items: [] },
    });
    expect(wrapper.find('h1').exists()).toBe(false);
  });
});
```

- [ ] **Step 2 — run unit test to confirm failure**

```bash
cd frontend
npx vitest run tests/unit/components/common/AppDataTable.spec.js
```

Expected: FAIL — no `h1` (current markup is a `<div>`).

- [ ] **Step 3 — update AppDataTable.vue**

In `frontend/src/components/common/AppDataTable.vue` lines 20-31, replace:

```vue
<div v-if="title" class="text-subtitle-1 font-weight-bold text-teal-darken-2">
  {{ title }}
</div>
```

with:

```vue
<component
  :is="titleTag"
  v-if="title"
  class="text-subtitle-1 font-weight-bold text-teal-darken-2 ma-0"
>
  {{ title }}
</component>
```

In the `<script setup>` block, add the prop. Look at the top of `<script setup>`; find or create the `defineProps` call:

```js
defineProps({
  title: { type: String, default: '' },
  titleTag: { type: String, default: 'h1' },
  // ...existing props
});
```

If the component already uses `defineProps({ ... })`, just add `titleTag` alongside. If the existing props are declared differently, preserve the style.

- [ ] **Step 4 — re-run unit test**

```bash
cd frontend
npx vitest run tests/unit/components/common/AppDataTable.spec.js
```

Expected: PASS (3 tests).

- [ ] **Step 5 — verify no regression on list pages (unit)**

The Phenopackets/Publications/Variants views already pass `title="..."` to `AppDataTable` without specifying `titleTag`. The new default is `h1` so no view change is required for these three.

- [ ] **Step 6 — promote PhenopacketCreateEdit page title to h1**

In `frontend/src/views/PhenopacketCreateEdit.vue` line ~5, locate the `<v-card-title class="text-h4">...</v-card-title>`. Replace it with a real `<h1>` that keeps the visual styling:

```vue
<h1 class="v-card-title text-h4">Create New Phenopacket</h1>
```

Preserve existing bindings (e.g., if the title is dynamic like `{{ isEdit ? 'Edit' : 'Create' }} ...`, preserve that inside the `<h1>`). The `v-card-title` class is Vuetify's and applies the same padding/typography.

- [ ] **Step 7 — extend Playwright a11y spec with h1 assertions**

Append to `frontend/tests/e2e/ui-hardening-a11y.spec.js`:

```js
test.describe('Real h1 on list + create views (H2)', () => {
  for (const path of ['/phenopackets', '/publications', '/variants']) {
    test(`${path} exposes an h1`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('h1')).toHaveCount(1);
      const text = await page.locator('h1').innerText();
      expect(text.length).toBeGreaterThan(0);
    });
  }

  test('/phenopackets/create exposes an h1', async ({ page, request }) => {
    // Authenticated route; use API login + cookie priming helper.
    const { apiLogin, primeAuthSession } = await import('./helpers/auth.js');
    const apiBase = process.env.E2E_API_BASE || 'http://localhost:8000/api/v2';
    const auth = await apiLogin(request, apiBase, 'dev-admin', 'DevAdmin!2026');
    await primeAuthSession(page, auth);
    await page.goto('/phenopackets/create');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
  });
});
```

- [ ] **Step 8 — run the extended e2e spec**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "exposes an h1"
```

Expected: PASS on all four tests.

- [ ] **Step 9 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 10 — commit**

```bash
git add frontend/src/components/common/AppDataTable.vue \
        frontend/src/views/PhenopacketCreateEdit.vue \
        frontend/tests/unit/components/common/AppDataTable.spec.js \
        frontend/tests/e2e/ui-hardening-a11y.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): render list and create page titles as real h1 (H2)

AppDataTable.title now renders via <component :is="titleTag"> with a
default of h1, giving Phenopackets / Publications / Variants screens a
real document-level heading instead of a styled div. PhenopacketCreateEdit
swaps its v-card-title for an h1 with the same classes.

Adds tests/unit/components/common/AppDataTable.spec.js for the prop, and
extends tests/e2e/ui-hardening-a11y.spec.js with h1-presence checks on
the three list routes and /phenopackets/create.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md H2
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Keyboard row activation via chip anchors (H3)

**Commit message:** `feat(frontend): keyboard-activate list rows via chip anchors (H3)`

**Files:**
- Modify: `frontend/src/views/Phenopackets.vue` (add `:to` on subject_id chip around line 117-122)
- Modify: `frontend/src/views/Variants.vue` (add `:to` on simple_id chip around line 102)
- Modify: `frontend/tests/e2e/ui-hardening-a11y.spec.js` (add keyboard-flow test)

- [ ] **Step 1 — write failing Playwright test for keyboard flow**

Append to `frontend/tests/e2e/ui-hardening-a11y.spec.js`:

```js
test.describe('Keyboard row activation (H3)', () => {
  test('Tab reaches first subject-id chip on /phenopackets and Enter navigates', async ({ page }) => {
    await page.goto('/phenopackets');
    await page.waitForLoadState('networkidle');
    const firstChipAnchor = page.locator('table a.v-chip').first();
    await firstChipAnchor.waitFor({ state: 'visible' });
    await firstChipAnchor.focus();
    const href = await firstChipAnchor.getAttribute('href');
    expect(href).toMatch(/^\/phenopackets\/[^/]+$/);
    await firstChipAnchor.press('Enter');
    await page.waitForURL(/\/phenopackets\/[^/]+$/, { timeout: 5000 });
  });

  test('/variants first chip is a keyboard-reachable anchor', async ({ page }) => {
    await page.goto('/variants');
    await page.waitForLoadState('networkidle');
    const firstChipAnchor = page.locator('table a.v-chip').first();
    await firstChipAnchor.waitFor({ state: 'visible' });
    const href = await firstChipAnchor.getAttribute('href');
    expect(href).toMatch(/^\/variants\//);
  });

  test('/publications PMID chip is a keyboard-reachable anchor', async ({ page }) => {
    await page.goto('/publications');
    await page.waitForLoadState('networkidle');
    const firstChipAnchor = page.locator('table a.v-chip[href*="/publications/"]').first();
    await firstChipAnchor.waitFor({ state: 'visible' });
    const href = await firstChipAnchor.getAttribute('href');
    expect(href).toMatch(/^\/publications\//);
  });
});
```

- [ ] **Step 2 — run tests to confirm two failures**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "Keyboard row activation"
```

Expected: FAIL on Phenopackets + Variants chip tests (no anchors yet). Publications test should PASS — it already has `:to`.

- [ ] **Step 3 — add :to to subject-id chip in Phenopackets.vue**

In `frontend/src/views/Phenopackets.vue` around line 117-122, change:

```vue
<template #item.subject_id="{ item }">
  <v-chip color="teal-lighten-3" size="x-small" variant="flat">
    <v-icon start size="x-small">mdi-card-account-details</v-icon>
    {{ item.subject_id || 'N/A' }}
  </v-chip>
</template>
```

to:

```vue
<template #item.subject_id="{ item }">
  <v-chip
    :to="{ name: 'PagePhenopacket', params: { phenopacket_id: item.phenopacket_id } }"
    color="teal-lighten-3"
    size="x-small"
    variant="flat"
  >
    <v-icon start size="x-small">mdi-card-account-details</v-icon>
    {{ item.subject_id || 'N/A' }}
  </v-chip>
</template>
```

Note: `handleRowClick` at line ~530 stays in place as mouse progressive-enhancement. Chip click events do not bubble to the row click handler in Vuetify `v-data-table`, so there is no double-navigation.

- [ ] **Step 4 — add :to to simple_id chip in Variants.vue**

In `frontend/src/views/Variants.vue` around line 102, change:

```vue
<template #item.simple_id="{ item }">
  <v-chip color="pink-lighten-3" size="x-small" variant="flat">
    {{ item.simple_id }}
    <v-icon end size="x-small">mdi-dna</v-icon>
  </v-chip>
</template>
```

to:

```vue
<template #item.simple_id="{ item }">
  <v-chip
    :to="`/variants/${encodeURIComponent(item.variant_id)}`"
    color="pink-lighten-3"
    size="x-small"
    variant="flat"
  >
    {{ item.simple_id }}
    <v-icon end size="x-small">mdi-dna</v-icon>
  </v-chip>
</template>
```

The target URL matches `handleRowClick` at line 533 (`this.$router.push('/variants/' + encodeURIComponent(row.item.variant_id))`) so keyboard + mouse flows converge.

- [ ] **Step 5 — re-run the Playwright keyboard spec**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "Keyboard row activation"
```

Expected: PASS on all three tests.

- [ ] **Step 6 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 7 — commit**

```bash
git add frontend/src/views/Phenopackets.vue \
        frontend/src/views/Variants.vue \
        frontend/tests/e2e/ui-hardening-a11y.spec.js
git commit -m "$(cat <<'EOF'
feat(frontend): keyboard-activate list rows via chip anchors (H3)

Adds :to bindings to the primary identity chip on /phenopackets
(subject_id → PagePhenopacket) and /variants (simple_id → variant
detail). Vuetify renders v-chip with :to as a router-link <a>, giving
native keyboard focusability and Enter activation. Publications PMID
chip already had :to, so no change there. The row @click:row handler
remains as mouse progressive enhancement.

Adds three keyboard-activation tests to tests/e2e/ui-hardening-a11y.spec.js.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md H3
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Tiptap composer a11y + formatting toolbar (H5)

**Commit message:** `fix(frontend): add accessible name and formatting toolbar to Tiptap composer (H5)`

**Files:**
- Modify: `frontend/src/components/comments/CommentComposer.vue`
- Modify: `frontend/tests/e2e/ui-hardening-a11y.spec.js` (add composer a11y test)

- [ ] **Step 1 — write failing Playwright test**

Append to `frontend/tests/e2e/ui-hardening-a11y.spec.js`:

```js
test.describe('Tiptap composer accessibility (H5)', () => {
  test('Discussion composer exposes aria-label and a formatting toolbar', async ({ page, request }) => {
    const { apiLogin, primeAuthSession } = await import('./helpers/auth.js');
    const apiBase = process.env.E2E_API_BASE || 'http://localhost:8000/api/v2';
    const auth = await apiLogin(request, apiBase, 'dev-admin', 'DevAdmin!2026');
    await primeAuthSession(page, auth);

    // Visit a phenopacket detail page and open the Discussion tab.
    await page.goto('/phenopackets');
    await page.waitForLoadState('networkidle');
    const firstChip = page.locator('table a.v-chip').first();
    await firstChip.click();
    await page.waitForLoadState('networkidle');

    const discussionTab = page.getByRole('tab', { name: /discussion/i });
    if (await discussionTab.count()) {
      await discussionTab.click();
    }

    const editor = page.locator('.comment-composer .ProseMirror');
    await editor.waitFor({ state: 'visible' });
    await expect(editor).toHaveAttribute('aria-label', /comment body/i);

    await expect(page.locator('.comment-composer [data-testid="composer-toolbar"]'))
      .toBeVisible();
    await expect(page.getByRole('button', { name: /bold/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /italic/i })).toBeVisible();
  });
});
```

- [ ] **Step 2 — run test to confirm failure**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "Tiptap composer"
```

Expected: FAIL — editor has no `aria-label`, no toolbar.

- [ ] **Step 3 — update CommentComposer.vue template**

In `frontend/src/components/comments/CommentComposer.vue`, replace the template block (lines 1-27) with:

```vue
<template>
  <div class="comment-composer">
    <div
      class="composer-toolbar d-flex align-center ga-1 mb-2"
      data-testid="composer-toolbar"
      role="toolbar"
      aria-label="Comment formatting"
    >
      <v-btn
        icon
        size="small"
        variant="text"
        aria-label="Bold"
        :disabled="!editor"
        @click="editor?.chain().focus().toggleBold().run()"
      >
        <v-icon>mdi-format-bold</v-icon>
      </v-btn>
      <v-btn
        icon
        size="small"
        variant="text"
        aria-label="Italic"
        :disabled="!editor"
        @click="editor?.chain().focus().toggleItalic().run()"
      >
        <v-icon>mdi-format-italic</v-icon>
      </v-btn>
      <v-btn
        icon
        size="small"
        variant="text"
        aria-label="Insert link"
        :disabled="!editor"
        @click="insertLink"
      >
        <v-icon>mdi-link-variant</v-icon>
      </v-btn>
      <v-btn
        icon
        size="small"
        variant="text"
        aria-label="Mention user"
        :disabled="!editor"
        @click="insertMentionTrigger"
      >
        <v-icon>mdi-at</v-icon>
      </v-btn>
    </div>
    <editor-content
      :editor="editor"
      class="composer-editor"
      aria-label="Comment body"
      aria-describedby="composer-char-count"
    />
    <Teleport to="body">
      <div
        v-if="suggestionVisible"
        class="mention-suggestion-wrapper"
        :style="{ top: suggestionPosition.top + 'px', left: suggestionPosition.left + 'px' }"
      >
        <MentionSuggestionList
          ref="suggestionListRef"
          :items="suggestionItems"
          :command="suggestionCommand"
        />
      </div>
    </Teleport>
    <div class="d-flex align-center mt-2">
      <v-btn color="primary" :disabled="!canSubmit" :loading="submitting" @click="onSubmit">
        {{ submitLabel }}
      </v-btn>
      <v-btn v-if="editingComment" variant="text" class="ml-2" @click="$emit('cancel')">
        Cancel
      </v-btn>
      <span
        id="composer-char-count"
        class="ml-3 text-caption text-medium-emphasis"
        aria-live="polite"
      >
        {{ charCount }} / 10000
      </span>
    </div>
  </div>
</template>
```

- [ ] **Step 4 — wire toolbar handlers in script setup**

In the same file's `<script setup>`, after the existing `collectMentions` function and before `const onSubmit = ...`, insert:

```js
const insertLink = () => {
  if (!editor.value) return;
  const url = window.prompt('Enter URL');
  if (!url) return;
  editor.value.chain().focus().setLink({ href: url }).run();
};

const insertMentionTrigger = () => {
  if (!editor.value) return;
  editor.value.chain().focus().insertContent('@').run();
};
```

Note: `setLink` requires the Tiptap `@tiptap/extension-link` add-on. StarterKit does **not** include it by default. Add the import at the top of the script:

```js
import Link from '@tiptap/extension-link';
```

Then update the `extensions` array in `useEditor(...)`:

```js
const editor = useEditor({
  content: content.value,
  extensions: [StarterKit, Markdown, mentionExtension, Link],
  onUpdate: ({ editor: ed }) => {
    content.value = ed.storage.markdown.getMarkdown();
  },
});
```

- [ ] **Step 5 — install the link extension**

```bash
cd frontend
npm install --save @tiptap/extension-link@^3.22.3
```

Expected: `package.json` gains `@tiptap/extension-link` at `^3.22.3`. `package-lock.json` updates.

- [ ] **Step 6 — apply aria-label to the ProseMirror contenteditable**

Tiptap renders `editor-content` as a wrapper `<div>`, and the actual `contenteditable` is the inner `.ProseMirror`. The `aria-label` attribute on `<editor-content>` is forwarded to the wrapper, not the editable. To put it on `.ProseMirror`, configure `editorProps.attributes` in `useEditor`:

Edit the `useEditor` call:

```js
const editor = useEditor({
  content: content.value,
  extensions: [StarterKit, Markdown, mentionExtension, Link],
  editorProps: {
    attributes: {
      'aria-label': 'Comment body',
      'aria-describedby': 'composer-char-count',
    },
  },
  onUpdate: ({ editor: ed }) => {
    content.value = ed.storage.markdown.getMarkdown();
  },
});
```

Remove the `aria-label` / `aria-describedby` from `<editor-content>` in the template (the editorProps path is the correct one; leaving it on the wrapper is harmless but redundant).

- [ ] **Step 7 — re-run the Playwright a11y spec for composer**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "Tiptap composer"
```

Expected: PASS.

- [ ] **Step 8 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 9 — commit**

```bash
git add frontend/src/components/comments/CommentComposer.vue \
        frontend/package.json \
        frontend/package-lock.json \
        frontend/tests/e2e/ui-hardening-a11y.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): add accessible name and formatting toolbar to Tiptap composer (H5)

Wires aria-label="Comment body" onto the ProseMirror contenteditable via
editorProps.attributes so axe-core's "region has accessible name" check
passes. Adds a formatting toolbar (Bold, Italic, Link, Mention) with
aria-labels to surface the @mention convention and enable keyboard-first
comment formatting. Adds @tiptap/extension-link for the Insert link
button.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md H5
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — Dark-theme detail header contrast (H6)

**Commit message:** `fix(frontend): respect dark theme on phenopacket hero header (H6)`

**Files:**
- Modify: `frontend/src/views/PagePhenopacket.vue` (CSS at ~line 781)
- Create: `frontend/tests/e2e/ui-hardening-dark-theme.spec.js`

- [ ] **Step 1 — write failing Playwright test**

Create `frontend/tests/e2e/ui-hardening-dark-theme.spec.js`:

```js
import { test, expect } from '@playwright/test';

/**
 * Parse an "rgb(r, g, b)" / "rgba(r, g, b, a)" string into [r, g, b].
 */
function parseRgb(css) {
  const m = css.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  return m[1].split(',').slice(0, 3).map((s) => Number(s.trim()));
}

function relativeLuminance([r, g, b]) {
  const toLinear = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const [R, G, B] = [toLinear(r), toLinear(g), toLinear(b)];
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function contrastRatio(rgb1, rgb2) {
  const L1 = relativeLuminance(rgb1);
  const L2 = relativeLuminance(rgb2);
  const [hi, lo] = L1 > L2 ? [L1, L2] : [L2, L1];
  return (hi + 0.05) / (lo + 0.05);
}

test('PagePhenopacket hero-section uses dark gradient under v-theme--dark', async ({ page }) => {
  await page.goto('/phenopackets');
  await page.waitForLoadState('networkidle');
  const firstChip = page.locator('table a.v-chip').first();
  await firstChip.click();
  await page.waitForLoadState('networkidle');

  // Flip theme via ThemeSwitcher if present; otherwise via store.
  await page.evaluate(() => {
    const root = document.documentElement;
    root.classList.remove('v-theme--light');
    root.classList.add('v-theme--dark');
    document.body.classList.remove('v-theme--light');
    document.body.classList.add('v-theme--dark');
  });

  const hero = page.locator('.hero-section');
  await hero.waitFor({ state: 'visible' });

  const styles = await hero.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      background: cs.backgroundImage,
      heroStart: cs.getPropertyValue('--hero-start'),
      heroEnd: cs.getPropertyValue('--hero-end'),
    };
  });
  // Dark gradient endpoints start with #10/#0d range, not #e0f2f1.
  expect(styles.heroStart.trim()).not.toMatch(/#e0f2f1/i);
  expect(styles.heroStart.trim()).toMatch(/#102a2b/i);

  // Verify h1 contrast against the dark gradient start color.
  const h1 = page.locator('.hero-section h1').first();
  const { h1Color, heroStart } = await h1.evaluate((el) => {
    const cs = getComputedStyle(el);
    const parentCs = getComputedStyle(el.closest('.hero-section'));
    return {
      h1Color: cs.color,
      heroStart: parentCs.getPropertyValue('--hero-start').trim(),
    };
  });
  const hexToRgb = (hex) => {
    const h = hex.replace('#', '');
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  };
  const ratio = contrastRatio(parseRgb(h1Color), hexToRgb(heroStart));
  expect(ratio).toBeGreaterThanOrEqual(4.5);
});
```

- [ ] **Step 2 — run test to confirm failure**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-dark-theme.spec.js
```

Expected: FAIL — `--hero-start` resolves to nothing (not defined) and the h1 color is against a light gradient.

- [ ] **Step 3 — update hero-section CSS**

In `frontend/src/views/PagePhenopacket.vue` locate the `.hero-section` block (around line 781). Replace the static gradient with CSS variables and add theme-conditional overrides:

```css
.hero-section {
  background: linear-gradient(
    135deg,
    var(--hero-start) 0%,
    var(--hero-mid) 50%,
    var(--hero-end) 100%
  );
  border-bottom: 1px solid var(--hero-border);
  --hero-start: #e0f2f1;
  --hero-mid: #b2dfdb;
  --hero-end: #f5f7fa;
  --hero-border: rgba(0, 0, 0, 0.05);
}

:global(.v-theme--dark) .hero-section {
  --hero-start: #102a2b;
  --hero-mid: #1e3a3a;
  --hero-end: #0d1b1c;
  --hero-border: rgba(255, 255, 255, 0.08);
}

:global(.v-theme--dark) .hero-section h1,
:global(.v-theme--dark) .hero-section .v-tab,
:global(.v-theme--dark) .hero-section [data-testid="state-actions-button"] {
  color: rgb(178, 223, 219) !important; /* teal-lighten-3 — WCAG AA against #102a2b */
}
```

Note: because `PagePhenopacket.vue`'s `<style>` block is `scoped`, use `:global(...)` (or `:deep(...)` followed by a class) to target the document-level theme class. The simplest working approach is `:global(.v-theme--dark) .hero-section { ... }`. If scoped selectors cause regressions, convert the block to `<style>` (non-scoped) for just the theme-conditional overrides while keeping the component-scoped styles separate.

- [ ] **Step 4 — re-run the dark-theme spec**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-dark-theme.spec.js
```

Expected: PASS.

- [ ] **Step 5 — manual spot-check at 1440×900 and 390×844**

Start dev servers (`make backend` + `make frontend`), sign in as `dev-admin / DevAdmin!2026`, open a phenopacket detail page, toggle to dark theme via the theme switcher, confirm:

- hero background is visibly dark teal
- `<h1>` "Individual Details" is legible
- tab labels (OVERVIEW / TIMELINE / RAW JSON) legible
- STATE ACTIONS button legible
- re-size viewport to 390×844 — same elements remain legible

- [ ] **Step 6 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 7 — commit**

```bash
git add frontend/src/views/PagePhenopacket.vue \
        frontend/tests/e2e/ui-hardening-dark-theme.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): respect dark theme on phenopacket hero header (H6)

Replaces the static light-teal gradient on .hero-section with CSS
custom properties that flip under v-theme--dark, and scopes
theme-sensitive foreground color overrides for h1, tab labels, and the
state-actions button so each hits ≥4.5:1 contrast against the dark
gradient.

Adds tests/e2e/ui-hardening-dark-theme.spec.js with a contrast-ratio
DOM probe.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md H6
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §6

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8 — Reproduce and repair /aggregations blank page (C1, H4)

**Commit message:** `fix(frontend): reproduce and repair /aggregations blank page (C1)`

**Files:**
- Modify: `frontend/src/views/AggregationsDashboard.vue`
- Modify: `frontend/tests/e2e/ui-hardening-critical.spec.js`

- [ ] **Step 1 — reproduce the blank page with Playwright**

Start dev servers first (`make backend` + `make frontend`). Then capture console errors:

```bash
cd frontend
cat > /tmp/repro-aggregations.js <<'EOF'
import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const consoleEntries = [];
  page.on('console', (msg) => consoleEntries.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', (err) => consoleEntries.push({ type: 'pageerror', text: err.message }));
  const responses = [];
  page.on('response', (r) => {
    if (r.url().includes('/api/')) responses.push({ status: r.status(), url: r.url() });
  });
  await page.goto('http://localhost:5173/aggregations');
  await page.waitForLoadState('networkidle');
  const hasTabs = await page.locator('.v-tabs').count();
  const bodyText = (await page.locator('body').innerText()).trim();
  console.log(JSON.stringify({ consoleEntries, responses, hasTabs, bodyTextLength: bodyText.length }, null, 2));
  await browser.close();
})();
EOF
node /tmp/repro-aggregations.js
```

Expected: the JSON output reveals either (a) a Vue runtime error crashing the component tree, (b) a series of 401/500 responses from `/api/v2/aggregations/...`, or (c) empty `bodyText` with no errors. Record the actual output in the commit message later. Decide fix path based on which case it is.

- [ ] **Step 2 — write the failing Playwright test**

Append to `frontend/tests/e2e/ui-hardening-critical.spec.js`:

```js
test.describe('/aggregations reliability (C1)', () => {
  test('renders a page-level h1 and either data or an error card — never pure white', async ({ page }) => {
    await page.goto('/aggregations');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
    // At least one of: tab chrome, a chart container, an error alert.
    const tabCount = await page.locator('.v-tabs').count();
    const alertCount = await page.locator('.v-alert').count();
    const chartCount = await page.locator('canvas, svg').count();
    expect(tabCount + alertCount + chartCount).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 3 — run the test to confirm failure**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-critical.spec.js -g "/aggregations reliability"
```

Expected: FAIL (based on the review's report).

- [ ] **Step 4 — apply the baseline fix (always-present h1 + error boundaries)**

In `frontend/src/views/AggregationsDashboard.vue`, change the template outer wrapper (around lines 2-15) so a page-level heading renders unconditionally:

```vue
<template>
  <v-container fluid>
    <h1 class="text-h5 font-weight-bold text-teal-darken-2 mb-3">Aggregations</h1>
    <v-alert
      v-if="pageError"
      type="error"
      variant="tonal"
      class="mb-3"
      data-testid="aggregations-page-error"
    >
      <v-alert-title>Unable to load aggregations</v-alert-title>
      {{ pageError }}
    </v-alert>
    <v-row>
      <v-col cols="12">
        <v-sheet outlined>
          <v-card>
            <v-tabs v-model="activeTabLabel" bg-color="primary">
              ...
```

Add a `pageError` ref near the other refs in `<script setup>`:

```js
const pageError = ref(null);
```

- [ ] **Step 5 — wrap all fetch calls in try/catch that set pageError**

In the same file, update the existing fetch functions so any thrown error sets `pageError.value`. Example shape for `fetchStackedBarData`:

```js
function fetchStackedBarData() {
  window.logService.debug('Fetching stacked bar chart data');

  API.getPhenotypicFeaturesAggregation()
    .then((response) => {
      window.logService.info('Stacked bar chart data loaded', {
        count: response.data?.length,
      });
      stackedBarChartData.value = response.data || [];
    })
    .catch((error) => {
      window.logService.error('Error fetching stacked bar chart data', {
        error: error.message,
      });
      pageError.value = `Stacked bar data unavailable: ${error.message}`;
    });
}
```

Apply the same `.catch(...) { ...; pageError.value = ...; }` pattern to `fetchAggregationData`, `fetchComparisonData`, and `fetchSurvivalData`.

- [ ] **Step 6 — guard the computed activeTabLabel against undefined**

The `activeTabLabel` computed already falls back to `AGGREGATION_TABS[0].label` via `getTabLabel`. If the Step 1 repro indicated that `getTabLabel` receives a value that returns `undefined` (e.g., the schema default somehow becomes `null`), harden it:

In `frontend/src/utils/aggregationConfig.js` `getTabLabel`, ensure a defined fallback:

```js
export function getTabLabel(slug) {
  const tab = AGGREGATION_TABS.find((t) => t.slug === slug);
  return tab ? tab.label : AGGREGATION_TABS[0]?.label || '';
}
```

If Step 1 did **not** identify this as a contributing cause, skip this sub-step.

- [ ] **Step 7 — re-run the repro**

```bash
cd frontend
node /tmp/repro-aggregations.js
```

Expected: `hasTabs >= 1` AND either `bodyTextLength > 100` or an `aggregations-page-error` alert visible. No pure-white render.

- [ ] **Step 8 — re-run the Playwright test**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-critical.spec.js -g "/aggregations reliability"
```

Expected: PASS.

- [ ] **Step 9 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 10 — commit**

```bash
git add frontend/src/views/AggregationsDashboard.vue \
        frontend/src/utils/aggregationConfig.js \
        frontend/tests/e2e/ui-hardening-critical.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): reproduce and repair /aggregations blank page (C1)

Ensures /aggregations always renders an h1 and, when any aggregation
fetch throws, a visible error alert with the failure reason. Previously
the page could render pure white to anonymous visitors when an early
fetch rejection unmounted the component tree.

Wraps every fetch* function in the view with a catch that sets a
pageError state; hardens getTabLabel fallback; adds a Playwright test
that guarantees non-blank output regardless of backend state.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md C1, H4
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §5

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Also delete `/tmp/repro-aggregations.js` — it was a throwaway.

---

## Task 9 — Demote anonymous token refresh log (M12)

**Commit message:** `chore(frontend): demote anonymous token-refresh log to debug (M12)`

**Files:**
- Modify: `frontend/src/stores/authStore.js` (lines 119-143 and 207-242)
- Create: `frontend/tests/unit/stores/authStore.spec.js` (or extend if it exists)

- [ ] **Step 1 — write the failing unit test**

Create `frontend/tests/unit/stores/authStore.spec.js`:

```js
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api';

vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock('@/api/session', () => ({
  clearTokens: vi.fn(),
  getAccessToken: vi.fn(() => null),
  persistTokens: vi.fn(),
}));

describe('authStore — log hygiene (M12)', () => {
  let logSpy;

  beforeEach(() => {
    setActivePinia(createPinia());
    logSpy = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
    window.logService = logSpy;
    vi.clearAllMocks();
  });

  it('logs anonymous refresh rejection at debug, not error', async () => {
    apiClient.post.mockRejectedValueOnce(new Error('401 Unauthorized'));
    const store = useAuthStore();
    // No user set → anonymous.
    await expect(store.refreshAccessToken()).rejects.toThrow();
    expect(logSpy.error).not.toHaveBeenCalledWith(
      'Token refresh failed',
      expect.anything()
    );
    expect(logSpy.debug).toHaveBeenCalledWith(
      'Anonymous session refresh rejected (expected)',
      expect.objectContaining({ error: expect.any(String) })
    );
  });

  it('logs authenticated refresh rejection at error', async () => {
    apiClient.post.mockRejectedValueOnce(new Error('500 Server'));
    const store = useAuthStore();
    store.user = { username: 'x', role: 'curator' };
    await expect(store.refreshAccessToken()).rejects.toThrow();
    expect(logSpy.error).toHaveBeenCalledWith(
      'Token refresh failed',
      expect.objectContaining({ error: expect.any(String) })
    );
  });

  it('initialize() logs anonymous failure at debug', async () => {
    apiClient.post.mockRejectedValueOnce(new Error('401 Unauthorized'));
    const store = useAuthStore();
    await store.initialize();
    expect(logSpy.warn).not.toHaveBeenCalledWith(
      'Failed to initialize user session',
      expect.anything()
    );
    expect(logSpy.debug).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2 — run test to confirm failure**

```bash
cd frontend
npx vitest run tests/unit/stores/authStore.spec.js
```

Expected: FAIL — current `refreshAccessToken` always logs error; `initialize()` always logs warn.

- [ ] **Step 3 — edit refreshAccessToken**

In `frontend/src/stores/authStore.js` lines 119-143, replace the function body with:

```js
  async function refreshAccessToken() {
    const wasAuthenticated = !!user.value;
    try {
      const response = await apiClient.post('/auth/refresh', null, {
        withCredentials: true,
      });

      const { access_token } = response.data;

      // Update the short-lived access token in memory only.
      accessToken.value = access_token;
      persistTokens({ accessToken: access_token });

      window.logService.debug('Access token refreshed');

      return access_token;
    } catch (err) {
      if (wasAuthenticated) {
        window.logService.error('Token refresh failed', {
          error: err.message,
        });
      } else {
        window.logService.debug('Anonymous session refresh rejected (expected)', {
          error: err.message,
        });
      }

      // If refresh fails, logout user (skip backend call since token is already invalid)
      await logout(true);
      throw err;
    }
  }
```

- [ ] **Step 4 — edit initialize()**

In the same file lines 207-242, replace the two `logService.warn('Failed to initialize user session', ...)` calls with a wasAuthenticated-aware split. Adjust the inner block to:

```js
    initializationPromise = (async () => {
      if (accessToken.value) {
        try {
          await fetchCurrentUser();
        } catch (err) {
          // Token might be expired, will be handled by interceptor
          const level = user.value ? 'warn' : 'debug';
          window.logService[level]('Failed to initialize user session', {
            error: err.message,
          });
        }
        return;
      }

      try {
        await refreshAccessToken();
        await fetchCurrentUser();
      } catch (err) {
        // Anonymous visitor — refresh rejection is expected.
        window.logService.debug('Anonymous session bootstrap skipped', {
          error: err.message,
        });
      }
    })();
```

- [ ] **Step 5 — re-run unit test**

```bash
cd frontend
npx vitest run tests/unit/stores/authStore.spec.js
```

Expected: PASS (3 tests).

- [ ] **Step 6 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 7 — commit**

```bash
git add frontend/src/stores/authStore.js \
        frontend/tests/unit/stores/authStore.spec.js
git commit -m "$(cat <<'EOF'
chore(frontend): demote anonymous token-refresh log to debug (M12)

refreshAccessToken() now branches on whether a user was authenticated
before the refresh attempt. Authenticated failures still log at ERROR;
anonymous 401s (expected when a first-time visitor reaches a public
page) log at DEBUG. Same logic applied to initialize() so anonymous
bootstrap no longer surfaces WARN rows in the in-app log viewer.

Adds tests/unit/stores/authStore.spec.js covering both paths.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md M12
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §7

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10 — Hide API docs link when VITE_API_URL unset in prod (M10)

**Commit message:** `fix(frontend): hide API docs link when VITE_API_URL unset in prod (M10)`

**Files:**
- Modify: `frontend/src/components/FooterBar.vue` (around line 174-200)
- Create: `frontend/tests/unit/components/FooterBar.spec.js` (or extend if present)

- [ ] **Step 1 — inspect current loadFooterConfig**

Open `frontend/src/components/FooterBar.vue`. The critical block is at lines 174-200 (see spec §7). Current behavior: if `VITE_API_URL` is unset, `apiDocsUrl` becomes `http://localhost:8000/api/v2/docs` unconditionally.

- [ ] **Step 2 — write unit test**

Create `frontend/tests/unit/components/FooterBar.spec.js`:

```js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import FooterBar from '@/components/FooterBar.vue';

const vuetify = createVuetify();

function mockFetchConfig(config) {
  global.fetch = vi.fn(() =>
    Promise.resolve({ json: () => Promise.resolve(config) })
  );
}

describe('FooterBar API docs link (M10)', () => {
  const origProd = import.meta.env.PROD;
  const origApi = import.meta.env.VITE_API_URL;

  beforeEach(() => {
    window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  });

  afterEach(() => {
    import.meta.env.PROD = origProd;
    import.meta.env.VITE_API_URL = origApi;
    vi.restoreAllMocks();
  });

  it('omits the API docs link when VITE_API_URL is unset in prod build', async () => {
    import.meta.env.PROD = true;
    import.meta.env.VITE_API_URL = '';
    mockFetchConfig([
      { enabled: true, label: 'API', url: '__API_DOCS_URL__' },
      { enabled: true, label: 'GitHub', url: 'https://github.com/x/y' },
    ]);
    const wrapper = mount(FooterBar, { global: { plugins: [vuetify] } });
    // Allow the onMounted effect to settle.
    await new Promise((r) => setTimeout(r, 20));
    const hrefs = wrapper.findAll('a').map((a) => a.attributes('href'));
    expect(hrefs).not.toContain('http://localhost:8000/api/v2/docs');
    expect(hrefs.some((h) => h && h.includes('github.com'))).toBe(true);
    expect(window.logService.warn).toHaveBeenCalledWith(
      expect.stringContaining('API docs URL not configured'),
      expect.anything()
    );
  });

  it('includes the API docs link when VITE_API_URL is set', async () => {
    import.meta.env.PROD = true;
    import.meta.env.VITE_API_URL = 'https://api.example.com/api/v2';
    mockFetchConfig([{ enabled: true, label: 'API', url: '__API_DOCS_URL__' }]);
    const wrapper = mount(FooterBar, { global: { plugins: [vuetify] } });
    await new Promise((r) => setTimeout(r, 20));
    const hrefs = wrapper.findAll('a').map((a) => a.attributes('href'));
    expect(hrefs).toContain('https://api.example.com/api/v2/docs');
  });
});
```

- [ ] **Step 3 — run test to confirm failure**

```bash
cd frontend
npx vitest run tests/unit/components/FooterBar.spec.js
```

Expected: FAIL — link is currently `http://localhost:8000/api/v2/docs` in prod.

- [ ] **Step 4 — edit FooterBar.vue**

Replace the `loadFooterConfig` logic in `frontend/src/components/FooterBar.vue` (around lines 174-200):

```js
const loadFooterConfig = async () => {
  const rawApi = import.meta.env.VITE_API_URL || '';
  const isProd = import.meta.env.PROD === true;

  // In prod, require an explicit VITE_API_URL before exposing the API docs link.
  let apiDocsUrl = null;
  if (rawApi) {
    apiDocsUrl = rawApi.replace(/\/+$/, '') + '/docs';
  } else if (!isProd) {
    apiDocsUrl = 'http://localhost:8000/api/v2/docs';
  } else {
    window.logService.warn('API docs URL not configured (VITE_API_URL unset)', {
      env: 'production',
    });
  }

  try {
    const response = await fetch('/config/footerConfig.json');
    const config = await response.json();

    footerLinks.value = config
      .filter((link) => link.enabled)
      .map((link) => ({
        ...link,
        url: link.url === '__API_DOCS_URL__' ? apiDocsUrl : link.url,
      }))
      .filter((link) => link.url); // drop links with null URL (e.g. API docs in misconfigured prod)

    window.logService.info('Footer configuration loaded', {
      linksCount: footerLinks.value.length,
    });
  } catch (error) {
    window.logService.error('Failed to load footer configuration', {
      error: error.message,
      path: '/config/footerConfig.json',
    });
  }
};
```

- [ ] **Step 5 — re-run unit test**

```bash
cd frontend
npx vitest run tests/unit/components/FooterBar.spec.js
```

Expected: PASS.

- [ ] **Step 6 — run lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 7 — commit**

```bash
git add frontend/src/components/FooterBar.vue \
        frontend/tests/unit/components/FooterBar.spec.js
git commit -m "$(cat <<'EOF'
fix(frontend): hide API docs link when VITE_API_URL unset in prod (M10)

The footer previously fell back to http://localhost:8000/api/v2/docs
unconditionally, which meant production deployments without a
configured VITE_API_URL exposed a broken localhost link. Now the docs
link is suppressed in prod when the env var is missing, and a WARN is
emitted so operators see the misconfiguration.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md M10
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §7

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11 — Skip-to-main-content link (L6)

**Commit message:** `feat(frontend): add skip-to-main-content link (L6)`

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/tests/e2e/ui-hardening-a11y.spec.js` (append skip-link test)

- [ ] **Step 1 — write failing Playwright test**

Append to `frontend/tests/e2e/ui-hardening-a11y.spec.js`:

```js
test.describe('Skip-to-main-content (L6)', () => {
  test('first tab-able element is a visible skip link pointing to #main-content', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? { tag: el.tagName, href: el.getAttribute('href'), text: el.textContent?.trim() } : null;
    });
    expect(focused?.tag).toBe('A');
    expect(focused?.href).toBe('#main-content');
    expect(focused?.text?.toLowerCase()).toContain('skip');
    // #main-content target exists.
    await expect(page.locator('#main-content')).toHaveCount(1);
  });
});
```

- [ ] **Step 2 — run to confirm failure**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "Skip-to-main-content"
```

Expected: FAIL — no skip link, no `#main-content` anchor.

- [ ] **Step 3 — edit App.vue**

Replace `frontend/src/App.vue` template block with:

```vue
<template>
  <v-app>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <AppBar @toggle-drawer="drawer = !drawer" />
    <MobileDrawer v-model="drawer" />
    <v-main id="main-content">
      <router-view />
    </v-main>
    <FooterBar />
    <LogViewer />
  </v-app>
</template>

<style>
.skip-link {
  position: absolute;
  top: 0;
  left: 0;
  padding: 8px 12px;
  background: #00695c;
  color: #ffffff;
  text-decoration: none;
  z-index: 10000;
  transform: translateY(-120%);
  transition: transform 0.15s ease-in-out;
}
.skip-link:focus {
  transform: translateY(0);
  outline: 2px solid #ffffff;
  outline-offset: 2px;
}
</style>
```

- [ ] **Step 4 — re-run Playwright test**

```bash
cd frontend
npx playwright test tests/e2e/ui-hardening-a11y.spec.js -g "Skip-to-main-content"
```

Expected: PASS.

- [ ] **Step 5 — lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: no errors.

- [ ] **Step 6 — commit**

```bash
git add frontend/src/App.vue \
        frontend/tests/e2e/ui-hardening-a11y.spec.js
git commit -m "$(cat <<'EOF'
feat(frontend): add skip-to-main-content link (L6)

Adds a visually-hidden "Skip to main content" anchor as the first
tab-able element, revealed on focus. Target is #main-content on
<v-main>, giving keyboard-only and screen-reader users a one-press
bypass of the AppBar on every route.

Refs: .planning/reviews/2026-04-17-ui-ux-design-review.md L6
Spec:  .planning/specs/2026-04-17-ui-hardening-immediate-design.md §7

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12 — Full local verification before pushing

**Commit message:** none (pure verification task)

**Files:** none

- [ ] **Step 1 — run the full frontend unit suite**

```bash
cd frontend
npm run test
```

Expected: all Vitest specs pass. If any pre-existing spec fails because of the new `h1` or chip-anchor changes, investigate and fix — do not skip.

- [ ] **Step 2 — run the full Playwright suite**

```bash
cd frontend
npx playwright test
```

Expected: every e2e spec passes. Includes the three new files:

- `ui-hardening-critical.spec.js`
- `ui-hardening-a11y.spec.js`
- `ui-hardening-dark-theme.spec.js`

Plus all pre-existing specs (`comments.spec.js`, `dual-read-invariant.spec.js`, `phenopacket-ui-review.spec.js`, `state-lifecycle.spec.js`, `table-url-state.spec.js`).

If any pre-existing spec breaks, triage: either the spec was asserting the buggy dual-state (legitimate pre-existing test needs update) or our fix introduced a regression (revert + reroute).

- [ ] **Step 3 — run the backend smoke test suite**

```bash
cd ~/development/hnf1b-db
make test
```

Expected: backend pytest passes. No backend changes in this batch, but we sanity-check that the contract endpoints hit by the frontend are intact.

- [ ] **Step 4 — run frontend lint + format**

```bash
cd frontend
npm run lint:check
npm run format:check
```

Expected: clean.

- [ ] **Step 5 — manual visual verification**

With `make backend` and `make frontend` running, log in as `dev-admin / DevAdmin!2026` and walk the eleven pages from the review's per-page-scores table. Confirm:

- `/phenopackets`, `/publications`, `/variants` each show one visible `h1`.
- `/phenopackets/new` redirects to `/phenopackets/create`.
- `/aggregations` shows at minimum an `h1` and a tabbed chrome or error card (not pure white).
- Hero-section on a phenopacket detail page is legible under dark theme at desktop and phone viewports.
- Tab to the first focusable element on `/` → skip link appears.
- Keyboard-only: Tab to the first subject-ID chip on `/phenopackets`, Enter, lands on the detail page.

Record any surprises; fix before the push step.

- [ ] **Step 6 — push and open PR**

```bash
git push -u origin ui-hardening-immediate
gh pr create --base main --title "UI hardening: Critical + High + M10/M12/L6" \
  --body "$(cat <<'EOF'
## Summary

Closes all Critical and High findings from
`.planning/reviews/2026-04-17-ui-ux-design-review.md`, plus M10 (API
docs link fallback), M12 (anonymous token-refresh log hygiene), and L6
(skip-to-main-content link).

| Finding | Status |
|---|---|
| C1 `/aggregations` blank page | Fixed — always renders h1 + error boundary |
| C2 `/phenopackets/new` dual error | Fixed — redirect + mutually-exclusive render |
| H1 External `rel="noopener noreferrer"` | Fixed — sweep + new `<ExternalLink>` |
| H2 Real `h1` on list/create pages | Fixed — AppDataTable `titleTag` prop |
| H3 Keyboard row activation | Fixed — chips are router-link anchors |
| H4 `/aggregations` empty-state | Resolved by C1 |
| H5 Tiptap composer accessible name | Fixed — aria-label + formatting toolbar |
| H6 Dark-theme detail contrast | Fixed — CSS variables flip under v-theme--dark |
| M10 Hardcoded localhost in footer | Fixed — suppress link in prod when env unset |
| M12 Anonymous refresh log ERROR | Fixed — branch on wasAuthenticated |
| L6 Skip-link | Added |

Spec: `.planning/specs/2026-04-17-ui-hardening-immediate-design.md`
Plan: `.planning/plans/2026-04-17-ui-hardening-immediate.md`

## Test plan

- [ ] `cd frontend && npm run test` passes
- [ ] `cd frontend && npx playwright test` passes
- [ ] `make test` (backend smoke) passes
- [ ] `cd frontend && npm run lint:check && npm run format:check` clean
- [ ] Manual verification of the eleven pages in the review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Record the PR URL. Watch CI; if it fails, triage and fix with further commits on the same branch.

- [ ] **Step 7 — watch CI to green**

```bash
gh pr status
gh run list --branch ui-hardening-immediate --limit 3
```

Expected: all checks green. If any check fails, read the log, fix on `ui-hardening-immediate`, push a new commit. Do not merge or request review until CI is green.

---

## Exit Criteria

- All 12 commits landed on `ui-hardening-immediate`.
- PR open against `main` with CI green.
- Every finding in the Plan's scope has at least one passing test guarding the fix.
- Manual visual verification of dark theme + keyboard flows complete.
- No regression in pre-existing Playwright or Vitest specs.

## Risk Notes

- **`:global(.v-theme--dark)` in scoped styles** — If Vue 3.5 + `<style scoped>` rejects `:global`, fall back to a non-scoped sibling `<style>` block in the same SFC.
- **Tiptap link extension version pin** — `@tiptap/extension-link` must match the other Tiptap packages' major. Repo uses `^3.22.3`; install the same.
- **Playwright auth helper env** — the `E2E_API_BASE` env var must point at a running backend (default `http://localhost:8000/api/v2`). Two specs (h1 on create page, composer a11y) require authenticated sessions.
- **C1 repro uncertainty** — if Step 1 of Task 8 reveals a cause that cannot be fixed without a backend change (e.g., a mandatory-auth public endpoint), reduce Task 8's scope to the baseline fix (h1 + error boundary) and document the backend-side follow-up as a finding in `.planning/reviews/` rather than expanding the PR.
- **Commit independence** — each commit should leave CI green. If a later commit depends on an earlier one's test fixture setup, the earlier commit must establish that fixture.

## Sources

- `.planning/specs/2026-04-17-ui-hardening-immediate-design.md`
- `.planning/reviews/2026-04-17-ui-ux-design-review.md`
- Vuetify 4 docs: https://vuetifyjs.com/en/
- Tiptap v3 editor-props: https://tiptap.dev/api/editor#editor-props
- MDN `rel="noopener"`: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel#noopener
- WCAG 2.2 Skip-Link guidance (2.4.1 Bypass Blocks): https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks.html
