# Phase 1: Pydantic Deprecation Fixes - Research

**Researched:** 2026-01-19
**Domain:** Pydantic v2 migration, FastAPI validation
**Confidence:** HIGH

## Summary

This phase addresses Pydantic v2 deprecation warnings in the backend codebase. Through investigation of the codebase and verification against official Pydantic v2 documentation, the scope is narrower than initially described in GitHub Issue #134.

**Key finding:** The codebase has 7 instances of class-based `Config` deprecation warnings. The `regex=` and `example=` patterns mentioned in the issue are already fixed - the codebase correctly uses `pattern=` and `examples=[]`.

**Primary recommendation:** Replace all 7 class-based `Config` inner classes with `model_config = ConfigDict(from_attributes=True)`.

## Standard Stack

The established patterns for this migration:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | 2.11.7 | Data validation | Already in use, v2 migration required |
| FastAPI | 0.116.1+ | Web framework | Already in use, follows Pydantic patterns |

### Supporting
| Import | Purpose | When to Use |
|--------|---------|-------------|
| `from pydantic import ConfigDict` | Model configuration | All models needing ORM/attribute support |
| `model_config = ConfigDict(...)` | Configuration attribute | Replaces inner `class Config:` |

**Installation:**
No new dependencies required - all imports available in current Pydantic version.

## Architecture Patterns

### Recommended Pattern: ConfigDict

**Old pattern (DEPRECATED):**
```python
from pydantic import BaseModel

class MyModel(BaseModel):
    field: str

    class Config:
        """Pydantic configuration."""
        from_attributes = True
```

**New pattern (REQUIRED):**
```python
from pydantic import BaseModel, ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str
```

### Key Migration Rules

1. **Import `ConfigDict`** from pydantic
2. **Replace** `class Config:` block with `model_config = ConfigDict(...)`
3. **Position** `model_config` as first class attribute (before field definitions)
4. **Remove** Config class docstrings (inline comment acceptable if needed)

### Anti-Patterns to Avoid
- **Partial migration:** Don't leave some models with old Config and some with new
- **Plain dict:** Don't use `model_config = {'from_attributes': True}` - use `ConfigDict()` for type checking support

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ORM model support | Custom serialization | `ConfigDict(from_attributes=True)` | Automatic attribute mapping |
| Validation config | Manual validators | `ConfigDict` settings | Built-in, tested patterns |

**Key insight:** Pydantic's ConfigDict is fully compatible with the existing `from_attributes=True` setting - it's a direct 1:1 migration.

## Common Pitfalls

### Pitfall 1: Forgetting to Import ConfigDict
**What goes wrong:** NameError: ConfigDict not defined
**Why it happens:** Just adding `model_config` without updating imports
**How to avoid:** Always check import statement includes `ConfigDict`
**Warning signs:** Tests fail immediately on import

### Pitfall 2: Using Wrong Configuration Keys
**What goes wrong:** ConfigDict silently ignores unknown keys
**Why it happens:** Typos or using V1 configuration names
**How to avoid:** Use IDE autocomplete with ConfigDict, verify key names
**Warning signs:** Configuration doesn't take effect

### Pitfall 3: Breaking Inheritance
**What goes wrong:** Child classes may not inherit parent config correctly
**Why it happens:** Not understanding how model_config merges
**How to avoid:** Pydantic v2 automatically merges ConfigDict from parent classes
**Warning signs:** None - this pitfall was fixed in Pydantic v2

## Code Examples

### Complete Migration Pattern
```python
# BEFORE
from pydantic import BaseModel, Field

class ReferenceGenomeSchema(BaseModel):
    """Reference genome assembly schema."""

    id: UUID
    name: str = Field(..., description="Assembly name")
    is_default: bool = Field(..., description="Whether default")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


# AFTER
from pydantic import BaseModel, ConfigDict, Field

class ReferenceGenomeSchema(BaseModel):
    """Reference genome assembly schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., description="Assembly name")
    is_default: bool = Field(..., description="Whether default")
```

### Multiple Models in Same File
```python
from pydantic import BaseModel, ConfigDict, Field

# Apply ConfigDict to each model individually
class ModelA(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field_a: str

class ModelB(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field_b: str
```

## Affected Files

### Files Requiring Changes (7 class-based Config instances)

| File | Line | Class | Current Config |
|------|------|-------|----------------|
| `backend/app/reference/schemas.py` | 28 | `ReferenceGenomeSchema` | `from_attributes = True` |
| `backend/app/reference/schemas.py` | 47 | `ExonSchema` | `from_attributes = True` |
| `backend/app/reference/schemas.py` | 71 | `ProteinDomainSchema` | `from_attributes = True` |
| `backend/app/reference/schemas.py` | 95 | `TranscriptSchema` | `from_attributes = True` |
| `backend/app/reference/schemas.py` | 128 | `GeneSchema` | `from_attributes = True` |
| `backend/app/phenopackets/models.py` | 432 | `PhenopacketResponse` | `from_attributes = True` |
| `backend/app/phenopackets/models.py` | 472 | `PhenopacketAuditResponse` | `from_attributes = True` |

### Files Already Using Modern Patterns (No Changes Needed)

| File | Pattern | Status |
|------|---------|--------|
| `backend/app/schemas/auth.py` | Uses `pattern=` in Field | CORRECT |
| `backend/app/phenopackets/routers/crud.py` | Uses `pattern=` in Query | CORRECT |
| `backend/app/phenopackets/routers/aggregations/variants.py` | Uses `pattern=` in Query | CORRECT |
| `backend/app/variant_validator_endpoint.py` | Uses `examples=[]` in Query | CORRECT |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `class Config:` inner class | `model_config = ConfigDict()` | Pydantic v2.0 (2023) | Deprecated but functional |
| `regex=` in Field/Query | `pattern=` | Pydantic v2.0 (2023) | Already migrated in codebase |
| `example=` in Field | `examples=[]` (list) | Pydantic v2.0 (2023) | Already migrated in codebase |

**Deprecated/outdated:**
- Class-based `Config` - Will be removed in Pydantic v3.0

## Testing Approach

### Verification Commands

**Before migration - count warnings:**
```bash
cd backend
uv run python -W all -c "import app.main" 2>&1 | grep -c "class-based.*config.*deprecated"
# Expected: 7
```

**After migration - verify zero warnings:**
```bash
cd backend
uv run python -W all -c "import app.main" 2>&1 | grep -c "class-based.*config.*deprecated"
# Expected: 0
```

**Run full test suite:**
```bash
cd backend
make check
```

### Verification Checklist
- [ ] Zero Pydantic deprecation warnings on app import
- [ ] All tests pass
- [ ] Linting passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)

## Open Questions

None - the migration path is straightforward and well-documented.

## Sources

### Primary (HIGH confidence)
- Pydantic official documentation: https://docs.pydantic.dev/latest/concepts/config/
- Pydantic v2 migration guide: https://docs.pydantic.dev/latest/migration/
- FastAPI validation docs: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/

### Verification (HIGH confidence)
- Live codebase analysis via grep and python import testing
- Pydantic version verification: 2.11.7

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Pydantic documentation confirms patterns
- Architecture: HIGH - Direct 1:1 migration, no architectural changes
- Affected files: HIGH - Verified via grep and import testing
- Testing approach: HIGH - Tested commands on actual codebase

**Research date:** 2026-01-19
**Valid until:** 2027-01-19 (Pydantic v3.0 not expected before then)

## Issue Clarification

The original GitHub Issue #134 mentioned 12 deprecation warnings including `regex` and `example` patterns. Investigation reveals:

1. **Actual warnings:** 7 (all class-based Config)
2. **`regex=` pattern:** NOT FOUND in codebase - already uses `pattern=`
3. **`example=` pattern:** NOT FOUND in codebase - already uses `examples=[]`

The scope of this phase is therefore **7 file changes across 2 files**, not 12.
