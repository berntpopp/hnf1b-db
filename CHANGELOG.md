# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-10-27

### Added

- `GET /api/v2/reference/genes/{symbol}/structure` serves the HNF1B experimental structure (PDB 2H8R, mmCIF) and `.../structure/dna-distances` the per-residue distance to DNA computed from it. The 3D viewer and the DNA distance analysis now read both from the API (the structure file moved from the frontend to the backend), and the distances are available to MCP clients.
- Pre-commit/CI guard `no-domain-data-in-frontend` rejects data and structure files in the frontend, and a unit test pins Vuetify's cascade-layer order to the installed version.

### Changed

- First paint shows the app bar immediately (static app shell in `index.html`) instead of a blank page while the bundle loads; mobile first contentful paint 5.0 s → 2.7 s.
- Main pages' code is prefetched when the browser is idle, so first clicks no longer wait on downloads; a thin progress bar appears under the app bar for navigations slower than 150 ms.
- Curator-only History and Discussion tabs load on demand; the public phenopacket page drops from 237 KB to 11 KB gzipped.
- The icon font is subset at build time to the icons in use (403 KB → 14 KB); icon and text fonts are preloaded.
- Loading skeletons appear only after 300 ms, so fast responses go straight to content.
- Home: the landing page is part of the main bundle, and the headline numbers show as soon as they load instead of counting up for 1.5 s.
- Aggregations: DNA distance analysis fetches per-residue distances from the API instead of loading the 3D viewer and structure file in the browser; the Variant Comparison and Survival data load in the background; tabs switch without animation, hold their height while loading and no longer show spinners for fast responses.

### Fixed

- Production builds loaded Vuetify's stylesheets in an order that let its reset beat component styles (e.g. small buttons rendered at 16 px). The cascade-layer order is now pinned.
- Table skeletons rendered as stacked dark-grey blocks.
- Aggregations: the Stacked Bar tab jumped (CLS 0.33) and briefly showed "No data available" while loading; distance-category bars had white text below WCAG AA contrast.
- Charts in dark mode: titles, axis labels, legends, gridlines and tooltips used fixed black/white/grey and were unreadable; they now follow the theme. PNG export uses the chart's own background so dark-mode exports stay legible.
- Charts on phones: dense charts (survival, stacked bar, variant comparison) scroll sideways at a readable size instead of shrinking text to a few pixels; the distance box plot redraws to its container instead of being clipped; long stacked-bar labels no longer overlap the next row; median labels on survival curves no longer overlap; "p = < 0.0001" reads "p < 0.0001".

## [0.4.1] - 2026-10-26

### Added

- Light/dark theme toggle in the app bar again (it was removed as dead code in 0.3.1); new visitors follow their OS setting until they choose.
- Unit test that fails on Material Design Icon names missing from `@mdi/font`.

### Changed

- Fonts (Inter, JetBrains Mono) are self-hosted instead of loaded from Google Fonts: no render-blocking third-party request, no visitor IPs sent to Google, and compatible with the production CSP.
- Light-theme brand primary moves to Teal 700 (`#00796B`) and semantic info/success/warning to 700–800 shades so text and tonal components pass WCAG AA.
- Production bundle no longer preloads route-only code (3D structure viewer, curator editor) on every page; only the ~240 icon rules in use ship in the render-blocking stylesheet.

### Fixed

- Dark mode readability across all pages: hard-coded light colours (footer, card headers, labels, variant page hero/background, chips, legends) are now theme-aware. Zero WCAG AA contrast failures across 15 pages in both themes.
- Layout shift on load (registry tables, pagination, footer, detail-page heroes, breadcrumbs, scrollbar appearance) — CLS ≤ 0.008.
- Missing chip spacing (`gap-N` is not a Vuetify utility; now `ga-N`), headings falling back to an unloaded Roboto, and three icons that rendered blank.
- Accessibility: unnamed tooltips and icon buttons, label-in-name mismatches, invalid list semantics in search results, diff lines that relied on colour alone, and horizontal overflow at 320 px. Lighthouse accessibility 100 on desktop.

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
