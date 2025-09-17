# HNF1B-API Phenopackets Migration Guide

## Overview

This guide documents the direct migration process from Google Sheets data to GA4GH Phenopackets v2 format.

## Migration Summary

### Direct Migration Approach

The new migration system transforms data directly from Google Sheets into standardized Phenopackets format, bypassing intermediate database normalization for improved efficiency and data integrity.

### New Architecture

```
Google Sheets (CSV) → Direct Phenopackets Builder → PostgreSQL JSONB Storage
```

## Quick Start

### 1. Prerequisites

- PostgreSQL 15+ with JSONB support
- Python 3.10+
- UV package manager
- Valid Google Sheets URLs
- Environment variables configured in `.env`

### 2. Installation

```bash
# Install dependencies
uv sync

# Start database services
make hybrid-up

# Verify environment
cat .env  # Ensure DATABASE_URL points to hnf1b_phenopackets database
```

### 3. Run Direct Migration

```bash
# Full migration - all individuals from Google Sheets
make phenopackets-migrate

# Test migration - 20 individuals only
make phenopackets-migrate-test

# Dry run - outputs to JSON file without database changes
make phenopackets-migrate-dry
```

## Migration Process Details

### Data Sources

The migration reads directly from Google Sheets:
- **Individuals Sheet**: Core patient demographics and clinical data
- **Variants Data**: Genetic variant information (prioritizes Varsome format)
- **Clinical Features**: Mapped to HPO terms
- **Disease Diagnoses**: Mapped to MONDO ontology

### Key Mappings

#### Subject Information
- `individual_id` → `subject.id` (primary identifier)
- `IndividualIdentifier` → `subject.alternateIds`
- `Sex` → `subject.sex` (MALE/FEMALE/UNKNOWN)
- `AgeReported` → `subject.timeAtLastEncounter.age`

#### Clinical Features (HPO Terms)
- Renal manifestations → HP:0012622-HP:0012626 (CKD stages)
- Diabetes → HP:0000819 (Diabetes mellitus)
- Hypomagnesemia → HP:0002917
- Liver abnormalities → HP:0031865 (Abnormal liver physiology)
- Brain abnormalities → HP:0012443 (Abnormality of brain morphology)
- Mental/behavioral → HP:0000708 (Behavioral abnormality)

#### Variant Information
Priority order:
1. Varsome column (GA4GH compliant format)
2. hg38 column (genomic coordinates)
3. Other variant columns

### Manual Migration

For custom configurations:

```bash
# Direct execution
uv run python migration/direct_sheets_to_phenopackets.py

# With options
uv run python migration/direct_sheets_to_phenopackets.py --test  # 20 individuals
uv run python migration/direct_sheets_to_phenopackets.py --dry-run  # JSON output only
```

## Configuration

### Google Sheets URLs

Update URLs in `migration/direct_sheets_to_phenopackets.py`:

```python
INDIVIDUALS_SHEET_URL = "your_sheet_url_here"
```

### Database Connection

Set in `.env` file:
```
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets
```

## Validation

### Check Migration Results

```bash
# Connect to database
psql -U hnf1b_user -d hnf1b_phenopackets -h localhost -p 5433

# Count phenopackets
SELECT COUNT(*) FROM phenopackets;

# Verify data structure
SELECT
    phenopacket_id,
    phenopacket->>'id' as id,
    phenopacket->'subject'->>'id' as subject_id,
    jsonb_array_length(phenopacket->'phenotypicFeatures') as features_count
FROM phenopackets
LIMIT 5;
```

### API Verification

```bash
# Start API server
make server

# Test endpoints
curl http://localhost:8000/api/v2/phenopackets
curl http://localhost:8000/api/v2/phenopackets/aggregate/phenotypes
curl http://localhost:8000/api/v2/clinical/renal-insufficiency
```

## Troubleshooting

### Common Issues

1. **Database connection failed**
   - Verify PostgreSQL is running: `docker ps`
   - Check DATABASE_URL in `.env`
   - Ensure database exists: `make hybrid-up`

2. **Google Sheets access error**
   - Verify sheet URLs are public or accessible
   - Check internet connectivity
   - Ensure CSV export is enabled

3. **Invalid data mappings**
   - Review PHENOPACKETS_DATA_MAPPING.md
   - Check HPO term validity
   - Verify variant format

## Files and Structure

### Key Files

- `migration/direct_sheets_to_phenopackets.py` - Direct migration script
- `PHENOPACKETS_DATA_MAPPING.md` - Detailed field mappings
- `app/phenopackets/models.py` - Phenopacket data models
- `app/phenopackets/validator.py` - Validation logic
- `Makefile` - Migration commands

### Database Schema

Primary table: `phenopackets`
- `id`: UUID primary key
- `phenopacket_id`: Unique phenopacket identifier
- `phenopacket`: JSONB containing full phenopacket
- `subject_id`: Extracted for indexing
- `created_at`, `updated_at`: Timestamps

## Migration Statistics

Expected results from full migration:
- ~864 phenopackets created
- 96% with phenotypic features
- 49% with genetic variants
- 100% with disease diagnoses

## Support

For issues or questions:
- Check logs: `uv run python migration/direct_sheets_to_phenopackets.py --verbose`
- Review mappings: See PHENOPACKETS_DATA_MAPPING.md
- API documentation: http://localhost:8000/api/v2/docs