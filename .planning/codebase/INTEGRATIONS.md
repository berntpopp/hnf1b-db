# External Integrations

**Analysis Date:** 2026-01-19

## APIs & External Services

### Ensembl VEP (Variant Effect Predictor)

**Purpose:** Variant annotation with consequence predictions, CADD scores, gnomAD frequencies

**Configuration (`backend/config.yaml`):**
```yaml
external_apis:
  vep:
    base_url: "https://rest.ensembl.org"
    timeout_seconds: 30
    max_retries: 3
    retry_backoff_factor: 2.0
    batch_size: 50
    cache_enabled: true
    cache_size_limit: 1000
    cache_ttl_seconds: 86400
```

**Implementation:**
- Client: `backend/app/variants/service.py`
- HTTP: `httpx` async client
- Rate limit: 15 req/sec (configurable)
- Storage: Permanent database caching in `variant_annotation_cache` table

**Endpoints Used:**
- `POST /vep/human/hgvs` - HGVS notation annotation
- `POST /vep/human/region` - VCF-style annotation

### PubMed E-Utilities

**Purpose:** Publication metadata fetching (title, authors, year, DOI, abstract)

**Configuration (`backend/config.yaml`):**
```yaml
external_apis:
  pubmed:
    base_url: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    timeout_seconds: 5
    version: "2.0"
```

**Implementation:**
- Client: `backend/app/publications/service.py`
- HTTP: `aiohttp` async client
- Rate limit: 3 req/sec (without API key), 10 req/sec (with key)
- Storage: Permanent database caching in `publication_metadata` table

**Environment:**
```bash
PUBMED_API_KEY=<optional-ncbi-api-key>  # Increases rate limit
```

### HPO JAX API

**Purpose:** Human Phenotype Ontology term lookup and validation

**Implementation:**
- Client: `backend/app/services/ontology_service.py` (HPOAPIClient)
- Base URL: `https://hpo.jax.org/api/hpo`
- HTTP: `requests` sync client
- Fallback: Local hardcoded mappings in `migration/phenopackets/hpo_mapper.py`

**Endpoints Used:**
- `GET /term/{hpo_id}` - Get term details

### EBI Ontology Lookup Service (OLS)

**Purpose:** Ontology term autocomplete and lookup (HPO, MONDO, etc.)

**Configuration (`backend/config.yaml`):**
```yaml
external_apis:
  ols:
    base_url: "https://www.ebi.ac.uk/ols4/api"
    timeout_seconds: 10
    cache_size_limit: 100
    cache_ttl_seconds: 3600
```

**Implementation:**
- Client: `backend/app/services/ontology_service.py` (OLSAPIClient)
- Provides fallback when HPO JAX API fails

### Ensembl REST API (Reference Data)

**Purpose:** Gene, transcript, and exon coordinates for chr17q12 region

**Implementation:**
- Client: `backend/app/reference/service.py`
- Base URL: `https://rest.ensembl.org`
- HTTP: `httpx` async client
- Rate limit: 10 req/sec (0.1s delay between requests)

**Endpoints Used:**
- `GET /overlap/region/human/{region}?feature=gene` - Genes in region
- `GET /lookup/id/{gene_id}?expand=1` - Gene details with transcripts

### Google Sheets (Data Source)

**Purpose:** Source data for phenopacket migration

**Implementation:**
- Module: `backend/migration/direct_sheets_to_phenopackets.py`
- Reads from public Google Sheets export URLs
- One-time import, not a runtime integration

## Data Storage

### PostgreSQL Database

**Type:** PostgreSQL 15-alpine

**Connection:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/db
```

**Configuration (`backend/config.yaml`):**
```yaml
database:
  pool_size: 20
  max_overflow: 0
  pool_recycle_seconds: 3600
  command_timeout_seconds: 60
  pool_pre_ping: true
```

**Implementation:**
- ORM: SQLAlchemy 2.0 async (`backend/app/database.py`)
- Driver: asyncpg
- Migrations: Alembic (`backend/alembic/`)

**Key Tables:**
- `phenopackets` - Main data with JSONB storage
- `publication_metadata` - Cached PubMed data
- `variant_annotation_cache` - Cached VEP annotations
- `reference_genomes`, `genes`, `transcripts`, `exons`, `protein_domains` - Reference data
- `users` - Authentication
- `audit_log` - Change tracking
- `mv_*` - Materialized views for aggregations

### Redis Cache

**Type:** Redis 7-alpine

**Connection:**
```bash
REDIS_URL=redis://localhost:6379/0
```

**Configuration:**
```yaml
# Docker compose settings
maxmemory: 256mb
maxmemory-policy: allkeys-lru
appendonly: yes
```

**Purpose:**
- Rate limiting state
- Session caching (potential)
- API response caching (potential)

**Implementation:**
- Client: `redis` Python package
- Currently used primarily for rate limiting middleware

### File Storage

**Approach:** Local filesystem only (no cloud storage)

**Generated Files:**
- `backend/migration/output/` - Migration dry-run output (JSON)
- `frontend/dist/` - Built frontend assets
- `frontend/dist/bundle-analysis.html` - Build analysis

## Authentication & Identity

### Custom JWT Authentication

**Implementation:**
- Module: `backend/app/auth/` (endpoints, dependencies)
- Token Generation: PyJWT
- Password Hashing: passlib with bcrypt
- Storage: `users` table in PostgreSQL

**Configuration (`backend/config.yaml`):**
```yaml
security:
  jwt_algorithm: "HS256"
  access_token_expire_minutes: 30
  refresh_token_expire_days: 7
  password_min_length: 8
  max_login_attempts: 5
  account_lockout_minutes: 15
```

**Environment:**
```bash
JWT_SECRET=<32-byte-hex-string>  # REQUIRED - app exits if empty
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@hnf1b-db.local
ADMIN_PASSWORD=ChangeMe!Admin2025
```

**Endpoints:**
- `POST /api/v2/auth/login` - Get access and refresh tokens
- `POST /api/v2/auth/refresh` - Refresh access token
- `GET /api/v2/auth/me` - Get current user
- `POST /api/v2/auth/logout` - Invalidate session

**Frontend:**
- Token storage: localStorage (`access_token`, `refresh_token`)
- Auto-refresh: Axios interceptor in `frontend/src/api/index.js`
- State: Pinia store in `frontend/src/stores/authStore.js`

## Monitoring & Observability

### Error Tracking

**Approach:** Custom logging (no external service)

**Backend:**
- Python logging module
- Configurable via `LOG_LEVEL` env var

**Frontend:**
- Custom `logService` with PII/PHI redaction
- Access via `window.logService.debug/info/warn/error()`
- Automatic redaction of HPO terms, emails, variants, tokens

### Logs

**Backend:**
- JSON-formatted Docker logs
- Max size: 50m per file, 5 files retained
- Log rotation handled by Docker

**Frontend:**
- Browser console via logService
- Production builds strip console.log (terser config)

### Health Checks

**Backend:**
- `GET /health` - Health endpoint
- Docker healthcheck: `curl --fail http://localhost:8000/health`

**Frontend:**
- Docker healthcheck: `wget --spider http://127.0.0.1:80/`

## CI/CD & Deployment

### Hosting

**Platform:** Docker Compose self-hosted

**Modes:**
1. **Hybrid Development:** PostgreSQL + Redis in Docker, apps run locally
2. **Full Docker:** All services containerized
3. **Production (NPM):** Behind Nginx Proxy Manager

**Docker Files:**
- `docker/docker-compose.yml` - Base configuration
- `docker/docker-compose.dev.yml` - Development services only
- `docker/docker-compose.npm.yml` - Production overlay

### CI Pipeline

**Platform:** GitHub Actions

**Workflow:** `.github/workflows/ci.yml`

**Triggers:**
- Push to main, develop, refactor--* branches
- Pull requests to main, develop

**Jobs:**
1. **Backend Tests:**
   - PostgreSQL 15 + Redis 7 services
   - Alembic migrations
   - Ruff linting
   - Mypy type checking
   - Pytest with coverage
   - Codecov upload

2. **Frontend Tests:**
   - Node.js 20
   - Vitest tests
   - ESLint check
   - Prettier format check

## Environment Configuration

### Required Environment Variables

**Backend (`.env`):**
| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | 32-byte hex string for JWT signing |
| `REDIS_URL` | No | Redis connection (default: localhost:6379) |
| `PUBMED_API_KEY` | No | NCBI API key for higher rate limits |
| `ADMIN_USERNAME` | No | Initial admin username |
| `ADMIN_EMAIL` | No | Initial admin email |
| `ADMIN_PASSWORD` | No | Initial admin password |
| `CORS_ORIGINS` | No | Allowed origins (comma-separated) |
| `DEBUG` | No | Enable debug mode |

**Frontend (`.env`):**
| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | No | Backend API URL (default: /api/v2) |

### Secrets Location

**Development:**
- `backend/.env` - Backend secrets
- `frontend/.env` - Frontend config

**Production:**
- `.env.docker` - Docker Compose environment
- Secrets passed via Docker environment variables

## Webhooks & Callbacks

### Incoming Webhooks

**None** - No external webhook integrations

### Outgoing Webhooks

**None** - No outgoing webhook integrations

## Data Sync Commands

**Publication Metadata:**
```bash
make publications-sync      # Sync all
make publications-sync-dry  # Dry run
```

**Variant Annotations:**
```bash
make variants-sync      # Sync all
make variants-sync-dry  # Dry run
```

**Reference Data:**
```bash
make reference-init  # Initialize GRCh38 + HNF1B
make genes-sync      # Sync chr17q12 genes from Ensembl
```

**Phenopacket Import:**
```bash
make phenopackets-migrate       # Full import (864 records)
make phenopackets-migrate-test  # Test import (20 records)
```

---

*Integration audit: 2026-01-19*
