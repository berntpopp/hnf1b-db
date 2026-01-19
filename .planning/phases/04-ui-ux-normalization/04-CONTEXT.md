# Phase 4: UI/UX Normalization - Context

**Gathered:** 2026-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a consistent design system across all views with design tokens, standardized Vuetify theme, and reusable UI components (PageHeader.vue, DataTableToolbar.vue). This phase establishes visual consistency and component patterns. New features or functionality are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Color System
- Modernize slightly: Keep teal (#009688) as primary brand color, refresh with deeper variants
- Accent color: Change from coral (#FF8A65) to gold/amber for better visual harmony
- Chart/chip unification: Ensure charts use the same semantic colors as chips throughout the app (sex: blue/pink, features: green, publications: orange)
- Dark mode preparation: Structure design tokens to support future dark mode (Global → Alias → Component hierarchy), but don't implement dark mode itself
- Maintain existing semantic color system from docs/COLOR_STYLE_GUIDE.md

### Component Patterns - PageHeader.vue
- Semantic HTML structure: Use `<header>` element with `<h1>` for page title
- Include subtitle support via slot or prop
- Actions slot for page-level actions (buttons, toggles)
- Accessibility focus: Manage focus on navigation, ensure screen reader compatibility
- SEO optimization: Semantic heading hierarchy, structured data support where applicable
- Props: title, subtitle, breadcrumbs (optional)
- Slots: actions, prepend (for icons/badges)

### Component Patterns - DataTableToolbar.vue
- Full toolbar system with:
  - Search input with debounce
  - Filter chips for active filters
  - Result count display
  - Column visibility settings menu
  - Export actions (where applicable)
- Batch actions: Inline in toolbar (not floating bottom bar)
- Progressive disclosure: Advanced filters in expandable section
- Responsive: Collapse to icon buttons on mobile
- Props: searchPlaceholder, filterOptions, showColumnSettings, showExport
- Events: @search, @filter-change, @column-toggle, @export

### Spacing & Typography
- Spacing system: Document Vuetify's existing system with semantic aliases
  - `--spacing-xs`: 4px (ma-1)
  - `--spacing-sm`: 8px (ma-2)
  - `--spacing-md`: 16px (ma-4)
  - `--spacing-lg`: 24px (ma-6)
  - `--spacing-xl`: 32px (ma-8)
- Typography: Keep Roboto (Vuetify default)
- Audit current typography usage and adjust minimally for WCAG accessibility (4.5:1 contrast, 1.5× line height for body text)
- Don't create new spacing system, document what exists

### Migration Approach
- Order: Design Tokens → Theme Update → Components → Views (incremental)
- First reference view: Phenopackets list (most comprehensive table view)
- Migration style: Clean break (not gradual deprecation with legacy classes)
- Each view gets migrated fully before moving to next
- Test each migrated view visually before proceeding

### Claude's Discretion
- Exact shade values for refreshed teal variants
- Specific gold/amber hex code selection
- Component internal implementation details
- Order of views after Phenopackets list
- Exact responsive breakpoints for toolbar collapse

</decisions>

<specifics>
## Specific Ideas

- Charts should use the same color for "Male" as chips do (currently inconsistent)
- Reference Linear's clean card design for overall aesthetic direction
- The existing COLOR_STYLE_GUIDE.md has good semantic color definitions to preserve
- Publication timeline chart colors should match publication chips
- Consider Atlassian's 8px grid system as validation for Vuetify's spacing

</specifics>

<deferred>
## Deferred Ideas

- Dark mode toggle implementation — future phase (tokens prepared now)
- Advanced filtering UI with saved filter presets — separate feature
- Drag-and-drop column reordering — out of scope for normalization

</deferred>

## Baseline Screenshots

Screenshots captured for before/after comparison in `.playwright-mcp/`:

| View | File | Notes |
|------|------|-------|
| Home | baseline-01-home.png | Hero section, feature cards |
| Phenopackets List | baseline-02-phenopackets.png | Data table, filters, pagination |
| Variants List | baseline-03-variants.png | Data table with variant data |
| Publications List | baseline-04-publications.png | Publication cards/table |
| Aggregations | baseline-05-aggregations.png | Charts dashboard |
| Phenopacket Detail | baseline-06-phenopacket-detail.png | Individual phenopacket view |
| Variant Detail | baseline-07-variant-detail.png | Individual variant view |
| Publication Detail | baseline-08-publication-detail.png | Individual publication view |

---

*Phase: 04-ui-ux-normalization*
*Context gathered: 2026-01-20*
