# Coding Conventions

**Analysis Date:** 2026-01-19

## Naming Patterns

**Files:**
- Backend Python: `snake_case.py` (e.g., `variant_validator.py`, `crud.py`)
- Frontend Vue: `PascalCase.vue` for components (e.g., `AppDataTable.vue`, `HNF1BProteinVisualization.vue`)
- Frontend JS utils: `camelCase.js` (e.g., `logSanitizer.js`, `sex.js`)
- Test files: Backend `test_*.py`, Frontend `*.spec.js`

**Functions:**
- Backend: `snake_case` (e.g., `get_password_hash`, `build_offset_response`)
- Frontend: `camelCase` (e.g., `getSexIcon`, `sanitizeLogData`, `processQueue`)

**Variables:**
- Backend: `snake_case` (e.g., `filter_sex`, `page_number`, `db_session`)
- Frontend: `camelCase` (e.g., `accessToken`, `isRefreshing`, `mockResponse`)

**Types/Classes:**
- Backend: `PascalCase` (e.g., `Phenopacket`, `PhenopacketCreate`, `VariantValidator`)
- Frontend: `PascalCase` for stores (e.g., `useAuthStore`)

**Constants:**
- Backend: `UPPER_SNAKE_CASE` (in config)
- Frontend: `UPPER_SNAKE_CASE` for mappings (e.g., `SEX_ICONS`, `REDACTION_PATTERNS`)

## Code Style

**Formatting:**
- Backend: ruff with line-length 88
- Frontend: Prettier with printWidth 100

**Backend (ruff):**
```toml
# From backend/pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**Frontend (Prettier):**
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
- Backend: ruff (replaces black, isort, flake8)
  - Enabled: E (pycodestyle errors), W (warnings), F (pyflakes), I (isort), D (pydocstyle)
  - Docstring style: Google convention
- Frontend: ESLint with Vue plugin
  - Unused vars with `_` prefix ignored: `argsIgnorePattern: '^_'`
  - Required: `vue/require-default-prop`, `vue/require-prop-types`
  - Block order enforced: `template`, `script`, `style`

## Import Organization

**Backend Order:**
1. Standard library imports (`import json`, `import logging`)
2. Third-party imports (`from fastapi import...`, `from sqlalchemy import...`)
3. Local application imports (`from app.database import...`, `from app.phenopackets.models import...`)

**Frontend Order:**
1. Vue/framework imports (`import { describe, it, expect } from 'vitest'`)
2. Third-party libraries (`import axios from 'axios'`)
3. Local imports with `@/` alias (`import { useAuthStore } from '@/stores/authStore'`)

**Path Aliases:**
- Frontend: `@` maps to `src/` (configured in `vitest.config.js` and `vite.config.js`)

## Error Handling

**Backend Patterns:**
```python
# HTTP exceptions with detail
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Phenopacket not found")
raise HTTPException(status_code=403, detail="Cannot delete your own account")

# Async cleanup with rollback
try:
    await db_session.execute(delete_stmt)
    await db_session.commit()
except Exception:
    await db_session.rollback()
    raise
```

**Frontend Patterns:**
```javascript
// Try-catch with logService
try {
  const response = await apiClient.post('/auth/login', credentials);
  return response.data;
} catch (error) {
  window.logService.error('Login failed', { error: error.message });
  throw error;
}

// Graceful degradation
apiClient.post.mockRejectedValueOnce(new Error('API Error'));
await authStore.logout();
// Should still clear local state even if API call fails
```

## Logging

**Backend Framework:** Python `logging` module
```python
import logging
logger = logging.getLogger(__name__)

logger.info("User logged in")
logger.error("Database connection failed", exc_info=True)
```

**Frontend Framework:** Custom `window.logService` with PII redaction
```javascript
// NEVER use console.log() - use logService instead
window.logService.info('User logged in successfully', { username: 'testuser' });
window.logService.error('API error', { error: err.message });
window.logService.warn('Token refresh failed, redirecting to login');
window.logService.debug('Access token refreshed');
```

**PII Redaction Patterns (frontend):**
- HPO terms: `HP:\d{7}` -> `[HPO_TERM]`
- Variants: `NM_\d+\.\d+:c\.\d+[ATCG]>[ATCG]` -> `[VARIANT]`
- MONDO: `MONDO:\d+` -> `[DISEASE]`
- Email: `[\w.+-]+@[\w.-]+\.\w+` -> `[EMAIL]`
- JWT: `Bearer\s+[\w.-]+` -> `Bearer [TOKEN]`
- Subject IDs: `HNF1B-\d{3}` -> `[SUBJECT_ID]`
- DNA sequences: `[ATCG]{8,}` -> `[DNA_SEQUENCE]`

## Comments

**When to Comment:**
- Complex business logic requiring domain knowledge
- Non-obvious workarounds with issue/PR references
- SQL queries and JSONPath expressions
- Regex patterns

**Docstring Style (Backend - Google):**
```python
def create_audit_entry(action: str, data: dict) -> AuditEntry:
    """Create an audit trail entry.

    Args:
        action: The action performed (create, update, delete)
        data: The data being audited

    Returns:
        AuditEntry object with timestamp
    """
```

**JSDoc Style (Frontend):**
```javascript
/**
 * Get Material Design Icon for a sex value.
 *
 * @param {string|null|undefined} sex - Sex value from phenopacket
 * @returns {string} MDI icon name
 *
 * @example
 * getSexIcon('MALE') // Returns: 'mdi-gender-male'
 */
export function getSexIcon(sex) {
  return SEX_ICONS[sex] ?? 'mdi-help-circle';
}
```

## Function Design

**Size:** Keep modules under 500 lines; extract helpers when exceeding

**Parameters (Backend):**
```python
# Use FastAPI Query with aliases for JSON:API compliance
page_number: int = Query(1, alias="page[number]", ge=1, description="Page number")
filter_sex: Optional[str] = Query(None, alias="filter[sex]")
```

**Parameters (Frontend):**
```javascript
// Props with defaults and validators
defineProps({
  serverSide: {
    type: Boolean,
    default: true,
  },
  density: {
    type: String,
    default: 'compact',
    validator: (value) => ['default', 'comfortable', 'compact'].includes(value),
  },
});
```

**Return Values:**
- Backend: Use Pydantic response models for type safety
- Frontend: Return values directly or use computed refs

## Module Design

**Exports (Backend):**
```python
# Router files export router instance
router = APIRouter(tags=["phenopackets-crud"])

# Models export classes directly
from app.phenopackets.models import Phenopacket, PhenopacketCreate
```

**Exports (Frontend):**
```javascript
// Named exports preferred
export function getSexIcon(sex) { ... }
export function getSexChipColor(sex) { ... }
export function formatSex(sex) { ... }

// Default export for backward compatibility
export default { sanitizeLogData, containsSensitiveData, REDACTION_PATTERNS };
```

**Barrel Files:** Not heavily used; prefer direct imports

## Vue Component Conventions

**Block Order (enforced by ESLint):**
1. `<template>`
2. `<script setup>`
3. `<style scoped>`

**Props:**
- Always define type and default
- Use `defineProps()` in `<script setup>`

**Component Naming:**
- Multi-word names preferred (ESLint rule disabled but follow anyway)
- Use `App` prefix for common components: `AppDataTable`, `AppPagination`

## UI Color Conventions

**Reference:** `docs/COLOR_STYLE_GUIDE.md`

**Semantic Colors (Vuetify lighten-3 variants):**
- Subject IDs: `teal-lighten-3`
- Male: `blue-lighten-3`, Female: `pink-lighten-3`
- Has data: `green-lighten-3` (features), `blue-lighten-3` (variants), `orange-lighten-3` (publications)
- Empty/Unknown: `grey-lighten-2`

**Use centralized utilities:**
```javascript
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';
```

## Data Table Conventions

**Server-side pagination required:**
```vue
<AppDataTable
  :server-side="true"
  :items="phenopackets"
  :items-length="totalCount"
  @update:options="onOptionsChange"
>
```

**Sort parameter format:**
- JSON:API compliant: `sort=-created_at,subject_id`
- Prefix `-` for descending order

---

*Convention analysis: 2026-01-19*
