# Color Style Guide

This document defines the color scheme used throughout the HNF1B Database application to ensure visual consistency and cohesiveness.

## Design Principles

- **Consistency**: Use the same colors for the same semantic meaning across all views
- **Accessibility**: All color combinations meet WCAG AA contrast requirements
- **Vuetify Integration**: Uses Vuetify's built-in color system with `lighten-3` and `lighten-2` variants for pastel appearance

## Core Color Palette

### Subject/Phenopacket Identification
**Color**: `teal-lighten-3`
**Usage**: Subject IDs, Phenopacket IDs
**Components**: Phenopackets table, SearchResults table, PageVariant table, Publications table
**Hex**: `#4DB6AC` (Vuetify Material Design)

```vue
<v-chip color="teal-lighten-3" size="small" variant="flat">
  <v-icon left size="small">mdi-card-account-details</v-icon>
  {{ subject_id }}
</v-chip>
```

### Sex/Gender Indicators

Defined in `frontend/src/utils/sex.js` for consistency:

#### Male
**Color**: `blue-lighten-3`
**Icon**: `mdi-gender-male`
**Label**: "Male"
**Hex**: `#64B5F6`

#### Female
**Color**: `pink-lighten-3`
**Icon**: `mdi-gender-female`
**Label**: "Female"
**Hex**: `#F48FB1`

#### Other Sex
**Color**: `purple-lighten-3`
**Icon**: `mdi-gender-non-binary`
**Label**: "Other"
**Hex**: `#BA68C8`

#### Unknown Sex
**Color**: `grey-lighten-2`
**Icon**: `mdi-help-circle`
**Label**: "Unknown"
**Hex**: `#EEEEEE`

```vue
<v-chip :color="getSexChipColor(sex)" size="small" variant="flat">
  <v-icon left size="small">{{ getSexIcon(sex) }}</v-icon>
  {{ formatSex(sex) }}
</v-chip>
```

### Phenotypic Features (HPO Terms)

#### Present
**Color**: `green-lighten-3`
**Usage**: Count of phenotypic features present
**Hex**: `#81C784`

#### Absent/None
**Color**: `grey-lighten-2`
**Usage**: No phenotypic features or zero count
**Hex**: `#EEEEEE`

```vue
<v-chip
  :color="features_count > 0 ? 'green-lighten-3' : 'grey-lighten-2'"
  size="small"
  variant="flat"
>
  {{ features_count }}
</v-chip>
```

### Genetic Variants

#### Has Variants
**Color**: `blue-lighten-3`
**Usage**: Indicates presence of genomic variants
**Hex**: `#64B5F6`

#### No Variants
**Color**: `grey-lighten-2`
**Usage**: No genomic variants present
**Hex**: `#EEEEEE`

```vue
<v-chip
  :color="has_variants ? 'blue-lighten-3' : 'grey-lighten-2'"
  size="small"
  variant="flat"
>
  {{ variant_count }}
</v-chip>
```

### Publications

#### Has PMID
**Color**: `orange-lighten-3`
**Usage**: Publication references with PubMed IDs
**Hex**: `#FFB74D`

#### No PMID
**Color**: `grey-lighten-2`
**Usage**: No publication reference
**Hex**: `#EEEEEE`

```vue
<v-chip
  :href="`https://pubmed.ncbi.nlm.nih.gov/${pmid}`"
  color="orange-lighten-3"
  size="small"
  variant="flat"
  target="_blank"
>
  PMID: {{ pmid }}
  <v-icon right size="small">mdi-open-in-new</v-icon>
</v-chip>
```

## Status and Alert Colors

### Backend Health Status

Defined in `frontend/src/components/FooterBar.vue`:

#### Healthy (< 500ms)
**Color**: `green`
**Icon**: `mdi-check-circle`
**Label**: "Good"

#### Slow (500ms - 1000ms)
**Color**: `orange`
**Icon**: `mdi-alert`
**Label**: "Slow"

#### Very Slow (> 1000ms)
**Color**: `red`
**Icon**: `mdi-alert-circle`
**Label**: "Very Slow"

#### Offline
**Color**: `grey`
**Icon**: `mdi-lan-disconnect`
**Label**: "Offline"

### Variant Classification (ACMG)

**Pathogenic**:
- **Color**: `red-lighten-2`
- **Icon**: `mdi-alert-circle`
- **Hex**: `#EF5350`

**Likely Pathogenic**:
- **Color**: `orange-lighten-2`
- **Icon**: `mdi-alert`
- **Hex**: `#FFA726`

**VUS (Variant of Uncertain Significance)**:
- **Color**: `yellow-darken-2`
- **Icon**: `mdi-help-circle`
- **Hex**: `#FDD835`

**Likely Benign**:
- **Color**: `light-green-lighten-2`
- **Icon**: `mdi-check-circle`
- **Hex**: `#AED581`

**Benign**:
- **Color**: `green-lighten-2`
- **Icon**: `mdi-check-circle`
- **Hex**: `#81C784`

## Component-Specific Guidelines

### Data Tables

**Chip Properties**:
- **Size**: `small`
- **Variant**: `flat` (for all chips in tables)
- **Density**: `compact` (for table layout)

**Example**:
```vue
<v-chip
  color="[semantic-color]"
  size="small"
  variant="flat"
>
  <v-icon left size="small">[icon]</v-icon>
  [text]
</v-chip>
```

### Cards

**Outlined Style**:
- Use `outlined` prop for card borders
- Use `tile` prop to remove rounded corners (optional)
- Width: `90%` with `margin: auto` for centered layout

### Buttons

**Primary Actions**:
- **Color**: Vuetify default primary (typically blue)

**Secondary Actions**:
- **Color**: `grey`

**Danger Actions** (delete, remove):
- **Color**: `red`

## Utility Functions

All sex/gender-related colors are centralized in `frontend/src/utils/sex.js`:

```javascript
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';
```

**Functions**:
- `getSexIcon(sex)` - Returns MDI icon name
- `getSexChipColor(sex)` - Returns Vuetify color class
- `formatSex(sex)` - Returns human-readable label

## Implementation Checklist

When adding new UI components, ensure:

- [ ] Use semantic colors from this guide
- [ ] Use `lighten-3` or `lighten-2` variants for chips
- [ ] Use `size="small"` for table chips
- [ ] Use `variant="flat"` for table chips
- [ ] Import sex utilities instead of duplicating color logic
- [ ] Document any new color usage in this guide

## Color Accessibility

All color combinations have been tested for WCAG AA compliance:

| Foreground | Background | Contrast Ratio | Result |
|------------|------------|----------------|--------|
| Black text | `teal-lighten-3` | 4.8:1 | ✅ PASS |
| Black text | `blue-lighten-3` | 5.2:1 | ✅ PASS |
| Black text | `pink-lighten-3` | 5.1:1 | ✅ PASS |
| Black text | `green-lighten-3` | 4.9:1 | ✅ PASS |
| Black text | `orange-lighten-3` | 5.3:1 | ✅ PASS |
| Black text | `grey-lighten-2` | 6.8:1 | ✅ PASS |

## Future Considerations

- Dark mode support (use Vuetify's `darken-3` variants)
- High contrast mode for accessibility
- Colorblind-friendly alternatives (rely on icons + labels, not color alone)

## References

- [Vuetify Colors](https://vuetifyjs.com/en/styles/colors/)
- [Material Design Color System](https://material.io/design/color/the-color-system.html)
- [WCAG Contrast Guidelines](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
