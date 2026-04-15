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
- `roadmaps/2026-04-10-codebase-refactor-roadmap-design.md`
- `specs/2026-04-12-wave-7-d1-state-machine-design.md`
- `specs/2026-04-14-wave-7-d2-comments-and-clone-advancement-design.md`
- `plans/2026-04-12-wave-7-d1-state-machine.md`
- `plans/2026-04-14-wave-7-d2-comments-and-clone-advancement.md` — feature-specific supporting plan, not the release driver
- `plans/variant-annotation-implementation-plan.md`
- `reviews/2026-04-11-platform-readiness-review.md`
- `reviews/2026-04-15-path-to-8plus-and-pr-254-review.md` — supporting assessment for the master release-hardening plan
- `reviews/2026-04-15-senior-codebase-platform-review.md` — supporting assessment for the master release-hardening plan
- `reviews/codebase-best-practices-review-2026-04-09.md`
