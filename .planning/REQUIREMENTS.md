# Requirements: HNF1B Database Final Polish

**Defined:** 2026-01-19
**Core Value:** Ship a production-quality codebase with improved maintainability, accessibility, and documentation

## v1 Requirements

Requirements grouped by logical category, derived from GitHub issues.

### Code Quality - Backend

- [x] **QUAL-01**: Fix Pydantic `regex` deprecation by replacing with `pattern` in all Query parameters (#134)
- [x] **QUAL-02**: Fix Pydantic `example` deprecation by replacing with `examples=[]` in all Field definitions (#134)
- [x] **QUAL-03**: Replace class-based `Config` with `ConfigDict` in all Pydantic models (#134)
- [x] **QUAL-04**: Create `backend/app/constants.py` with documented named constants (#137)
- [x] **QUAL-05**: Modernize test suite with async context manager fixtures (#94) - Already uses @pytest_asyncio.fixture with async def
- [x] **QUAL-06**: Standardize test naming to `test_<feature>_<scenario>_<expected_result>` (#94)
- [x] **QUAL-07**: Consolidate test utilities in `conftest.py` (#94)
- [ ] **QUAL-08**: Achieve 60% test coverage minimum (#94) - DEFERRED: Current 53.50%, improvement to future milestone

### Code Quality - Frontend

- [x] **QUAL-09**: Extract ProteinStructure3D.vue into sub-components (<500 lines each) (#133)
- [x] **QUAL-10**: Create `StructureViewer.vue` for NGL.js canvas (#133)
- [x] **QUAL-11**: Create `StructureControls.vue` for representation toggles (#133)
- [x] **QUAL-12**: Create `VariantPanel.vue` for variant list/selection (#133)
- [x] **QUAL-13**: Create `DistanceDisplay.vue` for distance alerts and legends (#133)
- [x] **QUAL-14**: Create `frontend/src/constants/` module with documented constants (#137)
- [x] **QUAL-15**: Create `frontend/src/config/` with centralized configuration (#91) - Already exists: `app.js`, `navigationItems.js`
- [x] **QUAL-16**: Move visualization dimensions to config (#91) - Already in `VIZ_CONFIG`
- [x] **QUAL-17**: Move API timeouts to config (#91)
- [x] **QUAL-18**: Add config validation on app startup (#91)

### UI/UX Normalization

- [x] **UIUX-01**: Create design tokens file with consistent color palette (#98)
- [x] **UIUX-02**: Update Vuetify theme with standardized colors (#98)
- [x] **UIUX-03**: Create reusable `PageHeader.vue` component (#98)
- [x] **UIUX-04**: Create reusable `DataTableToolbar.vue` component (#98)
- [x] **UIUX-05**: Standardize icon usage across all views (#98)
- [x] **UIUX-06**: Normalize typography hierarchy (h4/h5/h6 usage) (#98)
- [x] **UIUX-07**: Standardize card styles and spacing (#98)

### Accessibility

- [x] **A11Y-01**: Add `aria-describedby` to all chart components (#135)
- [x] **A11Y-02**: Add screen reader text summaries for charts (#135)
- [ ] **A11Y-03**: Add pattern fills option for colorblind mode (#135) - DEFERRED
- [x] **A11Y-04**: Test charts with screen readers (VoiceOver/NVDA) (#135)
- [x] **A11Y-05**: Meet WCAG 2.1 Level A for non-text content (1.1.1) (#135)
- [x] **A11Y-06**: Meet WCAG 2.1 Level A for use of color (1.4.1) (#135)

### Chart Enhancements

- [x] **CHART-01**: Add arc tween animation to donut charts (#139)
- [x] **CHART-02**: Add height tween animation to bar charts with stagger (#139)
- [x] **CHART-03**: Add path drawing animation to line charts (#139)
- [x] **CHART-04**: Respect `prefers-reduced-motion` media query (#139)
- [x] **CHART-05**: Create `frontend/src/utils/export.js` with export utilities (#136)
- [x] **CHART-06**: Create `ChartExportMenu.vue` component (#136)
- [x] **CHART-07**: Add PNG export at 2x resolution (#136)
- [x] **CHART-08**: Add CSV export with headers (#136)
- [x] **CHART-09**: Add export button to all chart components (#136)

### Backend Features

- [x] **FEAT-01**: Add optional user dependency to aggregation endpoints (#140)
- [x] **FEAT-02**: Log user_id for authenticated aggregation requests (#140)
- [x] **FEAT-03**: Skip tracking for unauthenticated requests (per CONTEXT.md - no anonymous tracking) (#140)
- [x] **FEAT-04**: Remove TODO comment in aggregations.py:1247 (#140) - N/A, already removed during planning

### PWA/Caching

- [x] **PWA-01**: Add `vite-plugin-pwa` dependency (#138)
- [x] **PWA-02**: Configure service worker with workbox (#138)
- [x] **PWA-03**: Cache structure files (2h8r.cif) with CacheFirst strategy (#138)
- [x] **PWA-04**: Add offline fallback page (#138)

### Database Maintenance

- [ ] **DB-01**: Create `001_initial_schema.py` merged migration (#102)
- [ ] **DB-02**: Archive old migrations in `versions/archive/` (#102)
- [ ] **DB-03**: Verify fresh database setup with single migration (#102)
- [ ] **DB-04**: Document production migration procedure (#102)

### Testing

- [ ] **TEST-01**: Install and configure Playwright (#48)
- [ ] **TEST-02**: Add navigation E2E tests (home -> phenopackets -> detail) (#48)
- [ ] **TEST-03**: Add search E2E tests (query, filters, results) (#48)
- [ ] **TEST-04**: Add aggregations E2E tests (all charts load) (#48)
- [ ] **TEST-05**: Add variant flow E2E tests (list -> detail -> individuals) (#48)
- [ ] **TEST-06**: Configure E2E tests in CI/CD (#48)

### Documentation

- [ ] **DOCS-01**: Write user guide (getting started, features, FAQ) (#50)
- [ ] **DOCS-02**: Update developer guide (setup, architecture, testing) (#50)
- [ ] **DOCS-03**: Document all v2 API endpoints (#50)
- [ ] **DOCS-04**: Create changelog (v2.0.0 release notes) (#50)
- [ ] **DOCS-05**: Add screenshots to documentation (#50)

## v2 Requirements

Deferred to future milestone. Not in current scope.

- Real-time notifications for data updates
- Advanced audit logging dashboard
- Performance monitoring integration

## Out of Scope

| Feature | Reason |
|---------|--------|
| New clinical features | This milestone is polish only |
| Major database schema changes | Risk to production data |
| Major UI redesign | Only normalizing existing patterns |
| API endpoint changes | Only deprecation fixes |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| QUAL-01 | Phase 1 | Complete |
| QUAL-02 | Phase 1 | Complete |
| QUAL-03 | Phase 1 | Complete |
| QUAL-04 | Phase 2 | Complete |
| QUAL-05 | Phase 3 | Complete (pre-existing) |
| QUAL-06 | Phase 3 | Complete |
| QUAL-07 | Phase 3 | Complete |
| QUAL-08 | Phase 3 | Deferred (53.50% coverage) |
| QUAL-09 | Phase 2 | Complete |
| QUAL-10 | Phase 2 | Complete |
| QUAL-11 | Phase 2 | Complete |
| QUAL-12 | Phase 2 | Complete |
| QUAL-13 | Phase 2 | Complete |
| QUAL-14 | Phase 2 | Complete |
| QUAL-15 | Phase 2 | Complete (pre-existing) |
| QUAL-16 | Phase 2 | Complete (pre-existing) |
| QUAL-17 | Phase 2 | Complete |
| QUAL-18 | Phase 2 | Complete |
| UIUX-01 | Phase 4 | Complete |
| UIUX-02 | Phase 4 | Complete |
| UIUX-03 | Phase 4 | Complete |
| UIUX-04 | Phase 4 | Complete |
| UIUX-05 | Phase 4 | Complete |
| UIUX-06 | Phase 4 | Complete |
| UIUX-07 | Phase 4 | Complete |
| A11Y-01 | Phase 5 | Complete |
| A11Y-02 | Phase 5 | Complete |
| A11Y-03 | Phase 5 | Deferred |
| A11Y-04 | Phase 5 | Complete |
| A11Y-05 | Phase 5 | Complete |
| A11Y-06 | Phase 5 | Complete |
| CHART-01 | Phase 5 | Complete |
| CHART-02 | Phase 5 | Complete |
| CHART-03 | Phase 5 | Complete |
| CHART-04 | Phase 5 | Complete |
| CHART-05 | Phase 5 | Complete |
| CHART-06 | Phase 5 | Complete |
| CHART-07 | Phase 5 | Complete |
| CHART-08 | Phase 5 | Complete |
| CHART-09 | Phase 5 | Complete |
| FEAT-01 | Phase 6 | Complete |
| FEAT-02 | Phase 6 | Complete |
| FEAT-03 | Phase 6 | Complete |
| FEAT-04 | Phase 6 | Complete (N/A) |
| PWA-01 | Phase 6 | Complete |
| PWA-02 | Phase 6 | Complete |
| PWA-03 | Phase 6 | Complete |
| PWA-04 | Phase 6 | Complete |
| DB-01 | Phase 7 | Pending |
| DB-02 | Phase 7 | Pending |
| DB-03 | Phase 7 | Pending |
| DB-04 | Phase 7 | Pending |
| TEST-01 | Phase 8 | Pending |
| TEST-02 | Phase 8 | Pending |
| TEST-03 | Phase 8 | Pending |
| TEST-04 | Phase 8 | Pending |
| TEST-05 | Phase 8 | Pending |
| TEST-06 | Phase 8 | Pending |
| DOCS-01 | Phase 9 | Pending |
| DOCS-02 | Phase 9 | Pending |
| DOCS-03 | Phase 9 | Pending |
| DOCS-04 | Phase 9 | Pending |
| DOCS-05 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 53 total
- Mapped to phases: 53
- Unmapped: 0
- Pre-existing (complete): 2 (QUAL-15, QUAL-16)

---
*Requirements defined: 2026-01-19*
*Last updated: 2026-01-20 - Phase 6 complete (FEAT-01 through FEAT-04, PWA-01 through PWA-04 complete)*
