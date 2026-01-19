# Codebase Concerns

**Analysis Date:** 2026-01-19

## Tech Debt

**Passlib/bcrypt Compatibility Pinning:**
- Issue: `passlib` library is unmaintained and incompatible with `bcrypt>=5.0`. Pinned to `bcrypt>=3.2.0,<6.0.0`
- Files: `backend/pyproject.toml:12`
- Impact: Cannot upgrade bcrypt to latest versions; potential security updates blocked
- Fix approach: Migrate to `argon2-cffi` or direct `bcrypt` usage without passlib wrapper

**Dead Code in Database Initialization:**
- Issue: Commented-out models import code block with TODO marker
- Files: `backend/app/database.py:100-115`
- Impact: Code clarity reduced; confusion about whether models module should exist
- Fix approach: Remove commented code block entirely or create the models module if needed

**In-Memory Task Tracking for Admin Sync:**
- Issue: Using dict `_sync_tasks` for task state instead of persistent storage
- Files: `backend/app/api/admin_endpoints.py:97`
- Impact: Task state lost on server restart; not suitable for multi-instance deployment
- Fix approach: Migrate to Redis-backed task queue (Celery/RQ) or persist to database

**Frontend Variant Limit Hardcoding:**
- Issue: `MAX_VARIANTS_FOR_PRIORITY_SORT: 1000` will break when database exceeds this limit
- Files: `frontend/src/config/app.js:36`
- Impact: Priority sorting, gene visualizations, and CNV displays fail silently beyond 1000 variants
- Fix approach: Implement server-side sorting with cursor pagination (see `docs/issues/issue-93-incremental-variant-loading.md`)

**Multiple Type Ignores and Noqa Comments:**
- Issue: 25+ type ignores and noqa directives scattered across codebase
- Files: `backend/app/reference/router.py`, `backend/app/variants/service.py`, `backend/app/core/mv_cache.py`, others
- Impact: Type safety holes; potential runtime errors hidden
- Fix approach: Address underlying type issues; document remaining legitimate suppressions

**Empty Exception Handlers:**
- Issue: Multiple `pass` statements in exception handlers and abstract method stubs
- Files: `backend/app/phenopackets/routers/crud.py:894`, `backend/app/phenopackets/routers/aggregations/survival_handlers.py:49-71`
- Impact: Silent failures possible; swallowed exceptions hide bugs
- Fix approach: Add proper logging or re-raise with context

## Known Bugs

**Zoom Functionality Broken in Visualizations:**
- Symptoms: D3.js zoom controls present but non-functional in gene/protein views
- Files: `frontend/src/components/gene/HNF1BGeneVisualization.vue`, `frontend/src/components/gene/HNF1BProteinVisualization.vue`
- Trigger: Attempt to zoom or pan on variant visualizations
- Workaround: None documented
- Reference: `docs/issues/issue-92-zoom-functionality-broken.md`

**Variant Search Not Working:**
- Symptoms: Search input exists but queries don't filter results
- Files: `frontend/src/views/Variants.vue` (544 lines)
- Trigger: Enter search query in variants table
- Workaround: None documented
- Reference: `docs/issues/issue-90-fix-variant-search.md`

**HPO Proxy Sometimes Returns Empty:**
- Symptoms: HPO term search occasionally returns empty results
- Files: `backend/app/hpo_proxy.py:206-211`
- Trigger: Rate limiting from upstream OLS API
- Workaround: Retry request; check Redis cache status
- Reference: `docs/TODO.md:101`

**Search Endpoint Timeout with Large Datasets:**
- Symptoms: Complex queries may timeout
- Files: `backend/app/search/services.py` (513 lines)
- Trigger: Complex full-text search queries against large dataset
- Workaround: Simplify query; use pagination

## Security Considerations

**Default Admin Credentials in Repository:**
- Risk: Default password `ChangeMe!Admin2025` documented in `.env.example` and CLAUDE.md
- Files: `backend/.env.example:15`, `CLAUDE.md:528`
- Current mitigation: Warning to change password after first login
- Recommendations: Remove default password from docs; generate random password on first setup

**JWT Secret Placeholder:**
- Risk: Placeholder `CHANGE_ME_TO_SECURE_RANDOM_STRING` if not changed leads to predictable tokens
- Files: `backend/.env.example:8`
- Current mitigation: Application exits if JWT_SECRET is empty (documented in CLAUDE.md:186)
- Recommendations: Auto-generate secret on first run if not set

**SQL Query String Formatting:**
- Risk: One instance of f-string SQL query
- Files: `backend/app/core/mv_cache.py:123`
- Current mitigation: `# noqa: S608` acknowledges risk; view_name is from config, not user input
- Recommendations: Use parameterized queries or verify view_name is from trusted source only

**CORS Configuration:**
- Risk: CORS settings need review for production origins
- Files: `backend/app/main.py` (presumed), `docs/TODO.md:128`
- Current mitigation: Environment-based configuration
- Recommendations: Implement specific origin allowlist for production

## Performance Bottlenecks

**Offset Pagination O(n) Performance:**
- Problem: Offset pagination requires COUNT query (~150ms per request)
- Files: `backend/app/phenopackets/routers/crud.py`
- Cause: COUNT(*) scans entire table for total count
- Improvement path: Use cursor pagination for large datasets (already supported); remove total count for cursor mode

**Large File Complexity:**
- Problem: Multiple files exceed 500-line guideline
- Files:
  - `backend/tests/test_variant_validator_enhanced.py` (1660 lines)
  - `backend/tests/test_comparisons.py` (1467 lines)
  - `backend/app/api/admin_endpoints.py` (1140 lines)
  - `backend/app/phenopackets/routers/aggregations/survival_handlers.py` (1055 lines)
  - `frontend/src/components/gene/HNF1BGeneVisualization.vue` (1421 lines)
  - `frontend/src/components/gene/ProteinStructure3D.vue` (1130 lines)
  - `frontend/src/components/gene/HNF1BProteinVisualization.vue` (1063 lines)
- Cause: Feature creep; insufficient refactoring
- Improvement path: Extract handlers/components into smaller focused modules

**External API Rate Limiting:**
- Problem: VEP and PubMed APIs have rate limits that can slow batch operations
- Files: `backend/app/variants/service.py`, `backend/app/publications/service.py`
- Cause: External dependency throttling
- Improvement path: Implement request queuing; pre-fetch and cache common queries

## Fragile Areas

**Survival Analysis Handlers:**
- Files: `backend/app/phenopackets/routers/aggregations/survival_handlers.py` (1055 lines)
- Why fragile: Complex SQL generation with multiple abstract base class implementations; many noqa suppressions
- Safe modification: Ensure test coverage for each handler type before changes
- Test coverage: Some tests exist but handler-specific coverage unclear

**Variant Validation Regex Patterns:**
- Files: `backend/app/phenopackets/validation/variant_validator.py` (966 lines)
- Why fragile: Complex regex for HGVS, VCF, SPDI parsing; edge cases in variant formats
- Safe modification: Add test case for new variant format before implementing parser change
- Test coverage: `backend/tests/test_variant_validator_enhanced.py` (1660 lines) - good coverage

**Gene Visualization Components:**
- Files: `frontend/src/components/gene/HNF1BGeneVisualization.vue` (1421 lines)
- Why fragile: D3.js integration with Vue reactivity; zoom state management; complex SVG manipulation
- Safe modification: Test zoom, pan, and variant display after any D3 changes
- Test coverage: Minimal - `frontend/tests/unit/components/` has only 3 test files for 41 components

## Scaling Limits

**Variant Count Limit:**
- Current capacity: 1000 variants for priority sorting/visualization
- Limit: Frontend breaks silently when exceeding MAX_VARIANTS_FOR_PRIORITY_SORT
- Scaling path: Implement server-side sorting; cursor pagination for variants endpoint

**Database Connection Pool:**
- Current capacity: pool_size=20, max_overflow=0
- Limit: 20 concurrent database connections
- Scaling path: Increase pool_size in `backend/config.yaml`; consider PgBouncer for production

## Dependencies at Risk

**passlib (Unmaintained):**
- Risk: No updates since 2020; incompatible with modern bcrypt
- Impact: Security patches unavailable; upgrade path blocked
- Migration plan: Replace with direct bcrypt or argon2-cffi

**ga4gh.vrs and bioutils (No Type Stubs):**
- Risk: Libraries lack py.typed marker and type stubs
- Impact: Type safety holes in variant processing code
- Migration plan: Wait for upstream type annotations or create local stubs
- Reference: `backend/pyproject.toml:83-86`

## Missing Critical Features

**Test Coverage Metrics:**
- Problem: No test coverage reporting configured
- Blocks: Unable to measure code coverage; quality gates incomplete
- Reference: `docs/TODO.md:44`

**Rate Limiting for API:**
- Problem: No rate limiting implemented on public endpoints
- Blocks: API abuse prevention; production hardening
- Reference: `docs/TODO.md:54`

**Error Tracking:**
- Problem: No Sentry or equivalent error tracking
- Blocks: Production monitoring; proactive bug detection
- Reference: `docs/TODO.md:57`

**Forgot Password Flow:**
- Problem: TODO in login view, flow not implemented
- Blocks: User self-service password recovery
- Files: `frontend/src/views/Login.vue:159`

## Test Coverage Gaps

**Frontend Component Tests:**
- What's not tested: 38 of 41 Vue components have no unit tests (only 3 test files exist)
- Files: `frontend/src/components/**/*.vue`
- Risk: UI regressions undetected; component behavior changes break silently
- Priority: High - visualization components are critical and complex

**Backend Integration Tests:**
- What's not tested: Some aggregation endpoints, survival analysis edge cases
- Files: `backend/app/phenopackets/routers/aggregations/*.py`
- Risk: SQL query generation errors; statistical calculation bugs
- Priority: Medium - covered by manual testing but automated coverage needed

**E2E Tests:**
- What's not tested: Critical user flows (login, phenopacket creation, search)
- Files: `frontend/tests/e2e/` (directory exists but sparse)
- Risk: Integration failures between frontend and backend undetected
- Priority: Medium - manual QA covers most flows currently

**Tests Use Same Database as Development:**
- What's not tested: True isolation of test data
- Files: `backend/tests/conftest.py:36-37` - comment states "using same database as development for now"
- Risk: Test pollution; flaky tests; data corruption
- Priority: High - should use separate test database or transactions

---

*Concerns audit: 2026-01-19*
