# feat(frontend): migrate individual detail page to phenopackets v2

## Summary

The individual detail page displays data from deprecated v1 normalized tables. Needs migration to display GA4GH Phenopackets v2 JSONB structure with modular card components.

**Current:** `/individuals/:id` → 404 (broken)
**Target:** `/phenopackets/:id` → Display nested phenopacket sections

## Details

See detailed implementation plan: [docs/issues/issue-32-migrate-individual-detail-page.md](../docs/issues/issue-32-migrate-individual-detail-page.md)

## Acceptance Criteria

- [ ] Route changed from `/individuals/:id` to `/phenopackets/:id`
- [ ] Page displays all phenopacket sections (subject, diseases, features, interpretations, metadata)
- [ ] Modular card components created in `components/phenopacket/`
- [ ] Download JSON button works
- [ ] Conditional rendering for optional sections (features, interpretations, measurements)
- [ ] ISO8601 durations formatted human-readable
- [ ] Sex icons color-coded (blue=male, pink=female, grey=unknown)
- [ ] No 404 errors, all API calls succeed
- [ ] Responsive 2-column layout

## Dependencies

- Issue #30 (API client migration) - ✅ Required
- Issue #31 (List view) - For navigation

## Priority

**P1 (High)** - Blocking user workflow

## Labels

`frontend`, `vue`, `phenopackets`, `migration`, `p1`
