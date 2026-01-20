---
phase: 06-backend-features-pwa
plan: 01
subsystem: api
tags: [auth, audit-logging, gdpr, aggregation, fastapi, jwt]

# Dependency graph
requires:
  - phase: 01-pydantic-deprecation
    provides: ConfigDict pattern for Pydantic models
provides:
  - get_current_user_optional dependency for optional auth
  - log_aggregation_access function for audit logging
  - Optional user tracking on all aggregation endpoints
affects: [documentation, monitoring, compliance]

# Tech tracking
tech-stack:
  added: []
  patterns: [optional-auth-dependency, gdpr-compliant-audit-logging]

key-files:
  created: []
  modified:
    - backend/app/auth/dependencies.py
    - backend/app/utils/audit_logger.py
    - backend/app/phenopackets/routers/aggregations/common.py
    - backend/app/phenopackets/routers/aggregations/summary.py
    - backend/app/phenopackets/routers/aggregations/features.py
    - backend/app/phenopackets/routers/aggregations/diseases.py
    - backend/app/phenopackets/routers/aggregations/demographics.py
    - backend/app/phenopackets/routers/aggregations/variants.py
    - backend/app/phenopackets/routers/aggregations/publications.py
    - backend/app/phenopackets/routers/aggregations/all_variants.py
    - backend/app/phenopackets/routers/aggregations/survival.py

key-decisions:
  - "Only log user_id (integer) not email for GDPR compliance"
  - "Return None for any auth failure in optional dependency"
  - "Skip tracking entirely for unauthenticated requests"

patterns-established:
  - "Optional auth pattern: Use HTTPBearer(auto_error=False) + silent exception handling"
  - "Audit log format: {event, timestamp, user_id, endpoint} for AGGREGATION_ACCESS"

# Metrics
duration: 15min
completed: 2026-01-20
---

# Phase 6 Plan 1: User Tracking for Aggregations Summary

**Optional user tracking for all 15 aggregation endpoints with GDPR-compliant audit logging (user_id only)**

## Performance

- **Duration:** 15 min
- **Started:** 2026-01-20T01:00:00Z
- **Completed:** 2026-01-20T01:15:00Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Created `get_current_user_optional` dependency that returns Optional[User] without raising 401
- Added `log_aggregation_access` function for structured audit logging with GDPR compliance
- Updated all 15 aggregation endpoints to accept optional Authorization header
- Authenticated requests now log user_id, timestamp, and endpoint to audit trail
- Unauthenticated requests continue to work without any tracking

## Task Commits

Each task was committed atomically:

1. **Task 1: Create optional auth dependency and audit logging function** - `c84f89c` (feat)
2. **Task 2: Add optional user tracking to all aggregation endpoints** - `228d8b2` (feat)

## Files Created/Modified

- `backend/app/auth/dependencies.py` - Added get_current_user_optional dependency and optional_security HTTPBearer
- `backend/app/utils/audit_logger.py` - Added log_aggregation_access function for AGGREGATION_ACCESS events
- `backend/app/phenopackets/routers/aggregations/common.py` - Re-exported auth and audit dependencies
- `backend/app/phenopackets/routers/aggregations/summary.py` - Added user tracking to get_summary_statistics
- `backend/app/phenopackets/routers/aggregations/features.py` - Added user tracking to aggregate_by_feature
- `backend/app/phenopackets/routers/aggregations/diseases.py` - Added user tracking to aggregate_by_disease, aggregate_kidney_stages
- `backend/app/phenopackets/routers/aggregations/demographics.py` - Added user tracking to aggregate_sex_distribution, aggregate_age_of_onset
- `backend/app/phenopackets/routers/aggregations/variants.py` - Added user tracking to aggregate_variant_pathogenicity, aggregate_variant_types
- `backend/app/phenopackets/routers/aggregations/publications.py` - Added user tracking to 4 publication endpoints
- `backend/app/phenopackets/routers/aggregations/all_variants.py` - Added user tracking to aggregate_all_variants
- `backend/app/phenopackets/routers/aggregations/survival.py` - Added user tracking to get_survival_data

## Decisions Made

1. **Use user_id (integer) not email in audit logs** - GDPR compliance requires minimizing PII in logs. User ID is sufficient for audit trail and usage analytics.

2. **Return None for any auth failure** - The optional dependency silently handles invalid/expired tokens by returning None instead of raising exceptions. This ensures unauthenticated and authentication-failed requests are treated identically.

3. **Skip tracking entirely for anonymous users** - Per CONTEXT.md requirements, anonymous users are not tracked at all. No "anonymous" placeholder in logs.

4. **Log at start of endpoint before DB queries** - Ensures access is logged even if the endpoint fails partway through.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Duplicate Optional import warning** - Fixed by removing redundant `from typing import Optional` when importing from common.py. This was a minor linting issue caught by ruff.

## Next Phase Readiness

- Backend user tracking infrastructure complete
- Ready for Phase 6 Plan 2: PWA and Service Worker implementation
- No blockers

---
*Phase: 06-backend-features-pwa*
*Completed: 2026-01-20*
