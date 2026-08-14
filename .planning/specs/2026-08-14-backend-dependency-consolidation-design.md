# Backend Dependency Consolidation Design

## Goal

Replace Dependabot PRs #447 through #451 with one resolver-consistent backend dependency update that passes local verification and GitHub Actions.

## Approaches Considered

1. Cherry-pick all five Dependabot commits. This preserves their exact patches but also preserves the known requirements-export drift in #447 and #449.
2. Merge the PR branches sequentially and resolve conflicts manually. This creates a noisy history and still treats generated requirements files as authoritative.
3. Apply valid direct constraints to `backend/pyproject.toml`, regenerate `backend/uv.lock`, and regenerate both requirements exports. This is the selected approach because `pyproject.toml` and `uv.lock` are the repository's dependency sources of truth.

## Dependency Scope

The consolidated change must request these direct dependency floors:

- `pydantic-settings>=2.15.0`
- `deepdiff>=9.1.0`
- `oaklib>=0.7.4`
- `types-pyyaml>=6.0.12.20260724`
- `sqlalchemy[asyncio]>=2.0.51`
- `uvicorn[standard]>=0.52.1`

The resolver remains authoritative for transitive dependencies:

- Keep `chardet==5.2.0` while `pronto==2.7.3` requires `chardet<6`; Dependabot's proposed `chardet==7.5.1` export is unsatisfiable.
- Keep `pydantic-core==2.46.4` while stable `pydantic==2.13.4` requires that exact version; do not introduce a pre-release solely to obtain `2.48.0`.
- Accept resolver-selected updates to transitive packages only when produced by the unified lock operation.

## Files and Data Flow

`backend/pyproject.toml` supplies direct constraints to `uv`. A single lock operation updates `backend/uv.lock`. `make -C backend export-requirements` then derives `backend/requirements.txt` and `backend/requirements-dev.txt` from the lock. Generated exports must never be hand-edited.

## Verification

Run the backend requirements-drift check, lock check, Ruff lint and format checks, mypy, database migrations, and the non-network backend test suite with CI-equivalent environment settings. After pushing, wait for all GitHub Actions checks and investigate any failure before treating the PR as complete.

## GitHub Handling

Open one draft PR against `main` with a dependency table, resolver corrections, validation evidence, and references to #447 through #451. Once the consolidated PR is green, close #447 through #451 with comments pointing to the replacement PR.
