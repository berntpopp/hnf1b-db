---
phase: 04-ui-ux-normalization
plan: 05
subsystem: frontend
tags:
  - PageHeader
  - design-tokens
  - views
  - hero-section
dependency-graph:
  requires:
    - 04-01
    - 04-02
  provides:
    - Detail views with PageHeader hero variant
    - Home.vue with design token colors
  affects:
    - 05-chart-polish (consistent color theming)
tech-stack:
  added: []
  patterns:
    - PageHeader hero variant for detail pages
    - Custom gradient overrides via deep selectors
    - Design token usage in templates
key-files:
  created: []
  modified:
    - frontend/src/views/PagePhenopacket.vue
    - frontend/src/views/PageVariant.vue
    - frontend/src/views/PagePublication.vue
    - frontend/src/views/Home.vue
decisions:
  - id: custom-hero-gradients
    choice: Use deep selectors to override PageHeader hero background
    rationale: Each detail page has unique color scheme (teal, pink, orange)
  - id: publication-token-color
    choice: Use orange for publications (from PUBLICATION design token)
    rationale: Consistency with design token definitions over previous cyan
  - id: phenotype-token-color
    choice: Use green for phenotypes (from PHENOTYPE design token)
    rationale: Align with DATA_COLORS semantic tokens
metrics:
  duration: 4m
  completed: 2026-01-20
---

# Phase 4 Plan 5: Detail Views & Home Page Migration Summary

**One-liner:** Migrated detail views (PagePhenopacket, PageVariant, PagePublication) to use PageHeader hero variant and updated Home.vue to use design tokens for stat card colors.

## Tasks Completed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Migrate PagePhenopacket.vue to PageHeader | Done | a9849f9 |
| 2 | Migrate PageVariant.vue and PagePublication.vue | Done | 7b66553 |
| 3 | Update Home.vue with design tokens | Done | edee470 |

## Changes Made

### Task 1: PagePhenopacket.vue Migration

**Files modified:**
- `frontend/src/views/PagePhenopacket.vue`

**Changes:**
- Replaced custom hero section with PageHeader component (hero variant)
- Imported and registered PageHeader component
- Moved stats chips (ID, sex, age, HPO count, variants count) to prepend slot
- Retained breadcrumbs computed property
- Removed redundant hero-section styling (PageHeader has its own)

### Task 2: PageVariant.vue and PagePublication.vue Migration

**Files modified:**
- `frontend/src/views/PageVariant.vue`
- `frontend/src/views/PagePublication.vue`

**PageVariant.vue changes:**
- Replaced hero section with PageHeader (hero variant)
- Moved variant chips (ID, pathogenicity, type) to prepend slot
- Created separate stats-section for quick stats cards
- Added custom pink gradient background via `:deep(.page-header--hero)` selector
- Props: `icon-color="pink-darken-2"`, `title-class="text-pink-darken-2"`

**PagePublication.vue changes:**
- Replaced hero section with PageHeader (hero variant)
- Moved publication chips (PMID link, year, individuals count) to prepend slot
- Added custom orange gradient background via `:deep(.page-header--hero)` selector
- Props: `icon-color="orange-darken-2"`, `title-class="text-orange-darken-2"`

### Task 3: Home.vue Design Tokens

**Files modified:**
- `frontend/src/views/Home.vue`

**Changes:**
- Imported DATA_COLORS from `@/utils/designTokens`
- Exposed `dataColors: DATA_COLORS` in setup return
- Updated Publications stat card to use `dataColors.PUBLICATION.vuetify` (orange-lighten-3)
- Updated Phenotypes stat card to use `dataColors.PHENOTYPE.vuetify` (green-lighten-3)
- Updated corresponding text colors to match (text-orange-darken-1, text-green-darken-1)

## Key Decisions

### 1. Custom Hero Gradients via Deep Selectors

Each detail page has a unique color scheme that distinguishes it visually:
- **PagePhenopacket:** Default teal gradient (from PageHeader)
- **PageVariant:** Pink gradient (genetic/variant theme)
- **PagePublication:** Orange gradient (publications/literature theme)

Using `:deep(.page-header--hero)` allows page-specific customization while reusing the PageHeader component.

### 2. Design Token Color Updates

Changed Home.vue stat card colors to match DATA_COLORS:
- **Publications:** cyan-darken-1 -> orange-lighten-3 (PUBLICATION token)
- **Phenotypes:** amber-darken-2 -> green-lighten-3 (PHENOTYPE token)

This ensures consistency between stat cards, chips, and charts across the application.

## Verification

- [x] All detail views use PageHeader with hero variant
- [x] All detail views have proper breadcrumb navigation
- [x] Home.vue uses design token colors for stat cards
- [x] Semantic HTML preserved (h1 for titles)
- [x] Build passes: `npm run build`
- [x] Tests pass: 295 tests passing

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Phase 4 UI/UX Normalization is now complete with:
- Design tokens foundation (04-01)
- PageHeader component (04-02)
- DataTableToolbar component (04-03)
- List views migration (04-04)
- Detail views and Home page migration (04-05)

Ready for Phase 5: Chart Polish.
