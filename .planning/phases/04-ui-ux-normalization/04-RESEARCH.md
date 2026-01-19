# Phase 04: UI/UX Normalization - Research

**Researched:** 2026-01-20
**Domain:** Vue 3 + Vuetify 3 Design System, Component Patterns
**Confidence:** HIGH

## Summary

This research analyzed the existing HNF1B Database codebase to identify current UI patterns, inconsistencies, and establish a clear path for design system normalization. The codebase already has strong foundations: a well-documented COLOR_STYLE_GUIDE.md, utility functions for colors and sex display, reusable components (AppDataTable, AppTableToolbar, AppPagination), and consistent use of Vuetify 3 Material Design.

The key findings reveal three main areas for normalization:
1. **Color system fragmentation**: Chart colors (in aggregationConfig.js) don't match chip colors (in utils/sex.js and utils/colors.js), specifically for sex display where charts use `#1976D2` for MALE while chips use Vuetify's `blue-lighten-3` (#64B5F6)
2. **Page header inconsistency**: Each view implements its own page header pattern (Home uses hero sections, Phenopackets/Variants/Publications use AppDataTable titles, PagePhenopacket uses a custom hero + breadcrumbs)
3. **Missing design tokens layer**: Colors and spacing are defined in multiple places without a single source of truth that maps to both Vuetify theme and D3 charts

**Primary recommendation:** Create a centralized `designTokens.js` file that exports both Vuetify color classes AND hex values for charts, then update all existing color utilities and chart configurations to import from this single source.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vuetify | 3.11.2 | UI Component Framework | Already in use, Material Design 3 |
| Vue | 3.5.26 | Frontend Framework | Already in use |
| D3.js | 7.9.0 | Chart Visualizations | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @mdi/font | 7.4.47 | Material Design Icons | Already configured |
| Pinia | 3.0.4 | State Management | For shared component state if needed |

### No New Dependencies Required

This phase should NOT introduce new packages. Vuetify 3's theming system and CSS custom properties are sufficient for:
- Design tokens via Vuetify's `createVuetify()` theme configuration
- Spacing system via Vuetify's existing classes (ma-1 through ma-8)
- Typography via Vuetify's text utilities

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── utils/
│   └── designTokens.js          # NEW: Centralized design tokens
├── components/
│   └── common/
│       ├── PageHeader.vue       # NEW: Reusable page header
│       ├── DataTableToolbar.vue # NEW: Enhanced toolbar (builds on AppTableToolbar)
│       ├── AppDataTable.vue     # EXISTS: Keep as-is
│       ├── AppTableToolbar.vue  # EXISTS: May deprecate after DataTableToolbar
│       └── AppPagination.vue    # EXISTS: Keep as-is
├── plugins/
│   └── vuetify.js               # MODIFY: Import design tokens
└── views/
    └── *.vue                    # MODIFY: Use new components
```

### Pattern 1: Design Tokens Architecture

**What:** Three-tier token hierarchy (Global -> Semantic -> Component)
**When to use:** All color definitions, spacing aliases, typography scale

**Example:**
```javascript
// frontend/src/utils/designTokens.js

/**
 * Design Tokens - Single Source of Truth
 *
 * Architecture:
 * 1. GLOBAL - Raw color values (brand colors, primitives)
 * 2. SEMANTIC - Purpose-based aliases (success, error, male, female)
 * 3. COMPONENT - Component-specific mappings (chart colors, chip colors)
 */

// ==================== GLOBAL TOKENS ====================
// Brand colors (from existing theme)
export const COLORS = {
  // Primary brand - Teal (keep established brand)
  PRIMARY: '#009688',
  PRIMARY_DARKEN_1: '#00796B',
  PRIMARY_LIGHTEN_3: '#4DB6AC',
  PRIMARY_LIGHTEN_4: '#80CBC4',

  // Secondary - Slate
  SECONDARY: '#37474F',
  SECONDARY_DARKEN_1: '#263238',

  // Accent - Gold/Amber (decision: change from coral)
  ACCENT: '#FFB300',
  ACCENT_LIGHTEN_3: '#FFE082',

  // Surfaces
  BACKGROUND: '#F5F7FA',
  SURFACE: '#FFFFFF',

  // Status colors (WCAG compliant)
  ERROR: '#B00020',
  SUCCESS: '#4CAF50',
  WARNING: '#FB8C00',
  INFO: '#2196F3',
};

// ==================== SEMANTIC TOKENS ====================
// Sex/Gender - CRITICAL: Used by both chips AND charts
export const SEX_COLORS = {
  MALE: {
    vuetify: 'blue-lighten-3',
    hex: '#64B5F6',
  },
  FEMALE: {
    vuetify: 'pink-lighten-3',
    hex: '#F48FB1',
  },
  OTHER_SEX: {
    vuetify: 'purple-lighten-3',
    hex: '#BA68C8',
  },
  UNKNOWN_SEX: {
    vuetify: 'grey-lighten-2',
    hex: '#EEEEEE',
  },
};

// Pathogenicity - ACMG classification
export const PATHOGENICITY_COLORS = {
  PATHOGENIC: {
    vuetify: 'red-lighten-1',
    hex: '#EF5350',
  },
  LIKELY_PATHOGENIC: {
    vuetify: 'orange-lighten-1',
    hex: '#FF9800',
  },
  VUS: {
    vuetify: 'yellow-darken-1',
    hex: '#FBC02D',
  },
  LIKELY_BENIGN: {
    vuetify: 'light-green-lighten-1',
    hex: '#9CCC65',
  },
  BENIGN: {
    vuetify: 'green-lighten-1',
    hex: '#66BB6A',
  },
};

// Data categories
export const DATA_COLORS = {
  PHENOPACKET: {
    vuetify: 'teal-lighten-3',
    hex: '#4DB6AC',
  },
  VARIANT: {
    vuetify: 'pink-lighten-3',
    hex: '#F48FB1',
  },
  PUBLICATION: {
    vuetify: 'orange-lighten-3',
    hex: '#FFB74D',
  },
  PHENOTYPE: {
    vuetify: 'green-lighten-3',
    hex: '#81C784',
  },
};

// ==================== SPACING TOKENS ====================
// Document Vuetify's system with semantic names
export const SPACING = {
  XS: 4,   // ma-1
  SM: 8,   // ma-2
  MD: 16,  // ma-4
  LG: 24,  // ma-6
  XL: 32,  // ma-8
};

// ==================== HELPERS ====================
/**
 * Get hex color for charts from any semantic token
 */
export function getChartColor(category, value) {
  const colorMap = {
    sex: SEX_COLORS,
    pathogenicity: PATHOGENICITY_COLORS,
    data: DATA_COLORS,
  };
  return colorMap[category]?.[value]?.hex || '#9E9E9E';
}

/**
 * Get Vuetify color class for chips
 */
export function getVuetifyColor(category, value) {
  const colorMap = {
    sex: SEX_COLORS,
    pathogenicity: PATHOGENICITY_COLORS,
    data: DATA_COLORS,
  };
  return colorMap[category]?.[value]?.vuetify || 'grey-lighten-2';
}

/**
 * Build color map for D3 charts (label -> hex)
 */
export function buildChartColorMap(category) {
  const colorMap = {
    sex: SEX_COLORS,
    pathogenicity: PATHOGENICITY_COLORS,
    data: DATA_COLORS,
  }[category];

  if (!colorMap) return {};

  return Object.fromEntries(
    Object.entries(colorMap).map(([key, value]) => [key, value.hex])
  );
}
```

### Pattern 2: PageHeader Component

**What:** Semantic HTML header with consistent structure
**When to use:** All page-level views (list pages, detail pages)

**Example:**
```vue
<!-- frontend/src/components/common/PageHeader.vue -->
<template>
  <header class="page-header" :class="{ 'page-header--hero': variant === 'hero' }">
    <v-container :fluid="fluid">
      <!-- Breadcrumbs -->
      <nav v-if="breadcrumbs?.length" aria-label="Breadcrumb">
        <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0 mb-2" />
      </nav>

      <!-- Title Row -->
      <div class="d-flex align-center flex-wrap gap-3">
        <!-- Back button -->
        <v-btn
          v-if="showBack"
          icon="mdi-arrow-left"
          variant="text"
          size="small"
          aria-label="Go back"
          @click="$emit('back')"
        />

        <!-- Icon -->
        <v-icon v-if="icon" :color="iconColor" size="large" aria-hidden="true">
          {{ icon }}
        </v-icon>

        <!-- Title + Subtitle -->
        <div class="flex-grow-1">
          <h1 class="text-h5 font-weight-bold" :class="titleClass">
            {{ title }}
          </h1>
          <p v-if="subtitle" class="text-body-2 text-medium-emphasis mb-0">
            {{ subtitle }}
          </p>
        </div>

        <!-- Prepend slot (for badges/chips next to title) -->
        <slot name="prepend" />

        <!-- Actions slot -->
        <div v-if="$slots.actions" class="d-flex align-center gap-2">
          <slot name="actions" />
        </div>
      </div>
    </v-container>
  </header>
</template>

<script>
export default {
  name: 'PageHeader',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    icon: { type: String, default: '' },
    iconColor: { type: String, default: 'teal-darken-2' },
    breadcrumbs: { type: Array, default: () => [] },
    showBack: { type: Boolean, default: false },
    variant: {
      type: String,
      default: 'default',
      validator: (v) => ['default', 'hero', 'compact'].includes(v),
    },
    fluid: { type: Boolean, default: true },
    titleClass: { type: String, default: 'text-teal-darken-2' },
  },
  emits: ['back'],
};
</script>

<style scoped>
.page-header {
  padding: 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.page-header--hero {
  padding: 24px 0;
  background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 50%, #f5f7fa 100%);
}
</style>
```

### Pattern 3: DataTableToolbar Component

**What:** Enhanced toolbar with search, filters, result count, and actions
**When to use:** All data table views (Phenopackets, Variants, Publications)

**Approach:** Build on existing AppTableToolbar, adding:
- Filter chips display
- Column visibility menu (optional)
- Export action slot
- Responsive collapse behavior

### Anti-Patterns to Avoid
- **Duplicating color definitions:** Don't define the same color in multiple files; import from designTokens.js
- **Hardcoded hex in Vue templates:** Use Vuetify color classes or computed properties that reference tokens
- **Mixing Options API and Composition API in new components:** Use Options API for consistency with existing codebase
- **Creating custom spacing values:** Use Vuetify's built-in spacing classes (ma-1 through ma-8)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Color consistency | Multiple color utility files | Single designTokens.js | Charts and chips need same source |
| Responsive spacing | Custom CSS media queries | Vuetify's responsive spacing (ma-md-4) | Already handles breakpoints |
| Typography scale | Custom font sizes | Vuetify text classes (text-h5, text-body-1) | WCAG compliant, consistent |
| Icon system | Custom icon components | @mdi/font with Vuetify | Already configured, 7000+ icons |
| Dark mode prep | CSS variables manually | Vuetify theme configuration | Built-in dark mode support |

**Key insight:** Vuetify 3 already provides a complete design system. The goal is documentation and unification, not replacement.

## Common Pitfalls

### Pitfall 1: Chart/Chip Color Mismatch
**What goes wrong:** D3 charts use different hex values than Vuetify chips for the same semantic meaning
**Why it happens:** aggregationConfig.js defines colors independently from utils/sex.js
**How to avoid:** Single source of truth in designTokens.js with both formats
**Warning signs:** "Male" appears as different blue in chart vs chip

**Current inconsistency identified:**
```javascript
// aggregationConfig.js - Chart colors
getSexDistribution: {
  MALE: '#1976D2',    // Dark blue
  FEMALE: '#E91E63',  // Pink (different shade)
}

// utils/sex.js - Chip colors
SEX_CHIP_COLORS = {
  MALE: 'blue-lighten-3',    // #64B5F6 (lighter blue)
  FEMALE: 'pink-lighten-3',  // #F48FB1 (lighter pink)
}
```

### Pitfall 2: Inconsistent Page Headers
**What goes wrong:** Each view implements its own header structure
**Why it happens:** No shared PageHeader component existed
**How to avoid:** Create PageHeader.vue and migrate all views
**Warning signs:** Different heading levels (h1, h3, h6), different layouts between pages

**Current patterns found:**
- Home.vue: `<h1 class="text-h3">` in custom hero section
- Phenopackets.vue: Uses AppDataTable `title` prop (renders as subtitle-1)
- PagePhenopacket.vue: `<h1 class="text-h6">` in custom hero with breadcrumbs
- AggregationsDashboard.vue: No page header, tabs are the main structure

### Pitfall 3: Semantic HTML Gaps
**What goes wrong:** Page titles use non-semantic heading levels or divs
**Why it happens:** Vuetify components don't enforce semantic HTML
**How to avoid:** PageHeader.vue uses `<header>` element with `<h1>` for main title
**Warning signs:** Screen reader testing shows inconsistent navigation

### Pitfall 4: Typography Inconsistency
**What goes wrong:** Mixed use of text-h4, text-h5, text-h6 for similar content
**Why it happens:** No documented typography hierarchy
**How to avoid:** Document the hierarchy:
- `text-h4`: Section titles within cards
- `text-h5`: Page titles (via PageHeader)
- `text-h6`: Subsection titles, card headers
- `text-subtitle-1`: Table titles, toolbar titles
- `text-body-1`: Primary content
- `text-body-2`: Secondary content, table cells
- `text-caption`: Metadata, timestamps

### Pitfall 5: Card Style Variations
**What goes wrong:** Cards use different elevation, rounding, borders
**Why it happens:** Different developers, different times
**How to avoid:** Use Vuetify defaults (already configured in vuetify.js)
**Warning signs:** Some cards use `elevation="2"`, others use `variant="outlined"`

**Current vuetify.js defaults (keep these):**
```javascript
VCard: {
  rounded: 'lg',
  elevation: 2,
}
```

## Code Examples

Verified patterns from the existing codebase:

### Sex Display Pattern (from utils/sex.js)
```javascript
// Centralized in utils/sex.js - KEEP THIS PATTERN
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';

// In template:
<v-chip :color="getSexChipColor(item.sex)" size="x-small" variant="flat">
  <v-icon start size="x-small">{{ getSexIcon(item.sex) }}</v-icon>
  {{ formatSex(item.sex) }}
</v-chip>
```

### Data Table Pattern (from Phenopackets.vue)
```vue
<!-- KEEP THIS PATTERN - Already standardized -->
<AppDataTable
  v-model:options="options"
  :headers="headers"
  :items="items"
  :loading="loading"
  title="Registry Name"
>
  <template #toolbar>
    <AppTableToolbar
      v-model:search-query="searchQuery"
      search-placeholder="Search..."
      :result-count="pagination.totalRecords"
      :loading="loading"
    />
  </template>

  <template #top>
    <AppPagination ... />
  </template>
</AppDataTable>
```

### Vuetify Theme Extension Pattern
```javascript
// frontend/src/plugins/vuetify.js - EXTEND THIS
import { COLORS } from '@/utils/designTokens';

const hnf1bTheme = {
  dark: false,
  colors: {
    background: COLORS.BACKGROUND,
    surface: COLORS.SURFACE,
    primary: COLORS.PRIMARY,
    'primary-darken-1': COLORS.PRIMARY_DARKEN_1,
    secondary: COLORS.SECONDARY,
    accent: COLORS.ACCENT,  // Changed from coral to gold
    error: COLORS.ERROR,
    info: COLORS.INFO,
    success: COLORS.SUCCESS,
    warning: COLORS.WARNING,
  },
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Individual color utilities | Centralized design tokens | This phase | Charts match chips |
| Per-view page headers | PageHeader.vue component | This phase | Consistent UX |
| coral (#FF8A65) accent | gold/amber (#FFB300) accent | This phase (decision) | Better harmony with teal |

**Deprecated/outdated:**
- `AppTableToolbar.vue`: Will be enhanced/replaced by `DataTableToolbar.vue`
- Direct hex colors in aggregationConfig.js: Should import from designTokens.js

## Open Questions

Things that couldn't be fully resolved:

1. **Exact gold/amber shade**
   - What we know: Decision to change from coral to gold/amber
   - What's unclear: Exact hex value (#FFB300 vs #FFC107 vs #FFD54F)
   - Recommendation: Use #FFB300 (amber-600) - good contrast, distinct from orange-based warnings

2. **AppTableToolbar deprecation timeline**
   - What we know: DataTableToolbar.vue will be more comprehensive
   - What's unclear: Whether to keep both or deprecate AppTableToolbar
   - Recommendation: Keep AppTableToolbar, build DataTableToolbar as enhancement, deprecate later

3. **View migration order after Phenopackets**
   - What we know: Phenopackets list is first reference view
   - What's unclear: Optimal order for remaining views
   - Recommendation: Variants -> Publications -> Home -> Detail pages -> AggregationsDashboard (least similar last)

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis (COLOR_STYLE_GUIDE.md, vuetify.js, utils/*.js)
- Vuetify 3.11.2 documentation structure
- Project CONTEXT.md decisions

### Secondary (MEDIUM confidence)
- Vuetify theming documentation patterns
- Material Design 3 color system principles

### Tertiary (LOW confidence)
- None - all findings based on codebase analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Existing codebase fully analyzed
- Architecture: HIGH - Patterns derived from working code
- Pitfalls: HIGH - Specific inconsistencies identified with file/line evidence
- Design tokens: MEDIUM - Structure proposed but implementation untested

**Research date:** 2026-01-20
**Valid until:** 2026-03-20 (60 days - stable domain, no external dependencies changing)

## Appendix: Current Color Inventory

### Colors in vuetify.js Theme
```javascript
primary: '#009688'      // Teal
'primary-darken-1': '#00796B'
secondary: '#37474F'    // Slate
accent: '#FF8A65'       // Coral (TO CHANGE)
error: '#B00020'
info: '#2196F3'
success: '#4CAF50'
warning: '#FB8C00'
background: '#F5F7FA'
surface: '#FFFFFF'
```

### Colors in aggregationConfig.js (Charts)
```javascript
// Sex - MISMATCH with sex.js
MALE: '#1976D2'         // vs blue-lighten-3 (#64B5F6)
FEMALE: '#E91E63'       // vs pink-lighten-3 (#F48FB1)

// Pathogenicity - Close match
Pathogenic: '#D32F2F'
'Likely Pathogenic': '#FF9800'
'Uncertain Significance': '#FDD835'
```

### Colors in utils/sex.js (Chips)
```javascript
MALE: 'blue-lighten-3'      // #64B5F6
FEMALE: 'pink-lighten-3'    // #F48FB1
OTHER_SEX: 'purple-lighten-3'
UNKNOWN_SEX: 'grey-lighten-2'
```

### Colors in utils/colors.js (Variants)
```javascript
PATHOGENIC: 'red-lighten-1'
LIKELY_PATHOGENIC: 'orange-lighten-1'
VUS: 'yellow-darken-1'
// ... (matches pathogenicity colors)
```

### Colors in COLOR_STYLE_GUIDE.md (Documentation)
- Subject IDs: teal-lighten-3 (#4DB6AC)
- Male: blue-lighten-3 (#64B5F6)
- Female: pink-lighten-3 (#F48FB1)
- Phenotypes present: green-lighten-3 (#81C784)
- Publications: orange-lighten-3 (#FFB74D)
- Variants: blue-lighten-3 (#64B5F6)

**Unification needed:** aggregationConfig.js should import from designTokens.js to match chip colors.
