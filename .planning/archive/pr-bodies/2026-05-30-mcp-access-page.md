## Summary

Adds a concise, public **"Connect an AI Agent (MCP)"** page (`/mcp`) plus a
bottom-bar (footer) menu item next to the existing **API** item, as requested.
The page explains — simply — how to connect the public, read-only HNF1B-db MCP
server (`https://mcp.hnf1b.org/mcp`) to **Claude** (web + desktop), **ChatGPT**,
and coding agents **Claude Code** and **Codex CLI**.

Mirrors the SysNDD `McpInfoView` pattern. Each connection recipe was researched
against current (2026) official docs.

## What changed

- **`McpAccess.vue` + `/mcp` route** — hero, a notice that the address is an MCP
  transport endpoint for clients (not a browsable website), a "what you get"
  card, the server address with copy-to-clipboard, and four per-client cards
  (short steps + copy-pasteable command/config + the key caveat):
  - **Claude:** Customize → Connectors → Add custom connector (paste URL, no auth).
  - **ChatGPT:** Settings → Apps → Developer mode → Create app (No authentication).
  - **Claude Code:** `claude mcp add --transport http hnf1b-db <url>` / `.mcp.json`.
  - **Codex CLI:** `~/.codex/config.toml` `[mcp_servers.hnf1b-db] url=…` / `codex mcp add … --url`.
- **Footer** — internal-route MCP button (`mdi-robot-outline`, tooltip
  "Connect an AI agent (MCP)") placed next to the API docs link. `sortApiDocsLast()`
  forces API docs last among external links so the MCP button is reliably
  adjacent regardless of `footerConfig.json` ordering.

## Quality

- Theme-aware throughout (works in light **and** dark theme — no hardcoded
  colors; `text-*-emphasis` + `rgba(var(--v-theme-*))`).
- Copy action reports success/failure via snackbar + `logService` (no silent
  no-op).
- Adversarially reviewed across 4 dimensions (spec, code quality, a11y/dark
  theme, instruction accuracy); all findings addressed.

## Testing

- `frontend`: `npm test` → **432 passed** (+1 expected-fail); `eslint` clean;
  `prettier --check` (src + tests) clean; `npm run build` OK.
- New `McpAccess.spec.js` (endpoint, page-vs-endpoint clarity, all four clients,
  Claude Code/Codex snippets, clipboard); extended `FooterBar.spec.js` (DOM-order
  assertion that the MCP button is adjacent to API docs).
- Playwright-verified on the running stack (`/mcp` renders, footer button next
  to API, copy works, light + dark theme legible).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
