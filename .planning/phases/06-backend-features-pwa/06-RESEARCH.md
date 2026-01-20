# Phase 6: Backend Features & PWA - Research

**Researched:** 2026-01-20
**Domain:** User tracking, audit logging, PWA/Service Workers
**Confidence:** HIGH

## Summary

This phase combines two distinct features: user tracking for aggregation endpoints (backend) and Progressive Web App (PWA) capabilities (frontend). Research confirms:

1. **User tracking** should use structured logging (not database) for GDPR compliance, aligning with the existing `audit_logger.py` pattern already in the codebase
2. **PWA implementation** with `vite-plugin-pwa` is well-suited for this project, with straightforward configuration for the required caching strategies
3. The existing health status indicator in `FooterBar.vue` can be extended for offline awareness

**Primary recommendation:** Extend existing audit logging pattern for user tracking; use vite-plugin-pwa with workbox for PWA caching.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite-plugin-pwa | ^1.2.0 | PWA generation | Zero-config, Vite-native, workbox integration |
| workbox (bundled) | v7.x | Service worker caching | Industry standard, bundled with vite-plugin-pwa |
| Python logging | stdlib | User tracking | Already used in audit_logger.py, GDPR-compliant |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| workbox-expiration | (bundled) | Cache expiration | API response cache management |
| workbox-strategies | (bundled) | Caching strategies | CacheFirst/NetworkFirst patterns |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Logging | Database table | Logging is simpler, no schema migration, easier GDPR deletion |
| vite-plugin-pwa | Manual SW | Plugin handles 90% of boilerplate automatically |

**Installation:**
```bash
npm install vite-plugin-pwa -D
```

## Architecture Patterns

### Recommended Approach: User Tracking

**Pattern: Extend Existing Audit Logger**

The codebase already has `backend/app/utils/audit_logger.py` with a well-designed pattern for GDPR-compliant logging. This should be extended, NOT replaced.

```python
# Source: Existing pattern in backend/app/utils/audit_logger.py
def log_aggregation_access(
    user_id: int,
    endpoint: str,
    timestamp: datetime,
) -> None:
    """Log aggregation endpoint access for authenticated users.

    Only logs for authenticated users - anonymous access is not tracked
    per CONTEXT.md decision.
    """
    log_entry = {
        "event": "AGGREGATION_ACCESS",
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "user_id": user_id,
        "endpoint": endpoint,
    }
    audit_logger.info("AGGREGATION_ACCESS", extra=log_entry)
```

**Why logging over database:**
1. **Query requirements:** Context says "track" not "query" - logging suffices
2. **Retention:** Log rotation handles GDPR deletion automatically
3. **Performance:** Zero latency impact (async logging)
4. **Privacy:** Centralized audit log is easier to export/delete for GDPR requests
5. **Existing pattern:** Matches `log_variant_search` already in use

### Recommended Approach: Optional User Dependency

**Pattern: Optional Authentication Dependency**

Create a new dependency that returns `User | None` instead of raising 401:

```python
# Source: FastAPI Users pattern + existing dependencies.py
from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Make security scheme optional (auto_error=False)
optional_security = HTTPBearer(auto_error=False)

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.

    Unlike get_current_user, this does NOT raise 401 for missing tokens.
    Used for optional tracking in public endpoints.
    """
    if credentials is None:
        return None

    try:
        # Reuse existing token verification logic
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        username = payload.get("sub")
        if not username:
            return None

        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        return user
    except Exception:
        # Any error (invalid token, expired, etc.) returns None
        return None
```

### PWA Architecture Pattern

**Pattern: vite-plugin-pwa Configuration**

```javascript
// Source: vite-pwa-org.netlify.app/guide/
import { VitePWA } from 'vite-plugin-pwa';

VitePWA({
  registerType: 'autoUpdate',
  includeAssets: ['favicon.ico', '2h8r.cif', 'offline.html'],
  manifest: {
    name: 'HNF1B Database',
    short_name: 'HNF1B-DB',
    description: 'Clinical and genetic data for HNF1B-related disorders',
    theme_color: '#009688', // From COLORS.PRIMARY in designTokens.js
    background_color: '#F5F7FA', // From COLORS.BACKGROUND
    display: 'standalone',
    icons: [
      { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
      { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
      { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  },
  workbox: {
    // Precache static assets
    globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],

    // Runtime caching strategies
    runtimeCaching: [
      // Structure file: CacheFirst (rarely changes)
      {
        urlPattern: /\/2h8r\.cif$/,
        handler: 'CacheFirst',
        options: {
          cacheName: 'structure-files',
          expiration: {
            maxEntries: 1,
            maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
          },
        },
      },
      // API responses: NetworkFirst (fresh data when online)
      {
        urlPattern: /\/api\/v2\/.*/,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'api-cache',
          networkTimeoutSeconds: 10,
          expiration: {
            maxEntries: 50,
            maxAgeSeconds: 60 * 60, // 1 hour
          },
          cacheableResponse: {
            statuses: [0, 200],
          },
        },
      },
    ],

    // Offline fallback
    navigateFallback: '/offline.html',
  },
})
```

### Anti-Patterns to Avoid
- **Database for tracking:** Adds migration complexity, harder GDPR deletion
- **Tracking anonymous users:** Violates CONTEXT.md decision, unnecessary data collection
- **Custom service worker:** Plugin handles 90% of complexity automatically
- **StaleWhileRevalidate for API:** Would show stale data as current; NetworkFirst is safer

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Service worker | Manual SW registration | vite-plugin-pwa | Handles precaching, updates, registration |
| Workbox config | Raw workbox-build | Plugin's workbox option | Integrated with Vite build |
| Manifest generation | Manual manifest.json | Plugin's manifest option | Auto-injected into HTML |
| Cache strategies | Custom fetch handlers | workbox-strategies | Tested, handles edge cases |
| Offline detection | Manual navigator.onLine | healthService exists | Already in FooterBar.vue |

**Key insight:** vite-plugin-pwa abstracts away service worker complexity. The 2h8r.cif file (554KB) is a perfect CacheFirst candidate since protein structures don't change.

## Common Pitfalls

### Pitfall 1: PWA Icon Size Requirements
**What goes wrong:** Browser won't show install prompt if icons < 192x192
**Why it happens:** Current icons are only 16x16, 32x32, 48x48
**How to avoid:** Generate 192x192 and 512x512 versions from HNF1B-db_logo.svg
**Warning signs:** No install prompt in browser, Lighthouse PWA audit fails

### Pitfall 2: Service Worker Caching Stale API Data
**What goes wrong:** Users see outdated data without realizing it
**Why it happens:** CacheFirst or StaleWhileRevalidate used for API
**How to avoid:** Use NetworkFirst for API routes (fetches fresh, falls back to cache)
**Warning signs:** Data doesn't update after backend changes

### Pitfall 3: Optional Auth Breaking Existing Endpoints
**What goes wrong:** Changing auth dependency affects protected endpoints
**Why it happens:** Modifying `get_current_user` instead of creating new dependency
**How to avoid:** Create separate `get_current_user_optional`, leave original untouched
**Warning signs:** 401 errors on protected endpoints

### Pitfall 4: Logging PII in Audit Trail
**What goes wrong:** User email/full name in logs creates GDPR exposure
**Why it happens:** Logging entire user object instead of just ID
**How to avoid:** Only log user.id (integer), never email/name
**Warning signs:** Email addresses visible in log files

### Pitfall 5: Offline Page Not in Build
**What goes wrong:** navigateFallback shows blank page
**Why it happens:** offline.html not included in includeAssets
**How to avoid:** Add 'offline.html' to includeAssets array
**Warning signs:** Blank page when offline instead of fallback

## Code Examples

Verified patterns from official sources:

### Optional User Dependency Usage
```python
# Source: FastAPI dependency pattern + existing codebase
from typing import Optional

@router.get("/aggregate/summary")
async def get_summary_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get summary statistics with optional user tracking."""

    # Track only if user is authenticated
    if current_user:
        log_aggregation_access(
            user_id=current_user.id,
            endpoint="/aggregate/summary",
            timestamp=datetime.now(timezone.utc),
        )

    # ... rest of endpoint logic unchanged ...
```

### Offline Page Structure
```html
<!-- Source: vite-pwa-org.netlify.app + Vuetify design system -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Offline - HNF1B-DB</title>
  <style>
    body {
      font-family: Roboto, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      background: #F5F7FA;
      color: #37474F;
      text-align: center;
    }
    .container { padding: 2rem; }
    h1 { color: #009688; margin-bottom: 1rem; }
    button {
      background: #009688;
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 1rem;
      margin-top: 1rem;
    }
    button:hover { background: #00796B; }
  </style>
</head>
<body>
  <div class="container">
    <h1>You're Offline</h1>
    <p>Please reconnect to continue using HNF1B-DB.</p>
    <button onclick="location.reload()">Retry</button>
  </div>
</body>
</html>
```

### Aggregation Tracking Function
```python
# Source: Extends existing audit_logger.py pattern
def log_aggregation_access(
    user_id: int,
    endpoint: str,
    timestamp: datetime,
) -> None:
    """Log aggregation endpoint access for authenticated users only.

    Args:
        user_id: Authenticated user's ID (integer only, not email)
        endpoint: Aggregation endpoint path (e.g., "/aggregate/summary")
        timestamp: Request timestamp

    GDPR Compliance:
        - Only logs user ID (not PII like email)
        - Only tracks authenticated users (anonymous not tracked)
        - Logs can be rotated/deleted per retention policy
    """
    log_entry = {
        "event": "AGGREGATION_ACCESS",
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "user_id": user_id,
        "endpoint": endpoint,
    }

    audit_logger.info("AGGREGATION_ACCESS", extra=log_entry)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual SW registration | vite-plugin-pwa autoUpdate | 2023+ | Zero-config PWA |
| Required auth dependencies | Optional pattern (auto_error=False) | FastAPI 0.100+ | Cleaner optional auth |
| Separate manifest.json | Plugin-generated manifest | vite-plugin-pwa | Build-integrated |

**Deprecated/outdated:**
- Manual workbox-build scripts: Use plugin's workbox option instead
- workbox v6: v7 is current, bundled with plugin

## Open Questions

Things that couldn't be fully resolved:

1. **PWA Icon Generation**
   - What we know: Need 192x192 and 512x512 PNG icons
   - What's unclear: Should use existing SVG logo or create new PWA-specific icons?
   - Recommendation: Generate from HNF1B-db_logo.svg using sharp or similar tool

2. **TODO Comment Location**
   - What we know: Requirements mention "aggregations.py:1247" TODO
   - What's unclear: This file has been refactored into modular structure; TODO may be removed
   - Recommendation: Verify TODO exists in current codebase; may already be resolved

3. **Session-Based API Cache**
   - What we know: CONTEXT.md requests "session-based cache expiration"
   - What's unclear: Service workers persist across sessions by design
   - Recommendation: Use short maxAgeSeconds (1 hour) as practical approximation

## Sources

### Primary (HIGH confidence)
- [vite-plugin-pwa official docs](https://vite-pwa-org.netlify.app/guide/) - PWA configuration patterns
- [Chrome Developers workbox-strategies](https://developer.chrome.com/docs/workbox/modules/workbox-strategies) - CacheFirst/NetworkFirst documentation
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) - Dependency injection patterns
- Existing codebase files:
  - `/home/bernt-popp/development/hnf1b-db/backend/app/utils/audit_logger.py` - Audit logging pattern
  - `/home/bernt-popp/development/hnf1b-db/backend/app/auth/dependencies.py` - Auth dependency pattern
  - `/home/bernt-popp/development/hnf1b-db/frontend/src/components/FooterBar.vue` - Health status indicator
  - `/home/bernt-popp/development/hnf1b-db/frontend/src/utils/designTokens.js` - Theme colors

### Secondary (MEDIUM confidence)
- [FastAPI Users optional current_user](https://fastapi-users.github.io/fastapi-users/10.1/usage/current-user/) - Optional auth pattern
- [Chapimaster PWA offline page](https://www.chapimaster.com/programming/vite/create-custom-offline-page-react-pwa) - Offline page setup
- [GDPR logging best practices](https://www.cookieyes.com/blog/gdpr-logging-and-monitoring/) - Audit trail requirements

### Tertiary (LOW confidence)
- WebSearch results for session-based cache expiration (no authoritative source found)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - vite-plugin-pwa is well-documented, existing patterns in codebase
- Architecture: HIGH - Extends existing audit_logger.py, follows FastAPI patterns
- Pitfalls: HIGH - Based on official docs and codebase analysis

**Research date:** 2026-01-20
**Valid until:** 2026-02-20 (30 days - stable domain)

---

## Implementation Notes for Planner

### Files to Create
1. `frontend/public/offline.html` - Offline fallback page
2. `frontend/public/pwa-192x192.png` - PWA icon (generate from SVG)
3. `frontend/public/pwa-512x512.png` - PWA icon (generate from SVG)

### Files to Modify
1. `backend/app/auth/dependencies.py` - Add `get_current_user_optional`
2. `backend/app/utils/audit_logger.py` - Add `log_aggregation_access`
3. `backend/app/phenopackets/routers/aggregations/*.py` - Add optional user tracking
4. `frontend/vite.config.js` - Add VitePWA plugin configuration
5. `frontend/package.json` - Add vite-plugin-pwa dependency

### Existing Assets to Leverage
- `frontend/public/2h8r.cif` (554KB) - Structure file for CacheFirst
- `frontend/src/utils/designTokens.js` - Theme colors (#009688 primary, #F5F7FA background)
- `frontend/src/services/healthService.js` - Offline detection already exists
- `frontend/src/components/FooterBar.vue` - Shows offline status already
