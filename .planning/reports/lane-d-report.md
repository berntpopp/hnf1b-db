# PR-422 Lane D report

## Delivered

- Curator-only source-observation ledger API with GET, projection preview,
  one-report PATCH, and append-only correction/resolution endpoints.
- Mandatory revision or `If-Match` preconditions, ETag responses, server-owned
  correction/resolution actor and timestamp fields, and structured errors.
- Server-side projection on each mutation, imported source identity protection,
  unknown legacy root-key preservation, and database-backed curation domain
  validation for publication type, classification system, and ISO dates.
- OpenAPI snapshot and generated MCP contract refreshed. MCP explicitly denies
  every curation/report route, so its existing individual tools remain limited
  to canonical person-level output.

## Verification

- Backend: 38 focused tests passed (`test_domain_validator`, curation API,
  OpenAPI contract, state canonicalization, and projection tests); Ruff passed.
- MCP: `make contract-verify` passed; generated artifacts were byte-identical
  on a second generation; `make check` passed (445 tests, 11 deselected).

## Known baseline

Targeted backend mypy also checks imported dependencies and reports four
pre-existing errors in `state_service.py`, `crud_helpers.py`, and
`phenopacket_service.py`; none are in Lane D files. Lane D's own mypy errors
were resolved before handoff.
