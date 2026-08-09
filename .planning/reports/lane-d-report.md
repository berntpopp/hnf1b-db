# PR-422 Lane D report

## Delivered

- Curator-only source-observation ledger API with GET, projection preview,
  one-report PATCH, and append-only correction/resolution endpoints.
- Mandatory revision or `If-Match` preconditions, ETag responses, server-owned
  correction/resolution actor and timestamp fields, and structured errors.
- Server-side projection on each mutation, recursively immutable source
  evidence (including nested raw/provenance fields), unknown legacy root-key
  preservation, and database-backed curation domain validation for publication
  type, classification system, and ISO dates.
- OpenAPI snapshot and generated MCP contract refreshed. MCP explicitly denies
  every curation/report route, so its existing individual tools remain limited
  to canonical person-level output.

## Review-fix follow-up

- The legacy full-record PUT now rejects observation-backed packets; changes
  must use the report/correction/resolution ledger endpoints.
- Active correction postimages now drive GET, preview, domain validation, and
  canonical projection without mutating stored source evidence.
- Projection uses only the newest resolution for a conflict and ignores one
  whose candidate digest is no longer current. This keeps the append-only
  ledger intact while reopening a conflict after corrected evidence changes.
- Projection issues expose `candidateSetDigest`, and curation request Pydantic
  failures use the same structured 422 envelope as semantic validation errors.
- Curation response models are now explicit in OpenAPI; the raw observation
  object remains forward-compatible/opaque because it includes the model's
  derived source-status field verbatim.

## Re-review follow-up

- A resolution may now supersede an already active decision for the same
  current conflict/digest. The ledger preserves both entries and projection
  deterministically selects the newest append.
- `resolvedValue` is parsed as typed ontology terms or constrained to the
  conflict's permitted string values at the request boundary. Invalid payloads
  use the structured 422 envelope.
- Preview now executes the same immutability, canonicalization/parser, and
  database-domain checks as report PATCH without persisting a revision.
- Canonical GA4GH fields are deep-merged into stored content, preserving
  legacy nested siblings. Correction ordering is deterministic by append
  timestamp (then ID) and subsequent corrections require an explicit current
  predecessor.
- OpenAPI now documents the actual runtime curation error envelope for 404,
  409, 422, and 428 responses.

## Final acceptance follow-up

- Canonicalization preserves unowned legacy nested keys but replaces all
  projector-owned subject, feature, disease, interpretation, and metadata
  fields exactly, removing stale sex and encounter values when projection no
  longer supplies them.
- Ledger observations are again typed as `ReportObservation` in the OpenAPI
  response model; derived phenotype source status now normalizes aliases before
  strict re-validation.

## Final integrity follow-up

- Correction-owned normalized values cannot be overwritten by report PATCH or
  preview. Every correction atomically appends its ID to the target observed
  value's immutable `correctionIds` backlink.
- Modifier conflicts accept typed ontology-term resolved values; contradictory
  raw source status is retained for strict validation and now fails closed.

## Verification

- Backend: 47 focused tests passed (`test_domain_validator`, curation API,
  OpenAPI contract, and projection tests); Ruff passed.
- MCP: `make check` passed (445 tests, 11 deselected). Contract artifacts were
  regenerated from the refreshed OpenAPI snapshot.

## Known baseline

Targeted backend mypy also checks imported dependencies and reports four
pre-existing errors in `state_service.py`, `crud_helpers.py`, and
`phenopacket_service.py`; none are in Lane D files. Lane D's own mypy errors
were resolved before handoff.
