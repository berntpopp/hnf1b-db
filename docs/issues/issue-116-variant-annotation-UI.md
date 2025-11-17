## Summary

Create a Vue.js component that allows users to input variants and view VEP annotations in real-time.

**Current**: No UI for variant annotation
**Target**: Interactive component with validation, annotation display, and format conversion

## Depends On

- #100 (VEP annotation API endpoint must be implemented first)

## User Story

As a researcher, I want to:
- Input a variant in any format (VCF or HGVS)
- See real-time validation feedback
- View functional predictions (consequence, impact)
- See pathogenicity scores (CADD)
- See population frequencies (gnomAD)
- Convert between formats

## Implementation

### File: `frontend/src/components/VariantAnnotator.vue` (NEW)

**Features**:
- Text input with format detection
- Real-time validation (blur event)
- Annotation button with loading state
- Results card with structured display:
  - Consequence (e.g., "missense_variant")
  - Impact badge (HIGH/MODERATE/LOW/MODIFIER with colors)
  - CADD score (if available)
  - gnomAD allele frequency (if available)
  - Format conversions (VCF ↔ HGVS)

**Integration Points**:
- `POST /api/v2/variants/annotate` - Get VEP annotation
- Vuetify components (v-text-field, v-card, v-chip)
- Error handling with user-friendly messages

### Usage Example

```vue
<template>
  <VariantAnnotator 
    @annotated="handleAnnotation"
    @error="handleError"
  />
</template>
```

## Acceptance Criteria

- [ ] Component accepts VCF format (17-36459258-A-G)
- [ ] Component accepts HGVS format (NM_000458.4:c.544+1G>A)
- [ ] Real-time validation with helpful error messages
- [ ] Displays consequence prediction
- [ ] Displays impact with color-coded badge
- [ ] Displays CADD score (when available)
- [ ] Displays gnomAD frequency (when available)
- [ ] Loading state during API call
- [ ] Error handling with user guidance
- [ ] Responsive design (mobile-friendly)
- [ ] Can be embedded in phenopacket edit form

## Estimated Effort

**1.5-2 hours**

## Priority

**P1 (High)** - Core user-facing functionality

## Related

- Implementation plan: `docs/variant-annotation-implementation-plan.md`
- API endpoint: #100
- Backend infrastructure: #56