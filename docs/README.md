# Documentation

## Overview

This directory contains all project documentation organized by category. Each subdirectory focuses on a specific aspect of the HNF1B-API project.

## Directory Structure

### 📁 [migration/](migration/)
Documentation related to data migration and database schema evolution.

- **[PHENOPACKETS_MIGRATION_RECORD.md](migration/PHENOPACKETS_MIGRATION_RECORD.md)** - Complete record of the migration from MongoDB to PostgreSQL with GA4GH Phenopackets v2 implementation

### 📁 [architecture/](architecture/)
*Coming soon: System architecture, design decisions, and technical specifications*

### 📁 [api/](api/)
API endpoint documentation and specifications.

- **[README.md](api/README.md)** - API overview
- **[variant-annotation.md](api/variant-annotation.md)** - VEP variant annotation endpoints
- **[reference-genome-api.md](api/reference-genome-api.md)** - Reference genome and gene endpoints

### 📁 [deployment/](deployment/)
Deployment guides, environment setup, and production configurations.

- **[docker.md](deployment/docker.md)** - Complete Docker deployment guide with automatic data sync

### 📁 [admin/](admin/)
Administrator guides for database management.

- **[update-annotations.md](admin/update-annotations.md)** - Guide for updating genomic annotations

## Key Documents

### [TODO.md](TODO.md)
Current project task list, priorities, and development roadmap.

## Quick Links

- **[Project README](../README.md)** - Main project overview, setup instructions, and quick start guide
- **[CLAUDE.md](../CLAUDE.md)** - Claude Code AI assistant guidance and available commands
- **[API Documentation](http://localhost:8000/docs)** - Interactive API documentation (when server is running)

## Contributing

When adding new documentation:
1. Place documents in the appropriate subdirectory
2. Update this README with a brief description
3. Follow markdown best practices for formatting
4. Include examples where applicable