# HNF1B-API Phenopackets Migration Guide

## Overview

This guide documents the complete restructuring of HNF1B-API from a normalized PostgreSQL database to a GA4GH Phenopackets v2 compliant system.

## Migration Summary

### What Changed

1. **Database Structure**: Replaced 13+ normalized tables with 4 phenopacket-centric tables
2. **Data Model**: Adopted GA4GH Phenopackets v2 as the core data model
3. **API Design**: New RESTful endpoints centered around phenopackets
4. **Query Capabilities**: Enhanced clinical feature queries using JSONB

### New Architecture

```
Google Sheets → Phenopackets Builder → PostgreSQL JSONB → Phenopackets API v2
```

## Quick Start

### 1. Prerequisites

- PostgreSQL 15+ (for JSONB features)
- Python 3.10+
- UV package manager

### 2. Installation

```bash
# Install dependencies
uv sync --all-groups

# Set up environment
cp .env.phenopackets .env
# Edit .env with your database credentials
```

### 3. Database Setup

```bash
# Create new phenopackets database
createdb hnf1b_phenopackets

# Apply schema
psql postgresql://user:pass@localhost/hnf1b_phenopackets < migration/phenopackets_schema.sql
```

### 4. Run Migration

```bash
# Full migration with backup
chmod +x migration/run_phenopackets_migration.sh
./migration/run_phenopackets_migration.sh

# Or run Python migration directly
uv run python migration/phenopackets_migration.py
```

### 5. Start API

```bash
# Start the new API
uv run python -m uvicorn app.main_v2:app --reload

# API will be available at http://localhost:8000
# Documentation at http://localhost:8000/api/v2/docs
```

## New API Endpoints

### Core Phenopacket Operations

- `GET /api/v2/phenopackets` - List all phenopackets
- `GET /api/v2/phenopackets/{id}` - Get specific phenopacket
- `POST /api/v2/phenopackets` - Create phenopacket
- `PUT /api/v2/phenopackets/{id}` - Update phenopacket
- `DELETE /api/v2/phenopackets/{id}` - Delete phenopacket
- `POST /api/v2/phenopackets/search` - Advanced search

### Clinical Feature Queries

- `GET /api/v2/clinical/renal-insufficiency` - Kidney disease cases
- `GET /api/v2/clinical/genital-abnormalities` - Genital tract abnormalities
- `GET /api/v2/clinical/diabetes` - Diabetes cases
- `GET /api/v2/clinical/hypomagnesemia` - Hypomagnesemia cases
- `GET /api/v2/clinical/pancreatic-abnormalities` - Pancreatic abnormalities
- `GET /api/v2/clinical/liver-abnormalities` - Liver abnormalities
- `GET /api/v2/clinical/kidney-morphology` - Kidney morphological features
- `GET /api/v2/clinical/multisystem-involvement` - Multi-system cases

### Aggregation Endpoints

- `GET /api/v2/phenopackets/aggregate/by-feature` - Aggregate by phenotypic features
- `GET /api/v2/phenopackets/aggregate/by-disease` - Aggregate by disease
- `GET /api/v2/phenopackets/aggregate/kidney-stages` - Kidney disease stage distribution
- `GET /api/v2/phenopackets/aggregate/sex-distribution` - Sex distribution
- `GET /api/v2/phenopackets/aggregate/variant-pathogenicity` - Variant classifications

## Data Structure

### Phenopacket Format

```json
{
  "id": "phenopacket:HNF1B:IND001",
  "subject": {
    "id": "IND001",
    "sex": "FEMALE",
    "timeAtLastEncounter": {
      "age": {"iso8601duration": "P25Y"}
    }
  },
  "phenotypicFeatures": [
    {
      "type": {
        "id": "HP:0012622",
        "label": "Chronic kidney disease"
      },
      "modifiers": [{
        "id": "HP:0012625",
        "label": "Stage 3 chronic kidney disease"
      }]
    }
  ],
  "diseases": [
    {
      "term": {
        "id": "MONDO:0018874",
        "label": "HNF1B-related autosomal dominant tubulointerstitial kidney disease"
      }
    }
  ],
  "interpretations": [
    {
      "id": "interpretation-001",
      "progressStatus": "COMPLETED",
      "diagnosis": {
        "disease": {"id": "OMIM:137920", "label": "HNF1B-related disease"},
        "genomicInterpretations": [...]
      }
    }
  ],
  "metaData": {
    "created": "2024-01-01T00:00:00Z",
    "createdBy": "HNF1B-API",
    "resources": [...],
    "phenopacketSchemaVersion": "2.0.0"
  }
}
```

## Testing

### Run Tests

```bash
# Run migration tests
uv run pytest tests/test_phenopackets_migration.py -v

# Test API endpoints
uv run pytest tests/test_phenopackets_api.py -v
```

### Validation

```bash
# Check migration status
psql -d hnf1b_phenopackets -c "SELECT COUNT(*) FROM phenopackets;"

# Validate phenopackets
uv run python -c "
from app.phenopackets.validator import PhenopacketValidator
validator = PhenopacketValidator()
# Test validation
"
```

## Rollback Procedure

If you need to rollback to the previous version:

```bash
# Restore from backup
psql postgresql://user:pass@localhost/hnf1b_db < backups/hnf1b_backup_[timestamp].sql

# Switch back to old API
uv run python -m uvicorn app.main:app --reload
```

## Key Files

### Schema and Models
- `migration/phenopackets_schema.sql` - Database schema
- `app/phenopackets/models.py` - SQLAlchemy models and Pydantic schemas
- `app/phenopackets/validator.py` - Validation utilities

### Migration
- `migration/phenopackets_migration.py` - Main migration script
- `migration/run_phenopackets_migration.sh` - Migration runner with backup

### API Endpoints
- `app/phenopackets/endpoints.py` - Core phenopacket endpoints
- `app/phenopackets/clinical_endpoints.py` - Clinical feature queries
- `app/main_v2.py` - New API application

### Configuration
- `.env.phenopackets` - Environment configuration template
- `pyproject.toml` - Dependencies (already updated)

## Ontology Mappings

### Phenotype Mappings (HPO)
- Renal insufficiency → HP:0012622
- Hypomagnesemia → HP:0002917
- Genital abnormality → HP:0000078
- Pancreatic abnormality → HP:0001732
- Liver abnormality → HP:0001392

### Disease Mappings (MONDO)
- HNF1B disease → MONDO:0018874
- Type 1 diabetes → MONDO:0005147
- Type 2 diabetes → MONDO:0005148
- MODY → MONDO:0015967

## Performance Considerations

### Indexes
- JSONB GIN indexes for fast queries
- Specific indexes for common search patterns
- Full-text search capabilities

### Query Optimization
- Use PostgreSQL native JSONB operators
- Materialized views for complex aggregations
- Batch operations for bulk updates

## Troubleshooting

### Common Issues

1. **Migration fails with connection error**
   - Check DATABASE_URL and OLD_DATABASE_URL in .env
   - Ensure PostgreSQL is running

2. **Validation errors during migration**
   - Check validation_errors.json for details
   - Review phenotype mappings

3. **API performance issues**
   - Check JSONB indexes are created
   - Consider increasing connection pool size

## Next Steps

1. **Ontology Integration**
   - Download latest HPO and MONDO files
   - Set up ontology service for term validation

2. **Enhanced Features**
   - Implement phenopacket comparison
   - Add export formats (JSON, TSV, FHIR)
   - Build phenopacket builder UI

3. **Production Deployment**
   - Configure proper CORS settings
   - Set up monitoring and logging
   - Implement rate limiting

## Support

For issues or questions:
1. Check the validation report: `migration_report_[timestamp].txt`
2. Review logs in the console output
3. Consult the GA4GH Phenopackets documentation

## References

- [GA4GH Phenopackets v2 Specification](https://phenopacket-schema.readthedocs.io/)
- [Human Phenotype Ontology](https://hpo.jax.org/)
- [Mondo Disease Ontology](https://mondo.monarchinitiative.org/)
- [PostgreSQL JSONB Documentation](https://www.postgresql.org/docs/current/datatype-json.html)