# HNF1B-API PostgreSQL Implementation Plan

This document provides a comprehensive implementation plan for the HNF1B-API PostgreSQL backend with Google Sheets as the primary data source.

## Executive Summary

**Goal**: Implement a clean PostgreSQL backend for HNF1B-API with Google Sheets integration, maintaining all existing functionality while improving data integrity and enabling better relational queries.

**Approach**: Dockerized PostgreSQL for development with local FastAPI hot-reload (hybrid development), following patterns from agde-api and kidney-genetics-db.

**Key Benefits**:
- ACID compliance and referential integrity
- Better query performance for relational data
- Standard SQL support and tooling
- Docker containerization for consistent dev environment
- Async PostgreSQL support with SQLAlchemy 2.0+
- Direct Google Sheets integration as primary data source

## Data Source Architecture

### Primary Data Source: Google Sheets
The system uses Google Sheets as the authoritative data source for all clinical, genetic, and publication data. The PostgreSQL database serves as a structured, queryable representation of this data.

**Google Sheets Structure**:
1. **Users Sheet** - System users and reviewers
2. **Individuals Sheet** - Patient demographics and clinical data
3. **Reports Sheet** - Clinical presentations with phenotype data
4. **Variants Sheet** - Genetic variant information
5. **Publications Sheet** - Research papers and references
6. **Proteins Sheet** - Protein structure and domain data
7. **Genes Sheet** - Gene structure and coordinate data

## PostgreSQL Schema Design

### Core Principles
- **Clean normalization** with proper foreign key relationships
- **Use PostgreSQL JSONB** for complex nested data (phenotypes, features, coordinates)
- **Implement proper constraints** and indexes for performance
- **Support async operations** with SQLAlchemy 2.0+
- **UUID primary keys** for better distributed system compatibility

### PostgreSQL Table Structure

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER UNIQUE NOT NULL,
    user_name VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    user_role VARCHAR(50) NOT NULL,
    first_name VARCHAR(100),
    family_name VARCHAR(100),
    orcid VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individuals table (main entity)
CREATE TABLE individuals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id VARCHAR(20) UNIQUE NOT NULL,
    sex VARCHAR(10),
    individual_doi VARCHAR(100),
    dup_check VARCHAR(50),
    individual_identifier VARCHAR(100),
    problematic VARCHAR(500) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reports table (clinical presentations)
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id VARCHAR(20) NOT NULL,
    individual_id UUID NOT NULL REFERENCES individuals(id) ON DELETE CASCADE,
    reviewed_by UUID REFERENCES users(id),
    publication_ref UUID REFERENCES publications(id),
    phenotypes JSONB DEFAULT '{}',
    review_date TIMESTAMPTZ,
    report_date TIMESTAMPTZ,
    comment TEXT,
    family_history TEXT,
    age_reported VARCHAR(50),
    age_onset VARCHAR(50),
    cohort VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Variants table
CREATE TABLE variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id VARCHAR(20) UNIQUE NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual-Variant relationship table (many-to-many)
CREATE TABLE individual_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id UUID NOT NULL REFERENCES individuals(id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    detection_method VARCHAR(100),
    segregation VARCHAR(100),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Variant classifications
CREATE TABLE variant_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    verdict VARCHAR(100),
    criteria TEXT,
    comment TEXT,
    system VARCHAR(50),
    classification_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Variant annotations
CREATE TABLE variant_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    transcript VARCHAR(100),
    c_dot TEXT,
    p_dot TEXT,
    source VARCHAR(50),
    annotation_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reported entries
CREATE TABLE reported_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    publication_ref UUID REFERENCES publications(id),
    variant_reported TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Publications table
CREATE TABLE publications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignee_id UUID REFERENCES users(id),
    publication_id VARCHAR(20) UNIQUE NOT NULL,
    publication_alias VARCHAR(100),
    publication_type VARCHAR(50),
    publication_entry_date TIMESTAMPTZ DEFAULT '2021-11-01',
    pmid INTEGER,
    doi VARCHAR(200),
    pdf VARCHAR(500),
    title TEXT,
    abstract TEXT,
    publication_date TIMESTAMPTZ,
    journal_abbreviation VARCHAR(100),
    journal VARCHAR(200),
    keywords JSONB DEFAULT '[]',
    medical_specialty JSONB DEFAULT '[]',
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Authors table (normalized from publications)
CREATE TABLE authors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id UUID NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    lastname VARCHAR(100),
    firstname VARCHAR(100),
    initials VARCHAR(20),
    affiliations JSONB DEFAULT '[]',
    author_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Proteins table
CREATE TABLE proteins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gene VARCHAR(50) NOT NULL,
    transcript VARCHAR(50),
    protein VARCHAR(50),
    features JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Genes table
CREATE TABLE genes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gene_symbol VARCHAR(50) NOT NULL,
    ensembl_gene_id VARCHAR(50) UNIQUE NOT NULL,
    transcript VARCHAR(50),
    exons JSONB DEFAULT '[]',
    hg38 JSONB DEFAULT '{}',
    hg19 JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Indexes for Performance

```sql
-- Core lookup indexes
CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_user_name ON users(user_name);
CREATE INDEX idx_users_email ON users(email);

CREATE INDEX idx_individuals_individual_id ON individuals(individual_id);
CREATE INDEX idx_reports_report_id ON reports(report_id);
CREATE INDEX idx_reports_individual_id ON reports(individual_id);

CREATE INDEX idx_variants_variant_id ON variants(variant_id);
CREATE INDEX idx_variants_is_current ON variants(is_current);

CREATE INDEX idx_publications_publication_id ON publications(publication_id);
CREATE INDEX idx_publications_pmid ON publications(pmid);

CREATE INDEX idx_genes_gene_symbol ON genes(gene_symbol);
CREATE INDEX idx_genes_ensembl_gene_id ON genes(ensembl_gene_id);

CREATE INDEX idx_proteins_gene ON proteins(gene);
CREATE INDEX idx_proteins_protein ON proteins(protein);

-- JSONB indexes for complex queries
CREATE INDEX idx_reports_phenotypes ON reports USING GIN(phenotypes);
CREATE INDEX idx_publications_keywords ON publications USING GIN(keywords);
CREATE INDEX idx_proteins_features ON proteins USING GIN(features);
CREATE INDEX idx_genes_exons ON genes USING GIN(exons);
```

## Implementation Architecture

### SQLAlchemy Models with Repository Pattern

**Core Components**:
1. **app/database.py** - Async PostgreSQL engine and session management
2. **app/models.py** - SQLAlchemy ORM models with relationships
3. **app/repositories/** - Repository pattern for data access abstraction
4. **app/schemas.py** - Pydantic models for API responses
5. **app/endpoints/** - FastAPI endpoints using dependency injection

### Google Sheets Integration

**Import Strategy**:
1. **authenticate_sheets()** - Google Sheets API authentication
2. **fetch_sheet_data()** - Retrieve data from specific sheets
3. **process_phenotypes()** - Complex phenotype mapping and validation
4. **enrich_publications()** - PubMed API integration for metadata
5. **process_variants()** - VEP/VCF file integration with genomic annotations
6. **import_all_data()** - Orchestrated import with proper dependency ordering

## Development Environment

### Docker Configuration

**docker-compose.services.yml**:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    container_name: hnf1b-postgres
    environment:
      POSTGRES_DB: hnf1b_db
      POSTGRES_USER: hnf1b_user
      POSTGRES_PASSWORD: hnf1b_pass
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hnf1b_user -d hnf1b_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: hnf1b-redis
    ports:
      - "6380:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### Hybrid Development Workflow

```bash
# Start PostgreSQL and Redis services
make hybrid-up

# Run FastAPI with hot-reload (local)
make server

# Import data from Google Sheets
uv run python import_from_sheets.py

# Database migrations
make db-migrate MESSAGE="description"
make db-upgrade

# Stop services
make hybrid-down
```

## API Implementation Status

**Completed Endpoints**:
- ✅ `/api/individuals` - Fully migrated to PostgreSQL with repository pattern

**Pending Migration**:
- `/api/variants` - Genetic variant queries with classifications/annotations
- `/api/publications` - Publication search with author relationships
- `/api/proteins` - Protein feature and domain queries
- `/api/genes` - Gene structure and coordinate queries
- `/api/search` - Cross-collection search functionality
- `/api/aggregations` - Statistical queries and data summaries
- `/api/auth` - User authentication with PostgreSQL user repository

## Data Import Process

### Google Sheets to PostgreSQL Pipeline

1. **Sheet Authentication** - Service account credentials for Google Sheets API
2. **Data Validation** - Pydantic models ensure data consistency
3. **Phenotype Processing** - Complex mapping from separate phenotype/modifier sheets
4. **External API Integration** - PubMed, VEP, Ensembl API calls for enrichment
5. **Relationship Building** - Foreign key relationships established during import
6. **Error Handling** - Comprehensive logging and rollback on failures

### Performance Considerations

- **Batch Processing** - Import data in batches for memory efficiency
- **Index Creation** - Indexes created after bulk import for speed
- **Connection Pooling** - Async connection pool for concurrent operations
- **JSONB Optimization** - Proper JSONB indexes for nested data queries

## Success Criteria

### Functional Requirements
- All existing API endpoints work identically
- All search and filtering functionality preserved
- Complex phenotype processing works correctly
- VEP/VCF genomic data processing functional
- PubMed integration and Ensembl API calls work
- Data integrity maintained across all operations

### Performance Requirements
- API response times meet production requirements
- Database queries optimized with proper indexing
- Memory usage within acceptable limits
- Concurrent user support maintained

### Data Quality Requirements
- Zero data loss during sheets import
- All relationships properly maintained
- JSONB data structure preserved and queryable
- All data accessible and searchable through APIs

## Deployment Strategy

### Production Readiness
1. **Security Review** - PostgreSQL configuration hardening
2. **Backup Procedures** - Automated backup and recovery systems  
3. **Monitoring Setup** - Application and database performance monitoring
4. **Documentation** - Complete API documentation and deployment guides

### Migration Process
1. **Google Sheets Preparation** - Ensure all source sheets are current and accessible
2. **PostgreSQL Setup** - Production database instance configuration
3. **Data Import Validation** - Full import test with data integrity verification
4. **Performance Testing** - Load testing with production-like data volumes
5. **Go-Live** - Coordinated deployment with rollback procedures ready