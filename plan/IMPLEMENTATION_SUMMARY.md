# Implementation Plan Summary
## Complete Database Preparation + Curation System

**Date**: 2025-11-16
**Status**: ✅ READY TO EXECUTE

---

## Overview

Two-phase approach to deploy the phenopacket curation system:

### Phase A: Fix Migration & Database (FIRST - 5 hours)
📄 **Plan**: `MIGRATION_FIX_IMPLEMENTATION_PLAN.md`

**What**: Fix import script to correctly populate database with:
- Proper curator attribution (via ReviewerMapper)
- Revision counter for optimistic locking
- Initial audit trail entries

**Why**: Database must be correctly structured BEFORE deploying curation UI

### Phase B: Deploy Curation System (SECOND - 3 weeks)
📄 **Plan**: `PHENOPACKET_CURATION_IMPLEMENTATION_GUIDE.md` (updated)

**What**: Implement UPDATE, DELETE, audit history UI

**Why**: Enables curators to edit/manage phenopackets with full audit trail

---

## Execution Order

### ✅ Step 1: Fix Migration (Do This First!)

```bash
# Follow: MIGRATION_FIX_IMPLEMENTATION_PLAN.md

# Summary:
1. Add revision column migration
2. Update storage.py to use ReviewerMapper
3. Update models.py to include revision field
4. Run tests
5. Drop database
6. Run migrations
7. Re-import with fixed script
8. Verify
```

**Deliverable**: Database with 864 phenopackets, proper attribution, revision=1

---

### ✅ Step 2: Deploy Curation System (Do This Second!)

```bash
# Follow: PHENOPACKET_CURATION_IMPLEMENTATION_GUIDE.md

# Summary:
- Phase 1: Authorization service, audit utilities (Week 1)
- Phase 2: UPDATE & DELETE endpoints (Week 2)
- Phase 3: Frontend UI components (Week 3)
```

**Deliverable**: Full CRUD system with audit trail

---

## Key Terminology Changes

| Old (Wrong) | New (Correct) | Purpose |
|-------------|---------------|---------|
| `version` (Integer) | `revision` (Integer) | Optimistic locking counter |
| `version` (String) | `version` (String) | GA4GH schema version ("2.0") - unchanged! |
| `expected_version` | `expected_revision` | API parameter for optimistic locking |

**Why the change**:
- `version` field already exists as String for GA4GH schema version
- Cannot overload it for optimistic locking
- Solution: Add new `revision` field (Integer) for concurrency control

---

## Critical Files

### Migration Fix Files
```
backend/alembic/versions/002_add_revision_column.py  (NEW)
backend/app/phenopackets/models.py                   (MODIFY - add revision field)
backend/migration/database/storage.py                (MODIFY - use ReviewerMapper)
backend/migration/phenopackets/builder_simple.py     (MODIFY - attach metadata)
backend/tests/test_migration_*.py                    (NEW - 3 test files)
```

### Curation System Files
```
backend/app/auth/authorization.py                    (NEW)
backend/app/utils/audit.py                           (NEW)
backend/app/phenopackets/endpoints.py                (MODIFY - UPDATE/DELETE/audit)
frontend/src/components/phenopacket/*.vue            (NEW - 6 components)
frontend/src/api/index.js                            (MODIFY - add methods)
```

---

## Verification Steps

### After Migration Fix:
```bash
# Check revision column exists
psql $DATABASE_URL -c "\d phenopackets" | grep revision

# Check attribution (should NOT all be same value)
psql $DATABASE_URL -c "SELECT created_by, COUNT(*) FROM phenopackets GROUP BY created_by;"

# Check audit entries exist
psql $DATABASE_URL -c "SELECT COUNT(*) FROM phenopacket_audit WHERE action='CREATE';"
```

### After Curation System:
```bash
# Test optimistic locking
# (Open same phenopacket in 2 tabs, edit both, save second → 409 Conflict)

# Test audit history
curl http://localhost:8000/api/v2/phenopackets/HNF1B-001/audit
```

---

## Common Mistakes to Avoid

1. ❌ **Don't deploy curation system before fixing migration**
   - Will have wrong data (no revision, wrong attribution)

2. ❌ **Don't use `version` for optimistic locking**
   - Use `revision` instead

3. ❌ **Don't skip testing after migration fix**
   - Must verify attribution and revision before proceeding

4. ❌ **Don't forget to run linting**
   - `make check` in both backend and frontend

---

## Success Criteria

### Migration Fix Complete When:
- ✅ `revision` column exists and all rows = 1
- ✅ `created_by` has multiple distinct values (not all "direct_sheets_migration")
- ✅ Each phenopacket has CREATE audit entry
- ✅ All tests pass

### Curation System Complete When:
- ✅ Can edit phenopacket via UI
- ✅ Can delete phenopacket (soft delete)
- ✅ Can view audit history
- ✅ Optimistic locking prevents concurrent edits
- ✅ All authorization checks work

---

## Timeline

| Phase | Duration | Start After |
|-------|----------|-------------|
| **A. Migration Fix** | 5 hours | Now |
| **B. Curation System - Phase 1** | 1 week | Migration fix complete |
| **B. Curation System - Phase 2** | 1 week | Phase 1 complete |
| **B. Curation System - Phase 3** | 1 week | Phase 2 complete |

**Total**: ~3.5 weeks

---

## Next Action

**START HERE**: `MIGRATION_FIX_IMPLEMENTATION_PLAN.md`

Then proceed to: `PHENOPACKET_CURATION_IMPLEMENTATION_GUIDE.md`

---

## Documents in This Plan

1. ✅ **MIGRATION_FIX_IMPLEMENTATION_PLAN.md** (this must be done FIRST)
   - Database schema fixes
   - Import script updates
   - Testing strategy
   - Database regeneration steps

2. ✅ **PHENOPACKET_CURATION_IMPLEMENTATION_GUIDE.md** (do SECOND)
   - Complete curation system
   - Authorization, audit, UI
   - 3-phase implementation

3. ✅ **MIGRATION_COMPATIBILITY_ANALYSIS.md** (reference only)
   - Analysis that identified the issues
   - Explains WHY we need migration fix

4. ✅ **IMPLEMENTATION_SUMMARY.md** (this document)
   - Executive overview
   - Execution order
   - Quick reference

---

**Status**: All plans are complete and ready for implementation. Start with migration fix, then proceed to curation system deployment.
