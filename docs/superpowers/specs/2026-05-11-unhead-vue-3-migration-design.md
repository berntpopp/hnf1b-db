# @unhead/vue v3 Migration — Design

**Date:** 2026-05-11
**PR:** [#278](https://github.com/berntpopp/hnf1b-db/pull/278) — `@unhead/vue` 2.1.13 → 3.1.0
**Reviewer:** Claude Code (Opus 4.7)

## Goal

Adopt `@unhead/vue` v3 by merging the dependabot PR `#278` after a final rebase. No code changes.

## Scope

One change: `frontend/package.json` + `frontend/package-lock.json` only.

## Context

`@unhead/vue` v3 introduces:
- Bundler-agnostic streaming SSR plugin (we do not use SSR — N/A).
- `@unhead/cli` migration codemod and `@unhead/eslint-plugin` (optional; for catching v2 misuse).
- `defineX` helpers around tag literals for stronger typing (we use plain JS, no TS — N/A).
- Several v2 props deprecated under v3, with the legacy export path restored.

Our usage of `@unhead/vue`:
- `frontend/src/main.js:4` — `import { createHead } from '@unhead/vue/client'`, then `createHead()` registered as a Vue plugin.
- `frontend/src/composables/useSeoMeta.js` — `useHead({...})` + `useSeoMeta({...})` for variant/phenopacket/publication SEO + JSON-LD injection.
- `frontend/src/views/NotFound.vue` — `useHead` + `useSeoMeta` for 404 noindex hints.

**Critical evidence:** the rebased `#278` CI is fully green across all four jobs (`test`, `frontend`, `pre-commit hygiene gate`, `E2E tests (Playwright)`). This proves our existing import paths and composable usage compile, build, and pass unit + E2E tests under v3 with no source changes required.

## Architecture

No architecture change. The library upgrade is opaque to our composables.

## Verification

Per user direction (2026-05-11): **CI-only** — same rationale as the parallel vite-8 spec.

## Risk + Rollback

**Highest-risk surface:** runtime behavior of `useSeoMeta` JSON-LD script injection (`useSeoMeta.js` injects `application/ld+json` scripts via `useHead({ script: ... })` in 5 places). If v3 changed how reactive script blocks render to the DOM, SEO crawlers could see stale or missing structured data.

**Mitigation:** if structured-data injection regresses post-deploy (visible via Google Search Console "Items detected" drops, or by inspecting page source for `<script type="application/ld+json">` on `/variants/:id`, `/phenopackets/:id`, `/publications/:pmid`, `/faq`, breadcrumbs), `git revert` the squash-commit. Our Playwright E2E already loads these views in CI, so DOM-level rendering is implicitly covered by green CI.

## What we are NOT doing

- No code changes to `useSeoMeta.js`, `NotFound.vue`, or `main.js`.
- No adoption of `@unhead/cli` codemod or `@unhead/eslint-plugin` (YAGNI — green CI shows nothing to migrate).
- No SSR streaming wiring (the new v3 feature is SSR-only).

## Execution

1. Verify `#278` is still mergeable against current `main` (re-rebase via `@dependabot rebase` if `main` has moved).
2. Wait for post-rebase CI to finish all four jobs green.
3. Squash-merge with `gh pr merge 278 --squash --delete-branch`.
4. After deploy, spot-check a `/variants/:id` page source for an intact `<script type="application/ld+json">` block.
