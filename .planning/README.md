# Planning Index

`.planning/` is the single home for internal planning material. `docs/` is for
durable reference documentation only.

## Layout

- `codebase/` — current-state architecture, structure, conventions, testing, and concerns
- `specs/` — active design specs that still guide implementation
- `plans/` — active execution plans and implementation guides
- `roadmaps/` — active multi-phase strategy documents
- `reviews/` — active assessments and review documents
- `tracking/` — active issue or milestone tracking material
- `archive/specs/` — completed or superseded specs
- `archive/plans/` — completed or superseded implementation plans
- `archive/roadmaps/` — retired roadmap material
- `archive/reviews/` — historical reviews, exit notes, and retrospectives
- `archive/tracking/` — historical issue trackers, TODOs, and migration-era planning

## Filing Rules

1. New specs go in `specs/`.
2. New implementation plans go in `plans/`.
3. Broad sequencing or decomposition work goes in `roadmaps/`.
4. Reviews that still drive work stay in `reviews/`; otherwise archive them.
5. If a document is finished, superseded, or mainly historical, move it to the
   matching `archive/` type directory aggressively.

## Current Active Set

- `plans/2026-04-15-release-hardening-and-8plus-plan.md` — current source of truth for release-readiness sequencing and go/no-go criteria
- `reviews/2026-04-17-ui-ux-design-review.md` — current UI/UX assessment after PR #263; still contains actionable medium/low follow-ups

## Current Notes

- The April 10 roadmap and the April 12-17 implementation specs/plans were implemented or superseded and have been archived.
- `codebase/*.md` remains the reference area for current-state architecture and conventions, but several files are now stale and need a refresh before they should be treated as authoritative.
