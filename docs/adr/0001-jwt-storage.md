# ADR 0001: JWT Storage Location

**Status:** Superseded by ADR 0002
**Date:** 2026-04-12
**Superseded Date:** 2026-04-23
**Superseded By:** [ADR 0002: Cookie-backed refresh sessions with in-memory access token](0002-cookie-refresh-and-memory-access-token.md)
**Context:** 2026-04-09 review flagged localStorage JWT as "vulnerable to XSS" (P5 #26)

## Superseded

This ADR no longer describes the live authentication/session design.
The application has since migrated away from `localStorage` token storage.
Current behavior is documented in ADR 0002:

- Access tokens are short-lived and kept in frontend memory only.
- Refresh tokens are stored in a rotating `HttpOnly` cookie.
- Cookie-auth mutation flows require a CSRF double-submit check using the
  readable `csrf_token` cookie and the `X-CSRF-Token` request header.

The historical decision record below is preserved for context only.

## Context

The HNF1B frontend currently stores the JWT access token and refresh
token in `localStorage`. The 2026-04-09 codebase review flagged this
as a medium-severity concern because `localStorage` is accessible to
any JavaScript that runs on the page, making it vulnerable to token
theft via XSS.

Two mitigating actions were taken in Waves 1-2:

1. **Wave 1:** The XSS vulnerability in `FAQ.vue` and `About.vue`
   (`v-html` rendering of unsanitized markdown) was fixed via a
   DOMPurify-based `sanitize()` utility. A dedicated sanitize test
   verifies injected `<script>` tags are stripped.

2. **Wave 2:** A Content Security Policy (CSP) header was added by
   `SecurityHeadersMiddleware` restricting script sources and
   frame ancestors.

## Options considered

### Option A: Migrate to HttpOnly cookies

- **Pro:** JavaScript cannot read the token. XSS cannot exfiltrate it.
- **Con:** Adds CSRF handling complexity (double-submit token, or
  `SameSite=Strict` cookie combined with an Origin-header check).
- **Con:** Requires backend changes to set and refresh cookies on
  login, refresh, and logout endpoints.
- **Con:** Breaks the existing refresh flow and all existing frontend
  code that reads the token from `localStorage` (auth store,
  `transport.js` interceptor, `session.js` helpers).
- **Cost:** ~1-2 weeks of work including tests and rollout.

### Option B: Keep localStorage + accept the residual risk

- **Pro:** Zero additional work.
- **Pro:** Wave 1 XSS fix + Wave 2 CSP + security headers narrow the
  attack surface significantly. The only remaining sinks for injected
  content go through `sanitize()`, which is tested.
- **Con:** Still vulnerable to XSS in any unfixed sink.
- **Con:** Any new dependency with an XSS sink is a risk.

### Option C: Hybrid — `sessionStorage` instead of `localStorage`

- **Pro:** Token is cleared on tab close; doesn't persist across
  browser sessions.
- **Con:** Poor UX — users re-login on every new tab.
- **Con:** Same XSS exposure as localStorage (any JS on the page can
  still read `sessionStorage`).

## Decision

**Option B: Keep localStorage with the Wave 1/2 mitigations.**

Rationale:

- The Wave 1 `sanitize()` utility + the XSS characterization test +
  the Wave 2 CSP header provide defense in depth. An attacker needs
  both (a) a new injection sink that bypasses `sanitize()` and (b) a
  CSP bypass to exfiltrate tokens.
- The HNF1B database is a curated research artifact, not a consumer
  application. It is not a high-value credential-harvesting target,
  so the cost/benefit of HttpOnly cookies is low compared to other
  roadmap priorities.
- Migration to HttpOnly is scheduled as **potential future work**,
  not a blocker. If future XSS vulnerabilities emerge, the threat
  model changes (e.g., external contributors granted write access),
  or the application grows in user base / data sensitivity, revisit
  this decision.

## Consequences

- No additional work at this time.
- The XSS test from Wave 1 must never regress — any change that
  disables or weakens it requires updating this ADR.
- Developers adding any new `v-html`, `innerHTML`, or other
  HTML-string-based rendering must pipe through `sanitize()` from
  `@/utils/sanitize.js`.
- A future migration to HttpOnly cookies should supersede this ADR
  with an "ADR-N" that references this record and updates this
  record's status to **Superseded by ADR-N**.

## References

- [frontend/src/utils/sanitize.js](../../frontend/src/utils/sanitize.js) — Wave 1 sanitize utility
- [frontend/tests/unit/utils/sanitize.spec.js](../../frontend/tests/unit/utils/sanitize.spec.js) — XSS characterization test
- [backend/app/core/security_headers.py](../../backend/app/core/security_headers.py) — Wave 2 CSP middleware
- [.planning/reviews/codebase-best-practices-review-2026-04-09.md](../../.planning/reviews/codebase-best-practices-review-2026-04-09.md) — original finding (P5 #26, §8 Security)
