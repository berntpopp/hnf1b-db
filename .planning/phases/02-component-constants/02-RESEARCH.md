# Phase 02: Component Refactoring & Constants - Research

**Researched:** 2026-01-19
**Domain:** Vue.js component extraction, JavaScript/Python constants organization
**Confidence:** HIGH

## Summary

This phase involves two distinct but related goals: (1) extracting the 1,130-line ProteinStructure3D.vue component into manageable sub-components (<500 lines each), and (2) creating centralized constants files for both backend and frontend to eliminate hardcoded magic numbers.

The codebase already has excellent patterns to follow: `frontend/src/config/app.js` provides a clean constants organization pattern, `frontend/src/utils/aggregationConfig.js` shows how to extract configuration from components, and `backend/app/core/config.py` demonstrates the separation between environment-based configuration and hardcoded values.

**Primary recommendation:** Extract ProteinStructure3D.vue into 4 sub-components (viewer, controls, variant panel, distance display) following the existing "props down, events up" pattern, and create domain-specific constants files using SCREAMING_SNAKE_CASE for true constants.

## Standard Stack

### Core (Already in Use)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vue 3 | 3.x | Component framework | Already used, Composition API available |
| Vuetify 3 | 3.x | UI components | Already used for all UI |
| NGL.js | 2.x | 3D structure viewer | Already used in ProteinStructure3D |

### Supporting (Already Established)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| markRaw | Vue 3 built-in | Prevent NGL reactivity | Required for Three.js/NGL objects |

### No New Dependencies Required

This phase is purely organizational - no new libraries needed.

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── components/
│   └── gene/
│       ├── ProteinStructure3D.vue          # Parent orchestrator (~300 lines)
│       └── protein-structure/              # Sub-components (kebab-case dir)
│           ├── StructureViewer.vue         # NGL canvas (~250 lines)
│           ├── StructureControls.vue       # Representation toggles (~150 lines)
│           ├── VariantPanel.vue            # Variant list with filters (~300 lines)
│           └── DistanceDisplay.vue         # Distance info + line toggle (~150 lines)
├── config/
│   ├── app.js                              # EXISTING - API/viz config
│   └── navigationItems.js                  # EXISTING - nav items
├── constants/
│   ├── index.js                            # Barrel file for convenience
│   ├── thresholds.js                       # Distance, size thresholds
│   ├── pubmed.js                           # PubMed URL patterns
│   ├── structure.js                        # PDB structure boundaries
│   └── pathogenicity.js                    # Classification values

backend/app/
├── core/
│   └── config.py                           # EXISTING - env + YAML config
└── constants.py                            # NEW - hardcoded domain values
```

### Pattern 1: Props Down, Events Up (Vue Standard)
**What:** Parent component owns all state; children receive props and emit events
**When to use:** Always for parent-child component communication in Vue

```javascript
// Parent (ProteinStructure3D.vue)
<StructureViewer
  :structure-loaded="structureLoaded"
  :representation="representation"
  :show-dna="showDNA"
  :active-variant="activeVariant"
  @structure-ready="handleStructureReady"
  @variant-highlighted="handleVariantHighlighted"
/>

// Child (StructureViewer.vue)
const props = defineProps({
  structureLoaded: Boolean,
  representation: String,
  showDNA: Boolean,
  activeVariant: Object
});

const emit = defineEmits(['structure-ready', 'variant-highlighted']);
```

### Pattern 2: NGL Module Scope Variables
**What:** Keep NGL objects outside Vue reactivity to avoid Three.js conflicts
**When to use:** Any component using NGL.js or Three.js

```javascript
// Module scope (outside component) - REQUIRED for NGL
let nglStage = null;
let nglStructureComponent = null;

export default {
  // Component code references module-scope variables
}
```

This pattern is already used in ProteinStructure3D.vue and MUST be preserved when extracting the StructureViewer component. The NGL objects cannot be in Vue's reactive system due to Three.js proxy conflicts.

### Pattern 3: Constants Organization
**What:** Separate constants files by domain, use SCREAMING_SNAKE_CASE
**When to use:** For any hardcoded values that are domain-significant or reused

```javascript
// constants/thresholds.js
/**
 * Distance threshold for "close" classification (in Angstroms).
 * Variants closer than this are likely to have direct DNA contact.
 */
export const DISTANCE_CLOSE_THRESHOLD = 5;

/**
 * Distance threshold for "medium" classification (in Angstroms).
 * Variants between CLOSE and MEDIUM are at medium distance.
 */
export const DISTANCE_MEDIUM_THRESHOLD = 10;
```

### Anti-Patterns to Avoid

- **Prop drilling through many layers:** Parent should pass directly to children, avoid grandchildren
- **Mixing config and constants:** Config is environment-dependent; constants are hardcoded domain values
- **TypeScript in this project:** Project uses plain JavaScript per user decision
- **Creating index.js for every directory:** Only create barrel files when import convenience outweighs performance cost

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Color mapping | Custom color functions | `@/utils/colors.js` | Already exists with pathogenicity colors |
| Distance calculation | Inline math | `@/utils/dnaDistanceCalculator.js` | Already exists with full implementation |
| Variant position extraction | Manual parsing | `@/utils/proteinDomains.js` | Already exists with HGVS parsing |
| Config validation | Custom validator | Pydantic validators in config.py | Backend already has validation pattern |

**Key insight:** The codebase already has excellent utility extraction patterns. Follow them rather than creating new patterns.

## Common Pitfalls

### Pitfall 1: Breaking NGL Reactivity Isolation
**What goes wrong:** Moving NGL code to sub-component puts variables in Vue reactive scope
**Why it happens:** Natural refactor would put `let nglStage` inside component
**How to avoid:** Keep NGL variables at module scope even in extracted components
**Warning signs:** Three.js warnings about Proxy, structure fails to render

### Pitfall 2: Over-Extracting Components
**What goes wrong:** Creating too many tiny components increases complexity
**Why it happens:** Strict adherence to line count targets
**How to avoid:** Let natural code boundaries guide extraction, not arbitrary line counts
**Warning signs:** Components that are always used together, excessive prop passing

### Pitfall 3: Barrel File Performance Impact
**What goes wrong:** Importing `from '@/constants'` loads all constants
**Why it happens:** Convenient single import point
**How to avoid:** Use direct imports for tree-shaking: `from '@/constants/thresholds'`
**Warning signs:** Larger bundle sizes, slower dev builds

### Pitfall 4: Inconsistent Constant Naming
**What goes wrong:** Mix of camelCase and SCREAMING_SNAKE_CASE constants
**Why it happens:** Different developers, different preferences
**How to avoid:** Use SCREAMING_SNAKE_CASE for true constants, camelCase for computed/derived
**Warning signs:** ESLint warnings, code review feedback

### Pitfall 5: Constants Without Documentation
**What goes wrong:** Magic numbers extracted but not explained
**Why it happens:** Rushing to meet line count targets
**How to avoid:** Every constant gets a JSDoc comment explaining its purpose
**Warning signs:** PRs rejected for missing documentation

## Code Examples

### Component Extraction Pattern

```javascript
// Source: Vue.js official style guide
// Parent component (ProteinStructure3D.vue) - orchestrator role

<template>
  <v-card class="protein-3d-card">
    <!-- Header with title and variant info -->
    <v-card-title>...</v-card-title>

    <v-card-text>
      <!-- Loading/Error states handled by parent -->
      <div v-if="loading">...</div>
      <v-alert v-else-if="error">...</v-alert>

      <!-- Main content delegates to children -->
      <v-row v-show="!loading && !error">
        <v-col :cols="showAllVariants ? 8 : 12">
          <StructureViewer
            ref="viewer"
            :representation="representation"
            :show-dna="showDNA"
            :color-by-domain="colorByDomain"
            :active-variant="activeVariant"
            @structure-ready="onStructureReady"
          />
        </v-col>
        <v-col v-if="showAllVariants" cols="4">
          <VariantPanel
            :variants="variantsInStructure"
            :selected-id="selectedVariantId"
            @select="selectVariant"
            @hover="hoverVariant"
          />
        </v-col>
      </v-row>

      <!-- Controls row -->
      <StructureControls
        v-model:representation="representation"
        v-model:show-dna="showDNA"
        v-model:color-by-domain="colorByDomain"
        :show-distance-button="activeVariantInStructure"
        @reset-view="resetView"
        @toggle-distance="toggleDistanceLine"
      />

      <!-- Distance display -->
      <DistanceDisplay
        v-if="activeVariantDistanceInfo"
        :distance-info="activeVariantDistanceInfo"
        :show-line="showDistanceLine"
      />
    </v-card-text>
  </v-card>
</template>
```

### Constants File Pattern

```javascript
// Source: Existing pattern from frontend/src/config/app.js
// constants/thresholds.js

/**
 * Distance Thresholds for DNA Proximity Analysis
 *
 * These thresholds categorize variant-to-DNA distances in the PDB 2H8R structure.
 * Based on structural biology conventions for protein-DNA interactions.
 */

/**
 * Close distance threshold (Angstroms).
 * Residues closer than this value likely have direct DNA contact.
 */
export const DISTANCE_CLOSE_THRESHOLD = 5;

/**
 * Medium distance threshold (Angstroms).
 * Residues between CLOSE and MEDIUM may have indirect effects on DNA binding.
 */
export const DISTANCE_MEDIUM_THRESHOLD = 10;

/**
 * Size threshold for structural variants (base pairs).
 * Variants >= this size are classified as CNVs rather than indels.
 */
export const STRUCTURAL_VARIANT_SIZE_THRESHOLD = 50;

/**
 * Overlap threshold for variant label positioning (amino acids).
 * Labels closer than this are stacked to avoid visual collision.
 */
export const LABEL_OVERLAP_THRESHOLD = 30;
```

### Backend Constants Pattern

```python
# Source: Following PEP 8 and existing backend/app/core/config.py patterns
# backend/app/constants.py

"""
Domain constants for the HNF1B database.

This module contains hardcoded values that are domain-specific and do not
change based on environment. For environment-dependent configuration,
see app/core/config.py.

Usage:
    from app.constants import STRUCTURE_START, STRUCTURE_END
"""

# =============================================================================
# PDB 2H8R Structure Boundaries
# =============================================================================

# PDB 2H8R maps to UniProt P35680 residues 90-308
STRUCTURE_START = 90  # First residue visible in structure
STRUCTURE_END = 308   # Last residue visible in structure

# Gap in structure (linker region not resolved in crystal)
STRUCTURE_GAP_START = 187
STRUCTURE_GAP_END = 230

# =============================================================================
# HNF1B Gene Boundaries (GRCh38)
# =============================================================================

HNF1B_GENE_START = 37686430
HNF1B_GENE_END = 37745059
HNF1B_CHROMOSOME = "17"

# =============================================================================
# Variant Classification Thresholds
# =============================================================================

# Size threshold (bp) for CNV vs indel classification
CNV_SIZE_THRESHOLD = 50

# =============================================================================
# Domain Boundaries (UniProt P35680)
# =============================================================================

DOMAIN_BOUNDARIES = {
    "dimerization": {"start": 1, "end": 31},
    "pou_specific": {"start": 88, "end": 173},
    "pou_homeodomain": {"start": 232, "end": 305},
    "transactivation": {"start": 314, "end": 557},
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Barrel files everywhere | Direct imports preferred | 2024-2025 | 15-70% faster builds (per Next.js team) |
| Mixed constant casing | SCREAMING_SNAKE_CASE for constants | Industry standard | Clearer code intent |
| Options API only | Composition API available | Vue 3 (2020) | But project uses Options API |

**Deprecated/outdated:**
- `this.$children` for accessing child components - use refs instead
- Global event bus - use props/events or Pinia

**Note:** This project uses Options API throughout. While Composition API is available in Vue 3, consistency with existing code is more important than adopting newer patterns.

## Open Questions

1. **NGL initialization location**
   - What we know: Currently in mounted() hook of ProteinStructure3D
   - What's unclear: Whether to keep in parent or move to StructureViewer child
   - Recommendation: Move to StructureViewer but keep NGL variables at module scope

2. **Barrel file usage**
   - What we know: Performance cost of barrel files is well-documented
   - What's unclear: Whether convenience outweighs cost for small constants modules
   - Recommendation: Create barrel file but document that direct imports are preferred for performance-critical paths

3. **Exact component boundaries**
   - What we know: ROADMAP suggests 5 components; CONTEXT.md says let code dictate
   - What's unclear: Final component count until we start extraction
   - Recommendation: Start with 4 natural boundaries, adjust based on actual code

## Sources

### Primary (HIGH confidence)
- Vue.js Official Style Guide: [Priority B Rules](https://vuejs.org/style-guide/rules-strongly-recommended.html) - Component naming, file naming
- Vue.js Component Basics: [Events](https://vuejs.org/guide/components/events.html) - Props/events pattern
- PEP 8 Style Guide: [Naming Conventions](https://peps.python.org/pep-0008/) - Python constant naming

### Secondary (MEDIUM confidence)
- Atlassian Engineering Blog: [75% Faster Builds by Removing Barrel Files](https://www.atlassian.com/blog/atlassian-engineering/faster-builds-when-removing-barrel-files) - Barrel file performance impact
- JavaScript Style Guide (W3Schools): [Naming Conventions](https://www.w3schools.com/js/js_conventions.asp) - JavaScript constant naming

### Tertiary (LOW confidence)
- Medium articles on barrel files and naming conventions - General community consensus

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies, using existing patterns
- Architecture: HIGH - Following Vue official patterns and existing codebase
- Pitfalls: HIGH - Based on actual codebase analysis and known Vue/NGL issues

**Research date:** 2026-01-19
**Valid until:** 2026-02-19 (30 days - stable patterns, no fast-moving dependencies)

---

## Appendix: Current Codebase Hardcoded Values Audit

### Frontend - High Priority (Extract to constants)

| File | Value | Purpose | Suggested Constant |
|------|-------|---------|-------------------|
| `dnaDistanceCalculator.js` | 5, 10 | Distance thresholds | Already exported |
| `dnaDistanceCalculator.js` | 90, 308, 187, 230 | Structure boundaries | Already exported |
| `geneVisualization.js` | 37680000, 37750000 | HNF1B gene boundaries | Consolidate with existing |
| `variants.js` | 36098063, 36112306 | HNF1B gene (different values?) | Reconcile with geneVisualization |
| `variantStore.js` | 37686430, 37745059 | HNF1B gene boundaries | Consolidate |
| `tooltip.js` | 300, 200, 15, 10 | Tooltip dimensions | `UI_DEFAULTS` |
| `HNF1BProteinVisualization.vue` | 30 | Overlap threshold | `LABEL_OVERLAP_THRESHOLD` |
| `searchHistory.js` | 5 | Max recent searches | `MAX_RECENT_SEARCHES` |
| `variantStore.js` | 5 * 60 * 1000 | Cache TTL | `CACHE_TTL_MS` |

### Frontend - Medium Priority (Consider extracting)

| File | Value | Purpose | Notes |
|------|-------|---------|-------|
| Views | 10, 20, 50, 100 | Page size options | Already in config/app.js pattern |
| Various | 300 | Debounce delay | Common pattern, may not need extraction |
| Various | 500 | Page height | CSS-related, may stay in components |

### Backend - High Priority (Extract to constants.py)

| File | Value | Purpose | Suggested Constant |
|------|-------|---------|-------------------|
| `reference/service.py` | 36000000-39900000 | 17q12 region | `CHR17Q12_REGION_*` |
| `reference/service.py` | 0.1 | Rate limit delay | Keep in config.yaml |
| `reference/router.py` | 86400 | Cache max age | `CACHE_MAX_AGE_SECONDS` |
| `aggregations/all_variants.py` | Domain boundaries dict | HNF1B domains | `DOMAIN_BOUNDARIES` |
| `variant_search_validation.py` | 200 | Batch size | `VARIANT_RECODER_BATCH_SIZE` |

### Already Well-Organized

These are already properly extracted or configured:
- `frontend/src/config/app.js` - API config, page sizes
- `frontend/src/utils/colors.js` - Pathogenicity colors
- `frontend/src/utils/aggregationConfig.js` - Aggregation options
- `backend/app/core/config.py` - All env-based and YAML config
- `backend/app/phenopackets/molecular_consequence.py` - VEP consequence mapping
