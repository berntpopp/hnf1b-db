# PR #422 coordinated patch release

## Decision

Release the three independently versioned deliverables together after the PR
#422 remediation:

| Deliverable | Current | Release version |
| --- | --- | --- |
| `hnf1b-api` | 0.2.1 | 0.2.2 |
| `hnf1b-mcp` | 0.1.1 | 0.1.2 |
| `hnf1b-db-frontend` | 0.0.5 | 0.0.6 |

This is a patch release. It introduces corrective behavior and data integrity
guarantees without intentionally changing a public API major/minor contract.

## Implementation boundary

- Update the canonical API project version in `backend/pyproject.toml` and
  regenerate the OpenAPI snapshot because API metadata exposes that version.
- Update the canonical MCP project version in `mcp/pyproject.toml` and its
  authoritative lock metadata.
- Update the frontend package and package-lock root versions together.
- Do not alter dependency versions, generated dependency resolutions, or
  unrelated application metadata as part of the release bump.

## Verification and publication

1. Verify the changed metadata and generated artifacts are internally
   consistent.
2. Push the bump to the existing PR #422 branch.
3. Require a fresh GitHub Actions run to pass all required checks.
4. Merge that existing PR only after the fresh required Actions checks pass,
   as authorized by the requester. Do not create a replacement PR.

The controlled corpus reconciliation and exact Opus 5 adversarial-review
requirements remain separately documented operational gates; this version bump
does not misrepresent them as completed.
