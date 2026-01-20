# Phase 7: Migration Consolidation - Research

**Researched:** 2026-01-20
**Domain:** Alembic migration consolidation, PostgreSQL schema management, database backup/rollback
**Confidence:** HIGH

## Summary

Migration consolidation involves collapsing 30 existing Alembic migrations into a single `001_initial_schema.py` file. The standard approach is to use `pg_dump --schema-only` to capture the current database state, then create a new migration that executes this SQL. The key challenge is ensuring the new consolidated migration produces a schema identical to running all 30 migrations sequentially.

The project already has a working backup infrastructure (`docker/backup.sh`) that uses `pg_dump` with gzip compression to the `./backups/` directory. This provides a solid foundation for the backup strategy. The verification approach should use multiple methods: pg_dump schema comparison, SQLAlchemy metadata inspection via `alembic.autogenerate.compare_metadata()`, and confirming `alembic revision --autogenerate` produces an empty migration.

**Primary recommendation:** Use `pg_dump -s -O -x` to capture schema-only SQL, create a consolidated migration that executes this SQL using `op.execute()`, verify with schema diff, then delete old migrations and document the archived commit hash.

## Standard Stack

The established tools for this domain:

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Alembic | 1.18.x | Migration framework | Already in use, native autogenerate verification |
| pg_dump | PostgreSQL 16+ | Schema extraction | Official PostgreSQL tool, widely trusted |
| SQLAlchemy | 2.0+ | ORM/metadata | Already in use, provides `compare_metadata()` |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `alembic stamp` | Mark migration as applied | Production deployment without re-running |
| `diff` | Text comparison | Compare pg_dump outputs |
| gzip | Compression | Backup storage efficiency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pg_dump schema | SQLAlchemy create_all | Misses triggers, functions, MVs |
| Text diff | pgquarrel | More complex setup, overkill for this use case |
| Manual SQL | alembic autogenerate | Autogenerate misses custom SQL (triggers, etc.) |

**Installation:**
No additional dependencies needed - all tools already available in project.

## Architecture Patterns

### Recommended Migration File Structure
```
backend/alembic/versions/
├── 001_initial_schema.py    # New consolidated migration
└── (archive deleted)        # Old files removed, git history preserves
```

### Pattern 1: SQL-Based Consolidated Migration
**What:** Read and execute pg_dump SQL in upgrade()
**When to use:** When schema includes triggers, functions, materialized views
**Example:**
```python
# Source: https://notes.alexkehayias.com/squash-migrations-using-alembic/
"""Consolidated initial schema

Previous migrations archived in commit: <commit_hash>

Tables: phenopackets, users, families, cohorts, resources, phenopacket_audit,
        hpo_terms_lookup, publication_metadata, variant_annotations,
        reference_genomes, genes, transcripts, exons, protein_domains,
        sex_values, interpretation_status_values, progress_status_values,
        allelic_state_values, evidence_code_values

Materialized Views: mv_feature_aggregation, mv_disease_aggregation,
                    mv_sex_distribution, mv_summary_statistics,
                    global_search_index

Functions: phenopackets_search_vector_update(),
           refresh_all_aggregation_views()

Triggers: phenopackets_search_vector_trigger

Extensions: pg_trgm
"""
from pathlib import Path
from alembic import op

revision = "001_initial_schema"
down_revision = None

def upgrade():
    # Load and execute consolidated schema SQL
    sql_file = Path(__file__).parent / "001_initial_schema.sql"
    sql = sql_file.read_text()

    # Execute statements individually (asyncpg requirement)
    for stmt in sql.split(";\n"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            op.execute(stmt + ";")

def downgrade():
    # Drop all objects in reverse dependency order
    # (Generated from pg_dump reverse order)
    pass
```

### Pattern 2: Production Deployment with `alembic stamp`
**What:** Mark migration as already applied without executing
**When to use:** Production database already has the schema
**Example:**
```bash
# Source: Alembic documentation
# In production, schema already exists from previous migrations
# Just mark the new consolidated migration as current
alembic stamp 001_initial_schema
```

### Anti-Patterns to Avoid
- **Using SQLAlchemy create_all():** Misses triggers, functions, materialized views, extensions
- **Inline SQL in migration:** Hard to maintain, split SQL into separate .sql file
- **Keeping old migrations with new:** Creates confusion, delete and rely on git history

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema extraction | Parse models manually | `pg_dump -s` | Captures everything including triggers, MVs |
| Schema comparison | Custom diff script | `compare_metadata()` | Built into Alembic, well-tested |
| Backup verification | Manual SQL queries | pg_dump schema diff | Reliable, captures all objects |
| Empty migration check | Custom inspection | `alembic revision --autogenerate` | Should produce empty if schemas match |

**Key insight:** The existing pg_dump and Alembic tools already handle the complexity of PostgreSQL schema management. Custom solutions would miss edge cases like generated columns, trigger dependencies, and materialized view definitions.

## Common Pitfalls

### Pitfall 1: Trigger and Function Dependencies
**What goes wrong:** SQL statements executed out of order cause errors
**Why it happens:** pg_dump outputs CREATE FUNCTION before CREATE TRIGGER, but semicolon splitting may break multi-line functions
**How to avoid:**
- Use `pg_dump --clean --if-exists` format
- Split on `;\n` (semicolon + newline) not just `;`
- Test migration on fresh database before committing
**Warning signs:** "function does not exist" errors, syntax errors in migrations

### Pitfall 2: Missing Extensions
**What goes wrong:** pg_trgm index creation fails on fresh database
**Why it happens:** `CREATE EXTENSION IF NOT EXISTS pg_trgm` may be in a later migration
**How to avoid:** Ensure extensions are created first in consolidated SQL
**Warning signs:** "operator class gin_trgm_ops does not exist"

### Pitfall 3: Generated Column Syntax
**What goes wrong:** GENERATED ALWAYS columns may have database-specific syntax
**Why it happens:** pg_dump captures exact PostgreSQL syntax which may differ from SQLAlchemy representation
**How to avoid:** Keep pg_dump output as-is, verify with fresh database test
**Warning signs:** Column type mismatches in autogenerate comparison

### Pitfall 4: Materialized View Ordering
**What goes wrong:** MV creation fails because dependent tables don't exist yet
**Why it happens:** pg_dump may not output in correct dependency order for MVs
**How to avoid:** Place MV creation at end of SQL file, manually verify order
**Warning signs:** "relation does not exist" during migration

### Pitfall 5: Data Population Migrations
**What goes wrong:** Controlled vocabulary tables (sex_values, etc.) are empty
**Why it happens:** Data INSERT migrations are lost when consolidating
**How to avoid:** Include INSERT statements from data migrations (88b3a0c19a89, b1e70338f190)
**Warning signs:** Empty dropdowns in frontend, foreign key violations

## Code Examples

Verified patterns from research:

### pg_dump Schema Extraction
```bash
# Source: PostgreSQL documentation
# Extract schema without ownership or privileges (portable across users)
pg_dump -s -O -x \
  --file=001_initial_schema.sql \
  -U hnf1b_user \
  -d hnf1b_phenopackets

# Options explained:
# -s: schema-only (no data)
# -O: no owner commands (prevents "role does not exist" errors)
# -x: no privileges (prevents ACL issues)
```

### Full Backup for Rollback
```bash
# Source: Existing docker/backup.sh pattern
# Full backup with data for rollback capability
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
pg_dump -U hnf1b_user -d hnf1b_phenopackets | \
  gzip > ./backups/hnf1b_backup_${TIMESTAMP}.sql.gz
```

### Schema Verification with Alembic
```python
# Source: Alembic autogenerate documentation
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine
from app.database import Base

engine = create_engine("postgresql://...")
mc = MigrationContext.configure(engine.connect())

# Import all models to ensure metadata is complete
from app.phenopackets.models import *

# Compare - empty list means schemas match
diff = compare_metadata(mc, Base.metadata)
if diff:
    print("Schema mismatch:", diff)
else:
    print("Schemas match!")
```

### Verification Script Pattern
```bash
#!/bin/bash
# verify_migration.sh

set -e

# 1. Create temp database
createdb -U hnf1b_user hnf1b_verify_temp

# 2. Run consolidated migration
DATABASE_URL="postgresql://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_verify_temp" \
  alembic upgrade head

# 3. Dump schema
pg_dump -s -O -x -d hnf1b_verify_temp > /tmp/migrated_schema.sql

# 4. Compare with production schema
diff /tmp/production_schema.sql /tmp/migrated_schema.sql

# 5. Cleanup
dropdb -U hnf1b_user hnf1b_verify_temp
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Multiple small migrations | Consolidated + incremental | Project maturity | Faster test DB setup |
| No pg_dump verification | Compare before/after | Best practice | Catches schema drift |
| Manual schema comparison | alembic compare_metadata | Alembic 1.8+ | Automated verification |

**Deprecated/outdated:**
- `alembic_verify` library: Not actively maintained, use built-in compare_metadata instead
- Manual SQL generation: pg_dump is more reliable and captures all objects

## Rollback Strategy

Based on the CONTEXT.md decisions for backup and rollback:

### Pre-Migration Backup
```bash
# Create timestamped full backup before any changes
make db-backup  # New target to create

# Backup includes both schema AND data
# Stored in ./backups/ (gitignored)
# Format: hnf1b_backup_2026-01-20_143052.sql.gz
```

### Rollback Procedure
If migration fails or introduces issues:

1. **Stop application** to prevent further database writes
2. **Restore from backup:**
   ```bash
   # Drop current database
   dropdb -U hnf1b_user hnf1b_phenopackets

   # Recreate empty database
   createdb -U hnf1b_user hnf1b_phenopackets

   # Restore from backup
   gunzip -c ./backups/hnf1b_backup_TIMESTAMP.sql.gz | \
     psql -U hnf1b_user -d hnf1b_phenopackets
   ```
3. **Verify restoration** with application smoke test
4. **Investigate** root cause before re-attempting

### Production Considerations
Per CONTEXT.md: Production can be fully rebuilt from Google Sheets import. This means:
- Full rebuild is acceptable recovery strategy
- No complex incremental rollback needed
- Focus on verification before deployment, not complex rollback

## Open Questions

Things that couldn't be fully resolved:

1. **Exact statement splitting for asyncpg**
   - What we know: asyncpg requires single statements, not multi-statement execution
   - What's unclear: Best regex/approach for splitting pg_dump output
   - Recommendation: Test splitting approach on complex functions, use `;\n` delimiter

2. **Materialized view refresh after migration**
   - What we know: MVs need refreshing after fresh database creation
   - What's unclear: Should this be in migration or separate make target
   - Recommendation: Add to migration as final step, also document manual refresh

## Sources

### Primary (HIGH confidence)
- [PostgreSQL pg_dump Documentation](https://www.postgresql.org/docs/current/app-pgdump.html) - Official flags and options
- [Alembic Autogenerate API](https://alembic.sqlalchemy.org/en/latest/api/autogenerate.html) - compare_metadata() usage
- [Alembic Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html) - Building databases from scratch

### Secondary (MEDIUM confidence)
- [Squash Alembic Migrations](https://notes.alexkehayias.com/squash-migrations-using-alembic/) - Step-by-step process with pg_dump
- [Alembic Discussion #1572](https://github.com/sqlalchemy/alembic/discussions/1572) - Community approaches to squashing
- [Alembic Discussion #1259](https://github.com/sqlalchemy/alembic/discussions/1259) - Best practices for large migration sets

### Tertiary (LOW confidence)
- [pgquarrel](https://github.com/eulerto/pgquarrel) - Schema comparison tool (not verified for this use case)
- [alembic-verify](https://alembic-verify.readthedocs.io/en/latest/) - Verification library (maintenance status unclear)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use, documented officially
- Architecture: HIGH - Pattern used successfully in multiple projects
- Pitfalls: MEDIUM - Gathered from community discussions, may miss edge cases
- Rollback strategy: HIGH - Based on existing docker/backup.sh pattern

**Research date:** 2026-01-20
**Valid until:** Stable - Alembic and pg_dump patterns are mature
