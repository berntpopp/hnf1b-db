# feat(frontend): migrate individual detail page to phenopackets v2

## Summary

The individual detail page displays data from deprecated v1 normalized tables. Needs migration to display GA4GH Phenopackets v2 JSONB structure with modular card components.

**Current:** `/individuals/:id` → 404 (broken)
**Target:** `/phenopackets/:id` → Display nested phenopacket sections

## Details

See detailed implementation plan: [docs/issues/issue-32-migrate-individual-detail-page.md](../docs/issues/issue-32-migrate-individual-detail-page.md)

## Acceptance Criteria

### Frontend Display
- [x] Route changed from `/individuals/:id` to `/phenopackets/:id`
- [x] Page displays all phenopacket sections (subject, diseases, features, interpretations, metadata)
- [x] Modular card components created in `components/phenopacket/`
- [x] Download JSON button works
- [x] Conditional rendering for optional sections (features, interpretations, measurements)
- [x] ISO8601 durations formatted human-readable
- [x] Sex icons color-coded (blue=male, pink=female, grey=unknown)
- [x] No 404 errors, all API calls succeed
- [x] Responsive 2-column layout

### Data Quality (Multi-Study Individuals)
- [x] Sex correctly prioritizes non-UNKNOWN values across multiple studies
- [x] Phenotypic features sorted chronologically (earliest onset first)
- [x] Temporal onset shows both HPO term and specific age
- [x] Overlapping CNV variants merged with alternate coordinates
- [x] Variant labels concise with literature size and dbVar IDs
- [x] Variant descriptions display fully without truncation
- [x] Evidence from multiple publications merged correctly

## Dependencies

- Issue #30 (API client migration) - ✅ Required
- Issue #31 (List view) - For navigation

## Priority

**P1 (High)** - Blocking user workflow

## Labels

`frontend`, `vue`, `phenopackets`, `migration`, `p1`
