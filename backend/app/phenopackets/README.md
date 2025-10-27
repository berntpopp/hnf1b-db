# Phenopackets Module

This module implements GA4GH Phenopackets v2 API endpoints and services for the HNF1B database.

## Overview

The phenopackets module provides RESTful API endpoints for:
- Phenopacket CRUD operations
- Variant aggregation and search
- Clinical feature queries
- Disease and publication aggregation

## Directory Structure

```
app/phenopackets/
├── endpoints.py                      # Main API endpoints
├── clinical_endpoints.py             # Clinical feature queries
├── models.py                         # Pydantic models
├── validator.py                      # Phenopacket validation
├── variant_search_validation.py     # Variant search input validation
├── molecular_consequence.py         # Molecular consequence computation
├── clinical_queries.py              # Clinical query helpers
└── age_utils.py                     # Age/temporal utilities
```

## API Endpoints

### Core Phenopacket Endpoints

- `GET /phenopackets/` - List phenopackets with filters
- `GET /phenopackets/{id}` - Get single phenopacket
- `POST /phenopackets/` - Create new phenopacket (auth required)
- `PUT /phenopackets/{id}` - Update phenopacket (auth required)
- `DELETE /phenopackets/{id}` - Delete phenopacket (auth required)
- `GET /phenopackets/batch` - Batch fetch by IDs (prevents N+1)
- `POST /phenopackets/search` - Advanced search with filters

### Variant Endpoints

- `GET /phenopackets/aggregate/all-variants` - **Search and filter variants**
  - 8 search fields: HGVS notations, variant ID, coordinates, type, classification, gene, consequence
  - Full documentation: [docs/api/VARIANT_SEARCH.md](../../../docs/api/VARIANT_SEARCH.md)
- `GET /phenopackets/by-variant/{variant_id}` - Get phenopackets for a variant
- `GET /phenopackets/aggregate/variant-pathogenicity` - Classification distribution
- `GET /phenopackets/aggregate/variant-types` - Variant type distribution

### Aggregation Endpoints

- `GET /phenopackets/aggregate/summary` - Summary statistics
- `GET /phenopackets/aggregate/sex-distribution` - Sex distribution
- `GET /phenopackets/aggregate/by-feature` - HPO term frequencies
- `GET /phenopackets/aggregate/by-disease` - Disease frequencies
- `GET /phenopackets/aggregate/kidney-stages` - Kidney disease stages
- `GET /phenopackets/aggregate/publications` - Publication statistics

### Clinical Query Endpoints

See `clinical_endpoints.py`:
- `GET /clinical/renal-insufficiency` - Kidney disease cases
- `GET /clinical/genital-abnormalities` - Genital tract abnormalities
- `GET /clinical/diabetes` - Diabetes cases
- `GET /clinical/hypomagnesemia` - Hypomagnesemia cases

## Variant Search Feature

The variant search endpoint (`/aggregate/all-variants`) supports comprehensive searching and filtering:

### Search Fields (8 total)

1. **Transcript (c. notation)** - e.g., `c.1654-2A>T`
2. **Protein (p. notation)** - e.g., `p.Arg177Ter`
3. **Variant ID** - e.g., `Var1`, `ga4gh:VA.xxx`
4. **HG38 Coordinates** - e.g., `chr17:36098063`
5. **Variant Type** - SNV, deletion, duplication, etc.
6. **Classification** - PATHOGENIC, LIKELY_PATHOGENIC, etc.
7. **Gene Symbol** - HNF1B
8. **Molecular Consequence** - Frameshift, Nonsense, etc.

### Example Queries

```bash
# Search by HGVS notation
GET /phenopackets/aggregate/all-variants?query=c.1654-2A>T

# Filter pathogenic deletions
GET /phenopackets/aggregate/all-variants?variant_type=deletion&classification=PATHOGENIC

# Search with molecular consequence
GET /phenopackets/aggregate/all-variants?consequence=Frameshift
```

**Full Documentation:** [docs/api/VARIANT_SEARCH.md](../../../docs/api/VARIANT_SEARCH.md)

## Key Modules

### variant_search_validation.py

Input validation for variant search parameters:
- HGVS notation format validation (c., p., g.)
- HG38 coordinate format validation
- Character whitelist enforcement (SQL injection prevention)
- Length limits (DoS prevention)
- Enum validation for controlled vocabularies

**Usage:**
```python
from app.phenopackets.variant_search_validation import (
    validate_search_query,
    validate_variant_type,
    validate_classification,
)

# Validates and sanitizes input
query = validate_search_query("c.1654-2A>T")
variant_type = validate_variant_type("deletion")
classification = validate_classification("PATHOGENIC")
```

### molecular_consequence.py

Computes molecular consequences from HGVS notations:
- Frameshift detection from p. notation
- Nonsense/stop-gained detection
- Missense, splice site, CNV consequence inference

**Usage:**
```python
from app.phenopackets.molecular_consequence import compute_molecular_consequence

consequence = compute_molecular_consequence(
    transcript="NM_000458.4:c.544+1G>T",
    protein=None,
    variant_type=None
)
# Returns: "Splice Donor"
```

### validator.py

Phenopacket validation and sanitization:
- GA4GH Phenopackets v2 schema validation
- Required field checking
- Data sanitization

**Usage:**
```python
from app.phenopackets.validator import PhenopacketValidator

validator = PhenopacketValidator()
errors = validator.validate(phenopacket_dict)
if errors:
    raise ValidationError(errors)
```

## Security Features

### Input Validation

All user inputs are validated before database queries:
- Character whitelist: `[A-Za-z0-9._:>()+=*\-/\s]`
- Length limits: 200 characters max for search queries
- HGVS format validation for notation strings
- Enum validation for categorical filters

### SQL Injection Prevention

- All queries use parameterized statements (`:param` syntax)
- No f-string interpolation of user input
- WHERE clauses built from pre-validated literals only

### Error Handling

- HTTPException with appropriate status codes
- Clear error messages for users
- No sensitive information leaked in errors

## Performance Optimizations

### Database Indexes

GIN indexes on JSONB paths (see `alembic/versions/003_add_variant_search_indexes.py`):
- `idx_variant_descriptor_id` - Fast variant ID lookups
- `idx_variant_expressions` - Fast HGVS notation search
- `idx_variant_structural_type` - Fast type filtering
- `idx_variant_classification` - Fast classification filtering

**Performance Impact:**
- Before indexes: ~500ms (sequential scan)
- After indexes: ~50ms (index scan)
- **10x faster** variant searches

### Batch Endpoints

Prevent N+1 query problems:
- `GET /phenopackets/batch` - Fetch multiple phenopackets in one query
- `GET /variants/batch` - Fetch variants for multiple phenopackets
- `GET /features/batch` - Fetch features for multiple phenopackets

## Testing

Run tests from the backend directory:

```bash
# All tests
make test

# Specific module tests
uv run pytest tests/test_variant_search.py -v

# With coverage
uv run pytest --cov=app/phenopackets tests/test_variant_search.py
```

See [tests/README.md](../../tests/README.md) for detailed testing documentation.

## Data Models

### PhenopacketResponse

```python
{
    "id": "uuid",
    "phenopacket_id": "HNF1B_001",
    "version": 1,
    "phenopacket": {
        "id": "HNF1B_001",
        "subject": {...},
        "phenotypicFeatures": [...],
        "interpretations": [...],
        "diseases": [...],
        "metaData": {...}
    },
    "created_at": "2025-10-27T12:00:00Z",
    "updated_at": "2025-10-27T12:00:00Z",
    "schema_version": "2.0"
}
```

### Variant Search Response

```python
[
    {
        "simple_id": "Var1",
        "variant_id": "ga4gh:VA.xxx",
        "label": "HNF1B:c.1654-2A>T",
        "gene_symbol": "HNF1B",
        "gene_id": "HGNC:5024",
        "structural_type": "SNV",
        "pathogenicity": "PATHOGENIC",
        "phenopacket_count": 15,
        "hg38": "chr17:36098063",
        "transcript": "NM_000458.4:c.1654-2A>T",
        "protein": "NP_000449.3:p.Ser552Ter",
        "molecular_consequence": "Splice Acceptor"
    }
]
```

## Development Guidelines

### Adding New Endpoints

1. Define endpoint in `endpoints.py` or `clinical_endpoints.py`
2. Add Pydantic models to `models.py`
3. Add validation logic if needed
4. Write tests in `tests/test_*.py`
5. Update this README

### Adding New Filters

1. Add validation function to `variant_search_validation.py`
2. Add filter logic to endpoint query building
3. Add tests for validation and filtering
4. Update API documentation

### Database Queries

- Use parameterized queries (`:param` syntax)
- Always validate user inputs before queries
- Use batch endpoints when fetching related data
- Consider adding indexes for new query patterns

## Related Documentation

- **Variant Search:** [docs/api/VARIANT_SEARCH.md](../../../docs/api/VARIANT_SEARCH.md)
- **Backend README:** [backend/README.md](../../README.md)
- **Project Overview:** [CLAUDE.md](../../../CLAUDE.md)
- **API Documentation:** Available at `/docs` when server is running
- **Testing Guide:** [tests/README.md](../../tests/README.md)

## Support

For questions or issues:
1. Check the documentation in `docs/`
2. Review existing tests for examples
3. Check FastAPI auto-generated docs at `/docs` endpoint
4. See [CLAUDE.md](../../../CLAUDE.md) for development workflow
