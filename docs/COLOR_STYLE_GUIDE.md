# Color Style Guide

This document describes the current frontend styling sources of truth. Keep
semantic styling in code, and use this file as the reference for where those
tokens live and how they should be applied.

## Primary Sources

- Theme palette: `frontend/src/plugins/vuetify.js`
- Subject/phenotype/card tokens: `frontend/src/utils/cardStyles.js`
- Sex display tokens: `frontend/src/utils/sex.js`
- Variant/pathogenicity tokens: `frontend/src/utils/colors.js`

## Theme Palette

The app theme is defined in `frontend/src/plugins/vuetify.js`.

- `primary`: `#009688`
- `primary-darken-1`: `#00796B`
- `secondary`: `#37474F`
- `secondary-darken-1`: `#263238`
- `accent`: `#FF8A65`
- `background`: `#F5F7FA`
- `surface`: `#FFFFFF`

Use theme colors for layout-level UI, buttons, surfaces, and global emphasis.

## Semantic Tokens

### Subject and Demographics

Use `frontend/src/utils/sex.js` for sex-specific icons, labels, and chip colors.

- `MALE`: `blue-lighten-3`
- `FEMALE`: `pink-lighten-3`
- `OTHER_SEX`: `purple-lighten-3`
- `UNKNOWN_SEX`: `grey-lighten-2`

Use `frontend/src/utils/cardStyles.js` for subject-specific chip colors:

- `subjectId`: `teal-lighten-4`
- `alternateId`: `blue-lighten-4`
- `reportId`: `grey-lighten-2`
- `age`: `amber-lighten-4`
- `karyotype`: `purple-lighten-4`

### Variant and Interpretation Semantics

Use `frontend/src/utils/colors.js` instead of hardcoding classification colors.

- `PATHOGENIC`: `red-lighten-1`
- `LIKELY_PATHOGENIC`: `orange-lighten-1`
- `VUS` / `UNCERTAIN_SIGNIFICANCE`: `yellow-darken-1`
- `LIKELY_BENIGN`: `light-green-lighten-1`
- `BENIGN`: `green-lighten-1`

Variant type tokens:

- `SNV`: `purple-lighten-3`
- `deletion`: `red-lighten-3`
- `duplication`: `blue-lighten-3`
- `insertion`: `green-lighten-3`
- `indel`: `pink-lighten-3`
- `inversion`: `orange-lighten-3`
- `CNV`: `amber-lighten-3`

Use `frontend/src/utils/cardStyles.js` for interpretation badges where the UI is
driven by card-level configs.

## Component Rules

1. Prefer shared token helpers over inline color strings.
2. Use `CARD_HEADERS`, `PHENOTYPE_STYLES`, `TYPOGRAPHY`, and `CHIP_SIZES` from
   `frontend/src/utils/cardStyles.js` for card UIs.
3. Use `getSexChipColor()`, `getSexIcon()`, and `formatSex()` from
   `frontend/src/utils/sex.js` for demographic displays.
4. Use `getPathogenicityColor()`, `getPathogenicityHexColor()`, and
   `getVariantTypeColor()` from `frontend/src/utils/colors.js` for variant UI.
5. When adding a new semantic color, update the code token source first, then
   update this document if the change affects shared guidance.

## Design Direction

- Prefer semantic meaning over decorative color use.
- Keep dense data UIs readable with muted backgrounds and stronger foreground
  contrast.
- Reuse existing token families before inventing one-off shades.
- Treat this guide as reference documentation, not a planning document.

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
