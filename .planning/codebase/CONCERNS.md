# Codebase Concerns

**Analysis Date:** 2026-01-19

## Tech Debt

**Dead Code in Database Initialization:**
- Issue: Commented-out code block for importing models that never existed
- Files: `backend/app/database.py:100-115`
- Impact: Minor - confusing for maintainers, no runtime effect
- Fix approach: Remove the commented TODO block entirely since models are defined inline

**Deprecated Pagination Functions:**
- Issue: Legacy `pageToSkipLimit()` function marked deprecated but still exported
- Files: `backend/app/utils/pagination.py:12`, `frontend/src/api/index.js:119-128`
- Impact: Medium - new code might use outdated patterns
- Fix approach: Remove deprecated functions after ensuring no usages remain, or add deprecation warnings at runtime

**Hardcoded Exon Data Fallback:**
- Issue: HNF1B exon data is hardcoded as fallback when JSON fails to load
- Files: `backend/scripts/import_hnf1b_reference_data.py:251-274`, `backend/app/reference/service.py:344`
- Impact: Low - ensures functionality but duplicates data
- Fix approach: Remove fallback once JSON data loading is stable, or version-lock the fallback data

**Search Vector Trigger with BUGGY Comments:**
- Issue: Migration file contains comments marked "BUGGY" for field names
- Files: `backend/alembic/versions/f74b2759f2a9_fix_search_vector_trigger_camelcase.py:115-125`
- Impact: Low - comments indicate historical fix, but migration itself works
- Fix approach: Clarify comments to explain what was buggy and how it was fixed

## Known Bugs

**Forgot Password Not Implemented:**
- Symptoms: Clicking "Forgot Password" shows alert instead of actual functionality
- Files: `frontend/src/views/Login.vue:159-162`
- Trigger: User clicks forgot password link
- Workaround: Admin must manually reset passwords

**D3.js Zoom Non-functional in Visualizations:**
- Symptoms: Zoom controls present but zoom/pan doesn't work
- Files: `frontend/src/components/gene/HNF1BGeneVisualization.vue`, `frontend/src/components/gene/HNF1BProteinVisualization.vue`
- Trigger: User attempts to zoom/pan in gene or protein visualizations
- Workaround: None documented
- Reference: `docs/issues/issue-92-zoom-functionality-broken.md`

## Security Considerations

**Default Admin Password in Code:**
- Risk: Default password `ChangeMe!Admin2025` is in source code
- Files: `backend/app/core/config.py:286`, `backend/.env.example:15`
- Current mitigation: Documentation warns to change immediately
- Recommendations: Add runtime warning if default password is detected, or require password change on first login

**Console.log Usage in Production Code:**
- Risk: Sensitive data could leak to browser console
- Files: `frontend/src/utils/searchHistory.js:13,37,51`, `frontend/src/components/SearchCard.vue:107`
- Current mitigation: Project has logService with PII redaction
- Recommendations: Replace remaining console.* calls with window.logService

**JWT Secret Validation:**
- Risk: Application fails fast if JWT_SECRET is empty (good)
- Files: `backend/app/core/config.py:301-320`
- Current mitigation: Validator raises ValueError on startup
- Recommendations: Good - no changes needed

**SQL Injection Prevention:**
- Risk: JSONB queries could be vulnerable
- Files: Various - `backend/app/variants/service.py:83`, `backend/app/publications/service.py:80`
- Current mitigation: Input validation with regex patterns, parameterized queries
- Recommendations: Security is well-handled; continue pattern of validating all user input

## Performance Bottlenecks

**Client-side Variant Priority Sorting:**
- Problem: All variants (up to MAX_VARIANTS_FOR_PRIORITY_SORT=1000) fetched for client-side sorting
- Files: `frontend/src/config/app.js:13-36`
- Cause: Priority sorting not implemented server-side; client fetches all to sort locally
- Improvement path: Implement server-side priority sorting in backend API

**COUNT Query on Large Datasets:**
- Problem: Offset pagination uses COUNT query on every request (~150ms overhead)
- Files: `backend/app/phenopackets/routers/crud.py:114-123`
- Cause: JSON:API requires total count for pagination links
- Improvement path: Use cursor pagination exclusively, or cache count results

**Materialized View Refresh:**
- Problem: Views refreshed on every data import, not lazy
- Files: `backend/app/database.py:147-205`
- Cause: CONCURRENTLY refresh still blocks briefly
- Improvement path: Use background task for refresh, or refresh only changed views

## Fragile Areas

**Large Vue Components:**
- Files:
  - `frontend/src/components/gene/HNF1BGeneVisualization.vue` (1421 lines)
  - `frontend/src/components/gene/ProteinStructure3D.vue` (1130 lines)
  - `frontend/src/components/gene/HNF1BProteinVisualization.vue` (1063 lines)
  - `frontend/src/views/PageVariant.vue` (1032 lines)
- Why fragile: Large files are harder to test, maintain, and reason about
- Safe modification: Extract reusable logic to composables, split into sub-components
- Test coverage: Limited unit tests for visualization components

**Large Backend Modules:**
- Files:
  - `backend/app/api/admin_endpoints.py` (1140 lines)
  - `backend/app/phenopackets/routers/aggregations/survival_handlers.py` (1055 lines)
  - `backend/app/phenopackets/routers/aggregations/survival.py` (1025 lines)
  - `backend/app/phenopackets/routers/crud.py` (1002 lines)
- Why fragile: Violates single responsibility, hard to unit test
- Safe modification: Extract handler classes, use strategy pattern
- Test coverage: Good test coverage for crud.py, survival modules have dedicated tests

**External API Dependencies:**
- Files: `backend/app/variants/service.py`, `backend/app/hpo_proxy.py`
- Why fragile: VEP API rate limits (15 req/sec), OLS API for HPO terms
- Safe modification: Always use retry logic, cache responses
- Test coverage: Tests mock external APIs

## Scaling Limits

**Variant Count Hard Limit:**
- Current capacity: ~864 variants in database
- Limit: MAX_VARIANTS_FOR_PRIORITY_SORT = 1000
- Scaling path: Implement server-side priority sorting, increase limit if needed
- Reference: `frontend/src/config/app.js:13-36`

**Database Connection Pool:**
- Current capacity: pool_size from config.yaml (default: 5)
- Limit: max_overflow setting determines burst capacity
- Scaling path: Increase pool_size for higher concurrency
- Files: `backend/app/database.py:19-35`

**VEP Batch Size:**
- Current capacity: 50 variants per batch
- Limit: Ensembl recommends max 200, but 50 is more reliable
- Scaling path: Increase batch_size in config if VEP becomes more reliable
- Files: `backend/app/core/config.py:83`

## Dependencies at Risk

**Type Ignore Pragmas:**
- Risk: Type safety bypassed in several locations
- Files:
  - `backend/app/reference/router.py:327,439` (type: ignore)
  - `backend/app/phenopackets/routers/comparisons.py:104` (type: ignore)
  - `backend/app/core/retry.py:178` (type: ignore)
  - `backend/app/reference/schemas.py:145` (type: ignore)
- Impact: TypeScript/mypy can't catch errors in these areas
- Migration plan: Fix underlying type issues, remove ignores

**noqa Overrides for Linting:**
- Risk: Linting rules bypassed
- Files:
  - `backend/app/api/admin_endpoints.py:8` (noqa: E501 - line length)
  - `backend/scripts/sync_publication_metadata.py:28` (noqa: E501)
  - `backend/app/phenopackets/routers/comparisons.py:8` (noqa: E501, F821)
- Impact: Code style inconsistencies, potential unused imports
- Migration plan: Refactor long SQL strings, fix unused variable references

## Missing Critical Features

**Password Reset Flow:**
- Problem: No mechanism for users to reset forgotten passwords
- Blocks: Users locked out if password forgotten
- Reference: `frontend/src/views/Login.vue:159`

**Variant Count Monitoring:**
- Problem: No endpoint to return total variant count for limit monitoring
- Blocks: Cannot warn users when approaching MAX_VARIANTS limit
- Reference: `frontend/src/config/app.js:31-32` (TODO comments)

## Test Coverage Gaps

**Frontend Visualization Components:**
- What's not tested: D3.js rendering, zoom behavior, SVG generation
- Files:
  - `frontend/src/components/gene/HNF1BGeneVisualization.vue`
  - `frontend/src/components/gene/HNF1BProteinVisualization.vue`
  - `frontend/src/components/gene/ProteinStructure3D.vue`
  - `frontend/src/components/analyses/*.vue`
- Risk: Visualization bugs go unnoticed until manual testing
- Priority: Medium - core feature but complex to test

**Frontend Unit Test Count:**
- What's not tested: Only 10 spec files exist for entire frontend
- Files: `frontend/tests/unit/**/*.spec.js`
- Risk: Most Vue components, composables, and utilities lack tests
- Priority: High - frontend code changes frequently

**Backend-Frontend Integration:**
- What's not tested: E2E flows from UI to database
- Files: `frontend/tests/e2e/` (only 2 spec files)
- Risk: Integration issues discovered late
- Priority: Medium - manual testing catches most issues

**Empty Return Paths:**
- What's not tested: Error paths returning empty arrays/dicts
- Files: Multiple `return []` and `return {}` in backend services
- Risk: Silent failures not properly handled
- Priority: Low - most have corresponding error handling

---

*Concerns audit: 2026-01-19*
