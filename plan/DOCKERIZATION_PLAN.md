# HNF1B Database Dockerization Plan

> **Target Domain:** hnf1b.org
> **VPS Integration:** Strato VPS with Nginx Proxy Manager (NPM)
> **Reference Projects:** phentrive, gtex-link
> **Version:** 2.0 (Revised with expert review corrections)
> **Date:** December 2025

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Target Architecture](#3-target-architecture)
4. [Data Persistence Strategy](#4-data-persistence-strategy)
5. [Security Hardening](#5-security-hardening)
6. [Dockerfile Specifications](#6-dockerfile-specifications)
7. [Docker Compose Configurations](#7-docker-compose-configurations)
8. [Environment Configuration](#8-environment-configuration)
9. [Data Import Configuration](#9-data-import-configuration)
10. [Nginx Configuration](#10-nginx-configuration)
11. [NPM Integration](#11-npm-integration)
12. [Makefile Targets](#12-makefile-targets)
13. [Health Checks & Monitoring](#13-health-checks--monitoring)
14. [Deployment Workflow](#14-deployment-workflow)
15. [Backup & Recovery](#15-backup--recovery)
16. [Migration Checklist](#16-migration-checklist)
17. [Testing Strategy](#17-testing-strategy)

---

## 1. Executive Summary

### Objectives

Transform the HNF1B Database from a development-focused Docker setup to a **production-ready, security-hardened deployment** suitable for hosting on the Strato VPS behind Nginx Proxy Manager at `hnf1b.org`.

### Key Deliverables

| Deliverable | Description |
|-------------|-------------|
| `backend/Dockerfile.prod` | Multi-stage build with uv, non-root user, security hardening |
| `frontend/Dockerfile.prod` | Multi-stage build with nginx-unprivileged |
| `docker-compose.npm.yml` | Production config for NPM integration |
| `docker-compose.dev.yml` | Development overlay with port exposure |
| `.env.docker.template` | Production environment template with data import config |
| `setup_hnf1b.sh` | Automated VPS deployment script |
| `docker/backup.sh` | Database backup script |

### Architecture Pattern

Following the proven patterns from **phentrive** and **gtex-link**:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Internet                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS (443)
┌───────────────────────────▼─────────────────────────────────────┐
│                  Nginx Proxy Manager                             │
│                  (npm_default network)                           │
│    ┌──────────────────┬──────────────────┬────────────────────┐ │
│    │ hnf1b.org        │ api.hnf1b.org    │ (other services)   │ │
└────┴────────┬─────────┴────────┬─────────┴────────────────────┴─┘
              │                  │
    ┌─────────▼──────┐ ┌────────▼────────┐
    │ hnf1b_frontend │ │ hnf1b_api       │
    │ :8080 (nginx)  │ │ :8000 (uvicorn) │
    └────────────────┘ └────────┬────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
    ┌────▼─────┐          ┌─────▼────┐          ┌─────▼────┐
    │ PostgreSQL│          │  Redis   │          │ (future) │
    │ :5432     │          │  :6379   │          │          │
    └───────────┘          └──────────┘          └──────────┘
         │
    Named Volume:
    hnf1b_postgres_data
```

---

## 2. Current State Analysis

### Existing Docker Files

| File | Purpose | Production Ready |
|------|---------|------------------|
| `docker-compose.yml` | Full stack containerization | ⚠️ Partial |
| `docker-compose.services.yml` | Hybrid dev mode | ✅ Good for dev |
| `backend/Dockerfile` | FastAPI container | ⚠️ Needs hardening |
| `frontend/Dockerfile` | Vue.js + nginx | ⚠️ Needs hardening |
| `frontend/nginx.conf` | SPA routing | ⚠️ Missing security headers |

### Issues Identified

1. **Security**
   - Containers run as root
   - No capability dropping
   - No read-only filesystem
   - No resource limits
   - Hard-coded credentials in compose

2. **Production Gaps**
   - No NPM network integration
   - Missing health check endpoints
   - No log rotation configuration
   - No environment separation (dev/prod)
   - Missing `.dockerignore` files

3. **Data Management**
   - No backup strategy
   - Data import not configurable (always runs)
   - Volume persistence not clearly defined

---

## 3. Target Architecture

### Container Layout

```yaml
Services:
  hnf1b_api:
    Image: hnf1b-db/api:latest
    Port: 8000 (internal)
    User: 10001:10001 (hnf1b)
    Networks: [hnf1b_internal, npm_default]

  hnf1b_frontend:
    Image: hnf1b-db/frontend:latest
    Port: 8080 (internal)
    User: 101:101 (nginx)
    Networks: [hnf1b_internal, npm_default]

  hnf1b_db:
    Image: postgres:15-alpine
    Port: 5432 (internal only)
    Networks: [hnf1b_internal]
    Volumes: [hnf1b_postgres_data]

  hnf1b_cache:
    Image: redis:7-alpine
    Port: 6379 (internal only)
    Networks: [hnf1b_internal]
    Volumes: [hnf1b_redis_data]
```

### Network Strategy

| Network | Purpose | External |
|---------|---------|----------|
| `hnf1b_internal` | Inter-service communication | No |
| `npm_default` | NPM reverse proxy access | Yes |

### Domain Mapping

| Domain | Service | Port |
|--------|---------|------|
| `hnf1b.org` | hnf1b_frontend | 8080 |
| `api.hnf1b.org` | hnf1b_api | 8000 |

---

## 4. Data Persistence Strategy

### Volume Configuration

| Volume | Purpose | Backup Priority | Size Estimate |
|--------|---------|-----------------|---------------|
| `hnf1b_postgres_data` | Phenopackets database | **Critical** | ~500MB |
| `hnf1b_redis_data` | Cache persistence | Low | ~50MB |

### What Gets Persisted

```yaml
PostgreSQL (hnf1b_postgres_data):
  - All phenopacket records (864+ records)
  - User accounts and sessions
  - Alembic migration history
  - Audit logs

Redis (hnf1b_redis_data):
  - API response cache
  - Rate limiting data
  - Session tokens (optional)

  Note: Redis uses AOF persistence with everysec fsync
  Recovery: Cache can be rebuilt; persistence is optional
```

### Volume Lifecycle

```bash
# Volumes are NOT removed by default stop/restart
docker compose down              # Keeps volumes ✅
docker compose down -v           # REMOVES volumes ⚠️ DATA LOSS!

# Explicit volume management
docker volume ls | grep hnf1b    # List volumes
docker volume inspect hnf1b_postgres_data  # Check size/location
```

### Host Volume Location (VPS)

```
/var/lib/docker/volumes/
├── hnf1b_postgres_data/
│   └── _data/           # PostgreSQL data files
└── hnf1b_redis_data/
    └── _data/           # Redis AOF files
```

---

## 5. Security Hardening

Based on [Docker Security Best Practices 2025](https://cloudnativenow.com/topics/cloudnativedevelopment/docker/docker-security-in-2025-best-practices-to-protect-your-containers-from-cyberthreats/) and [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html).

### 5.1 Non-Root Users

```dockerfile
# Backend: Create dedicated user (UID 10001)
RUN groupadd -r -g 10001 hnf1b && \
    useradd -r -u 10001 -g hnf1b -d /app -s /sbin/nologin hnf1b

USER hnf1b:hnf1b

# Frontend: Use nginx-unprivileged (UID 101)
FROM nginxinc/nginx-unprivileged:1.27-alpine3.20-slim
```

### 5.2 Read-Only Filesystem

```yaml
services:
  hnf1b_api:
    read_only: true
    tmpfs:
      - /tmp:uid=10001,gid=10001,size=100M,mode=1777

  hnf1b_frontend:
    read_only: true
    tmpfs:
      - /var/cache/nginx:uid=101,gid=101,size=50M,mode=0755
      - /var/run:uid=101,gid=101,size=10M,mode=0755
      - /tmp:uid=101,gid=101,size=10M,mode=1777
```

### 5.3 Capability Dropping & Security Options

```yaml
services:
  hnf1b_api:
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
```

### 5.4 Resource Limits

> **Note:** `deploy.resources.reservations` [only works in Swarm mode](https://github.com/docker/compose/issues/10046). Only `limits` are enforced in standard Docker Compose.

```yaml
services:
  hnf1b_api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  hnf1b_frontend:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  hnf1b_db:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  hnf1b_cache:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### 5.5 Security Checklist

| Security Feature | API | Frontend | DB | Redis |
|------------------|-----|----------|-----|-------|
| Non-root user | ✅ | ✅ | ✅ | ✅ |
| Read-only root FS | ✅ | ✅ | ❌ | ❌ |
| Drop all caps | ✅ | ✅ | ✅ | ✅ |
| no-new-privileges | ✅ | ✅ | ✅ | ✅ |
| Resource limits | ✅ | ✅ | ✅ | ✅ |
| Health checks | ✅ | ✅ | ✅ | ✅ |
| Log rotation | ✅ | ✅ | ✅ | ✅ |

---

## 6. Dockerfile Specifications

### 6.1 Backend Dockerfile (Multi-Stage with uv)

Based on [uv Docker Best Practices](https://docs.astral.sh/uv/guides/integration/docker/) and [Production-ready Python Docker with uv](https://hynek.me/articles/docker-uv/).

```dockerfile
# backend/Dockerfile.prod
# syntax=docker/dockerfile:1.11
# Pin to specific syntax version for reproducibility

# ============================================================================
# ARGUMENTS
# ============================================================================
ARG PYTHON_VERSION=3.11
ARG DEBIAN_VERSION=bookworm
ARG UV_VERSION=0.5.10

# ============================================================================
# STAGE 1: Build dependencies
# ============================================================================
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS builder

# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv - PIN TO SPECIFIC VERSION for reproducible builds
COPY --from=ghcr.io/astral-sh/uv:0.5.10 /uv /uvx /bin/

WORKDIR /app

# Phase 1: Install dependencies only (better layer caching)
# This layer is cached when only code changes, not dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .

# Phase 2: Install project (runs when code changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ============================================================================
# STAGE 2: Production runtime
# ============================================================================
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS production

# OCI standard labels
LABEL org.opencontainers.image.title="HNF1B Database API" \
      org.opencontainers.image.description="GA4GH Phenopackets v2 compliant REST API for HNF1B clinical data" \
      org.opencontainers.image.vendor="HNF1B Database" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/berntpopp/hnf1b-db"

# Install runtime dependencies and apply security updates
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache \
    # Security: Remove setuid/setgid bits
    && find /usr -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

# Security: Create non-root user (UID 10001 to avoid host conflicts)
RUN groupadd -r -g 10001 hnf1b && \
    useradd -r -u 10001 -g hnf1b -d /app -s /sbin/nologin hnf1b

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=hnf1b:hnf1b /app/.venv /app/.venv

# Copy application code
COPY --chown=hnf1b:hnf1b ./app ./app
COPY --chown=hnf1b:hnf1b ./alembic ./alembic
COPY --chown=hnf1b:hnf1b ./alembic.ini ./
COPY --chown=hnf1b:hnf1b ./migration ./migration

# Set environment - include UV optimizations for faster startup
ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app"

# Switch to non-root user
USER hnf1b:hnf1b

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v2/health || exit 1

EXPOSE 8000

# Use ENTRYPOINT + CMD for flexibility
# --proxy-headers: Required for proper X-Forwarded-* handling behind NPM
ENTRYPOINT ["uvicorn"]
CMD ["app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

### 6.2 Frontend Dockerfile (Multi-Stage)

```dockerfile
# frontend/Dockerfile.prod
# syntax=docker/dockerfile:1.11

# ============================================================================
# ARGUMENTS
# ============================================================================
ARG NODE_VERSION=20-alpine3.20
ARG NGINX_VERSION=1.27-alpine3.20-slim
ARG VITE_API_URL

# ============================================================================
# STAGE 1: Dependencies
# ============================================================================
FROM node:${NODE_VERSION} AS deps

WORKDIR /app

COPY package.json package-lock.json* ./

# Use --ignore-scripts for security (prevents postinstall attacks)
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts

# ============================================================================
# STAGE 2: Builder
# ============================================================================
FROM node:${NODE_VERSION} AS builder

ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build && \
    ls -la dist/

# ============================================================================
# STAGE 3: Runtime - nginx-unprivileged
# ============================================================================
FROM nginxinc/nginx-unprivileged:${NGINX_VERSION} AS runtime

# OCI standard labels
LABEL org.opencontainers.image.title="HNF1B Database Frontend" \
      org.opencontainers.image.description="Vue.js frontend for HNF1B clinical database" \
      org.opencontainers.image.vendor="HNF1B Database" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/berntpopp/hnf1b-db"

# Copy nginx configuration
COPY --chown=nginx:nginx nginx/nginx.prod.conf /etc/nginx/nginx.conf

# Copy built assets
COPY --chown=nginx:nginx --from=builder /app/dist /usr/share/nginx/html

# Apply security updates (need root temporarily)
USER root
RUN apk update && apk upgrade --no-cache && \
    rm -f /etc/nginx/conf.d/*.conf.default
USER nginx

# Health check - use correct wget flags for Alpine
# --no-verbose: Suppress output that can interfere with exit codes
# --tries=1: Let Docker handle retries
# 127.0.0.1: Alpine lacks proper localhost DNS resolution
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/health || exit 1

EXPOSE 8080

ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
```

### 6.3 .dockerignore Files

**backend/.dockerignore:**
```
# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.egg-info
.eggs
*.egg
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov

# Virtual environments
.venv
venv
env

# IDE
.idea
.vscode
*.swp
*.swo

# Local
.env
.env.local
*.log

# Tests (not needed in production)
tests/
conftest.py

# Docs
docs/
*.md
!README.md
```

**frontend/.dockerignore:**
```
# Git
.git
.gitignore

# Node
node_modules
npm-debug.log*

# Build outputs (we rebuild in container)
dist
.vite

# IDE
.idea
.vscode

# Local
.env
.env.local

# Tests
tests/
*.test.js
*.spec.js
coverage/
```

---

## 7. Docker Compose Configurations

### 7.1 NPM Production Mode (`docker-compose.npm.yml`)

```yaml
# docker-compose.npm.yml
# Production deployment for Nginx Proxy Manager integration
#
# Usage:
#   docker compose -f docker-compose.npm.yml --env-file .env.docker up -d
#
# Prerequisites:
#   1. NPM network must exist: docker network create npm_default
#   2. .env.docker must be configured from .env.docker.template

name: hnf1b-db

services:
  # ============================================
  # PostgreSQL Database
  # ============================================
  hnf1b_db:
    image: postgres:15-alpine
    container_name: hnf1b_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-hnf1b_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
      POSTGRES_DB: ${POSTGRES_DB:-hnf1b_phenopackets}
    volumes:
      - hnf1b_postgres_data:/var/lib/postgresql/data
    networks:
      - hnf1b_internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-hnf1b_user} -d ${POSTGRES_DB:-hnf1b_phenopackets}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
      - DAC_OVERRIDE
    security_opt:
      - no-new-privileges:true
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ============================================
  # Redis Cache
  # ============================================
  hnf1b_cache:
    image: redis:7-alpine
    container_name: hnf1b_cache
    restart: unless-stopped
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
    volumes:
      - hnf1b_redis_data:/data
    networks:
      - hnf1b_internal
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ============================================
  # FastAPI Backend
  # ============================================
  hnf1b_api:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
      args:
        BUILDKIT_INLINE_CACHE: 1
    image: hnf1b-db/api:${IMAGE_TAG:-latest}
    container_name: hnf1b_api
    restart: unless-stopped
    user: "10001:10001"
    read_only: true
    tmpfs:
      - /tmp:uid=10001,gid=10001,size=100M,mode=1777
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-hnf1b_user}:${POSTGRES_PASSWORD}@hnf1b_db:5432/${POSTGRES_DB:-hnf1b_phenopackets}
      REDIS_URL: redis://hnf1b_cache:6379/0
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET required}
      DEBUG: "false"
      LOG_LEVEL: ${LOG_LEVEL_API:-INFO}
      CORS_ORIGINS: ${CORS_ORIGINS:-https://hnf1b.org,https://www.hnf1b.org}
      # Data import configuration (see Section 9)
      ENABLE_DATA_IMPORT: ${ENABLE_DATA_IMPORT:-false}
      DATA_IMPORT_SOURCE: ${DATA_IMPORT_SOURCE:-}
    depends_on:
      hnf1b_db:
        condition: service_healthy
      hnf1b_cache:
        condition: service_healthy
    networks:
      - hnf1b_internal
      - npm_proxy_network
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/v2/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ============================================
  # Vue.js Frontend
  # ============================================
  hnf1b_frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        VITE_API_URL: ${VITE_API_URL:-https://api.hnf1b.org/api/v2}
        BUILDKIT_INLINE_CACHE: 1
    image: hnf1b-db/frontend:${IMAGE_TAG:-latest}
    container_name: hnf1b_frontend
    restart: unless-stopped
    user: "101:101"
    read_only: true
    tmpfs:
      - /var/cache/nginx:uid=101,gid=101,size=50M,mode=0755
      - /var/run:uid=101,gid=101,size=10M,mode=0755
      - /tmp:uid=101,gid=101,size=10M,mode=1777
    depends_on:
      hnf1b_api:
        condition: service_healthy
    networks:
      - npm_proxy_network
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/health || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

# ============================================
# Networks
# ============================================
networks:
  hnf1b_internal:
    name: hnf1b_internal
    driver: bridge
    ipam:
      config:
        - subnet: 172.26.0.0/16  # Explicit subnet to avoid conflicts

  npm_proxy_network:
    name: ${NPM_SHARED_NETWORK_NAME:-npm_default}
    external: true

# ============================================
# Volumes - CRITICAL FOR DATA PERSISTENCE
# ============================================
volumes:
  hnf1b_postgres_data:
    name: hnf1b_postgres_data
    # Data persists across container restarts
    # Use 'docker compose down -v' to remove (DATA LOSS!)

  hnf1b_redis_data:
    name: hnf1b_redis_data
    # Cache data - can be rebuilt if lost
```

### 7.2 Development Overlay (`docker-compose.dev.yml`)

```yaml
# docker-compose.dev.yml
# Development overlay - use with base compose file
#
# Usage:
#   docker compose -f docker-compose.npm.yml -f docker-compose.dev.yml up

services:
  hnf1b_api:
    build:
      context: ./backend
      dockerfile: Dockerfile  # Use existing dev Dockerfile
    user: root  # Allow hot reload file watching
    read_only: false
    environment:
      DEBUG: "true"
      LOG_LEVEL: DEBUG
      CORS_ORIGINS: "http://localhost:5173,http://localhost:8080,http://localhost:3000"
      ENABLE_DATA_IMPORT: ${ENABLE_DATA_IMPORT:-false}
    volumes:
      - ./backend/app:/app/app:ro
    ports:
      - "8000:8000"

  hnf1b_frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_URL: http://localhost:8000/api/v2
    user: root
    read_only: false
    ports:
      - "3000:80"

  hnf1b_db:
    ports:
      - "5433:5432"

  hnf1b_cache:
    ports:
      - "6380:6379"

networks:
  npm_proxy_network:
    external: false
    name: hnf1b_dev_network
```

---

## 8. Environment Configuration

### 8.1 Template File (`.env.docker.template`)

```bash
# ============================================
# HNF1B Database - Docker Environment Configuration
# ============================================
# Copy this file to .env.docker and configure values
# NEVER commit .env.docker to version control
# ============================================

# ============================================
# PostgreSQL Database
# ============================================
POSTGRES_USER=hnf1b_user
POSTGRES_PASSWORD=CHANGE_ME_TO_SECURE_PASSWORD
POSTGRES_DB=hnf1b_phenopackets

# ============================================
# Security (REQUIRED)
# ============================================
# Generate with: openssl rand -hex 32
JWT_SECRET=CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32

# ============================================
# API Configuration
# ============================================
LOG_LEVEL_API=INFO
CORS_ORIGINS=https://hnf1b.org,https://www.hnf1b.org

# ============================================
# Public URLs
# ============================================
VITE_API_URL=https://api.hnf1b.org/api/v2

# ============================================
# NPM Integration
# ============================================
# Must match your Nginx Proxy Manager network name
NPM_SHARED_NETWORK_NAME=npm_default

# ============================================
# Image Versioning (optional)
# ============================================
IMAGE_TAG=latest

# ============================================
# Admin Credentials (for db-init)
# ============================================
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@hnf1b.org
ADMIN_PASSWORD=CHANGE_ME_IMMEDIATELY

# ============================================
# DATA IMPORT CONFIGURATION
# ============================================
# Enable/disable initial data import from Google Sheets
# Set to 'true' ONLY for initial deployment, then set to 'false'
ENABLE_DATA_IMPORT=false

# Google Sheets credentials (only needed if ENABLE_DATA_IMPORT=true)
# DATA_IMPORT_SOURCE=path/to/credentials.json
# GOOGLE_SHEETS_ID=your_sheet_id
```

### 8.2 Production Symlink Pattern

```bash
# On deployment, create symlink:
ln -sf .env.docker .env

# Docker Compose loads from .env by default
docker compose -f docker-compose.npm.yml up -d
```

---

## 9. Data Import Configuration

### 9.1 Overview

The HNF1B database requires an **initial one-time import** of phenopacket data from Google Sheets. After initial deployment, this import should be disabled to:
- Prevent duplicate data on restarts
- Improve container startup time
- Reduce external dependencies in production

### 9.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_DATA_IMPORT` | `false` | Enable/disable data import on startup |
| `DATA_IMPORT_SOURCE` | `` | Path to Google Sheets credentials |
| `GOOGLE_SHEETS_ID` | `` | Google Sheets document ID |
| `DATA_IMPORT_MODE` | `full` | `full`, `test` (20 records), or `dry-run` |

### 9.3 Deployment Workflow

**Initial Deployment (First Time):**
```bash
# 1. Configure environment
cp .env.docker.template .env.docker
nano .env.docker

# Set these values:
ENABLE_DATA_IMPORT=true
DATA_IMPORT_MODE=full
# Add Google Sheets credentials

# 2. Start services
docker compose -f docker-compose.npm.yml --env-file .env.docker up -d

# 3. Monitor import
docker compose logs -f hnf1b_api | grep -i import

# 4. Verify data count
docker compose exec hnf1b_db psql -U hnf1b_user -d hnf1b_phenopackets \
  -c "SELECT COUNT(*) FROM phenopackets;"

# 5. IMPORTANT: Disable import after success
sed -i 's/ENABLE_DATA_IMPORT=true/ENABLE_DATA_IMPORT=false/' .env.docker
docker compose restart hnf1b_api
```

**Subsequent Deployments:**
```bash
# Import is disabled by default
# Data persists in hnf1b_postgres_data volume
docker compose -f docker-compose.npm.yml --env-file .env.docker up -d
```

### 9.4 Manual Data Import (Post-Deployment)

```bash
# Run import manually without restart
docker compose exec hnf1b_api python -m migration.main --mode full

# Test import (20 records)
docker compose exec hnf1b_api python -m migration.main --mode test

# Dry run (outputs JSON, no DB changes)
docker compose exec hnf1b_api python -m migration.main --mode dry-run
```

### 9.5 Makefile Targets for Data Import

```makefile
# Manual data import (after initial setup)
docker-import-full:
	docker compose -f docker-compose.npm.yml --env-file .env.docker \
		exec hnf1b_api python -m migration.main --mode full

docker-import-test:
	docker compose -f docker-compose.npm.yml --env-file .env.docker \
		exec hnf1b_api python -m migration.main --mode test

docker-import-dry:
	docker compose -f docker-compose.npm.yml --env-file .env.docker \
		exec hnf1b_api python -m migration.main --mode dry-run
```

---

## 10. Nginx Configuration

### 10.1 Production Nginx Config (`frontend/nginx/nginx.prod.conf`)

```nginx
# nginx.prod.conf - Production configuration for Vue.js SPA
# For nginx-unprivileged (runs as UID 101)

worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Security: Hide server version
    server_tokens off;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/json
        application/xml
        font/woff
        font/woff2
        image/svg+xml;

    # Temp paths for unprivileged nginx
    client_body_temp_path /tmp/client_body;
    proxy_temp_path /tmp/proxy;
    fastcgi_temp_path /tmp/fastcgi;
    uwsgi_temp_path /tmp/uwsgi;
    scgi_temp_path /tmp/scgi;

    server {
        listen 8080;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        # ========================================
        # Security Headers
        # ========================================
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
        add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.hnf1b.org; frame-ancestors 'self'; base-uri 'self'; form-action 'self';" always;

        # ========================================
        # Health Check Endpoint
        # ========================================
        location /health {
            access_log off;
            add_header Content-Type text/plain;
            return 200 "healthy\n";
        }

        # ========================================
        # API Proxy (optional)
        # ========================================
        location /api/ {
            proxy_pass http://hnf1b_api:8000/api/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
            proxy_buffering off;
        }

        # ========================================
        # Static Assets (long cache)
        # ========================================
        location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot|webp|map)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            access_log off;
        }

        # ========================================
        # SPA Fallback
        # ========================================
        location / {
            try_files $uri $uri/ /index.html;
            add_header Cache-Control "no-cache, no-store, must-revalidate";
        }

        error_page 404 /index.html;
        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
            root /usr/share/nginx/html;
        }
    }
}
```

---

## 11. NPM Integration

### 11.1 Required NPM Configuration

Configure in Nginx Proxy Manager admin panel:

**Proxy Host 1: Frontend (hnf1b.org)**

| Setting | Value |
|---------|-------|
| Domain Names | `hnf1b.org`, `www.hnf1b.org` |
| Scheme | http |
| Forward Hostname | `hnf1b_frontend` |
| Forward Port | `8080` |
| Cache Assets | Yes |
| Block Exploits | Yes |
| Websockets | Yes |

**SSL Tab:**
- Request Let's Encrypt certificate
- Force SSL: Yes
- HTTP/2 Support: Yes

**Proxy Host 2: API (api.hnf1b.org)**

| Setting | Value |
|---------|-------|
| Domain Names | `api.hnf1b.org` |
| Scheme | http |
| Forward Hostname | `hnf1b_api` |
| Forward Port | `8000` |
| Cache Assets | No |
| Block Exploits | Yes |
| Websockets | No |

**SSL Tab:**
- Request Let's Encrypt certificate
- Force SSL: Yes
- HTTP/2 Support: Yes

### 11.2 Add to strato_v6_docker_npm

Add to `config/projects.yaml`:

```yaml
hnf1b-db:
  enabled: true
  description: "HNF1B Clinical and Genetic Database"
  github_url: https://github.com/berntpopp/hnf1b-db
  repo_name: hnf1b-db_repo
  compose_file: docker-compose.npm.yml
  env_file: .env.docker
  containers:
    - hnf1b_api
    - hnf1b_frontend
    - hnf1b_db
    - hnf1b_cache
  domains:
    frontend: hnf1b.org
    api: api.hnf1b.org
  health_check:
    endpoint: /api/v2/health
    container: hnf1b_api
    port: 8000
```

---

## 12. Makefile Targets

Add to root `Makefile`:

```makefile
# ============================================
# Docker Production Targets
# ============================================

.PHONY: docker-build docker-npm docker-npm-bg docker-down docker-logs docker-clean

# Build production images
docker-build:
	docker compose -f docker-compose.npm.yml --env-file .env.docker build

# Start NPM production mode (foreground)
docker-npm:
	docker compose -f docker-compose.npm.yml --env-file .env.docker up --build

# Start NPM production mode (background)
docker-npm-bg:
	docker compose -f docker-compose.npm.yml --env-file .env.docker up -d --build

# Stop all containers (preserves data)
docker-down:
	docker compose -f docker-compose.npm.yml --env-file .env.docker down

# View logs
docker-logs:
	docker compose -f docker-compose.npm.yml --env-file .env.docker logs -f

docker-logs-api:
	docker compose -f docker-compose.npm.yml --env-file .env.docker logs -f hnf1b_api

docker-logs-frontend:
	docker compose -f docker-compose.npm.yml --env-file .env.docker logs -f hnf1b_frontend

# Clean up (preserves volumes)
docker-clean:
	docker compose -f docker-compose.npm.yml --env-file .env.docker down --rmi local

# Full clean (removes volumes - DATA LOSS!)
docker-clean-all:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker compose -f docker-compose.npm.yml --env-file .env.docker down -v --rmi local

# ============================================
# Docker Development Targets
# ============================================

docker-dev:
	docker compose -f docker-compose.npm.yml -f docker-compose.dev.yml --env-file .env.docker up --build

docker-dev-bg:
	docker compose -f docker-compose.npm.yml -f docker-compose.dev.yml --env-file .env.docker up -d --build

# ============================================
# Health & Status
# ============================================

docker-health:
	@echo "Checking container health..."
	@docker inspect --format='{{.Name}}: {{.State.Health.Status}}' hnf1b_api hnf1b_frontend hnf1b_db hnf1b_cache 2>/dev/null || echo "Containers not running"

docker-ps:
	docker compose -f docker-compose.npm.yml --env-file .env.docker ps

# ============================================
# Database Operations
# ============================================

docker-db-migrate:
	docker compose -f docker-compose.npm.yml --env-file .env.docker exec hnf1b_api alembic upgrade head

docker-db-init:
	docker compose -f docker-compose.npm.yml --env-file .env.docker exec hnf1b_api python -m app.scripts.create_admin

docker-db-backup:
	./docker/backup.sh

docker-shell-api:
	docker compose -f docker-compose.npm.yml --env-file .env.docker exec hnf1b_api /bin/sh

docker-shell-db:
	docker compose -f docker-compose.npm.yml --env-file .env.docker exec hnf1b_db psql -U hnf1b_user -d hnf1b_phenopackets

# ============================================
# Data Import
# ============================================

docker-import-full:
	docker compose -f docker-compose.npm.yml --env-file .env.docker exec hnf1b_api python -m migration.main --mode full

docker-import-test:
	docker compose -f docker-compose.npm.yml --env-file .env.docker exec hnf1b_api python -m migration.main --mode test
```

---

## 13. Health Checks & Monitoring

### 13.1 Container Health Check Summary

| Service | Endpoint | Interval | Start Period | Retries |
|---------|----------|----------|--------------|---------|
| hnf1b_api | `curl http://localhost:8000/api/v2/health` | 30s | 60s | 5 |
| hnf1b_frontend | `wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/health` | 30s | 10s | 3 |
| hnf1b_db | `pg_isready -U hnf1b_user` | 10s | 30s | 5 |
| hnf1b_cache | `redis-cli ping` | 10s | 10s | 5 |

### 13.2 API Health Endpoint

```python
# app/api/v2/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
import redis.asyncio as redis
import os

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check for container orchestration."""
    health = {"status": "healthy", "checks": {}}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        health["checks"]["database"] = "connected"
    except Exception as e:
        health["status"] = "unhealthy"
        health["checks"]["database"] = f"error: {str(e)}"

    # Redis check (optional)
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)
        await r.ping()
        health["checks"]["redis"] = "connected"
        await r.close()
    except Exception:
        health["checks"]["redis"] = "unavailable"

    return health
```

---

## 14. Deployment Workflow

### 14.1 Automated Setup Script (`setup_hnf1b.sh`)

```bash
#!/bin/bash
# setup_hnf1b.sh - Automated VPS deployment for HNF1B Database

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  HNF1B Database Setup Script${NC}"
echo -e "${GREEN}=====================================${NC}"

# Check prerequisites
command -v docker &> /dev/null || { echo -e "${RED}Error: Docker not installed${NC}"; exit 1; }
docker compose version &> /dev/null || { echo -e "${RED}Error: Docker Compose V2 not installed${NC}"; exit 1; }

# Check/create .env.docker
if [ ! -f ".env.docker" ]; then
    if [ -f ".env.docker.template" ]; then
        cp .env.docker.template .env.docker
        echo -e "${YELLOW}Created .env.docker - please configure it${NC}"
        exit 1
    else
        echo -e "${RED}Error: .env.docker.template not found${NC}"
        exit 1
    fi
fi

# Validate required variables
source .env.docker
[ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32" ] && {
    echo -e "${RED}Error: Configure JWT_SECRET (openssl rand -hex 32)${NC}"; exit 1;
}
[ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "CHANGE_ME_TO_SECURE_PASSWORD" ] && {
    echo -e "${RED}Error: Configure POSTGRES_PASSWORD${NC}"; exit 1;
}

# Check/create NPM network
NPM_NETWORK="${NPM_SHARED_NETWORK_NAME:-npm_default}"
docker network ls | grep -q "$NPM_NETWORK" || {
    echo -e "${YELLOW}Creating NPM network '$NPM_NETWORK'...${NC}"
    docker network create "$NPM_NETWORK"
}

# Create symlink
ln -sf .env.docker .env

# Build and start
echo -e "${GREEN}Building Docker images...${NC}"
docker compose -f docker-compose.npm.yml --env-file .env.docker build

echo -e "${GREEN}Starting services...${NC}"
docker compose -f docker-compose.npm.yml --env-file .env.docker up -d

echo -e "${YELLOW}Waiting for services...${NC}"
sleep 30

docker compose -f docker-compose.npm.yml --env-file .env.docker ps

# Run migrations
echo -e "${GREEN}Running database migrations...${NC}"
docker compose -f docker-compose.npm.yml --env-file .env.docker exec -T hnf1b_api alembic upgrade head

# Check if initial import needed
if [ "$ENABLE_DATA_IMPORT" = "true" ]; then
    echo -e "${GREEN}Running initial data import...${NC}"
    docker compose -f docker-compose.npm.yml --env-file .env.docker exec -T hnf1b_api python -m migration.main --mode full

    echo -e "${YELLOW}Disabling future auto-imports...${NC}"
    sed -i 's/ENABLE_DATA_IMPORT=true/ENABLE_DATA_IMPORT=false/' .env.docker
fi

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "1. Configure NPM proxy hosts for hnf1b.org and api.hnf1b.org"
echo -e "2. Point DNS to your VPS IP"
echo -e "3. Request SSL certificates via NPM"
echo ""
echo -e "Commands:"
echo -e "  make docker-logs     # View logs"
echo -e "  make docker-health   # Check health"
echo -e "  make docker-db-backup # Backup database"
```

---

## 15. Backup & Recovery

### 15.1 Backup Script (`docker/backup.sh`)

```bash
#!/bin/bash
# docker/backup.sh - PostgreSQL backup for HNF1B Database

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hnf1b_backup_$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating backup: $BACKUP_FILE"
docker compose -f docker-compose.npm.yml --env-file .env.docker exec -T hnf1b_db \
    pg_dump -U hnf1b_user -d hnf1b_phenopackets | gzip > "$BACKUP_FILE"

echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/hnf1b_backup_*.sql.gz | tail -n +8 | xargs -r rm --
echo "Cleanup complete. Keeping last 7 backups."
```

### 15.2 Restore from Backup

```bash
# Restore from backup
gunzip -c backups/hnf1b_backup_YYYYMMDD_HHMMSS.sql.gz | \
docker compose -f docker-compose.npm.yml --env-file .env.docker exec -T hnf1b_db \
    psql -U hnf1b_user -d hnf1b_phenopackets
```

---

## 16. Migration Checklist

### Pre-Migration

- [ ] Backup existing database (if any)
- [ ] Verify DNS records for hnf1b.org and api.hnf1b.org
- [ ] Ensure Google Sheets credentials available (for initial import)

### File Creation

- [ ] `backend/Dockerfile.prod`
- [ ] `frontend/Dockerfile.prod`
- [ ] `frontend/nginx/nginx.prod.conf`
- [ ] `docker-compose.npm.yml`
- [ ] `docker-compose.dev.yml`
- [ ] `.env.docker.template`
- [ ] `backend/.dockerignore`
- [ ] `frontend/.dockerignore`
- [ ] `setup_hnf1b.sh`
- [ ] `docker/backup.sh`

### Testing

- [ ] Test docker-compose.npm.yml locally
- [ ] Verify health checks work
- [ ] Test database migrations
- [ ] Test data import (dry run)

### Deployment

- [ ] Clone to VPS at `/opt/hnf1b-db`
- [ ] Configure `.env.docker` (set `ENABLE_DATA_IMPORT=true` for first run)
- [ ] Run `./setup_hnf1b.sh`
- [ ] Verify data imported (check count)
- [ ] Disable data import in `.env.docker`
- [ ] Configure NPM proxy hosts
- [ ] Request SSL certificates
- [ ] Add to strato_v6_docker_npm `projects.yaml`
- [ ] Set up backup cron job

### Post-Deployment

- [ ] Verify frontend at https://hnf1b.org
- [ ] Verify API at https://api.hnf1b.org/api/v2/health
- [ ] Test backup/restore procedure
- [ ] Document recovery procedures

---

## 17. Testing Strategy

### 17.1 Local Testing

```bash
# Create mock NPM network
docker network create npm_default

# Build and test
cp .env.docker.template .env.docker
# Edit .env.docker with test values

docker compose -f docker-compose.npm.yml --env-file .env.docker up --build

# Verify
curl http://localhost:8000/api/v2/health
curl http://localhost:8080/health

# Clean up
docker compose -f docker-compose.npm.yml --env-file .env.docker down
docker network rm npm_default
```

### 17.2 Volume Persistence Test

```bash
# Start services
docker compose -f docker-compose.npm.yml --env-file .env.docker up -d

# Add test data
docker compose exec hnf1b_db psql -U hnf1b_user -d hnf1b_phenopackets \
  -c "SELECT COUNT(*) FROM phenopackets;"

# Stop (without -v)
docker compose down

# Restart
docker compose up -d

# Verify data persists
docker compose exec hnf1b_db psql -U hnf1b_user -d hnf1b_phenopackets \
  -c "SELECT COUNT(*) FROM phenopackets;"
```

---

## Appendix A: File Structure

```
hnf1b-db/
├── backend/
│   ├── Dockerfile              # Dev Dockerfile (existing)
│   ├── Dockerfile.prod         # Production Dockerfile (NEW)
│   ├── .dockerignore           # Docker ignore (NEW)
│   └── ...
├── frontend/
│   ├── Dockerfile              # Dev Dockerfile (existing)
│   ├── Dockerfile.prod         # Production Dockerfile (NEW)
│   ├── .dockerignore           # Docker ignore (NEW)
│   ├── nginx.conf              # Dev nginx (existing)
│   └── nginx/
│       └── nginx.prod.conf     # Production nginx (NEW)
├── docker/
│   └── backup.sh               # Backup script (NEW)
├── docker-compose.yml          # Existing (keep)
├── docker-compose.services.yml # Hybrid dev (existing)
├── docker-compose.npm.yml      # NPM production (NEW)
├── docker-compose.dev.yml      # Dev overlay (NEW)
├── .env.docker.template        # Production env (NEW)
├── setup_hnf1b.sh              # Setup script (NEW)
└── Makefile                    # Updated with docker targets
```

---

## References

- [Docker Security Best Practices 2025](https://cloudnativenow.com/topics/cloudnativedevelopment/docker/docker-security-in-2025-best-practices-to-protect-your-containers-from-cyberthreats/)
- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [uv Docker Best Practices](https://docs.astral.sh/uv/guides/integration/docker/)
- [Production-ready Python Docker with uv](https://hynek.me/articles/docker-uv/)
- [FastAPI Docker Best Practices](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/)
- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose deploy.resources](https://github.com/docker/compose/issues/10046) - Swarm-only note
