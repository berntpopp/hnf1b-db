# Admin Guide: Updating Genomic Annotations

Guide for administrators to update genomic reference data (genes, protein domains, exons).

**Audience:** Database administrators, bioinformaticians
**Last Updated:** 2025-01-18

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Update Procedures](#update-procedures)
  - [Update HNF1B Reference Data](#update-hnf1b-reference-data)
  - [Import chr17q12 Region Genes](#import-chr17q12-region-genes)
  - [Add New Genome Assembly](#add-new-genome-assembly)
  - [Update Protein Domains](#update-protein-domains)
- [Data Sources](#data-sources)
- [Validation](#validation)
- [Rollback](#rollback)
- [Troubleshooting](#troubleshooting)

---

## Overview

Genomic reference annotations should be updated when:

- **New genome assemblies** are released (e.g., T2T-CHM13, GRCh39)
- **Protein domains** are corrected or refined (from UniProt updates)
- **Gene coordinates** change (rare, but can happen with assembly patches)
- **New transcripts** become canonical (MANE Select updates)

**Update Frequency:**
- Protein domains: Quarterly (check UniProt releases)
- Gene coordinates: As needed (monitor NCBI Gene updates)
- Genome assemblies: Rare (every few years)

---

## Prerequisites

### System Requirements

- **Python:** 3.10+ with `uv` package manager
- **Database:** PostgreSQL 14+ with write access
- **Environment:** Backend `.env` configured with `DATABASE_URL`

### Database Backup

**⚠️ ALWAYS backup the database before running update scripts!**

```bash
# Backup production database
pg_dump -h localhost -U hnf1b_user -d hnf1b_phenopackets > backup_$(date +%Y%m%d).sql

# Verify backup
ls -lh backup_*.sql
```

### Test Environment

Test all updates in a development/staging environment first:

```bash
# Use test database
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/hnf1b_test
```

---

## Update Procedures

### Update HNF1B Reference Data

Updates HNF1B gene, transcripts, exons, and protein domains.

**When to run:**
- UniProt updates protein domain boundaries
- NCBI updates transcript coordinates
- New canonical transcript is designated

**Script:** `backend/scripts/import_hnf1b_reference_data.py`

**What it does:**
1. Creates/updates GRCh38 genome assembly
2. Imports HNF1B gene coordinates (chr17:36,098,063-36,112,306)
3. Imports canonical transcript NM_000458.4
4. Imports 9 exon coordinates
5. Imports 4 protein domains from UniProt P35680

**Usage:**

```bash
cd backend

# 1. Review the script to verify data sources
cat scripts/import_hnf1b_reference_data.py

# 2. Update domain coordinates in the script if needed
# Edit HNF1B_DOMAINS list (lines 44-84)

# 3. Run the import
uv run python scripts/import_hnf1b_reference_data.py
```

**Expected Output:**

```
================================================================================
HNF1B Reference Data Import
================================================================================

[1/5] Importing GRCh38 genome assembly...
  ✓ Created genome: GRCh38 (ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

[2/5] Importing HNF1B gene...
  ✓ Created gene: HNF1B (17:36098063-36112306)

[3/5] Importing NM_000458.4 transcript...
  ✓ Created transcript: NM_000458.4 (protein: NP_000449.3)

[4/5] Importing exon coordinates...
  ✓ Created 9 exons

[5/5] Importing protein domains from UniProt P35680...
  ✓ Created 4 protein domains
    - Dimerization Domain (IPR000327): aa 1-31
    - POU-Specific Domain (IPR000327): aa 8-173
    - POU Homeodomain (IPR001356): aa 232-305
    - Transactivation Domain: aa 314-557

================================================================================
✓ Import completed successfully!
================================================================================

Test the API:
  GET http://localhost:8000/api/v2/reference/genomes
  GET http://localhost:8000/api/v2/reference/genes/HNF1B
  GET http://localhost:8000/api/v2/reference/genes/HNF1B/domains
```

**Validation:**

```bash
# Test API endpoints
curl http://localhost:8000/api/v2/reference/genes/HNF1B | jq
curl http://localhost:8000/api/v2/reference/genes/HNF1B/domains | jq
```

---

### Import chr17q12 Region Genes

Imports all 29 genes from the chr17q12 deletion syndrome region.

**When to run:**
- Initial database setup
- Adding new genes to the chr17q12 region
- Updating gene metadata (clinical significance, function)

**Script:** `backend/scripts/import_chr17q12_genes.py`

**Data Source:** `frontend/src/data/chr17q12_genes.json` (29 genes)

**What it does:**
1. Loads gene data from JSON file
2. Fetches GRCh38 genome assembly
3. Creates or updates genes in database
4. Stores clinical significance and function in `extra_data`

**Usage:**

```bash
cd backend

# 1. Review/update the JSON file if needed
cat ../frontend/src/data/chr17q12_genes.json | jq '.genes[] | {symbol, clinicalSignificance}'

# 2. Run the import
uv run python scripts/import_chr17q12_genes.py
```

**Expected Output:**

```
================================================================================
chr17q12 Region Genes Import (GRCh38)
================================================================================

📁 Loaded 29 genes from chr17q12_genes.json

[1/3] Fetching GRCh38 genome assembly...
  ✓ Found genome: GRCh38 (ID: xxxxxxxx)

[2/3] Importing 29 genes...
  + Imported: CCL3 (chr17:36091902-36093743)
  + Imported: CCL4 (chr17:36094684-36096627)
  ...
  ↻ Updated: HNF1B (chr17:36098063-36112306)
  ...

  ✓ Imported: 28 new genes
  ✓ Updated: 1 existing genes

[3/3] Committing changes...
  ✓ Changes committed

================================================================================
✓ Import completed successfully!
================================================================================

Summary:
  - Total genes in JSON: 29
  - New genes imported: 28
  - Existing genes updated: 1
  - Total genes in chr17q12 region: 29

Test the API:
  GET http://localhost:8000/api/v2/reference/genes?chromosome=17
  GET http://localhost:8000/api/v2/reference/regions/17:36000000-39900000
```

**Validation:**

```bash
# Test API endpoints
curl "http://localhost:8000/api/v2/reference/genes?chromosome=17" | jq '.genes | length'
curl "http://localhost:8000/api/v2/reference/regions/17:36000000-39900000" | jq '.gene_count'
```

---

### Add New Genome Assembly

Adds a new genome assembly (e.g., GRCh37, T2T-CHM13).

**When to run:**
- Adding legacy assembly support (GRCh37/hg19)
- Adding new reference assemblies (T2T-CHM13)

**Script:** `backend/scripts/add_grch37_assembly.py` (example)

**What it does:**
1. Checks if assembly already exists
2. Creates assembly record with metadata
3. Sets `is_default` flag appropriately

**Usage:**

```bash
cd backend

# Add GRCh37 assembly
uv run python scripts/add_grch37_assembly.py
```

**Expected Output:**

```
================================================================================
Add GRCh37 Genome Assembly
================================================================================

✓ Created GRCh37 genome assembly
  ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  UCSC: hg19
  Ensembl: GRCh37
  NCBI: GCA_000001405.14
  Version: p13
  Release: 2009-02-27

================================================================================
✓ GRCh37 assembly added successfully!
================================================================================

Next steps:
  1. Run liftover script to convert GRCh38 coordinates to GRCh37
  2. Test API: GET http://localhost:8000/api/v2/reference/genomes
```

**Creating a Custom Assembly Script:**

```python
# backend/scripts/add_custom_assembly.py
import asyncio
from datetime import datetime
from app.reference.models import ReferenceGenome

async def add_custom_assembly():
    genome = ReferenceGenome(
        name="T2T-CHM13",
        ucsc_name="hs1",
        ensembl_name="T2T-CHM13v2.0",
        ncbi_name="GCA_009914755.4",
        version="v2.0",
        release_date=datetime(2022, 4, 1),
        is_default=False,
        source_url="https://www.ncbi.nlm.nih.gov/assembly/GCA_009914755.4/",
        extra_data={"description": "Telomere-to-telomere CHM13 assembly"}
    )
    session.add(genome)
    await session.commit()
```

---

### Update Protein Domains

Updates protein domain annotations from UniProt.

**When to run:**
- UniProt releases corrected domain boundaries
- New domains are discovered
- Domain functions are updated

**Process:**

1. **Check UniProt for updates:**
   - Visit: https://www.uniprot.org/uniprotkb/P35680/entry
   - Compare domain boundaries with current data

2. **Update the import script:**

```python
# Edit backend/scripts/import_hnf1b_reference_data.py
# Update HNF1B_DOMAINS list (lines 44-84)

HNF1B_DOMAINS = [
    {
        "name": "Dimerization Domain",
        "short_name": "Dim",
        "start": 1,        # ← Update if changed
        "end": 31,         # ← Update if changed
        "function": "Mediates homodimer or heterodimer formation",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    # ... other domains
]
```

3. **Run the updated import:**

```bash
uv run python scripts/import_hnf1b_reference_data.py
```

4. **Verify changes:**

```bash
# Check domain coordinates
curl http://localhost:8000/api/v2/reference/genes/HNF1B/domains | jq '.domains'

# Compare with previous version (if backed up)
diff <(curl -s http://prod-server/api/v2/reference/genes/HNF1B/domains | jq '.domains') \
     <(curl -s http://localhost:8000/api/v2/reference/genes/HNF1B/domains | jq '.domains')
```

---

## Data Sources

### Primary Sources

| Data Type | Source | URL | Update Frequency |
|-----------|--------|-----|------------------|
| Gene coordinates | NCBI Gene | https://www.ncbi.nlm.nih.gov/gene/6928 | As needed |
| Protein domains | UniProt P35680 | https://www.uniprot.org/uniprotkb/P35680 | Quarterly |
| Transcript coords | RefSeq NM_000458.4 | https://www.ncbi.nlm.nih.gov/nuccore/NM_000458.4 | As needed |
| Genome assemblies | NCBI Assembly | https://www.ncbi.nlm.nih.gov/assembly | Rare |
| Exon coordinates | UCSC Genome Browser | https://genome.ucsc.edu/ | As needed |

### Data Verification

Always cross-reference with multiple sources:

- **Gene coordinates:** NCBI Gene, Ensembl, UCSC
- **Protein domains:** UniProt, Pfam, InterPro
- **Transcripts:** RefSeq, Ensembl, MANE Select

---

## Validation

### Post-Update Checklist

After running any update script:

- [ ] **API returns correct data:**
  ```bash
  curl http://localhost:8000/api/v2/reference/genes/HNF1B | jq
  ```

- [ ] **Domain counts match expected:**
  ```bash
  curl http://localhost:8000/api/v2/reference/genes/HNF1B/domains | jq '.domains | length'
  ```

- [ ] **Exon counts match expected:**
  ```bash
  curl http://localhost:8000/api/v2/reference/genes/HNF1B/transcripts | jq '.transcripts[0].exon_count'
  ```

- [ ] **Frontend visualizations render correctly:**
  - Visit: http://localhost:5173/
  - Check HNF1B protein domain visualization
  - Check chr17q12 gene visualization (CNV mode)

- [ ] **No database errors in logs:**
  ```bash
  grep -i error backend/logs/app.log | tail -20
  ```

---

## Rollback

### Restore from Backup

If an update causes issues, restore from backup:

```bash
# Stop the application
docker-compose down

# Restore database
psql -h localhost -U hnf1b_user -d hnf1b_phenopackets < backup_20250118.sql

# Restart application
docker-compose up -d
```

### Alembic Downgrade

If using database migrations:

```bash
# Rollback last migration
cd backend
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

---

## Troubleshooting

### Common Issues

**Issue:** Script fails with "Genome assembly 'GRCh38' not found"

**Solution:** Run `import_hnf1b_reference_data.py` first to create the genome assembly.

---

**Issue:** Script reports "Gene already exists" but doesn't update

**Solution:** The script checks for existing genes by symbol+genome_id. If you want to force an update, manually delete the gene first:

```sql
DELETE FROM genes WHERE symbol = 'HNF1B' AND genome_id = (SELECT id FROM reference_genomes WHERE name = 'GRCh38');
```

Then re-run the import script.

---

**Issue:** API returns old protein domain coordinates

**Solution:** Check if the database was actually updated:

```sql
SELECT name, start, "end", updated_at FROM protein_domains
WHERE transcript_id = (SELECT id FROM transcripts WHERE transcript_id = 'NM_000458.4')
ORDER BY start;
```

If `updated_at` is old, the import may have failed. Check logs for errors.

---

**Issue:** Frontend still shows hardcoded data

**Solution:** The frontend now fetches from the API. Clear browser cache and hard refresh (Ctrl+Shift+R).

---

### Getting Help

- **Backend issues:** Check `backend/logs/app.log`
- **Database issues:** Check PostgreSQL logs
- **API issues:** Test with `curl` and check Swagger UI at `/docs`
- **Import script issues:** Run with Python debugger:
  ```bash
  uv run python -m pdb scripts/import_hnf1b_reference_data.py
  ```

---

## See Also

- [API Documentation](../api/reference-genome-api.md)
- [Database Schema](../database/reference-schema.md)
- [Data Sources](../references/data-sources.md)
