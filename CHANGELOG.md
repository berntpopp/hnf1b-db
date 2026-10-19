# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-19

### Added
- Keyboard-first (`Cmd+K` / `/`) HPO quick-add bar with present/absent/onset toggles and clone cohort/sibling proband templates (`#549`, `#551`).
- Visual clinical diff summary cards and RFC-6901 path-aware side-by-side revision comparison in `PhenopacketReview` (`#550`).
- URL-synced saved searches and shareable cohort filters across Phenopackets, Variants, and Aggregations (`#553`).
- RAG-assisted phenotype suggestion from stored publication passages and interactive bulk import dry-run/commit workbench (`#552`, `#554`).
- Schema-drift CI checks (`alembic check`), OpenAPI contract snapshot enforcement, and APScheduler materialized-view refresh (`#517`, `#526`, `#536`).

### Changed
- Consolidated phenopacket repository queries, domain-partitioned frontend API clients, and extracted gene visualization sub-components (`#521`, `#532`, `#537`, `#542`, `#546`, `#547`, `#548`).
- Unified monorepo version tracking across `backend`, `frontend`, and `mcp` at `0.4.0` (`#545`).

### Fixed
- Hardened authentication, rate limiting, security headers, privacy redaction, and token storage (`#522`, `#523`, `#524`, `#525`, `#538`, `#539`).
- Corrected GA4GH Phenopacket v2 schema validation, VRS CNV representations, optimistic locking, survival analysis SQL paths, and cursor pagination (`#518`, `#519`, `#520`, `#527`, `#528`, `#529`, `#530`, `#531`, `#533`, `#534`, `#535`, `#540`, `#541`, `#543`, `#544`).

## [0.3.1] - 2026-10-19

### Changed
- Repo cleanup and dead code removal.
- MCP client cache bounding and security hardening.
- Added release management automation, citation metadata, and security policy.
