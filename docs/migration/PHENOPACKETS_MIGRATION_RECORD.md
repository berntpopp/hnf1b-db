# HNF1B Database to GA4GH Phenopackets Migration Record

## Executive Summary

This document records the complete migration journey of the HNF1B-DB API from a custom PostgreSQL database to the GA4GH Phenopackets v2 standard. The migration transformed 864 individuals' clinical and genetic data from Google Sheets into standardized, interoperable phenopackets stored as JSONB in PostgreSQL.

**Migration Outcome**: ✅ Successfully migrated 864 individuals with 96% having phenotypic features, 49% having genetic variants, and 100% having disease diagnoses.

---

## Migration Timeline & Phases

### Phase 1: Initial Assessment
**Objective**: Understand existing data structure and requirements

- **Source Data**: Google Sheets (ID: 1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw)
- **Records**: 939 rows representing 864 unique individuals
- **Challenge**: Custom database schema with non-standard clinical data representation

### Phase 2: Architecture Decision
**Objective**: Choose optimal migration approach

**Decision**: Direct Google Sheets → Phenopackets transformation
```
Google Sheets (CSV) → Direct Phenopackets Builder → PostgreSQL JSONB Storage
```

**Rationale**:
- Bypass intermediate normalization for improved efficiency
- Maintain data integrity with single transformation step
- Simplify migration process and reduce potential errors

### Phase 3: Data Mapping Design
**Objective**: Map all source fields to GA4GH Phenopackets v2 structure

#### Core Mappings Implemented

##### Subject Information
| Source Column | Phenopacket Field | Transformation |
|--------------|-------------------|----------------|
| individual_id | subject.id | Direct mapping (1, 2, 3...) |
| IndividualIdentifier | subject.alternateIds | Array of identifiers |
| Sex | subject.sex | female→FEMALE, male→MALE |
| AgeReported | timeAtLastEncounter | Parse to ISO8601 duration |
| AgeOnset | disease.onset | Age at disease manifestation |

##### Clinical Features (HPO Mappings)
| Clinical Feature | HPO Term | Description |
|-----------------|----------|-------------|
| RenalInsufficancy | HP:0000083 | Renal insufficiency |
| RenalCysts | HP:0000107 | Renal cyst |
| Hypomagnesemia | HP:0002917 | Hypomagnesemia |
| MODY | HP:0004904 | Maturity-onset diabetes |
| BrainAbnormality | HP:0012443 | Abnormality of brain morphology |
| MentalDisease | HP:0000708 | Behavioral abnormality |
| AbnormalLiverPhysiology | HP:0031865 | Abnormal liver physiology |

##### Genetic Variants
**Priority Order**:
1. **Varsome column** (GA4GH compliant): `HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)`
2. **hg38 column**: `chr17-37739578-G-C` (genomic coordinates)
3. **VariantReported column**: Fallback for descriptive text

### Phase 4: Technical Implementation

#### Database Schema
```sql
CREATE TABLE phenopackets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id VARCHAR UNIQUE NOT NULL,
    version VARCHAR NOT NULL DEFAULT '2.0',
    phenopacket JSONB NOT NULL,
    subject_id VARCHAR GENERATED ALWAYS AS (phenopacket->>'subject'->>'id') STORED,
    subject_sex VARCHAR GENERATED ALWAYS AS (phenopacket->>'subject'->>'sex') STORED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Comprehensive JSONB indexes for performance
CREATE INDEX idx_phenopackets_jsonb ON phenopackets USING gin (phenopacket);
CREATE INDEX idx_phenopackets_features ON phenopackets USING gin ((phenopacket->'phenotypicFeatures'));
```

#### Migration Script
**Location**: `/migration/direct_sheets_to_phenopackets.py`

**Key Components**:
1. **Data Loading**: Direct CSV parsing from Google Sheets
2. **Phenopacket Builder**: Constructs GA4GH v2 compliant structures
3. **Variant Processing**: GA4GH VRS 2.0 compliant variant representation
4. **Batch Storage**: Efficient PostgreSQL insertion with conflict handling

### Phase 5: GA4GH VRS Integration

#### VRS 2.0 Compliance
All variants represented using GA4GH Variation Representation Specification:

```json
{
  "vrsAllele": {
    "id": "ga4gh:VA.{digest}",
    "type": "Allele",
    "location": {
      "type": "SequenceLocation",
      "sequenceReference": {
        "refgetAccession": "SQ.{32-char-hash}"
      },
      "start": {"value": 37739578},
      "end": {"value": 37739579}
    },
    "state": {
      "type": "LiteralSequenceExpression",
      "sequence": "C"
    }
  }
}
```

**Digest Computation**:
- Primary: GA4GH standard SHA-512 truncated digest via `ga4gh.vrs` library
- Fallback: Deterministic placeholder for environments without library

### Phase 6: Ontology Service Enhancement

#### Hybrid Ontology Service Architecture
```
User Request
     ↓
Memory Cache → Found? → Return
     ↓ Not found
File Cache → Found? → Return
     ↓ Not found
APIs (if enabled) → Found? → Cache & Return
     ↓ Not found
Local Mappings → Found? → Return
     ↓ Not found
Unknown Term Placeholder
```

**Benefits**:
- No large ontology file downloads (saves ~150MB)
- Works offline with local mappings
- Always current with API lookups
- Fast with intelligent caching

**API Sources**:
1. HPO JAX API (https://hpo.jax.org/api/hpo)
2. EBI OLS API (https://www.ebi.ac.uk/ols4/api)
3. Monarch Initiative API (https://api.monarchinitiative.org/v3)

### Phase 7: API Development

#### Phenopackets v2 API Endpoints
**Base URL**: `/api/v2/`

| Endpoint | Purpose |
|----------|---------|
| `/phenopackets/` | CRUD operations for phenopackets |
| `/phenopackets/search` | Advanced search with filters |
| `/phenopackets/aggregate/*` | Statistical aggregations |
| `/clinical/renal-insufficiency` | Kidney disease queries |
| `/clinical/diabetes` | Diabetes cases |
| `/clinical/genital-abnormalities` | Genital tract queries |

---

## Migration Execution

### Commands
```bash
# Full migration - all 864 individuals
make phenopackets-migrate

# Test migration - 20 individuals
make phenopackets-migrate-test

# Dry run - JSON output only
make phenopackets-migrate-dry
```

### Migration Statistics

#### Final Results
- **Total Phenopackets**: 864
- **With Phenotypic Features**: 830 (96%)
- **With Genetic Variants**: 423 (49%)
- **With Disease Diagnoses**: 864 (100%)
- **Sex Distribution**:
  - Female: 412 (48%)
  - Male: 398 (46%)
  - Unknown: 54 (6%)

#### Data Quality Metrics
- **Variant Sources**:
  - Varsome (GA4GH compliant): ~476 records
  - hg38 genomic: ~300 records
  - Descriptive only: ~88 records
- **HPO Term Coverage**: 73 unique phenotype terms
- **Variant Types**: SNV (60%), Deletion (25%), Duplication (10%), Indel (5%)

---

## Technical Challenges & Solutions

### Challenge 1: Database Constraint Violations
**Issue**: INSERT statement missing required `id` and `version` columns

**Solution**:
```sql
-- Fixed INSERT statement
INSERT INTO phenopackets
(id, phenopacket_id, version, phenopacket, created_by, schema_version)
VALUES (gen_random_uuid(), :phenopacket_id, :version, :phenopacket, :created_by, :schema_version)
```

### Challenge 2: BCrypt Version Compatibility
**Issue**: passlib 1.7.4 incompatible with bcrypt 4.x

**Solution**: Pin bcrypt to version 3.x in `pyproject.toml`:
```toml
"bcrypt>=3.2.0,<4.0.0",  # Pin to version 3.x for passlib compatibility
```

### Challenge 3: Variant Representation Standardization
**Issue**: Multiple variant formats in source data

**Solution**: Implemented priority-based parsing:
1. Parse Varsome format (GA4GH compliant)
2. Parse hg38 genomic coordinates
3. Fallback to descriptive text with warnings

---

## Validation & Testing

### Database Validation
```sql
-- Verify migration success
SELECT COUNT(*) as total,
       COUNT(DISTINCT id) as unique_ids,
       COUNT(version) as has_version
FROM phenopackets;

-- Check data structure
SELECT phenopacket_id,
       jsonb_array_length(phenopacket->'phenotypicFeatures') as features,
       phenopacket->'interpretations' IS NOT NULL as has_variants
FROM phenopackets LIMIT 10;
```

### API Testing
```bash
# Test phenopacket retrieval
curl http://localhost:8000/api/v2/phenopackets

# Test clinical queries
curl http://localhost:8000/api/v2/clinical/renal-insufficiency

# Test aggregations
curl http://localhost:8000/api/v2/phenopackets/aggregate/phenotypes
```

---

## Lessons Learned

### What Worked Well
1. **Direct migration approach** eliminated intermediate errors
2. **JSONB storage** provided flexibility for phenopacket structure
3. **GA4GH standards** ensured interoperability
4. **Hybrid ontology service** avoided large file dependencies
5. **Generated columns** optimized query performance

### Areas for Improvement
1. Implement comprehensive test suite
2. Add data validation before migration
3. Create rollback mechanism for failed migrations
4. Implement incremental migration support
5. Add migration progress monitoring

---

## Current System Status

### ✅ Completed
- Full GA4GH Phenopackets v2 implementation
- Direct Google Sheets to Phenopackets migration
- GA4GH VRS 2.0 compliant variant representation
- RESTful API with phenopackets structure
- JWT authentication system
- Hybrid ontology service
- Comprehensive documentation

### ⚠️ Pending
- Production deployment configuration
- Performance testing with concurrent users
- Backup and recovery procedures
- API rate limiting
- Monitoring and alerting setup

---

## File Structure

### Core Migration Files
```
/migration/
  └── direct_sheets_to_phenopackets.py  # Main migration script

/app/
  ├── main.py                           # FastAPI application
  ├── phenopackets/                      # Phenopackets endpoints
  │   ├── models.py                     # Data models
  │   ├── router.py                     # API routes
  │   └── validator.py                  # Validation logic
  └── services/
      └── ontology_service.py           # Hybrid ontology service
```

### Configuration
```
.env                                     # Environment variables
pyproject.toml                          # Python dependencies
Makefile                                # Development commands
docker-compose.services.yml             # Database services
```

---

## Appendix: Quick Reference

### Development Commands
```bash
make help               # Show all commands
make dev                # Install dependencies
make hybrid-up          # Start PostgreSQL + Redis
make server             # Start API server
make phenopackets-migrate      # Run migration
make check              # Run all quality checks
make hybrid-down        # Stop services
```

### Environment Variables
```bash
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets
JWT_SECRET=your-secret-key
USE_ONTOLOGY_APIS=true
ONTOLOGY_API_TIMEOUT=5
ONTOLOGY_CACHE_TTL_HOURS=24
```

### API Documentation
- Swagger UI: http://localhost:8000/api/v2/docs
- ReDoc: http://localhost:8000/api/v2/redoc

---

*This migration record documents the transformation of HNF1B clinical data to GA4GH Phenopackets v2 standard, completed in 2024.*