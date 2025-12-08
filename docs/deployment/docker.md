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

# Start all services with data import
ENABLE_DATA_IMPORT=true docker compose -f docker/docker-compose.yml up -d --build

# Watch logs
docker compose -f docker/docker-compose.yml logs -f
```

The first startup with `ENABLE_DATA_IMPORT=true` will:
1. Run database migrations
2. Create admin user (if credentials provided)
3. Initialize reference data (GRCh38 + HNF1B)
4. Import phenopackets from Google Sheets
5. Sync publication metadata from PubMed
6. Sync VEP variant annotations from Ensembl
7. Sync chr17q12 region genes from Ensembl

### Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
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

Create a `.env.docker` file in the `docker/` directory:

```bash
# Copy example configuration
cp docker/.env.example docker/.env.docker
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

For development with ports exposed:

```bash
# Start services
docker compose -f docker/docker-compose.yml up -d --build

# With data import
ENABLE_DATA_IMPORT=true docker compose -f docker/docker-compose.yml up -d --build

# Stop services
docker compose -f docker/docker-compose.yml down

# Stop and remove volumes (clean reset)
docker compose -f docker/docker-compose.yml down -v
```

### Production with NPM

For production behind Nginx Proxy Manager:

```bash
# 1. Configure production environment
cp docker/.env.example docker/.env.docker
vim docker/.env.docker  # Set production values

# 2. Create NPM network
docker network create npm_default

# 3. Deploy with production overlay
docker compose \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.npm.yml \
  --env-file docker/.env.docker \
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

When `ENABLE_DATA_IMPORT=true`, the container entrypoint executes a sync pipeline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Container Startup Pipeline                        │
├─────────────────────────────────────────────────────────────────────┤
│  1. Wait for PostgreSQL                                              │
│  2. Run Alembic migrations                                           │
│  3. Create admin user (if credentials set)                           │
│  4. ENABLE_DATA_IMPORT=true?                                         │
│     ├── Initialize reference data (GRCh38 + HNF1B) ─────────────────│─► Idempotent
│     ├── Import phenopackets (if empty) ─────────────────────────────│─► One-time
│     ├── Sync publication metadata ──────────────────────────────────│─► Idempotent
│     ├── Sync VEP annotations ───────────────────────────────────────│─► Idempotent
│     └── Sync chr17q12 genes ────────────────────────────────────────│─► Idempotent
│  5. Start uvicorn                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

All sync operations are **idempotent** (safe to run multiple times).

### Reference Data Initialization

Initializes core genomic reference data:

| Data | Description |
|------|-------------|
| GRCh38 Genome | Reference genome assembly |
| HNF1B Gene | chr17:36,098,063-36,112,306 |
| NM_000458.4 Transcript | Canonical transcript |
| Exon coordinates | 9 exons |
| Protein domains | 4 domains from UniProt P35680 |

**Trigger condition:** Runs if no genome assemblies exist.

**Script:** `backend/scripts/sync_reference_data.py --init`

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

# Add to docker/.env.docker
echo "JWT_SECRET=$(openssl rand -hex 32)" >> docker/.env.docker
```

#### Data Import Not Running

**Symptom:** Container starts but no data is imported.

**Solution:** Ensure `ENABLE_DATA_IMPORT=true`:
```bash
ENABLE_DATA_IMPORT=true docker compose -f docker/docker-compose.yml up -d
```

Or add to `docker/.env.docker`:
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

## See Also

- [Admin Guide: Updating Annotations](../admin/update-annotations.md)
- [API Documentation](../api/README.md)
- [Variant Annotation API](../api/variant-annotation.md)
