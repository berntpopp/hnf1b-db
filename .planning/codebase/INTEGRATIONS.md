# External Integrations

**Analysis Date:** 2026-01-19

## APIs & External Services

**Bioinformatics APIs:**

- **Ensembl VEP (Variant Effect Predictor)** - Variant annotation
  - Endpoint: `https://rest.ensembl.org/vep/homo_sapiens/region`
  - SDK/Client: `httpx` (async)
  - Service: `backend/app/variants/service.py`
  - Auth: None (rate limited to 15 req/sec)
  - Features: CADD scores, gnomAD frequencies, consequence predictions, HGVS notation
  - Caching: Database-backed permanent cache (`variant_annotations` table)

- **Ensembl REST API** - Gene/genomic data
  - Endpoint: `https://rest.ensembl.org/overlap/region/human/{region}`
  - SDK/Client: `httpx` (async)
  - Service: `backend/app/reference/service.py`
  - Auth: None (rate limited to 10 req/sec)
  - Used for: chr17q12 region gene sync

- **NCBI PubMed E-utilities** - Publication metadata
  - Endpoint: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi`
  - SDK/Client: `aiohttp` (async)
  - Service: `backend/app/publications/service.py`
  - Auth: `PUBMED_API_KEY` env var (optional, 3 req/sec without key, 10 with key)
  - Caching: Database-backed permanent cache (`publication_metadata` table)

- **HPO JAX API** - Human Phenotype Ontology terms
  - Endpoint: `https://hpo.jax.org/api/hpo`
  - SDK/Client: `requests` (sync)
  - Service: `backend/app/services/ontology_service.py`
  - Auth: None
  - Caching: File cache (`.ontology_cache/`) with 24-hour TTL

- **EBI OLS (Ontology Lookup Service)** - Multi-ontology support
  - Endpoint: `https://www.ebi.ac.uk/ols4/api`
  - SDK/Client: `requests` (sync)
  - Service: `backend/app/services/ontology_service.py`
  - Auth: None
  - Supports: HPO, MONDO, ORDO (Orphanet)

- **Monarch Initiative API** - Disease/phenotype data
  - Endpoint: `https://api.monarchinitiative.org/v3`
  - SDK/Client: `requests` (sync)
  - Service: `backend/app/services/ontology_service.py`
  - Auth: None
  - Used as: Fallback for ontology term lookup

**Data Sources:**

- **Google Sheets** - Primary data source for phenopacket import
  - Access: Public CSV export URLs
  - SDK/Client: `pandas.read_csv()` with Google Sheets export URL
  - Service: `backend/migration/data_sources/google_sheets.py`
  - Auth: None (public sheets)
  - Used for: Initial data migration (864 phenopackets)

## Data Storage

**Databases:**

- **PostgreSQL 15** - Primary data store
  - Connection: `DATABASE_URL` env var
  - Format: `postgresql+asyncpg://user:pass@host:port/db`
  - Client: SQLAlchemy 2.0 async with asyncpg driver
  - Features: JSONB storage for phenopackets, GIN indexes for full-text search
  - Tables: `phenopackets`, `publication_metadata`, `variant_annotations`, `reference_genomes`, `genes`, `transcripts`, `exons`, `protein_domains`, `users`

**Caching:**

- **Redis 7** - Distributed cache
  - Connection: `REDIS_URL` env var (default: `redis://localhost:6379/0`)
  - Client: `redis-py` async
  - Used for: Session cache, rate limiting state
  - Config: 256MB memory limit, LRU eviction

**File Storage:**

- Local filesystem only
  - Ontology cache: `backend/.ontology_cache/`
  - Uploaded files: Not implemented

## Authentication & Identity

**Auth Provider:** Custom JWT implementation

**Implementation:**
- Token creation/verification: `backend/app/auth/tokens.py`
- Password hashing: bcrypt via passlib (`backend/app/auth/password.py`)
- Dependencies: `backend/app/auth/dependencies.py`
- Permissions: `backend/app/auth/permissions.py`

**Token Flow:**
1. Login via `/api/v2/auth/login` returns access + refresh tokens
2. Access token: 30-minute expiry (configurable)
3. Refresh token: 7-day expiry (configurable)
4. Frontend stores tokens in localStorage
5. Axios interceptor adds Bearer token to requests
6. Auto-refresh on 401 response

**Roles:**
- `admin` - Full access including user management
- `curator` - Can create/edit/delete phenopackets
- `viewer` - Read-only access (default)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry/Bugsnag integration)

**Logs:**
- Backend: Python `logging` module, JSON format in Docker
- Frontend: Custom `logService` with automatic PII redaction
- Docker: json-file driver with rotation (50MB max, 5 files)

**Health Checks:**
- Backend: `GET /health` endpoint
- Docker: Built-in health checks with configurable intervals

## CI/CD & Deployment

**Hosting:**
- Docker Compose (self-hosted)
- Nginx Proxy Manager for SSL termination (production)

**CI Pipeline:**
- GitHub Actions (`.github/workflows/ci.yml`)
- Runs on push/PR: lint, typecheck, test for both backend and frontend

**Deployment Modes:**
1. Hybrid (development): PostgreSQL + Redis in Docker, apps run locally
2. Full Docker: All services containerized
3. Production (NPM): Full Docker with Nginx Proxy Manager overlay

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` - PostgreSQL connection (required)
- `JWT_SECRET` - JWT signing secret (required, app exits if empty)

**Optional env vars:**
- `REDIS_URL` - Redis connection (default: `redis://localhost:6379/0`)
- `PUBMED_API_KEY` - Increases PubMed rate limit from 3 to 10 req/sec
- `CORS_ORIGINS` - Comma-separated allowed origins
- `DEBUG` - Enable debug mode
- `ADMIN_USERNAME/EMAIL/PASSWORD` - Initial admin user credentials
- `USE_ONTOLOGY_APIS` - Enable/disable ontology API calls (default: true)
- `ONTOLOGY_API_TIMEOUT` - API timeout in seconds (default: 5)
- `ONTOLOGY_CACHE_TTL_HOURS` - Cache TTL (default: 24)

**Secrets location:**
- Development: `backend/.env` (gitignored)
- Production: `.env.docker` or Docker secrets

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## API Standards Compliance

**GA4GH Standards:**
- Phenopackets v2 - Full compliance for phenotype data exchange
- VRS 2.0 - Deterministic variant identifiers with proper digests

**REST API Standards:**
- JSON:API v1.1 - Pagination format (offset + cursor modes)
- OpenAPI 3.0 - Auto-generated docs at `/docs`

## Rate Limiting

**External APIs (configured in `config.yaml`):**
| Service | Limit | Notes |
|---------|-------|-------|
| VEP | 15 req/sec | Ensembl guideline |
| PubMed (no key) | 3 req/sec | NCBI default |
| PubMed (with key) | 10 req/sec | With `PUBMED_API_KEY` |
| Ensembl REST | 10 req/sec | Self-imposed delay |

**Internal API:**
- 5 req/sec per endpoint (configurable)
- Implemented via rate limiting middleware

---

*Integration audit: 2026-01-19*
