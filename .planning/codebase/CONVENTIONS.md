# Coding Conventions

**Analysis Date:** 2026-01-19

## Naming Patterns

**Files:**
- Python: `snake_case.py` (e.g., `variant_validator.py`, `auth_endpoints.py`)
- Vue Components: `PascalCase.vue` (e.g., `KaplanMeierChart.vue`, `AppDataTable.vue`)
- JavaScript: `camelCase.js` (e.g., `authStore.js`, `logSanitizer.js`)
- Test files: Python `test_*.py`, JavaScript `*.spec.js`

**Functions:**
- Python: `snake_case` (e.g., `get_phenopackets`, `validate_hgvs_notation`)
- JavaScript: `camelCase` (e.g., `getPhenopackets`, `sanitizeLogData`)
- Vue composables: `use*` prefix (e.g., `useAsyncState`, `useTableUrlState`)
- Pinia stores: `use*Store` suffix (e.g., `useAuthStore`, `useVariantStore`)

**Variables:**
- Python: `snake_case` for variables, `UPPER_SNAKE_CASE` for constants
- JavaScript: `camelCase` for variables, `UPPER_SNAKE_CASE` for constants
- Vue refs: `camelCase` (e.g., `isLoading`, `accessToken`)

**Types:**
- Python Pydantic models: `PascalCase` (e.g., `PhenopacketCreate`, `JsonApiResponse`)
- Python dataclasses: `PascalCase` with descriptive suffixes (`*Config`, `*Response`)
- TypeScript/JSDoc: `PascalCase` for interfaces

**Classes:**
- Python: `PascalCase` (e.g., `VariantValidator`, `PhenopacketBuilder`)
- Exception classes: `*Error` suffix (e.g., `ValidationError`)

## Code Style

**Formatting:**
- Python: ruff formatter (replaces black, isort)
- JavaScript/Vue: Prettier with config at `frontend/.prettierrc`
- Line length: 88 chars (Python), 100 chars (JavaScript)

**Prettier Settings** (`frontend/.prettierrc`):
```json
{
  "printWidth": 100,
  "tabWidth": 2,
  "singleQuote": true,
  "trailingComma": "es5",
  "semi": true,
  "bracketSpacing": true,
  "arrowParens": "always"
}
```

**Linting:**
- Python: ruff (E, W, F, I, D rules enabled)
- JavaScript: ESLint with Vue plugin
- TypeScript: Not used (plain JS with JSDoc)

**Ruff Rules** (from `backend/pyproject.toml`):
```toml
select = ["E", "W", "F", "I", "D"]  # pycodestyle, pyflakes, isort, pydocstyle
ignore = ["D100", "D104", "D203", "D213"]
```

**ESLint Rules** (`frontend/eslint.config.js`):
- Vue recommended rules with some relaxations
- `vue/multi-word-component-names`: off
- `vue/require-default-prop`: error
- `vue/require-prop-types`: error
- `vue/block-order`: error (template, script, style)
- Unused vars with `_` prefix allowed

## Import Organization

**Python Order:**
1. Standard library
2. Third-party packages
3. Local application imports

**Python Example:**
```python
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
import pytest
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.auth import require_curator
from app.database import get_db
from app.phenopackets.models import Phenopacket
```

**JavaScript Order:**
1. Node/Vue built-ins
2. Third-party packages
3. Local imports with `@/` alias

**JavaScript Example:**
```javascript
import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';

import { apiClient } from '@/api';
import { sanitizeLogData } from '@/utils/logSanitizer';
```

**Path Aliases:**
- Frontend: `@/` maps to `frontend/src/`
- Configured in `frontend/vite.config.js` and `frontend/vitest.config.js`

## Error Handling

**Python Patterns:**
- Use FastAPI `HTTPException` for API errors with appropriate status codes
- Custom exception types for domain errors
- Always include descriptive `detail` messages

```python
from fastapi import HTTPException

raise HTTPException(
    status_code=404,
    detail=f"Phenopacket with ID {phenopacket_id} not found"
)

raise HTTPException(
    status_code=400,
    detail="Invalid variant format. Expected HGVS or VCF notation."
)
```

**JavaScript Patterns:**
- API calls wrapped in try/catch with logging
- Error state tracked in refs/stores
- User-friendly error messages extracted from response

```javascript
try {
  const response = await apiClient.post('/auth/login', credentials);
  // ...
} catch (err) {
  error.value = err.response?.data?.detail || 'Login failed';
  window.logService.error('Login failed', { error: error.value });
  throw err;
}
```

**Async Error Handling:**
- Python: `async/await` with try/except
- JavaScript: `async/await` with try/catch
- Always clean up loading states in `finally` blocks

## Logging

**Python Framework:** Standard `logging` module

**Python Pattern:**
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Processing phenopacket", extra={"id": phenopacket_id})
logger.error("Validation failed", extra={"errors": errors})
logger.debug("Query executed", extra={"sql": str(query)})
```

**JavaScript Framework:** Custom `logService` with privacy-first sanitization

**JavaScript Pattern - CRITICAL:**
- NEVER use `console.log()` in frontend code
- ALWAYS use `window.logService.*` methods
- Automatic PII/PHI redaction (HPO terms, emails, variants, tokens)

```javascript
// NEVER do this:
console.log('User data:', userData);

// ALWAYS do this:
window.logService.info('User logged in', { username: user.value?.username });
window.logService.error('API error', { error: err.message });
window.logService.debug('Fetching data', { endpoint });
```

**Log Sanitizer** (`frontend/src/utils/logSanitizer.js`):
- Redacts HPO terms: `HP:0001234` -> `[HPO_TERM]`
- Redacts variants: `NM_000458.4:c.544G>A` -> `[VARIANT]`
- Redacts emails: `user@example.com` -> `[EMAIL]`
- Redacts JWT tokens: `Bearer eyJ...` -> `Bearer [TOKEN]`
- Redacts DNA sequences (8+ nucleotides)

## Comments

**When to Comment:**
- Complex algorithms or business logic
- Non-obvious workarounds with issue references
- API endpoint documentation (FastAPI docstrings)
- Test purpose and coverage descriptions

**Python Docstrings:**
- Google-style docstrings enforced by ruff
- Required for public functions and classes
- Include Args, Returns, Raises sections

```python
def validate_hgvs_notation(notation: str) -> bool:
    """Validate HGVS notation format.

    Args:
        notation: HGVS string (e.g., "NM_000458.4:c.544G>A")

    Returns:
        True if valid HGVS format, False otherwise.

    Raises:
        ValueError: If notation is empty or None.
    """
```

**JavaScript JSDoc:**
- Used for function documentation
- Include param types, return types, examples

```javascript
/**
 * Sanitize log message and context
 * @param {string} message - Log message
 * @param {Object} context - Additional context data
 * @returns {Object} Sanitized message and context
 */
export function sanitizeLogData(message, context = {}) {
```

**Test Docstrings:**
- Describe what aspect is being tested
- Reference related issues when applicable

```python
"""Comprehensive unit tests for VEP annotation system.

Tests the VariantValidator class including:
- Format detection (VCF vs HGVS)
- VEP API annotation
- Rate limiting (configurable from settings)

Related: Issue #117, #100
"""
```

## Function Design

**Size Guidelines:**
- Functions should do one thing well
- Target <50 lines per function
- Extract helpers for complex logic
- Modules should stay under 500 lines

**Parameters:**
- Python: Use type hints for all parameters
- JavaScript: Use JSDoc for parameter documentation
- Default values for optional parameters
- Use FastAPI Query/Path for API parameters with validation

```python
async def list_phenopackets(
    page_number: int = Query(1, alias="page[number]", ge=1),
    page_size: int = Query(100, alias="page[size]", ge=1, le=1000),
    filter_sex: Optional[str] = Query(None, alias="filter[sex]"),
    db: AsyncSession = Depends(get_db),
):
```

**Return Values:**
- Python: Always specify return type hints
- Use Pydantic models for API responses
- Return early for error conditions
- Avoid returning `None` when a default makes sense

## Module Design

**Exports:**
- Python: Use `__all__` for public API
- JavaScript: Named exports preferred over default exports
- API functions exported from `frontend/src/api/index.js`

**Barrel Files:**
- Python: `__init__.py` files export public interfaces
- JavaScript: `index.js` files aggregate module exports

**Module Organization:**
- One responsibility per module
- Separate routers from business logic
- Keep models/schemas in dedicated files
- Utils/helpers in `utils/` directories

## Vue Component Conventions

**Block Order:**
1. `<template>`
2. `<script>`
3. `<style>`

**Script Setup Pattern:**
```vue
<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

// Props
const props = defineProps({
  survivalData: { type: Object, default: null },
  width: { type: Number, default: 1200 },
});

// State
const loading = ref(false);
const data = ref(null);

// Computed
const hasData = computed(() => !!data.value);

// Methods
function handleClick() {
  // ...
}

// Lifecycle
onMounted(() => {
  // ...
});
</script>
```

**Component Props:**
- Always define prop types
- Provide default values where appropriate
- Document complex props with JSDoc

## API Design Patterns

**JSON:API v1.1 Compliance:**
- Pagination: `page[number]`, `page[size]`, `page[after]`, `page[before]`
- Filtering: `filter[field_name]`
- Sorting: `sort=-created_at,subject_id`
- Response format: `{ data, meta, links }`

**Endpoint Naming:**
- REST conventions: `/phenopackets/`, `/phenopackets/{id}`
- Aggregations: `/aggregate/*`
- Actions: verb-based like `/search`, `/annotate`

**Server-Side Requirements:**
- NEVER use client-side pagination or sorting for data tables
- ALWAYS send sort parameters to backend
- Use `buildSortParameter()` from `@/utils/pagination`

---

*Convention analysis: 2026-01-19*
