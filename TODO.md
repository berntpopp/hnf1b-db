# HNF1B-API MongoDB to PostgreSQL Migration TODO

This document breaks down the comprehensive migration plan from `refactor.md` into actionable tasks organized by implementation phases.

## 📋 **Phase 1: Infrastructure Setup**
*Estimated Time: 3-5 days*

### Docker & Environment Configuration
- [ ] **1.1.1** Create `docker-compose.services.yml` for PostgreSQL and Redis
  - [ ] Configure PostgreSQL 15-alpine with health checks
  - [ ] Use non-standard ports (5433 for PostgreSQL, 6380 for Redis)
  - [ ] Set up proper networking and volumes
  - [ ] Add environment variables for development

- [ ] **1.1.2** Update `pyproject.toml` dependencies
  - [ ] Remove `motor>=3.7.1` (MongoDB driver)
  - [ ] Add `sqlalchemy[asyncio]>=2.0.25`
  - [ ] Add `asyncpg>=0.29.0`
  - [ ] Add `alembic>=1.13.1`
  - [ ] Add `psycopg2-binary>=2.9.9` (for sync operations)

- [ ] **1.1.3** Create/update environment configuration
  - [ ] Add `DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db`
  - [ ] Remove MongoDB-specific environment variables
  - [ ] Update `.env.example` with new variables

- [ ] **1.1.4** Update Makefile with hybrid development commands
  - [ ] Add `hybrid-up` and `hybrid-down` targets
  - [ ] Add `db-migrate`, `db-upgrade`, `db-reset` targets
  - [ ] Add `migrate-data` target for data migration

### Database Connection Setup
- [ ] **1.2.1** Create new `app/database.py` with async SQLAlchemy
  - [ ] Configure `create_async_engine` with proper settings
  - [ ] Set up `async_sessionmaker` with `AsyncSession`
  - [ ] Create `DeclarativeBase` for models
  - [ ] Implement `get_db()` dependency for FastAPI

- [ ] **1.2.2** Initialize Alembic for migrations
  - [ ] Run `uv run alembic init alembic`
  - [ ] Configure `alembic.ini` with PostgreSQL connection
  - [ ] Update `alembic/env.py` for async support
  - [ ] Set up proper target_metadata import

---

## 📋 **Phase 2: Database Schema & Models**
*Estimated Time: 5-7 days*

### PostgreSQL Schema Design
- [ ] **2.1.1** Create initial migration with complete schema
  - [ ] Users table with constraints and indexes
  - [ ] Individuals table with relationships
  - [ ] Reports table (extracted from individuals)
  - [ ] Variants table with normalization
  - [ ] Individual-Variant relationship table
  - [ ] Variant classifications, annotations, reported entries
  - [ ] Publications table with authors relationship
  - [ ] Proteins and genes tables
  - [ ] All necessary indexes for performance

- [ ] **2.1.2** Implement backward compatibility fields
  - [ ] Add `mongo_id` VARCHAR(24) to all tables
  - [ ] Ensure unique constraints on mongo_id fields
  - [ ] Add proper JSONB fields for complex data

### SQLAlchemy Models
- [ ] **2.2.1** Create base model classes in `app/models.py`
  - [ ] `User` model with relationships
  - [ ] `Individual` model with proper mappings
  - [ ] `Report` model with JSONB phenotypes field
  - [ ] `Variant` model with classification/annotation relationships
  - [ ] `Publication` model with authors relationship
  - [ ] `Protein` and `Gene` models with JSONB features

- [ ] **2.2.2** Update Pydantic schemas in `app/schemas.py`
  - [ ] Create response/request schemas for all models
  - [ ] Ensure `from_attributes=True` for ORM compatibility
  - [ ] Handle JSONB fields properly in schemas
  - [ ] Maintain API compatibility with existing endpoints

### Repository Pattern Implementation  
- [ ] **2.3.1** Create base repository in `app/repositories/base.py`
  - [ ] Generic `BaseRepository[T]` class
  - [ ] Standard CRUD operations (create, get, update, delete)
  - [ ] Pagination and filtering support
  - [ ] Async session management

- [ ] **2.3.2** Implement specific repositories
  - [ ] `UserRepository` with authentication methods
  - [ ] `IndividualRepository` with report loading
  - [ ] `ReportRepository` with phenotype search
  - [ ] `VariantRepository` with classification methods
  - [ ] `PublicationRepository` with author handling
  - [ ] `ProteinRepository` and `GeneRepository`

---

## 📋 **Phase 3: API Layer Migration**
*Estimated Time: 4-6 days*

### Endpoint Updates
- [ ] **3.1.1** Update `app/endpoints/individuals.py`
  - [ ] Replace MongoDB queries with repository calls
  - [ ] Implement search functionality with PostgreSQL
  - [ ] Handle complex filtering and pagination
  - [ ] Maintain existing API response format

- [ ] **3.1.2** Update `app/endpoints/variants.py`
  - [ ] Migrate variant queries to PostgreSQL
  - [ ] Handle classification and annotation relationships
  - [ ] Implement variant search across related tables
  - [ ] Preserve existing filtering capabilities

- [ ] **3.1.3** Update `app/endpoints/publications.py`
  - [ ] Convert to repository-based queries
  - [ ] Handle author relationships properly
  - [ ] Maintain publication search functionality
  - [ ] Preserve metadata handling

- [ ] **3.1.4** Update remaining endpoints
  - [ ] `app/endpoints/proteins.py` - protein feature queries
  - [ ] `app/endpoints/genes.py` - gene structure queries  
  - [ ] `app/endpoints/search.py` - cross-table search
  - [ ] `app/endpoints/aggregations.py` - statistical queries
  - [ ] `app/endpoints/auth.py` - user authentication

### Utility Functions
- [ ] **3.2.1** Update `app/utils.py` for PostgreSQL
  - [ ] Modify pagination helpers for SQLAlchemy
  - [ ] Update filter parsing for PostgreSQL queries
  - [ ] Adapt sorting functionality
  - [ ] Preserve existing utility interfaces

---

## 📋 **Phase 4: Data Migration Scripts**
*Estimated Time: 4-6 days*

### MongoDB to PostgreSQL Migration
- [ ] **4.1.1** Create `migrate_mongo_to_postgres.py`
  - [ ] Set up connections to both MongoDB and PostgreSQL
  - [ ] Implement `DataMigrator` class with async methods
  - [ ] Create migration methods for each collection
  - [ ] Handle relationship mapping between systems
  - [ ] Add comprehensive error handling and logging

- [ ] **4.1.2** Implement specific migration methods
  - [ ] `migrate_users()` - direct mapping
  - [ ] `migrate_publications()` - with authors extraction
  - [ ] `migrate_individuals_and_reports()` - normalize embedded reports
  - [ ] `migrate_variants()` - handle classifications/annotations
  - [ ] `migrate_proteins()` and `migrate_genes()` - JSONB features
  - [ ] Verification and rollback procedures

### PostgreSQL-Native Sheets Import
- [ ] **4.2.1** Create `migrate_from_sheets_pg.py`
  - [ ] Copy all utility functions from existing `migrate_from_sheets.py`
  - [ ] Preserve Google Sheets integration (same spreadsheet IDs)
  - [ ] Maintain PubMed enrichment with Bio.Entrez
  - [ ] Keep VEP/VCF/CADD file processing logic

- [ ] **4.2.2** Implement PostgreSQL import methods
  - [ ] `import_users()` - sheet to PostgreSQL via repositories
  - [ ] `import_publications()` - with PubMed enrichment
  - [ ] `import_individuals_with_reports()` - complex phenotype processing
  - [ ] `import_variants()` - genomic file integration
  - [ ] `import_proteins()` and `import_genes()` - Ensembl API
  - [ ] Preserve all phenotype mapping logic

- [ ] **4.2.3** Maintain complex business logic
  - [ ] Phenotype and modifier mappings from separate sheets
  - [ ] Special renal insufficiency staging logic
  - [ ] VEP annotation processing with NM_000458.4 filtering
  - [ ] CADD score integration
  - [ ] Ensembl protein feature and gene structure fetching
  - [ ] All existing error handling and validation

---

## 📋 **Phase 5: Testing & Validation**
*Estimated Time: 3-5 days*

### Test Infrastructure
- [ ] **5.1.1** Set up async testing framework
  - [ ] Create `tests/conftest.py` with async fixtures
  - [ ] Configure test database with proper isolation
  - [ ] Set up repository mocking for unit tests
  - [ ] Create test data factories

- [ ] **5.1.2** Database test utilities
  - [ ] Async engine and session fixtures
  - [ ] Database cleanup between tests
  - [ ] Migration testing utilities
  - [ ] Test data seeding functions

### Migration Testing
- [ ] **5.2.1** Create migration validation tests
  - [ ] Test MongoDB to PostgreSQL data migration
  - [ ] Verify data integrity and completeness
  - [ ] Test relationship mappings
  - [ ] Validate JSONB data structure preservation

- [ ] **5.2.2** API compatibility tests  
  - [ ] Test all existing endpoints maintain same responses
  - [ ] Verify search functionality works correctly
  - [ ] Test pagination and filtering
  - [ ] Ensure performance meets requirements

### Sheets Import Testing
- [ ] **5.3.1** Test PostgreSQL sheets import
  - [ ] Verify phenotype mapping works correctly
  - [ ] Test PubMed enrichment integration
  - [ ] Validate VEP/VCF processing
  - [ ] Test Ensembl API integration
  - [ ] Verify complex business logic preservation

---

## 📋 **Phase 6: Documentation & Deployment**
*Estimated Time: 2-3 days*

### Documentation Updates
- [ ] **6.1.1** Update `CLAUDE.md` with new commands
  - [ ] Add hybrid development workflow
  - [ ] Document migration commands
  - [ ] Update database setup instructions
  - [ ] Add troubleshooting guide

- [ ] **6.1.2** Update `README.md`
  - [ ] Change database requirements to PostgreSQL
  - [ ] Update installation instructions
  - [ ] Modify environment variable documentation
  - [ ] Update API documentation links

### Final Validation
- [ ] **6.2.1** End-to-end testing
  - [ ] Full migration test with production-like data
  - [ ] Performance benchmarking
  - [ ] Memory usage analysis
  - [ ] API response time validation

- [ ] **6.2.2** Production readiness
  - [ ] Security review of PostgreSQL configuration
  - [ ] Backup and recovery procedures
  - [ ] Monitoring and logging setup
  - [ ] Deployment scripts and documentation

---

## 📋 **Phase 7: Migration Execution & Cutover**
*Estimated Time: 1-2 days*

### Pre-Migration Checklist
- [ ] **7.1.1** Environment preparation
  - [ ] Backup existing MongoDB database
  - [ ] Set up PostgreSQL production instance
  - [ ] Configure monitoring and alerting
  - [ ] Prepare rollback procedures

### Migration Execution
- [ ] **7.2.1** Data migration
  - [ ] Run migration scripts with production data
  - [ ] Validate data integrity
  - [ ] Performance testing with real data
  - [ ] User acceptance testing

- [ ] **7.2.2** Deployment and cutover
  - [ ] Deploy new PostgreSQL-based application
  - [ ] Update environment configurations
  - [ ] Monitor application performance
  - [ ] Verify all functionality works correctly

---

## 🎯 **Success Criteria**

### Functional Requirements
- [ ] All existing API endpoints work identically
- [ ] All search and filtering functionality preserved
- [ ] Complex phenotype processing works correctly
- [ ] VEP/VCF genomic data processing functional
- [ ] PubMed integration and Ensembl API calls work
- [ ] Data integrity maintained across migration

### Performance Requirements
- [ ] API response times <= existing MongoDB performance
- [ ] Database queries optimized with proper indexing
- [ ] Memory usage within acceptable limits
- [ ] Concurrent user support maintained

### Data Quality Requirements
- [ ] Zero data loss during migration
- [ ] All relationships properly maintained
- [ ] JSONB data structure preserved and queryable
- [ ] Historical data accessible and searchable

---

## 🚨 **Risk Mitigation**

### High Priority Risks
- [ ] **Data Loss**: Comprehensive backup and validation procedures
- [ ] **Downtime**: Prepare rollback procedures and staging environment
- [ ] **Performance Issues**: Extensive testing with production-like data
- [ ] **Complex Query Migration**: Test all MongoDB aggregations thoroughly

### Rollback Plan
- [ ] Keep MongoDB instance running during initial deployment
- [ ] Maintain ability to switch back to MongoDB quickly
- [ ] Document rollback procedures step-by-step
- [ ] Test rollback procedures in staging environment

---

## 📊 **Timeline Summary**

| Phase | Description | Duration | Dependencies |
|-------|-------------|----------|--------------|
| 1 | Infrastructure Setup | 3-5 days | - |
| 2 | Database Schema & Models | 5-7 days | Phase 1 |
| 3 | API Layer Migration | 4-6 days | Phase 2 |
| 4 | Data Migration Scripts | 4-6 days | Phase 2 |
| 5 | Testing & Validation | 3-5 days | Phases 3,4 |
| 6 | Documentation & Deployment | 2-3 days | Phase 5 |
| 7 | Migration Execution | 1-2 days | All phases |

**Total Estimated Duration: 4-6 weeks**

---

## 🔧 **Development Commands Quick Reference**

```bash
# Start hybrid development
make hybrid-up
make server

# Database operations
make db-migrate MESSAGE="description"
make db-upgrade
make db-reset

# Data migration (choose one)
uv run python migrate_mongo_to_postgres.py       # From existing MongoDB
uv run python migrate_from_sheets_pg.py          # Fresh PostgreSQL import

# Stop development
make hybrid-down
```

## ✅ **Completion Checklist**

- [ ] All TODO items completed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Migration validated
- [ ] Performance verified
- [ ] Ready for production deployment