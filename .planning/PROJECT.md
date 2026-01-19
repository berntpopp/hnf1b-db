# HNF1B Database - Final Polish Milestone

## What This Is

A comprehensive code quality and polish milestone for the HNF1B Database, addressing 14 GitHub issues across code quality, UI/UX, features, testing, and documentation. This milestone transforms the existing production application into a polished, maintainable, and accessible codebase ready for long-term maintenance.

## Core Value

**Ship a production-quality codebase** — fix technical debt, improve accessibility, and ensure maintainability before adding new features.

## Requirements

### Validated

- ✓ Full-stack monorepo with FastAPI backend and Vue.js 3 frontend — existing
- ✓ GA4GH Phenopackets v2 compliance — existing
- ✓ JSON:API v1.1 pagination — existing
- ✓ VRS 2.0 compliant variant identifiers — existing
- ✓ D3.js data visualizations (charts) — existing
- ✓ NGL.js 3D protein structure viewer — existing
- ✓ JWT authentication system — existing

### Active

**Code Quality & Technical Debt:**
- [ ] Fix Pydantic deprecation warnings (#134) — regex→pattern, Config→ConfigDict
- [ ] Extract ProteinStructure3D.vue into sub-components (#133) — reduce from 1,106 to <500 lines
- [ ] Document magic numbers with named constants (#137) — both frontend and backend
- [ ] Move hardcoded values to configuration files (#91) — frontend configuration
- [ ] Modernize test suite structure and patterns (#94) — backend pytest improvements
- [ ] Merge alembic migrations into single clean schema (#102) — consolidate 20+ migrations

**UI/UX Enhancement:**
- [ ] Normalize UI/UX design across all views (#98) — consistent colors, icons, layouts
- [ ] Add ARIA labels and accessibility support for charts (#135) — WCAG 2.1 compliance
- [ ] Add chart animations for user engagement (#139) — D3.js transitions

**Feature Enhancements:**
- [ ] Implement chart data export (CSV, PNG) (#136) — export functionality
- [ ] Implement user ID tracking for aggregation queries (#140) — audit logging
- [ ] Add service worker caching for static assets (#138) — PWA capabilities

**Testing & Documentation:**
- [ ] Add E2E tests for critical user flows (#48) — Playwright tests
- [ ] Update user documentation (#50) — user guide, API reference, changelog

### Out of Scope

- New clinical features — this milestone is polish only
- Database schema changes beyond migration consolidation — risky
- Major UI redesign — only normalization of existing patterns
- Backend API changes — only deprecation fixes and user tracking

## Context

**Existing Codebase:**
- 864 phenopackets in production
- Frontend: Vue.js 3, Vuetify 3, D3.js, NGL.js
- Backend: FastAPI, SQLAlchemy 2.0, PostgreSQL with JSONB
- Test coverage: pytest (backend), vitest (frontend)

**Technical Debt Drivers:**
- ProteinStructure3D.vue is 1,106 lines (2x guideline)
- 12 Pydantic deprecation warnings in backend
- Magic numbers scattered across codebase
- 20+ alembic migration files
- Inconsistent UI patterns across views

**Quality Gaps:**
- Charts lack accessibility support
- No chart export functionality
- No E2E test coverage
- User documentation incomplete

## Constraints

- **Timeline**: All issues should be addressable in focused phases
- **Risk**: Migration consolidation (#102) requires production backup/restore
- **Dependencies**: E2E tests (#48) and docs (#50) depend on other issues being complete
- **Testing**: All changes must pass existing test suite (`make check`)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix bugs before refactoring | Pydantic warnings may affect refactored code | — Pending |
| Refactor before features | Clean code makes features easier | — Pending |
| Migration consolidation last | Highest risk, needs other work complete first | — Pending |
| E2E tests after features | Tests should cover final functionality | — Pending |

---
*Last updated: 2026-01-19 after initialization*
