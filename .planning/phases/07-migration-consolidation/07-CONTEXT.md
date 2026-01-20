# Phase 7: Migration Consolidation - Context

**Gathered:** 2026-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Consolidate alembic migration history into a single `001_initial_schema.py` migration. Delete old migrations (git history preserves them). Document production migration procedure. Production currently mirrors local state (Google Sheets import only), so full rebuild is acceptable.

</domain>

<decisions>
## Implementation Decisions

### Backup & rollback strategy
- Use `pg_dump` full backup (schema and data)
- Store backups in local `./backups/` directory (gitignored)
- Timestamp format for backup files: `hnf1b_backup_2026-01-20_143052.sql.gz`
- Enable gzip compression for smaller backup files
- Include automated verification step: restore to temp DB and compare schemas
- Manual cleanup only - user deletes old backups when no longer needed
- Create `make db-backup` Makefile target for automation
- Research best practices for rollback strategy (capture in research phase)

### Archive organization
- Delete old migrations from codebase - git history preserves them
- Use separate commits: one deletes old migrations, another adds new consolidated migration
- Include git reference comment in new migration pointing to archived commit
- Include detailed docstring listing tables, indexes, and constraints consolidated

### Production procedure
- Production environment: Docker Compose (same as dev)
- Production can be rebuilt from scratch (only contains Google Sheets import data)
- Recommended approach: Full rebuild (drop DB, run new migration, re-import)
- Documentation: Brief paragraph in README (not step-by-step checklist)

### Verification approach
- Use all three verification methods:
  1. `pg_dump --schema-only` comparison (before vs after)
  2. SQLAlchemy metadata inspection
  3. Alembic autogenerate check (should produce empty migration)
- Create `make db-verify-migration` Makefile target
- Test against both:
  - Fresh temp database (clean migration test)
  - Existing dev database (data compatibility)
- Include full data import test (`phenopackets-migrate`) after migration
- Playwright snapshot comparison against live HNF1B.org
- Key pages for snapshot comparison: Home, Phenopackets list, Variants list, Aggregations

### Claude's Discretion
- Specific pg_dump flags and options
- Temp database naming convention
- Schema diff algorithm/tooling choice
- Backup directory structure within ./backups/

</decisions>

<specifics>
## Specific Ideas

- "Production is the same state as local database currently - just the base import from Google Sheets, no other data entered"
- Playwright verification should capture screenshots and compare to HNF1B.org
- Belt-and-suspenders approach for verification (multiple methods)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-migration-consolidation*
*Context gathered: 2026-01-20*
