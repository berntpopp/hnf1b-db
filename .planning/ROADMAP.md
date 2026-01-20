# Roadmap: HNF1B Database Final Polish

**Created:** 2026-01-19
**Milestone:** Final Polish
**Status:** In Progress (5/9 phases complete)

## Overview

| Metric | Value |
|--------|-------|
| Total Phases | 9 |
| Total Requirements | 53 |
| GitHub Issues | 14 |
| Priority | Bug fixes → Refactoring → Features → Testing → Docs |

## Phase Summary

| # | Phase | Goal | Issues | Requirements | Priority |
|---|-------|------|--------|--------------|----------|
| 1 | Pydantic Fixes ✓ | Eliminate deprecation warnings | #134 | 3 | P2-Medium |
| 2 | Component & Constants ✓ | Extract large components, add constants | #133, #137, #91 | 13 | P1-High |
| 3 | Test Modernization ✓ | Upgrade backend test suite | #94 | 4 | P2-Medium |
| 4 | UI/UX Normalization ✓ | Consistent design system | #98 | 7 | P2-Medium |
| 5 | Chart Polish ✓ | Accessibility, animations, export | #135, #139, #136 | 15 | P2-Medium |
| 6 | Backend Features & PWA | User tracking, service worker | #140, #138 | 8 | P3-Low |
| 7 | Migration Consolidation | Clean alembic history | #102 | 4 | P3-Low |
| 8 | E2E Testing | Playwright test coverage | #48 | 6 | P3-Low |
| 9 | Documentation | User & developer docs | #50 | 5 | P1-High |

---

## Phase 1: Pydantic Deprecation Fixes ✓

**Goal:** Eliminate all 7 Pydantic class-based Config deprecation warnings from backend code

**Status:** Complete (2026-01-19)

**GitHub Issue:** #134

**Plans:** 1 plan

Plans:
- [x] 01-01-PLAN.md — Migrate class-based Config to ConfigDict in 2 schema files

**Requirements:**
- QUAL-01: Fix `regex` → `pattern` in Query parameters (ALREADY DONE - verified)
- QUAL-02: Fix `example` → `examples=[]` in Field definitions (ALREADY DONE - verified)
- QUAL-03: Replace class-based `Config` with `ConfigDict` (7 instances)

**Success Criteria:**
1. `make backend && make test` produces zero Pydantic deprecation warnings
2. All existing tests pass
3. API responses unchanged (no breaking changes)

**Dependencies:** None (can start immediately)

**Files to modify:**
- `backend/app/reference/schemas.py` (5 Config classes)
- `backend/app/phenopackets/models.py` (2 Config classes)

**Research Note:** Original issue #134 mentioned 12 warnings. Research revealed only 7 remain - all class-based Config. The `regex=` and `example=` patterns are already migrated.

---

## Phase 2: Component Refactoring & Constants ✓

**Goal:** Extract ProteinStructure3D.vue into sub-components and create centralized constants for backend and frontend

**Status:** Complete (2026-01-19)

**GitHub Issues:** #133, #137, #91

**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Create backend constants module
- [x] 02-02-PLAN.md — Create frontend constants module
- [x] 02-03-PLAN.md — Extract ProteinStructure3D.vue into sub-components

**Requirements:**
- QUAL-04: Create `backend/app/constants.py` with documented constants
- QUAL-09: Extract ProteinStructure3D.vue into sub-components (<500 lines each)
- QUAL-10: Create `StructureViewer.vue` for NGL.js canvas
- QUAL-11: Create `StructureControls.vue` for representation toggles
- QUAL-12: Create `VariantPanel.vue` for variant list/selection
- QUAL-13: Create `DistanceDisplay.vue` for distance info and legends
- QUAL-14: Create `frontend/src/constants/` module with documented constants
- QUAL-15: Create `frontend/src/config/` with centralized configuration
- QUAL-16: Move visualization dimensions to config
- QUAL-17: Move API timeouts to config
- QUAL-18: Add config validation on app startup

**Success Criteria:**
1. ProteinStructure3D.vue reduced to <500 lines
2. 4 sub-components created in `protein-structure/` directory
3. `backend/app/constants.py` exists with documented constants
4. `frontend/src/constants/` module exists with domain-specific files
5. All existing functionality preserved
6. All tests pass

**Dependencies:** Phase 1 complete

**Files to create:**
- `backend/app/constants.py`
- `frontend/src/constants/index.js`
- `frontend/src/constants/thresholds.js`
- `frontend/src/constants/structure.js`
- `frontend/src/constants/ui.js`
- `frontend/src/components/gene/protein-structure/StructureViewer.vue`
- `frontend/src/components/gene/protein-structure/StructureControls.vue`
- `frontend/src/components/gene/protein-structure/VariantPanel.vue`
- `frontend/src/components/gene/protein-structure/DistanceDisplay.vue`
- `frontend/src/components/gene/protein-structure/styles.css`

---

## Phase 3: Backend Test Modernization ✓

**Goal:** Upgrade test suite to modern pytest patterns with standardized naming and coverage measurement

**Status:** Complete (2026-01-19)

**GitHub Issue:** #94

**Plans:** 7 plans

Plans:
- [x] 03-01-PLAN.md — Configure pytest-cov and modernize conftest.py fixture naming
- [x] 03-02-PLAN.md — Migrate test naming Batch 1 (auth, config, phenopackets, ontology)
- [x] 03-03-PLAN.md — Migrate test naming Batch 2 (audit, patterns, batch, transaction) + consolidate fixtures
- [x] 03-04-PLAN.md — Migrate test naming Batch 3 (JSON:API, search, performance)
- [x] 03-05-PLAN.md — Migrate test naming Batch 4 (variant, CNV tests)
- [x] 03-06-PLAN.md — Migrate test naming Batch 5 (classification, survival, remaining)
- [x] 03-07-PLAN.md — Finalize: remove backward-compat aliases, verify full suite

**Requirements:**
- QUAL-05: Async context manager fixtures (pre-existing)
- QUAL-06: Standardized test naming (Complete)
- QUAL-07: Consolidated conftest.py (Complete)
- QUAL-08: 60% coverage minimum (Deferred - current: 53.50%)

**Success Criteria:**
1. ✓ All fixtures use async context managers (pre-existing)
2. ✓ Test names follow `test_<feature>_<scenario>_<expected_result>`
3. ✓ Duplicate utilities consolidated in conftest.py
4. ⚠ Coverage at 53.50% (below 60% goal, deferred to future)
5. ✓ No deprecated unittest.mock patterns

**Dependencies:** Phase 1 complete

**Test Suite Summary:**
- 768 tests collected, 762+ passing
- 1 known flaky race condition test
- Coverage: 53.50% (improvement deferred)

**Files modified:**
- `backend/tests/conftest.py`
- `backend/pyproject.toml`
- All 35 test files in `backend/tests/`

---

## Phase 4: UI/UX Normalization ✓

**Goal:** Consistent design system across all views

**Status:** Complete (2026-01-20)

**GitHub Issue:** #98

**Plans:** 5 plans

Plans:
- [x] 04-01-PLAN.md — Design tokens + Vuetify theme update
- [x] 04-02-PLAN.md — Create PageHeader.vue component
- [x] 04-03-PLAN.md — Create DataTableToolbar.vue component
- [x] 04-04-PLAN.md — Migrate list views (Phenopackets, Variants, Publications)
- [x] 04-05-PLAN.md — Migrate detail views + Home page

**Requirements:**
- UIUX-01: Create design tokens file with consistent color palette (#98)
- UIUX-02: Update Vuetify theme with standardized colors (#98)
- UIUX-03: Create reusable `PageHeader.vue` component (#98)
- UIUX-04: Create reusable `DataTableToolbar.vue` component (#98)
- UIUX-05: Standardize icon usage across all views (#98)
- UIUX-06: Normalize typography hierarchy (h4/h5/h6 usage) (#98)
- UIUX-07: Standardize card styles and spacing (#98)

**Success Criteria:**
1. Design tokens file created with color palette
2. Vuetify theme updated with standardized colors
3. `PageHeader.vue` component created and used
4. `DataTableToolbar.vue` component created and used
5. Consistent icon usage across views
6. Consistent typography hierarchy
7. Consistent card styles and spacing

**Dependencies:** Phase 2 complete (config files exist)

**Files to create:**
- `frontend/src/utils/designTokens.js`
- `frontend/src/components/common/PageHeader.vue`
- `frontend/src/components/common/DataTableToolbar.vue`

**Files to modify:**
- `frontend/src/plugins/vuetify.js`
- `frontend/src/utils/aggregationConfig.js`
- `frontend/src/views/Phenopackets.vue`
- `frontend/src/views/Variants.vue`
- `frontend/src/views/Publications.vue`
- `frontend/src/views/PagePhenopacket.vue`
- `frontend/src/views/PageVariant.vue`
- `frontend/src/views/PagePublication.vue`
- `frontend/src/views/Home.vue`

---

## Phase 5: Chart Polish ✓

**Goal:** Accessible, animated charts with export functionality

**Status:** Complete (2026-01-20)

**GitHub Issues:** #135, #139, #136

**Plans:** 6 plans

Plans:
- [x] 05-01-PLAN.md — Create shared chart utilities (export, accessibility, animation, ChartExportMenu)
- [x] 05-02-PLAN.md — Add accessibility, animation, export to DonutChart
- [x] 05-03-PLAN.md — Add accessibility, animation, export to StackedBarChart
- [x] 05-04-PLAN.md — Upgrade KaplanMeierChart with accessibility, animation, PNG/CSV export
- [x] 05-05-PLAN.md — Polish VariantComparisonChart and BoxPlotChart
- [x] 05-06-PLAN.md — Human verification of all chart behaviors

**Requirements:**
- A11Y-01: Add `aria-describedby` to all chart components (#135)
- A11Y-02: Add screen reader text summaries for charts (#135)
- A11Y-03: Add pattern fills option for colorblind mode (#135) - Deferred
- A11Y-04: Test charts with screen readers (VoiceOver/NVDA) (#135)
- A11Y-05: Meet WCAG 2.1 Level A for non-text content (1.1.1) (#135)
- A11Y-06: Meet WCAG 2.1 Level A for use of color (1.4.1) (#135)
- CHART-01: Add arc tween animation to donut charts (#139)
- CHART-02: Add height tween animation to bar charts with stagger (#139)
- CHART-03: Add path drawing animation to line charts (#139)
- CHART-04: Respect `prefers-reduced-motion` media query (#139)
- CHART-05: Create `frontend/src/utils/export.js` with export utilities (#136)
- CHART-06: Create `ChartExportMenu.vue` component (#136)
- CHART-07: Add PNG export at 2x resolution (#136)
- CHART-08: Add CSV export with headers (#136)
- CHART-09: Add export button to all chart components (#136)

**Success Criteria:**
1. All charts have `aria-labelledby` with title and desc elements
2. Screen reader descriptions generated for all chart types
3. `prefers-reduced-motion` respected (animations disabled)
4. Arc tween animation on donut charts
5. Height tween animation on bar charts with stagger
6. Path drawing animation on line charts
7. PNG export at 2x resolution working
8. CSV export with snake_case headers working
9. Export menu on all chart components

**Dependencies:** Phase 4 complete (design tokens for consistency)

**Summary:**
- 6 plans executed across 3 waves
- 487 frontend tests passing (85 utility + 202 chart component + existing)
- All 5 chart components have ARIA accessibility, entry animations, and export menus
- Human verification confirmed all behaviors work correctly

**Files to create:**
- `frontend/src/utils/export.js`
- `frontend/src/utils/chartAccessibility.js`
- `frontend/src/utils/chartAnimation.js`
- `frontend/src/components/common/ChartExportMenu.vue`

**Files to modify:**
- `frontend/src/components/analyses/DonutChart.vue`
- `frontend/src/components/analyses/StackedBarChart.vue`
- `frontend/src/components/analyses/KaplanMeierChart.vue`
- `frontend/src/components/analyses/VariantComparisonChart.vue`
- `frontend/src/components/analyses/BoxPlotChart.vue`

---

## Phase 6: Backend Features & PWA

**Goal:** User tracking for aggregations and service worker caching

**GitHub Issues:** #140, #138

**Plans:** 2 plans

Plans:
- [ ] 06-01-PLAN.md — Add optional user tracking to aggregation endpoints
- [ ] 06-02-PLAN.md — Configure PWA with service worker caching

**Requirements:**
- FEAT-01: Add optional user dependency to aggregation endpoints (#140)
- FEAT-02: Log user_id for authenticated aggregation requests (#140)
- FEAT-03: Skip tracking for unauthenticated requests (per CONTEXT.md) (#140)
- FEAT-04: TODO comment already removed (verified during planning)
- PWA-01: Add vite-plugin-pwa dependency (#138)
- PWA-02: Configure service worker with workbox (#138)
- PWA-03: Cache structure files (2h8r.cif) with CacheFirst strategy (#138)
- PWA-04: Add offline fallback page (#138)

**Success Criteria:**
1. Aggregation endpoints accept optional user dependency
2. User ID logged for authenticated requests
3. Unauthenticated requests work without tracking
4. vite-plugin-pwa installed and configured
5. Service worker caches static assets
6. Structure file (2h8r.cif) cached with CacheFirst
7. Offline fallback page works

**Dependencies:** Phase 2 complete (constants defined)

**Files to create:**
- `frontend/public/offline.html`
- `frontend/public/pwa-192x192.png`
- `frontend/public/pwa-512x512.png`

**Files to modify:**
- `backend/app/auth/dependencies.py`
- `backend/app/utils/audit_logger.py`
- `backend/app/phenopackets/routers/aggregations/*.py`
- `frontend/vite.config.js`
- `frontend/package.json`

---

## Phase 7: Migration Consolidation

**Goal:** Clean alembic migration history

**GitHub Issue:** #102

**Requirements:**
- DB-01 through DB-04 (migration cleanup)

**Success Criteria:**
1. Single `001_initial_schema.py` migration exists
2. Old migrations archived in `versions/archive/`
3. Fresh database setup works with single migration
4. All indexes and constraints present
5. Production migration procedure documented

**Dependencies:** All code changes complete (Phases 1-6)

**Risk Level:** HIGH - requires backup/restore procedure

**Files to create:**
- `backend/alembic/versions/001_initial_schema.py`
- `backend/alembic/versions/archive/` (directory)

**Files to modify:**
- Move all existing migrations to archive

---

## Phase 8: E2E Testing

**Goal:** Playwright E2E test coverage for critical flows

**GitHub Issue:** #48

**Requirements:**
- TEST-01 through TEST-06 (Playwright setup and tests)

**Success Criteria:**
1. Playwright installed and configured
2. Navigation tests pass (home → phenopackets → detail)
3. Search tests pass (query, filters, results)
4. Aggregations tests pass (all charts load)
5. Variant flow tests pass (list → detail → individuals)
6. E2E tests run in CI/CD

**Dependencies:** Phase 7 complete (stable codebase to test)

**Files to create:**
- `frontend/playwright.config.js`
- `frontend/e2e/navigation.spec.js`
- `frontend/e2e/search.spec.js`
- `frontend/e2e/aggregations.spec.js`
- `frontend/e2e/variants.spec.js`

---

## Phase 9: Documentation

**Goal:** Complete user and developer documentation

**GitHub Issue:** #50

**Requirements:**
- DOCS-01 through DOCS-05 (documentation)

**Success Criteria:**
1. User guide written (getting started, features, FAQ)
2. Developer guide updated (setup, architecture, testing)
3. All v2 API endpoints documented
4. Changelog created (v2.0.0 release notes)
5. Screenshots added to documentation

**Dependencies:** Phase 8 complete (document final state)

**Files to create/modify:**
- `docs/user-guide.md`
- `docs/developer-guide.md`
- `docs/api-reference.md`
- `CHANGELOG.md`
- `README.md` (update)

---

## Execution Order Rationale

1. **Phase 1 (Pydantic):** Bug fixes first - eliminates warnings that could mask other issues
2. **Phase 2 (Components/Constants):** Code quality foundation - cleaner code makes features easier
3. **Phase 3 (Tests):** Quality assurance - ensures refactoring didn't break anything
4. **Phase 4 (UI/UX):** Visual consistency - uses config from Phase 2
5. **Phase 5 (Charts):** Chart polish - builds on UI normalization
6. **Phase 6 (Features):** New capabilities - clean codebase ready for features
7. **Phase 7 (Migrations):** High risk - do after all code changes complete
8. **Phase 8 (E2E):** Test final state - verify everything works together
9. **Phase 9 (Docs):** Document final state - accurate documentation

---

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|------------|
| 1 | Low | Well-defined deprecation fixes |
| 2 | Medium | Extensive testing of refactored components |
| 3 | Low | Test improvements don't affect production |
| 4 | Low | Visual changes, no logic changes |
| 5 | Medium | D3.js animations need careful testing |
| 6 | Medium | Service worker can break offline behavior |
| 7 | **HIGH** | Backup before migration consolidation |
| 8 | Low | Tests don't affect production |
| 9 | Low | Documentation only |

---

*Roadmap created: 2026-01-19*
*Last updated: 2026-01-20 after phase 6 planning complete*
