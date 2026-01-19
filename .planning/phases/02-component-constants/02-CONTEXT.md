# Phase 2: Component Refactoring & Constants - Context

**Gathered:** 2026-01-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract ProteinStructure3D.vue into sub-components and create centralized constants files for both backend and frontend. This phase delivers cleaner code organization — no new features or user-facing behavior changes.

**GitHub Issues:** #133, #137, #91

</domain>

<decisions>
## Implementation Decisions

### Component Extraction
- Props down, events up — classic Vue pattern, parent owns state
- Tightly coupled components — specific to this view, co-located in protein-structure/
- Let code dictate the split — extract natural boundaries, may differ from roadmap's suggested 5
- Parent (ProteinStructure3D.vue) remains an orchestrator — manages state, coordinates sub-components
- Shared styles file — common styles in a shared CSS file, components reference it
- Add JSDoc comments — document props, events, and key methods
- No TypeScript — plain JavaScript throughout

### Claude's Discretion (Component Extraction)
- Where 3D viewer initialization logic lives — in component or composable based on complexity

### Constants Organization
- Frontend: multiple domain files (thresholds.js, pubmed.js, etc.)
- Consider existing frontend/src/config/ structure when organizing
- Backend: constants separate from config — config.py for env-based settings, constants.py for hardcoded values
- Consider existing backend/app/core/config.py when placing constants
- Research best practices for barrel file decision (index.js re-export vs direct imports)

### Naming Conventions
- Research best practices for:
  - JavaScript constant naming (SCREAMING_SNAKE_CASE vs camelCase)
  - Python constant naming (follow PEP 8 and existing patterns)
  - Vue file naming (PascalCase.vue vs kebab-case.vue)
  - Directory naming (protein-structure/ vs ProteinStructure/)
- Follow existing codebase patterns where established

### Threshold Ownership
- Full audit of entire codebase for hardcoded numbers
- Both criteria for extraction: domain-significant values OR reused 2+ times
- Document all constants — each constant has a comment explaining its purpose
- No source citations — document what constants mean, not where they came from

</decisions>

<specifics>
## Specific Ideas

- "Research best practices using websearch" — user wants Claude to research common conventions for naming and organization rather than making arbitrary decisions
- Existing structures to consider: frontend/src/config/, backend/app/core/config.py
- Focus on natural code boundaries for component extraction rather than adhering strictly to roadmap's suggested 5 components

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-component-constants*
*Context gathered: 2026-01-19*
