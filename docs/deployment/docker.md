# Docker Deployment Guide

Comprehensive guide for deploying HNF1B Database using Docker.

**Last Updated:** 2025-01-09

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Data Import Settings](#data-import-settings)
- [Deployment Modes](#deployment-modes)
  - [Local Development](#local-development)
  - [Production with NPM](#production-with-npm)
- [Automatic Data Sync](#automatic-data-sync)
  - [Sync Pipeline Overview](#sync-pipeline-overview)
  - [Reference Data Initialization](#reference-data-initialization)
  - [chr17q12 Genes Sync](#chr17q12-genes-sync)
  - [Publication Metadata Sync](#publication-metadata-sync)
  - [VEP Variant Annotations](#vep-variant-annotations)
- [Admin Dashboard](#admin-dashboard)
- [Manual Sync Commands](#manual-sync-commands)
- [Volumes and Persistence](#volumes-and-persistence)
- [Troubleshooting](#troubleshooting)

---

## Overview

The HNF1B Database uses Docker Compose to orchestrate four services:

| Service | Image | Purpose |
|---------|-------|---------|
| `hnf1b_db` | `postgres:15-alpine` | PostgreSQL database |
| `hnf1b_cache` | `redis:7-alpine` | Redis cache for rate limiting |
| `hnf1b_api` | Custom (FastAPI) | REST API backend |
| `hnf1b_frontend` | Custom (Vue.js) | Web application |

---

## Prerequisites

- **Docker Engine:** 20.10+ with Docker Compose V2
- **Memory:** 4GB minimum (8GB recommended)
- **Storage:** 10GB for images and data
- **Network:** Outbound access to external APIs (Ensembl, PubMed)

```bash
# Verify prerequisites
docker --version          # Docker 20.10+
docker compose version    # Docker Compose V2
```

---

## Quick Start

### Local Development

```bash
# Clone repository
git clone https://github.com/berntpopp/hnf1b-db.git
cd hnf1b-db

# Configure the docker env (REQUIRED). At minimum set:
#   ENVIRONMENT=development     (relaxes the prod SMTP/TLS/cookie validators)
#   ADMIN_PASSWORD=<strong>     (no default — the app refuses to boot if empty)
cp .env.docker.example .env.docker
$EDITOR .env.docker

# Build + start the whole stack (db, cache, api, mcp, frontend)
make dev-up
# equivalently:
#   docker compose -f docker/docker-compose.yml --env-file .env.docker up -d --build

# Watch logs
docker compose -f docker/docker-compose.yml logs -f
```

> **Why `--env-file` / `ENVIRONMENT=development` are required.** The base compose
> is production-oriented: `ENVIRONMENT` defaults to `production`, where the Wave 5c
> fail-closed validators require real SMTP, secure cookies, and a non-empty
> `ADMIN_PASSWORD`. `make dev-up` loads `.env.docker` so those values are present;
> set `ENVIRONMENT=development` there to boot locally without SMTP/TLS.
>
> The API container runs `alembic upgrade head` automatically on startup; the DB
> image is `pgvector/pgvector:pg15` (provides the `vector` extension for the
> publication RAG index). To populate the publication full-text RAG corpus on an
> existing DB, run `make publications-backfill`.

Every startup (regardless of `ENABLE_DATA_IMPORT`) will:
1. Run database migrations
2. Ensure reference data (GRCh38 + HNF1B transcript/exons/domains + cross-refs) — idempotent
3. Create admin user (if credentials provided)

A first startup additionally with `ENABLE_DATA_IMPORT=true` (set in `.env.docker`) will:
4. Import phenopackets from Google Sheets (if the DB is empty)
5. Sync publication metadata from PubMed
6. Sync VEP variant annotations from Ensembl
7. Sync chr17q12 region genes from Ensembl

### Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/v2/docs |
| Database | localhost:5433 |
| Redis | localhost:6380 |

---

## Architecture

```
                    ┌─────────────────┐
                    │  Web Browser    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐        ┌──────────▼──────────┐
     │  hnf1b_frontend │        │      hnf1b_api      │
     │    (Vue.js)     │        │     (FastAPI)       │
     │    Port 3000    │◄──────►│     Port 8000       │
     └─────────────────┘        └──────────┬──────────┘
                                           │
              ┌──────────────┬─────────────┤
              │              │             │
     ┌────────▼───────┐ ┌────▼─────┐  ┌───▼────────────┐
     │   hnf1b_db     │ │ hnf1b_   │  │ External APIs  │
     │  (PostgreSQL)  │ │  cache   │  │ - Ensembl VEP  │
     │   Port 5432    │ │ (Redis)  │  │ - Ensembl REST │
     └────────────────┘ └──────────┘  │ - PubMed       │
                                      └────────────────┘
```

---

## Configuration

### Environment Variables

Create a root `.env.docker` file:

```bash
# Copy example configuration
cp .env.docker.example .env.docker
```

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | `SecurePass123!` |
| `JWT_SECRET` | JWT signing key (32+ chars) | `openssl rand -hex 32` |

#### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `hnf1b_user` | Database username |
| `POSTGRES_DB` | `hnf1b_phenopackets` | Database name |
| `DB_PORT_HOST` | `5433` | PostgreSQL host port |
| `REDIS_PORT_HOST` | `6380` | Redis host port |
| `API_PORT_HOST` | `8000` | API host port |
| `FRONTEND_PORT_HOST` | `3000` | Frontend host port |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL_API` | `INFO` | API log level |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins |

#### Admin User

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_USERNAME` | `admin` | Admin username |
| `ADMIN_EMAIL` | `admin@hnf1b.local` | Admin email |
| `ADMIN_PASSWORD` | (none) | Admin password (required for creation) |

### Data Import Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_DATA_IMPORT` | `false` | Enable automatic data sync on startup |
| `GOOGLE_SHEETS_ID` | (hardcoded default) | Google Sheets ID for phenopacket import |

---

## Deployment Modes

### Local Development

For development with ports exposed (requires `.env.docker` with
`ENVIRONMENT=development` + `ADMIN_PASSWORD`; see Quick Start above):

```bash
# Start services (loads .env.docker via --env-file)
make dev-up
# equivalently:
#   docker compose -f docker/docker-compose.yml --env-file .env.docker up -d --build

# Stop services (preserves volumes)
make dev-down

# Stop and remove volumes (CLEAN RESET — destroys all DB data)
docker compose -f docker/docker-compose.yml --env-file .env.docker down -v
```

> Omitting `--env-file` (or leaving `ENVIRONMENT` unset) boots the stack in
> production mode, where the API refuses to start with an empty `ADMIN_PASSWORD`.

### Production with NPM

For production behind Nginx Proxy Manager:

```bash
# 1. Configure production environment
cp .env.docker.example .env.docker
vim .env.docker  # Set production values

# 2. Create NPM network
docker network create npm_default

# 3. Deploy with production overlay
docker compose \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.npm.yml \
  --env-file .env.docker \
  up -d --build
```

Production overlay features:
- No exposed ports (NPM handles routing)
- Security hardening (read-only filesystem, dropped capabilities)
- Resource limits (CPU/memory)
- Non-root user execution

---

## Automatic Data Sync

### Sync Pipeline Overview

The container entrypoint runs this pipeline on every start:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Container Startup Pipeline                        │
├─────────────────────────────────────────────────────────────────────┤
│  1. Wait for PostgreSQL                                              │
│  2. Run Alembic migrations ─────────────────────────────────────────│─► Idempotent (every start)
│  3. Ensure reference data (GRCh38 + HNF1B + transcript/exons/        │
│     domains + cross-refs) ──────────────────────────────────────────│─► Idempotent (every start)
│  4. Create admin user (if credentials set)                           │
│  5. ENABLE_DATA_IMPORT=true?  (heavy / external — opt-in)           │
│     ├── Import phenopackets (if empty) ─────────────────────────────│─► One-time
│     ├── Sync publication metadata ──────────────────────────────────│─► Idempotent
│     ├── Sync VEP annotations ───────────────────────────────────────│─► Idempotent
│     └── Sync chr17q12 genes ────────────────────────────────────────│─► Idempotent
│  6. Start uvicorn                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

Reference data is **essential static seed** the app contract depends on
(`get_gene_context`), so it is initialized on **every** start regardless of
`ENABLE_DATA_IMPORT`. The heavy/external syncs (phenopackets from Google Sheets,
PubMed, Ensembl) remain behind `ENABLE_DATA_IMPORT=true`. All steps are
**idempotent** (safe to run repeatedly).

### Reference Data Initialization

Seeds (and self-heals) core genomic reference data on every container start:

| Data | Description |
|------|-------------|
| GRCh38 Genome | Reference genome assembly |
| HNF1B Gene | chr17:36,098,063-36,112,306 + NCBI/HGNC/OMIM cross-refs |
| NM_000458.4 Transcript | Canonical transcript |
| Exon coordinates | 9 exons |
| Protein domains | 4 domains from UniProt P35680 |

**Idempotency:** each item is created only if missing, and a gene left by the
chr17q12 region sync without NCBI/HGNC/OMIM cross-references is **healed** (the
init no longer short-circuits on a coarse "genome exists" check).

**Script:** `backend/scripts/sync_reference_data.py --init` (run manually with
`make reference-init`).

### chr17q12 Genes Sync

Fetches all genes in the chr17q12 deletion syndrome region from Ensembl REST API.

| Parameter | Value |
|-----------|-------|
| Region | chr17:36,000,000-39,900,000 |
| Expected genes | ~70 |
| Source | Ensembl REST API (`/overlap/region`) |

**Trigger condition:** Runs if fewer than 60 chr17q12 genes exist.

**Script:** `backend/scripts/sync_reference_data.py --genes`

**API endpoint:** `GET https://rest.ensembl.org/overlap/region/human/17:36000000-39900000?feature=gene`

### Publication Metadata Sync

Fetches publication metadata (title, authors, year, DOI) from PubMed for all PMIDs referenced in phenopackets.

| Data | Source |
|------|--------|
| Titles | PubMed |
| Authors | PubMed |
| Year | PubMed |
| DOI | PubMed |

**Trigger condition:** Runs if cached publications < unique PMIDs in database.

**Script:** `backend/scripts/sync_publication_metadata.py`

**API endpoint:** NCBI E-utilities (efetch)

### VEP Variant Annotations

Fetches variant effect predictions from Ensembl VEP API for all VCF variants in phenopackets.

| Annotation | Description |
|------------|-------------|
| Consequence | e.g., `missense_variant`, `splice_donor_variant` |
| Impact | HIGH, MODERATE, LOW, MODIFIER |
| CADD scores | Deleteriousness prediction |
| gnomAD frequencies | Population allele frequencies |
| HGVS notation | c. and p. nomenclature |

**Trigger condition:** Runs if cached annotations < unique variants in database.

**Script:** `backend/scripts/sync_variant_annotations.py`

**API endpoint:** `POST https://rest.ensembl.org/vep/human/hgvs`

**Note:** VEP API is rate-limited. The sync includes automatic retry logic and respects rate limits.

---

## Admin Dashboard

The Admin Dashboard provides a web interface for monitoring and triggering sync operations.

**URL:** http://localhost:3000/admin (requires login)

### Reference Data Section

| Metric | Description |
|--------|-------------|
| Reference Data | GRCh38 genome presence |
| chr17q12 Genes | Count of synced genes |
| HNF1B Gene | HNF1B presence and coordinates |

**Actions:**
- **Sync Genes** - Trigger chr17q12 genes sync

### Annotations Section

| Metric | Description |
|--------|-------------|
| Publication Metadata | Cached publications count |
| VEP Annotations | Cached variant annotations count |

**Actions:**
- **Sync Publications** - Trigger PubMed metadata sync
- **Sync Variants** - Trigger VEP annotation sync

### Status Indicators

- **Green progress bar (100%)** - Data up to date
- **Yellow progress bar (<100%)** - Sync needed
- **Red errors** - Sync failed (check logs)

---

## Manual Sync Commands

### From Host (Makefile)

```bash
# Initialize reference data
make reference-init

# Sync chr17q12 genes
make genes-sync

# Sync publication metadata
make publications-sync

# Sync VEP annotations
make annotations-sync
```

### Inside Container

```bash
# Enter API container
docker compose -f docker/docker-compose.yml exec hnf1b_api bash

# Initialize reference data
python scripts/sync_reference_data.py --init

# Sync chr17q12 genes
python scripts/sync_reference_data.py --genes

# Dry run (no changes)
python scripts/sync_reference_data.py --genes --dry-run

# Limit for testing
python scripts/sync_reference_data.py --genes --limit 10

# Show current status
python scripts/sync_reference_data.py --status

# Sync publications
python scripts/sync_publication_metadata.py

# Sync VEP annotations
python scripts/sync_variant_annotations.py
```

### Via Admin API

```bash
# Trigger genes sync (requires auth)
curl -X POST http://localhost:8000/api/v2/admin/reference/sync-genes \
  -H "Authorization: Bearer <token>"

# Trigger publications sync
curl -X POST http://localhost:8000/api/v2/admin/publications/sync \
  -H "Authorization: Bearer <token>"

# Trigger VEP sync
curl -X POST http://localhost:8000/api/v2/admin/variants/sync \
  -H "Authorization: Bearer <token>"
```

---

## Volumes and Persistence

| Volume | Purpose | Mount Point |
|--------|---------|-------------|
| `hnf1b_postgres_data` | PostgreSQL data | `/var/lib/postgresql/data` |
| `hnf1b_redis_data` | Redis AOF persistence | `/data` |

### Backup Database

```bash
# Using Makefile
make docker-db-backup

# Manual
docker compose -f docker/docker-compose.yml exec -T hnf1b_db \
  pg_dump -U hnf1b_user hnf1b_phenopackets > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
# Stop API first
docker compose -f docker/docker-compose.yml stop hnf1b_api

# Restore
docker compose -f docker/docker-compose.yml exec -T hnf1b_db \
  psql -U hnf1b_user -d hnf1b_phenopackets < backup_20250109.sql

# Restart API
docker compose -f docker/docker-compose.yml start hnf1b_api
```

---

## Troubleshooting

### Check Container Health

```bash
# View container status
docker compose -f docker/docker-compose.yml ps

# View logs
docker compose -f docker/docker-compose.yml logs -f hnf1b_api

# Check health endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v2/health
```

### Common Issues

#### Ensembl API Errors (500/503)

```
[ERROR] VEP annotation sync failed with 198 error(s)
Error: HTTP 503 from rest.ensembl.org
```

**Cause:** Ensembl REST API temporary outage.

**Solution:** Wait and retry. Use Admin Dashboard "Sync Variants" button or:
```bash
docker compose -f docker/docker-compose.yml exec hnf1b_api \
  python scripts/sync_variant_annotations.py
```

#### Database Connection Failed

```
[ERROR] Failed to connect to database
```

**Solution:**
```bash
# Check if database is ready
docker compose -f docker/docker-compose.yml logs hnf1b_db

# Verify healthcheck
docker compose -f docker/docker-compose.yml exec hnf1b_db \
  pg_isready -U hnf1b_user -d hnf1b_phenopackets
```

#### JWT_SECRET Not Set

```
[ERROR] JWT_SECRET is empty - application will exit
```

**Solution:**
```bash
# Generate secure secret
openssl rand -hex 32

# Add to .env.docker
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env.docker
```

#### Data Import Not Running

**Symptom:** Container starts but no data is imported.

**Solution:** Ensure `ENABLE_DATA_IMPORT=true`:
```bash
ENABLE_DATA_IMPORT=true docker compose -f docker/docker-compose.yml up -d
```

Or add to `.env.docker`:
```bash
ENABLE_DATA_IMPORT=true
```

### View Sync Status

```bash
# Check reference data status
docker compose -f docker/docker-compose.yml exec hnf1b_api \
  python scripts/sync_reference_data.py --status
```

Expected output:
```
======================================================================
Reference Data Status
======================================================================

Genomes:
  - Count: 1
  - GRCh38 present: True

Genes:
  - Total: 176
  - HNF1B present: True
  - chr17q12 region: 175

Transcripts:
  - Count: 1

Exons:
  - Count: 9

Protein Domains:
  - Count: 4

Status: Reference data initialized
Status: chr17q12 genes synced
```

---

## MCP Server — mcp.hnf1b.org

The HNF1B MCP sidecar (`hnf1b_mcp`) runs on port **8788** and is exposed via
Nginx Proxy Manager in the same way as the API and frontend.

### NPM Proxy Host: mcp.hnf1b.org → hnf1b_mcp:8788

1. In the NPM dashboard, go to **Proxy Hosts → Add Proxy Host**.
2. Fill in the **Details** tab:

   | Field | Value |
   |---|---|
   | Domain Names | `mcp.hnf1b.org` |
   | Scheme | `http` |
   | Forward Hostname / IP | `hnf1b_mcp` |
   | Forward Port | `8788` |
   | Cache Assets | Off |
   | Block Common Exploits | On |
   | Websockets Support | Off |

3. On the **SSL** tab, select **Request a new SSL Certificate** (Let's Encrypt),
   tick **Force SSL** and **HTTP/2 Support**, enter a valid e-mail address, and
   accept the Let's Encrypt ToS.

4. On the **Advanced** tab, add the following custom Nginx directives to disable
   proxy buffering (required for Server-Sent Events / Streamable HTTP), set
   generous timeouts, and restrict the `Origin` header to the allowed clients:

   ```nginx
   # Required for MCP Streamable HTTP (SSE keep-alive)
   proxy_buffering off;
   proxy_read_timeout 300s;
   proxy_send_timeout 300s;

   # Origin allowlist — only Claude.ai and direct (no-origin) callers
   set $allowed_origin 0;
   if ($http_origin = "https://claude.ai")  { set $allowed_origin 1; }
   if ($http_origin = "https://claude.com") { set $allowed_origin 1; }
   if ($http_origin = "")                   { set $allowed_origin 1; }
   if ($allowed_origin = 0) {
       return 403;
   }
   ```

5. Click **Save**. NPM will obtain the Let's Encrypt certificate and activate
   the proxy.

6. Verify the endpoint:

   ```bash
   curl https://mcp.hnf1b.org/health
   # Expected: {"status": "ok"}
   ```

### Registering the connector in Claude.ai

1. Open **Claude.ai → Settings → Connectors**.
2. Click **Add custom connector**.
3. Enter the connector URL: `https://mcp.hnf1b.org/mcp`
4. Click **Save**.

Claude will call `hnf1b_get_capabilities` on the next session start to
discover the full tool inventory.

---

## See Also

- [Admin Guide: Updating Annotations](../admin/update-annotations.md)
- [API Documentation](../api/README.md)
- [Variant Annotation API](../api/variant-annotation.md)
- [MCP Server README](../../mcp/README.md)
