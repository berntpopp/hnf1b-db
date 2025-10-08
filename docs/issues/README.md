# Frontend Phenopackets v2 Migration - Issues

Complete migration of frontend from v1 normalized schema to GA4GH Phenopackets v2 JSONB backend.

## 📋 Quick Reference

**Milestone:** `frontend-phenopackets-v2-migration`

**Status:** 3/20 issues completed (15%)

**Timeline:** ~4 weeks (160 hours development)

## 📊 Progress Overview

| Phase | Issues | Completed | Remaining |
|-------|--------|-----------|-----------|
| Phase 0: Foundation | #30-32 | ✅ 3/3 | 0 |
| Phase 1: Core Views | #33-38 | 0/6 | 6 |
| Phase 2: Search | #39-40 | 0/2 | 2 |
| Phase 3: Visualizations | #41-43 | 0/3 | 3 |
| Phase 4: Comparisons | #44-45 | 0/2 | 2 |
| Phase 5: Survival | #46 | 0/1 | 1 |
| Phase 6: Polish | #47-49 | 0/3 | 3 |
| **Total** | **20** | **3** | **17** |

## 📁 Files in This Directory

### Planning Documents
- **`MILESTONE-frontend-phenopackets-migration.md`** - Complete milestone breakdown
- **`MIGRATION-SUMMARY.md`** - Quick reference & checklists

### Detailed Issue Plans
- **`issue-32-migrate-individual-detail-page.md`** ✅ (Completed)
- **`issue-33-update-aggregation-endpoints.md`**
- **`issue-34-migrate-variants-view.md`**
- **`issue-35-migrate-variant-detail-page.md`**
- **`issue-36-migrate-publications-view.md`**
- **`issue-37-40-batch.md`** - Issues #37, #39, #40
- **`issue-38-migrate-home-stats.md`**
- **`issue-41-46-visualizations.md`** - Issues #41-46
- **`issue-47-49-polish.md`** - Issues #47-49

### GitHub Templates
- **`github-issue-32-template.md`** ✅ (Used)
- **`github-issue-33-template.md`**
- **`github-templates-34-49.md`** - All remaining templates

## 🎯 Next Steps

### 1. Review Issues
Read through the detailed plans to understand scope.

### 2. Update Existing Issues (#33-40)
Edit your GitHub issues #33-40 using the detailed plans and templates provided.

### 3. Create New Issues (#41-49)
Use templates from `github-templates-34-49.md` to create GitHub issues.

### 4. Create Backend Issues
Issues marked ⚠️ need backend endpoints first (see MIGRATION-SUMMARY.md).

### 5. Start Implementation
Recommended order: #38 → #33 → #36 → #37 → (wait for backend) → #34 → #35

## ⚠️ Backend Blockers

These issues **CANNOT START** until backend endpoints created:

- **#34** - `/aggregate/variants` - ⚠️ **HIGH PRIORITY BLOCKER**
- **#35** - `/by-variant/{id}` - ⚠️ **HIGH PRIORITY BLOCKER**

Create backend issues for these FIRST.

## 🏷️ GitHub Setup

### Create Milestone
```
Name: frontend-phenopackets-v2-migration
Description: Complete migration to GA4GH Phenopackets v2 backend
Due date: [4 weeks from start]
```

### Create Labels
```
frontend, migration, phenopackets, visualization, feature
p0-critical, p1-high, p2-medium, p3-low
views, components, api-client, charts
```

## 📚 Documentation

- **Issue Management Guidelines:** See [../../CLAUDE.md](../../CLAUDE.md#issue-management)
- **Frontend Architecture:** See [../../frontend/CLAUDE.md](../../frontend/CLAUDE.md)

## 💡 Tips

- Use detailed plan files for implementation guidance
- Keep GitHub issues concise, link to detailed plans
- Follow conventional commit titles (feat, fix, test, docs)
- Update MIGRATION-SUMMARY.md as issues close
