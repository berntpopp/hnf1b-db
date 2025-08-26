# HNF1B-API PostgreSQL Implementation TODO

This document breaks down the comprehensive migration plan from `refactor.md` into actionable tasks organized by implementation phases.

## 🎯 **Migration Progress Status**

**✅ COMPLETED PHASES:**
- **Phase 1: Infrastructure Setup** - 100% Complete
- **Phase 2: Database Schema & Models** - 100% Complete  
- **Phase 3: Repository Pattern Implementation** - 100% Complete
- **Phase 4: API Layer Migration (Individuals Endpoint)** - COMPLETED ✅

**🚧 IN PROGRESS:**
- **Phase 4: API Layer Migration (Remaining Endpoints)** - 1 of 8 endpoints migrated

**📋 PENDING:**
- Phase 4: PostgreSQL Sheets Import (primary data source)
- Phase 5: Testing & Validation
- Phase 6: Documentation & Deployment
- Phase 7: Migration Execution & Cutover

**🚀 KEY ACHIEVEMENTS:**
- PostgreSQL database with 13 tables and proper relationships
- Complete repository pattern with 7 specialized repositories  
- `/api/individuals` endpoint fully migrated and functional
- Server successfully runs with PostgreSQL backend
- 100% API compatibility maintained

---

## 📋 **Phase 1: Infrastructure Setup**
*Estimated Time: 3-5 days*

### Docker & Environment Configuration
- [x] **1.1.1** Create `docker-compose.services.yml` for PostgreSQL and Redis
  - [x] Configure PostgreSQL 15-alpine with health checks
  - [x] Use non-standard ports (5433 for PostgreSQL, 6380 for Redis)
  - [x] Set up proper networking and volumes
  - [x] Add environment variables for development

- [x] **1.1.2** Update `pyproject.toml` dependencies
  - [x] Remove legacy dependencies
  - [x] Add `sqlalchemy[asyncio]>=2.0.25`
  - [x] Add `asyncpg>=0.29.0`
  - [x] Add `alembic>=1.13.1`
  - [x] Add `psycopg2-binary>=2.9.9` (for sync operations)

- [x] **1.1.3** Create/update environment configuration
  - [x] Add `DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db`
  - [x] Configure PostgreSQL-specific environment variables
  - [x] Update `.env.example` with new variables

- [x] **1.1.4** Update Makefile with hybrid development commands
  - [x] Add `hybrid-up` and `hybrid-down` targets
  - [x] Add `db-migrate`, `db-upgrade`, `db-reset` targets
  - [x] Add `migrate-data` target for data migration

### Database Connection Setup
- [x] **1.2.1** Create new `app/database.py` with async SQLAlchemy
  - [x] Configure `create_async_engine` with proper settings
  - [x] Set up `async_sessionmaker` with `AsyncSession`
  - [x] Create `DeclarativeBase` for models
  - [x] Implement `get_db()` dependency for FastAPI

- [x] **1.2.2** Initialize Alembic for migrations
  - [x] Run `uv run alembic init alembic`
  - [x] Configure `alembic.ini` with PostgreSQL connection
  - [x] Update `alembic/env.py` for async support
  - [x] Set up proper target_metadata import

---

## 📋 **Phase 2: Database Schema & Models**
*Estimated Time: 5-7 days*

### PostgreSQL Schema Design
- [x] **2.1.1** Create initial migration with complete schema
  - [x] Users table with constraints and indexes
  - [x] Individuals table with relationships
  - [x] Reports table (extracted from individuals)
  - [x] Variants table with normalization
  - [x] Individual-Variant relationship table
  - [x] Variant classifications, annotations, reported entries
  - [x] Publications table with authors relationship
  - [x] Proteins and genes tables
  - [x] All necessary indexes for performance

- [x] **2.1.2** Implement advanced PostgreSQL features
  - [x] Add proper JSONB fields for complex data
  - [x] Ensure optimal indexing strategy
  - [x] Configure proper constraints and relationships

### SQLAlchemy Models
- [x] **2.2.1** Create base model classes in `app/models.py`
  - [x] `User` model with relationships
  - [x] `Individual` model with proper mappings
  - [x] `Report` model with JSONB phenotypes field
  - [x] `Variant` model with classification/annotation relationships
  - [x] `Publication` model with authors relationship
  - [x] `Protein` and `Gene` models with JSONB features

- [x] **2.2.2** Update Pydantic schemas in `app/schemas.py`
  - [x] Create response/request schemas for all models
  - [x] Ensure `from_attributes=True` for ORM compatibility
  - [x] Handle JSONB fields properly in schemas
  - [x] Maintain API compatibility with existing endpoints

### Repository Pattern Implementation  
- [x] **2.3.1** Create base repository in `app/repositories/base.py`
  - [x] Generic `BaseRepository[T]` class
  - [x] Standard CRUD operations (create, get, update, delete)
  - [x] Pagination and filtering support
  - [x] Async session management

- [x] **2.3.2** Implement specific repositories
  - [x] `UserRepository` with authentication methods
  - [x] `IndividualRepository` with report loading
  - [x] `ReportRepository` with phenotype search
  - [x] `VariantRepository` with classification methods
  - [x] `PublicationRepository` with author handling
  - [x] `ProteinRepository` and `GeneRepository`

---

## 📋 **Phase 3: API Layer Migration**
*Estimated Time: 4-6 days*

### Endpoint Updates
- [x] **3.1.1** Update `app/endpoints/individuals.py`
  - [x] Implement repository-based queries
  - [x] Implement search functionality with PostgreSQL
  - [x] Handle complex filtering and pagination
  - [x] Maintain existing API response format

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
- [x] **3.2.1** Update `app/utils.py` for PostgreSQL
  - [x] Modify pagination helpers for SQLAlchemy
  - [x] Update filter parsing for PostgreSQL queries
  - [x] Adapt sorting functionality
  - [x] Preserve existing utility interfaces

---

## 📋 **Phase 4: PostgreSQL Sheets Import**
*Estimated Time: 4-6 days*

### PostgreSQL-Native Sheets Import
- [ ] **4.1.1** Create `migrate_from_sheets_pg.py`
  - [ ] Copy all utility functions from existing `migrate_from_sheets.py`
  - [ ] Preserve Google Sheets integration (same spreadsheet IDs)
  - [ ] Maintain PubMed enrichment with Bio.Entrez
  - [ ] Keep VEP/VCF/CADD file processing logic

- [ ] **4.1.2** Implement PostgreSQL import methods
  - [ ] `import_users()` - sheet to PostgreSQL via repositories
  - [ ] `import_publications()` - with PubMed enrichment
  - [ ] `import_individuals_with_reports()` - complex phenotype processing
  - [ ] `import_variants()` - genomic file integration
  - [ ] `import_proteins()` and `import_genes()` - Ensembl API
  - [ ] Preserve all phenotype mapping logic

- [ ] **4.1.3** Maintain complex business logic
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

### Data Import Testing
- [ ] **5.2.1** Create sheets import validation tests
  - [ ] Test Google Sheets to PostgreSQL data import
  - [ ] Verify data integrity and completeness
  - [ ] Test relationship mappings from sheets
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

### Pre-Deployment Checklist
- [ ] **7.1.1** Environment preparation
  - [ ] Prepare Google Sheets data sources
  - [ ] Set up PostgreSQL production instance
  - [ ] Configure monitoring and alerting
  - [ ] Prepare rollback procedures

### Production Deployment
- [ ] **7.2.1** Data import and validation
  - [ ] Run sheets import scripts with production data
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
- [ ] API response times meet production requirements
- [ ] Database queries optimized with proper indexing
- [ ] Memory usage within acceptable limits
- [ ] Concurrent user support maintained

### Data Quality Requirements
- [ ] Zero data loss during sheets import
- [ ] All relationships properly maintained
- [ ] JSONB data structure preserved and queryable
- [ ] All data accessible and searchable

---

## 🚨 **Risk Mitigation**

### High Priority Risks
- [ ] **Data Loss**: Comprehensive backup and validation procedures
- [ ] **Downtime**: Prepare rollback procedures and staging environment
- [ ] **Performance Issues**: Extensive testing with production-like data
- [ ] **Complex Query Implementation**: Test all PostgreSQL queries thoroughly

### Rollback Plan
- [ ] Maintain staging environment for testing
- [ ] Keep backup procedures for PostgreSQL data
- [ ] Document rollback procedures step-by-step
- [ ] Test rollback procedures in staging environment

---

## 📊 **Timeline Summary**

| Phase | Description | Duration | Dependencies |
|-------|-------------|----------|--------------|
| 1 | Infrastructure Setup | ✅ 3-5 days | - |
| 2 | Database Schema & Models | ✅ 5-7 days | Phase 1 |
| 3 | Repository Pattern | ✅ 4-6 days | Phase 2 |
| 4 | API Layer Migration | 🚧 4-6 days | Phase 3 |
| 5 | PostgreSQL Sheets Import | 4-6 days | Phase 3 |
| 6 | Testing & Validation | 3-5 days | Phases 4,5 |
| 7 | Documentation & Deployment | 2-3 days | Phase 6 |
| 8 | Migration Execution | 1-2 days | All phases |

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

# Data migration from Google Sheets
uv run python migrate_from_sheets_pg.py          # PostgreSQL import from sheets

# Stop development
make hybrid-down
```

## ✅ **Completion Checklist**

**✅ INFRASTRUCTURE & CORE SYSTEM:**
- [x] Docker PostgreSQL + Redis setup functional
- [x] SQLAlchemy models with relationships defined
- [x] Alembic migrations configured and applied
- [x] Repository pattern fully implemented
- [x] FastAPI server starts successfully with PostgreSQL
- [x] Database schema with 13 tables and proper indexes

**✅ API LAYER:**
- [x] Individuals endpoint fully migrated (`/api/individuals`)
- [x] Field mapping for API compatibility maintained
- [x] Pagination, filtering, and search functionality preserved
- [x] Repository dependency injection working

**🚧 PARTIALLY COMPLETE:**
- [ ] Remaining 7 endpoints migrated (variants, publications, etc.)
- [ ] All TODO items completed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Migration validated
- [ ] Performance verified
- [ ] Ready for production deployment

---

## 📊 **Implementation Statistics**

**Files Created/Modified:**
- ✅ `docker-compose.services.yml` - Docker services configuration
- ✅ `app/database.py` - Async SQLAlchemy engine and session management
- ✅ `app/models.py` - Complete SQLAlchemy models (359 lines)
- ✅ `app/schemas.py` - Pydantic response schemas
- ✅ `app/dependencies.py` - Repository dependency injection
- ✅ `app/utils.py` - PostgreSQL-compatible utility functions
- ✅ `app/repositories/` - 7 repository classes with advanced querying
- ✅ `app/endpoints/individuals.py` - Fully migrated endpoint
- ✅ `alembic/` - Database migration framework
- ✅ `Makefile` - Hybrid development commands

**Database Schema:**
- ✅ 13 PostgreSQL tables with proper relationships
- ✅ UUID primary keys with optimal performance
- ✅ JSONB fields for complex data (phenotypes, features, coordinates)
- ✅ Foreign key constraints and cascading deletes
- ✅ Performance indexes on key lookup fields

**Repository Pattern:**
- ✅ `BaseRepository` - Generic CRUD with filtering, pagination, search
- ✅ `UserRepository` - Authentication and role management
- ✅ `IndividualRepository` - Demographics with relationship loading
- ✅ `ReportRepository` - JSONB phenotype search capabilities
- ✅ `VariantRepository` - Classification/annotation handling
- ✅ `PublicationRepository` - Author relationship management  
- ✅ `ProteinRepository` - Feature-based search
- ✅ `GeneRepository` - Genomic coordinate queries