# HNF1B-API Refactoring & Optimization Action Plan

**Status:** Phase 1B COMPLETE (SQL Centralization) ✅
**Created:** 2025-12-06
**Updated:** 2025-12-07
**Priority:** Critical
**Principles:** DRY, KISS, SOLID, Configuration-as-Code

---

## 🔍 Senior Code Review Findings (Validated)

### Finding 1: "Shadow Config" Trap ⚠️ HIGH PRIORITY

**Issue:** Two configuration files exist, causing import confusion and potential config drift.

| File | Purpose | Status |
|------|---------|--------|
| `app/config.py` (85 lines) | Legacy pydantic-settings | ❌ DELETE |
| `app/core/config.py` (394 lines) | New YAML-backed config | ✅ KEEP |

**Files importing OLD config (MUST FIX):**
```
scripts/import_hnf1b_reference_data.py:33
scripts/import_chr17q12_genes.py:30
scripts/create_admin_user.py:14
scripts/add_grch37_assembly.py:22
tests/test_config.py:7
tests/conftest.py:12
```

### Finding 2: "Pattern Divergence" (DRY Violation)

**Issue:** `variant_search_validation.py` defines local patterns (lines 18-46) that duplicate `app/core/patterns.py`.

| Location | Patterns | Status |
|----------|----------|--------|
| `app/core/patterns.py` | VCF, HGVS, HG38, PMID, HPO | ✅ Source of truth |
| `app/phenopackets/variant_search_validation.py` | HGVS_PATTERNS, HG38_PATTERN | ❌ Duplicate (lines 18-46) |

**Risk:** Bug fix in `patterns.py` won't propagate to `variant_search_validation.py`.

### Finding 3: Publications Service Hardcoded Config

**Issue:** `publications/service.py` has hardcoded values that should use `settings.external_apis.pubmed`.

```python
# Lines 25-36 in publications/service.py (REMOVE)
PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
API_VERSION = "2.0"
MAX_REQUESTS_PER_SECOND = 10  # or 3
timeout = aiohttp.ClientTimeout(total=5)  # line 246

# Already exists in app/core/config.py
settings.external_apis.pubmed.base_url
settings.external_apis.pubmed.timeout_seconds
settings.rate_limiting.pubmed.requests_per_second_with_key
```

### Finding 4: SQL Logic Duplication

**Issue:** Variant type classification SQL exists in 3 places with overlapping logic.

| File | Constant | Lines | Purpose |
|------|----------|-------|---------|
| `survival.py` | `VARIANT_TYPE_CLASSIFICATION_SQL` | ~70 | CNV/Truncating/Non-truncating |
| `variants.py` | `VARIANT_TYPE_CASE` | ~60 | SNV/Deletion/Duplication/etc. |
| `all_variants.py` | `STRUCTURAL_TYPE_CASE` | ~45 | Structural type detection |

**Recommendation:** Create `aggregations/sql_fragments.py` to centralize SQL logic.

---

## Implementation Status Summary

| Section | Status | Notes |
|---------|--------|-------|
| 1. Unified Configuration System | ✅ DONE | `app/config.py` deleted, all imports unified |
| 2. Caching Architecture | ✅ DONE | Redis + in-memory fallback |
| 3. Database Optimization | ⚠️ PARTIAL | Views created, endpoints NOT updated |
| 4. Code Consolidation (DRY) | ✅ DONE | patterns.py universally used + 118 tests |
| 5. Security Improvements | ⚠️ PARTIAL | JWT validation done, admin pw pending |
| 6. Aggregations Modularization | ✅ DONE | 2971 → 2875 lines across 10 modules |

---

## Phase 1A: Code Cleanup Sprint (Immediate - THIS PR)

### Task 1.1: Kill Legacy Config ⚠️ CRITICAL

**Goal:** Remove `app/config.py` and migrate all imports to `app/core/config`.

**Steps:** ✅ ALL COMPLETE
1. [x] Update `scripts/import_hnf1b_reference_data.py:33`
   ```python
   # Before
   from app.config import settings
   # After
   from app.core.config import settings
   ```
2. [x] Update `scripts/import_chr17q12_genes.py:30`
3. [x] Update `scripts/create_admin_user.py:14`
4. [x] Update `scripts/add_grch37_assembly.py:22`
5. [x] Update `tests/test_config.py:7` - change to test `app.core.config.Settings`
6. [x] Update `tests/conftest.py:12`
7. [x] **DELETE** `app/config.py`
8. [x] Run tests: `uv run pytest tests/`

### Task 1.2: Unify Pattern Imports ✅ COMPLETE

**Goal:** Remove local patterns from `variant_search_validation.py`, use `app.core.patterns`.

**File:** `app/phenopackets/variant_search_validation.py`

**Before (lines 18-46):**
```python
# REMOVE these local definitions
HGVS_PATTERNS = {
    "c": re.compile(r"^c\.(..."),
    "p": re.compile(r"^p\.(..."),
    "g": re.compile(r"^g\.(..."),
}
HG38_PATTERN = re.compile(r"^(chr)?(\d+|X|Y|MT?)...")
```

**After:**
```python
from app.core.patterns import (
    HGVS_C_SEARCH_PATTERN,
    HGVS_P_SEARCH_PATTERN,
    HGVS_G_SEARCH_PATTERN,
    HG38_PATTERN,
    is_hgvs_c,
    is_hgvs_p,
    is_hg38_coordinate,
)

def validate_hgvs_notation(query: str) -> bool:
    """Validate HGVS notation using centralized patterns."""
    stripped = query.strip()
    if stripped.startswith("c."):
        return bool(HGVS_C_SEARCH_PATTERN.match(stripped))
    elif stripped.startswith("p."):
        return bool(HGVS_P_SEARCH_PATTERN.match(stripped))
    elif stripped.startswith("g."):
        return bool(HGVS_G_SEARCH_PATTERN.match(stripped))
    return False
```

### Task 1.3: Publications Service Config Migration ✅ COMPLETE

**Goal:** Use `settings.external_apis.pubmed` instead of hardcoded constants.

**File:** `app/publications/service.py`

**Before (lines 25-36):**
```python
PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")
API_VERSION = "2.0"
if PUBMED_API_KEY:
    MAX_REQUESTS_PER_SECOND = 10
else:
    MAX_REQUESTS_PER_SECOND = 3
```

**After:**
```python
from app.core.config import settings

# Access via settings
def _get_pubmed_config():
    return {
        "base_url": settings.external_apis.pubmed.base_url,
        "timeout": settings.external_apis.pubmed.timeout_seconds,
        "api_key": settings.PUBMED_API_KEY,
        "rate_limit": (
            settings.rate_limiting.pubmed.requests_per_second_with_key
            if settings.PUBMED_API_KEY
            else settings.rate_limiting.pubmed.requests_per_second_without_key
        ),
    }
```

**Also update line 246:**
```python
# Before
timeout = aiohttp.ClientTimeout(total=5)

# After
timeout = aiohttp.ClientTimeout(total=settings.external_apis.pubmed.timeout_seconds)
```

---

## Phase 1B: SQL Logic Centralization ✅ COMPLETE

### Task 1.4: Create sql_fragments.py Module ✅

**Goal:** Extract shared SQL logic to prevent drift between endpoints.

**Created:** `app/phenopackets/routers/aggregations/sql_fragments.py` (243 lines)

**Exports:**
- `VD_BASE`, `VD_ID`, `VD_EXTENSIONS`, `VD_EXPRESSIONS` - JSONB path constants
- `CURRENT_AGE_PATH`, `INTERP_STATUS_PATH` - Common SQL paths
- `VARIANT_TYPE_CLASSIFICATION_SQL` - Survival analysis (CNV/Truncating/Non-truncating)
- `VARIANT_TYPE_CASE` - Variant aggregation (SNV/Deletion/Duplication/etc.)
- `STRUCTURAL_TYPE_CASE` - All variants listing (structural type detection)

### Task 1.5: Update Aggregation Modules ✅

**Updated imports in:**
- [x] `survival.py` - imports `CURRENT_AGE_PATH`, `INTERP_STATUS_PATH`, `VARIANT_TYPE_CLASSIFICATION_SQL`
- [x] `variants.py` - imports `VARIANT_TYPE_CASE`
- [x] `all_variants.py` - imports `STRUCTURAL_TYPE_CASE`

**Lines removed (DRY):**
- `survival.py`: ~85 lines (local path constants + classification SQL)
- `variants.py`: ~60 lines (local VARIANT_TYPE_CASE)
- `all_variants.py`: ~45 lines (local STRUCTURAL_TYPE_CASE)

---

## Phase 2: Database Optimization (Next PR)

### 2.1 Materialized View Integration

**Goal:** Update aggregation endpoints to use existing materialized views.

**Views Available:**
- `mv_feature_aggregation` - HPO term statistics
- `mv_disease_aggregation` - Disease distribution
- `mv_sex_distribution` - Sex distribution
- `mv_summary_statistics` - Overall statistics

**Endpoints to Update:**
- [ ] `features.py:aggregate_by_feature()` → query `mv_feature_aggregation`
- [ ] `diseases.py:aggregate_by_disease()` → query `mv_disease_aggregation`
- [ ] `demographics.py:aggregate_sex_distribution()` → query `mv_sex_distribution`

### 2.2 View Refresh Strategy

**Goal:** Implement background task to refresh views after data import.

**Implementation:**
```python
# In app/database/utils.py
async def refresh_materialized_views(db: AsyncSession) -> None:
    """Refresh all materialized views after data changes."""
    for view in settings.materialized_views.views:
        await db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
    await db.commit()
```

---

## Phase 3: Security Hardening (Future PR)

### 3.1 Admin Password Validation

**Goal:** Reject default admin password in production.

**Implementation:**
```python
# In app/repositories/user_repository.py or app/auth/password.py
import os

def validate_admin_password(password: str) -> None:
    """Reject default password in production."""
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production" and password == "ChangeMe!Admin2025":
        raise ValueError(
            "Default admin password not allowed in production. "
            "Set ADMIN_PASSWORD in .env to a unique value."
        )
```

### 3.2 Legacy Cleanup Audit

**Check for deprecated code:**
- [ ] `app/utils.py` - `parse_filter_json`, `build_pagination_meta` may be unused
- [ ] Verify `model_to_dict` usage, move to `app/core/utils.py` if needed

---

## Completed Work

### PR #148: Unified Config System
- [x] Created `backend/config.yaml` with all tunable parameters
- [x] Created `backend/app/core/config.py` with Pydantic models
- [x] Created `backend/app/core/cache.py` with Redis service
- [x] Created `backend/app/core/patterns.py` with centralized regex
- [x] Refactored rate limiter to use Redis
- [x] Refactored variant validator to use Redis cache
- [x] Refactored HPO proxy to use Redis cache

### Commit 2d6cfc1: Aggregations Modularization
- [x] Extracted 10 modules from monolithic 2971-line file
- [x] Created `common.py` for shared imports
- [x] Created domain-specific modules (features, diseases, demographics, etc.)
- [x] Applied DRY to SQL path constants in survival.py
- [x] Deleted legacy `_legacy.py` file
- [x] Net reduction: 96 lines (2971 → 2875)

### Phase 1B: SQL Logic Centralization
- [x] Created `aggregations/sql_fragments.py` (243 lines)
- [x] Centralized JSONB path constants: `VD_BASE`, `VD_ID`, `VD_EXTENSIONS`, `VD_EXPRESSIONS`
- [x] Centralized common SQL paths: `CURRENT_AGE_PATH`, `INTERP_STATUS_PATH`
- [x] Centralized variant classification SQL for 3 different contexts:
  - `VARIANT_TYPE_CLASSIFICATION_SQL` - Survival analysis (CNV/Truncating/Non-truncating)
  - `VARIANT_TYPE_CASE` - Variant aggregation (SNV/Deletion/Duplication/etc.)
  - `STRUCTURAL_TYPE_CASE` - All variants listing (structural type detection)
- [x] Updated `survival.py` to use centralized SQL (~85 lines removed)
- [x] Updated `variants.py` to use centralized SQL (~60 lines removed)
- [x] Updated `all_variants.py` to use centralized SQL (~45 lines removed)
- [x] All 554 tests pass, mypy clean, ruff clean

**Final Module Structure:**
```
aggregations/
├── __init__.py          43 lines
├── common.py            70 lines
├── features.py         122 lines
├── diseases.py         123 lines
├── demographics.py     119 lines
├── variants.py         238 lines
├── publications.py     184 lines
├── summary.py          136 lines
├── all_variants.py     704 lines
└── survival.py        1136 lines
                       ─────
                       2875 lines total
```

---

## Implementation Checklist

### Phase 1A: Code Cleanup (This PR) ✅ COMPLETE
- [x] 1.1 Update 6 files importing `app.config`
- [x] 1.1 Delete `app/config.py`
- [x] 1.2 Refactor `variant_search_validation.py` to use `app.core.patterns`
- [x] 1.3 Refactor `publications/service.py` to use `settings.external_apis.pubmed`
- [x] Run tests, fix any failures
- [x] Add comprehensive tests for `app.core.patterns` (118 tests)

### Phase 1B: SQL Centralization ✅ COMPLETE
- [x] 1.4 Create `aggregations/sql_fragments.py`
- [x] 1.5 Update `survival.py`, `variants.py`, `all_variants.py`
- [x] Run tests (554 passed)

### Phase 2: Database Optimization (Next PR)
- [ ] Update aggregation endpoints to use materialized views
- [ ] Add view refresh after data import
- [ ] Benchmark performance improvement

### Phase 3: Security (Future PR)
- [ ] Add admin password production validation
- [ ] Audit and remove deprecated utilities

---

## Quality Gates

- [x] All tests pass after refactoring (554 tests: 436 existing + 118 patterns)
- [x] No duplicate config files (`app/config.py` deleted)
- [x] No inline regex patterns (use `app.core.patterns`)
- [x] No hardcoded API URLs (use `settings.external_apis`)
- [x] All config values documented in `config.yaml`
- [x] Redis connection gracefully degrades to in-memory
- [x] mypy strict mode passes
- [x] ruff lint passes
- [x] SQL logic centralized in `sql_fragments.py` (Phase 1B)
- [ ] Aggregation endpoints use materialized views (Phase 2)

---

## Related Documents

- [Aggregations Refactoring Plan](../02-completed/aggregations_refactoring_plan.md) - ✅ COMPLETE
- Issue #131: Refactor aggregations.py
- PR #148: Unified config system

---

*Updated: 2025-12-07 - Phase 1A + 1B fully implemented and verified (554 tests pass)*
