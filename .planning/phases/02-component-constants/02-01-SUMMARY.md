---
phase: 02-component-constants
plan: 01
subsystem: backend
tags: [python, constants, pep8, domain-values, hnf1b]

# Dependency graph
requires:
  - phase: 01-pydantic-fixes
    provides: Clean Pydantic models with ConfigDict
provides:
  - Centralized backend constants module (app/constants.py)
  - Documented domain-specific hardcoded values
  - DOMAIN_BOUNDARIES dict for protein analysis
  - CHR17Q12_REGION constants for Ensembl queries
  - CACHE_MAX_AGE_SECONDS for HTTP caching
  - VARIANT_RECODER_BATCH_SIZE for VEP API
affects: [02-02, phase-5-charts, frontend-constants]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SCREAMING_SNAKE_CASE for constants (PEP 8)"
    - "Centralized constants module separate from config"

key-files:
  created:
    - backend/app/constants.py
  modified:
    - backend/app/reference/service.py
    - backend/app/reference/router.py
    - backend/app/phenopackets/routers/aggregations/all_variants.py
    - backend/app/phenopackets/validation/variant_validator.py

key-decisions:
  - "Separate constants from config: constants.py for domain values, config.py for environment-based settings"
  - "Two domain boundary dicts: DOMAIN_BOUNDARIES (snake_case keys) and DOMAIN_BOUNDARIES_DISPLAY (human-readable keys)"

patterns-established:
  - "Pattern: Import from app.constants for hardcoded domain values"
  - "Pattern: Use SCREAMING_SNAKE_CASE with docstrings for all constants"

# Metrics
duration: 4min
completed: 2026-01-19
---

# Phase 02 Plan 01: Backend Constants Module Summary

**Centralized backend constants module with PDB structure boundaries, HNF1B gene coordinates, domain boundaries, and caching values**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-19T17:53:20Z
- **Completed:** 2026-01-19T17:56:57Z
- **Tasks:** 2/2
- **Files modified:** 5

## Accomplishments

- Created `backend/app/constants.py` with 150 lines of documented domain constants
- Extracted hardcoded values from 4 backend files into centralized imports
- Established pattern for constant organization with section headers and docstrings
- All lint checks and type checks pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create backend constants module** - `7eced1d` (feat)
2. **Task 2: Update backend files to use constants** - `f2e18a8` (refactor)

## Files Created/Modified

- `backend/app/constants.py` - New centralized constants module with:
  - PDB 2H8R structure boundaries (STRUCTURE_START, STRUCTURE_END, gap positions)
  - HNF1B gene boundaries (GRCh38 coordinates)
  - 17q12 region boundaries for Ensembl API
  - Variant classification thresholds (CNV_SIZE_THRESHOLD, VARIANT_RECODER_BATCH_SIZE)
  - DOMAIN_BOUNDARIES dict (snake_case keys for programmatic use)
  - DOMAIN_BOUNDARIES_DISPLAY dict (human-readable keys for UI)
  - CACHE_MAX_AGE_SECONDS for HTTP caching

- `backend/app/reference/service.py` - Now imports CHR17Q12_REGION_START/END
- `backend/app/reference/router.py` - Now imports CACHE_MAX_AGE_SECONDS
- `backend/app/phenopackets/routers/aggregations/all_variants.py` - Now imports DOMAIN_BOUNDARIES_DISPLAY
- `backend/app/phenopackets/validation/variant_validator.py` - Now imports VARIANT_RECODER_BATCH_SIZE

## Decisions Made

1. **Two domain boundary dicts** - Created both DOMAIN_BOUNDARIES (with snake_case keys like `pou_specific`) for programmatic use and DOMAIN_BOUNDARIES_DISPLAY (with human-readable keys like `POU-Specific Domain`) for UI/API responses. This maintains backward compatibility with existing code while providing a clean interface for analysis functions.

2. **Separate from config.py** - Constants go in constants.py, environment-based configuration stays in config.py/config.yaml. This follows the existing codebase pattern and maintains clear separation of concerns.

3. **TypedDict for type hints** - Used TypedDict for DomainBoundary to provide type safety for the domain boundary dictionaries.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Import replacement doubled suffixes** - When using `replace_all` to update variable names, the import statements also got replaced, creating names like `CACHE_MAX_AGE_SECONDS_SECONDS`. Fixed by manually correcting the import statements.

- **Pre-existing test failures** - Many tests failed due to database connection issues (infrastructure-related). These are pre-existing and not related to the constants refactoring. Verified by running lint, typecheck, and config-specific tests which all pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend constants module complete and operational
- Pattern established for frontend constants module (Plan 02-02)
- All backend files using centralized constants
- Ready for Plan 02-02 (frontend constants) and Plan 02-03 (ProteinStructure3D extraction)

---
*Phase: 02-component-constants*
*Completed: 2026-01-19*
