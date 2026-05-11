# Vite 8 Migration — Design

**Date:** 2026-05-11
**PR:** [#277](https://github.com/berntpopp/hnf1b-db/pull/277) — `vite` 7.3.2 → 8.0.12
**Reviewer:** Claude Code (Opus 4.7)

## Goal

Adopt `vite` v8 by merging the dependabot PR `#277` after a final rebase. No code changes.

## Scope

One change: `frontend/package.json` + `frontend/package-lock.json` only.

## Context

Vite 8 is a major version that switches the underlying bundler to **rolldown** (1.0.0-rc.17 at v8.0.10). Notable v8 differences relevant to this project:

- Rolldown bundler instead of Rollup for production builds.
- "Remove format sniffing module resolution from JS resolver."
- `bundled-dev`: rejects HMR patch requests from non-trustworthy origins.
- Misc TypeScript-rule and client typecheck refactors (do not affect us — no TS in frontend source).

Our plugin set is unchanged:
- `@vitejs/plugin-vue` ^6.0.6
- `vite-plugin-vuetify` ^2.1.2
- `vite-plugin-compression` ^0.5.1
- `rollup-plugin-visualizer` ^7.0.1

All are vite-8 compatible at their currently-pinned versions; the CI build on `#277` proves resolution + production build succeed end-to-end.

Our hand-tuned `vite.config.js` `manualChunks` (consolidated `vue-stack` chunk, fixed in `#286`) is plugin-agnostic — same rule applies under rolldown.

## Architecture

No architecture change. The bundler swap is opaque to our config.

## Verification

Per user direction (2026-05-11): **CI-only**. Rationale:

- Rebased `#277` CI is fully green across all four jobs (`test`, `frontend`, `pre-commit hygiene gate`, `E2E tests (Playwright)`).
- Our 4 plugins are mainstream and explicitly support vite 8.
- The `manualChunks` logic is bundler-agnostic — same rule, same chunks.

## Risk + Rollback

**Highest-risk surface:** the same class of TDZ regression we just fixed in `#286` (`"Cannot access X before initialization"` from cross-chunk circular evaluation under specific load orders). Rolldown's output ordering may differ from Rollup in edge cases.

**Mitigation:** if production exhibits TDZ-like errors after deploy, `git revert` the vite-8 squash-commit and re-deploy. The TDZ comments at `vite.config.js:122-127` referencing vitejs/vite#9686/#22122/#12209 remain in place and continue to apply under v8.

## What we are NOT doing

- No code changes.
- No `vite.config.js` edits.
- No plugin upgrades (those are tracked by their own dependabot PRs).
- No `define` / `optimizeDeps` retuning. YAGNI.

## Execution

1. Verify `#277` is still mergeable against current `main` (re-rebase via `@dependabot rebase` if `main` has moved).
2. Wait for post-rebase CI to finish all four jobs green.
3. Squash-merge with `gh pr merge 277 --squash --delete-branch`.
4. Watch the next prod deploy for TDZ-like console errors; revert if observed.
