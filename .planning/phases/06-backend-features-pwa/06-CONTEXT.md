# Phase 6: Backend Features & PWA - Context

**Gathered:** 2026-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Add user tracking for aggregation endpoints (logged-in users only) and implement PWA with service worker caching for offline support. User tracking logs which aggregations authenticated users access. PWA enables offline viewing of cached data and the 3D structure viewer.

</domain>

<decisions>
## Implementation Decisions

### User Tracking Scope
- Track endpoint + user ID + timestamp for aggregation requests
- Only track logged-in users — anonymous users are not tracked at all
- Log as 'anonymous' is NOT used — simply skip tracking for unauthenticated requests
- Remove TODO comment from aggregations.py as part of implementation

### User Tracking Storage
- **Research needed:** Investigate best practices for tracking data storage (logs vs database vs both)
- Researcher should evaluate: query requirements, retention, performance impact, privacy compliance

### PWA Caching Strategy
- **Structure file (2h8r.cif):** CacheFirst — always serve from cache, fastest loads
- **API responses:** NetworkFirst — fresh data when online, cached fallback when offline
- **Static assets (JS, CSS, images):** Precache all on first visit — guaranteed offline capability
- **API cache expiration:** Session-based — cache cleared when browser/tab closes

### Offline Experience
- **Fallback page:** Simple message — "You're offline. Please reconnect to continue." with retry button
- **Status indicator:** Review existing API connection indicator in codebase and integrate with it
- **Retry behavior:** Auto-retry when back online — automatically reload the page user was trying to access
- **3D structure viewer:** Full offline support — works offline with cached 2h8r.cif file

### Install Experience
- **Install prompts:** No custom prompts — let browser handle natively
- **App name:** "HNF1B-DB" (short form for home screen)
- **Display mode:** Standalone — looks like native app, no browser chrome
- **Theme color:** Use existing teal primary color from design tokens

### Claude's Discretion
- Exact logging format and log levels
- Service worker registration timing
- Precache manifest contents (which specific files)
- Offline page styling and layout
- PWA icon sizes and formats

</decisions>

<specifics>
## Specific Ideas

- Integrate offline status with existing API connection indicator rather than creating new UI
- Structure file should work fully offline for 3D visualization
- Session-based cache expiration keeps data fresh between visits

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-backend-features-pwa*
*Context gathered: 2026-01-20*
