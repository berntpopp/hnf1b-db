<p align="center">
  <a href="https://hnf1b.org/">
    <img src="frontend/public/HNF1B-db_logo.svg" alt="HNF1B-db" width="370">
  </a>
</p>

<p align="center">
  A curated database of individuals, variants and publications for
  <strong>HNF1B-related disease</strong>, built on GA4GH Phenopackets v2.
</p>

<p align="center">
  <a href="https://github.com/berntpopp/hnf1b-db/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/berntpopp/hnf1b-db/ci.yml?branch=main&label=CI&logo=github" alt="CI"></a>
  <a href="https://codecov.io/gh/berntpopp/hnf1b-db"><img src="https://codecov.io/gh/berntpopp/hnf1b-db/branch/main/graph/badge.svg" alt="Backend coverage"></a>
  <!-- Frontend Vitest line coverage; regenerate with `cd frontend && npx vitest run --coverage` -->
  <a href="frontend/vitest.config.js"><img src="https://img.shields.io/badge/frontend%20coverage-59%25-yellow?logo=vitest&logoColor=white" alt="Frontend coverage"></a>
  <a href="https://github.com/berntpopp/hnf1b-db/releases"><img src="https://img.shields.io/github/v/release/berntpopp/hnf1b-db?label=release&color=blue" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue%203-Vuetify%204-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue 3 + Vuetify 4">
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL + pgvector">
  <img src="https://img.shields.io/badge/GA4GH-Phenopackets%20v2-0A6EBD" alt="GA4GH Phenopackets v2">
  <img src="https://img.shields.io/badge/MCP-server-D97757" alt="MCP server">
</p>

<p align="center">
  <a href="https://hnf1b.org/">Live site</a> ·
  <a href="https://hnf1b.org/api/v2/docs">API docs</a> ·
  <a href="https://hnf1b.org/mcp">Use it from Claude / ChatGPT</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#cite">Cite</a>
</p>

---

HNF1B-db collects every published individual with an HNF1B variant, with
phenotypes as HPO terms, variants annotated with VEP and ACMG evidence, and
links to the source publications. Curators edit records through a versioned
review workflow; everyone else can browse, filter, chart and download the data,
or query it from an AI assistant through the read-only MCP server.

- **Browse:** individuals, variants and publications with server-side search and filters
- **Analyse:** phenotype frequencies, genotype–phenotype comparisons, renal survival curves, protein and 3D structure views
- **Curate:** draft → review → publish, with revision history, comments and an independent second reviewer
- **Integrate:** a REST API and an MCP server (`https://mcp.hnf1b.org/mcp`) over the same data

## Repository layout

| Directory   | Stack                                     | What it is                                  |
| ----------- | ----------------------------------------- | ------------------------------------------- |
| `backend/`  | FastAPI · async SQLAlchemy · Alembic · uv | REST API, curation workflow, data sync jobs |
| `frontend/` | Vue 3 · Vuetify 4 · Vite · D3             | Web application                             |
| `mcp/`      | FastMCP · uv                              | Read-only MCP server for AI clients         |
| `docker/`   | Docker Compose · nginx                    | Development and production stacks           |
| `docs/`     | Markdown                                  | Deployment, API, data model and user guides |

## Quick start

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make dev          # install backend + frontend dependencies
make hybrid-up    # PostgreSQL + Redis in Docker
make backend      # API on http://localhost:8000 (docs at /api/v2/docs)
make frontend     # web app on http://localhost:5173
```

Or run the whole stack in Docker:

```bash
cp .env.docker.example .env.docker   # set ENVIRONMENT=development and ADMIN_PASSWORD
make dev-up                          # db, cache, api, mcp, frontend (http://localhost:3000)
make dev-down
```

Migrations run on start-up. For role switching during development, set
`ENABLE_DEV_AUTH=true` in `backend/.env` and run `make dev-seed-users`; the
dev login is refused outside `ENVIRONMENT=development` and stripped from
production builds. Production deployment: [docs/deployment/docker.md](docs/deployment/docker.md).

## Checks

Local first: the same targets run on your machine and in CI.

```bash
make ci-static    # lint, format, types, unit tests and hygiene for all three apps (~20 s, runs on git push)
make ci           # ci-static + the backend suite (needs make hybrid-up)
```

CI adds Playwright end-to-end tests and Docker image builds, and skips draft pull requests.

## Documentation

- [docs/](docs/README.md): deployment, API, database, curation workflow, user guide
- [docs/adr/](docs/adr/): architecture decisions, including the [auth and session model](docs/adr/0002-cookie-refresh-and-memory-access-token.md)
- [AGENTS.md](AGENTS.md): conventions for contributors and coding agents
- [CHANGELOG.md](CHANGELOG.md): release notes

## Cite

If you use HNF1B-db, please cite it using [CITATION.cff](CITATION.cff)
(GitHub's "Cite this repository" button gives APA and BibTeX).

## License

[MIT](LICENSE) © Bernt Popp. For research use; not for clinical decision-making.
