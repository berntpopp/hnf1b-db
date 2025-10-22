# Completed Issues Archive

This folder contains detailed documentation for completed issues that have been implemented and merged.

## Purpose

- 📚 **Historical Reference** - Documents design decisions and implementation approaches
- 🎓 **Onboarding Resource** - New developers can understand how features were built
- 🔍 **Pattern Library** - Reusable patterns for similar future work
- 📝 **Implementation Notes** - Detailed technical context beyond git commits

## Archive Process

When an issue is completed:

1. **Close GitHub issue** with summary comment
2. **Move detailed plan** from `docs/issues/` to `docs/issues/completed/`
3. **Move GitHub template** from `docs/issues/` to `docs/issues/completed/`
4. **Update** `docs/issues/README.md` and `MIGRATION-SUMMARY.md`

## Completed Issues

### Phase 0: Foundation
- ✅ **#32** - Individual Detail Page → `issue-32-migrate-individual-detail-page.md`
  - Migrated to Phenopackets v2 format
  - Created detail card components (Subject, Diseases, Phenotypes, Interpretations, Metadata)
  - Fixed PMID mapping and added MONDO links

- ✅ **#33** - Aggregation Endpoints → `issue-33-update-aggregation-endpoints.md`
  - Updated dashboard for v2 API compatibility
  - Refactored DonutChart with interactive legend
  - Removed 3 deprecated tabs (for future reimplementation)

### Future Completions

As more issues are completed, they will be archived here following the same pattern.

## Accessing Archived Docs

All files remain in the git repository, so they are:
- ✅ Version controlled
- ✅ Searchable with `grep`, IDE search, or GitHub search
- ✅ Available in git history even if later deleted
- ✅ Part of project documentation

## Related Documentation

- **Active issues:** See `docs/issues/README.md`
- **Progress tracking:** See `docs/issues/MIGRATION-SUMMARY.md`
- **Milestone overview:** See `docs/issues/MILESTONE-frontend-phenopackets-migration.md`
