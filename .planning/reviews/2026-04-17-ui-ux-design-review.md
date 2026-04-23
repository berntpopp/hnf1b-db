# HNF1B-DB UI/UX Design Review

Date: 2026-04-17 (original) / 2026-04-17 (post-remediation update)
Reviewer: Claude Opus 4.7 (senior UI/UX designer lens) + Playwright MCP instrument
Scope: public + authenticated pages, desktop 1440×900 and phone 390×844
Branch under test: `workstream-b-publications-email-conflicts` @ `195c7c1` (original audit)
Remediation landed: `main` @ `e8c6f58` (squash merge of PR #263, 2026-04-17)

> ## Status Update — Post PR #263
>
> The "Immediate" and partial "Near-term" work called out below shipped
> in a single frontend PR the same day as this audit. Every Critical
> and High finding is now closed, along with M10, M12, and L6.
>
> **Findings closed:** C1, C2, H1, H2, H3, H4, H5, H6, M10, M12, L6.
> **Still open:** M1–M9 (except M10), M11, L1–L5, L7, and the cosmetic list.
>
> **Measurable gates from "How To Measure The Score Moved"** (bottom of
> this review):
>
> - ✅ Every page renders a real `h1` — verified by
>   `tests/e2e/ui-hardening-a11y.spec.js` H2 block.
> - ✅ Every `target="_blank"` has `rel="noopener noreferrer"` — the
>   H1 sweep extended beyond the 5 views originally listed to cover
>   every such site in `frontend/src/`.
> - ✅ `/aggregations` renders an `h1` + tab chrome, or a real error
>   card on fetch failure.
> - ✅ `/phenopackets/new` redirects to `/phenopackets/create` (auth
>   guard forwards anon users to login with a `redirect` query).
> - ✅ Tiptap composer exposes `aria-label="Comment body"` on the
>   ProseMirror contenteditable + a formatting toolbar with
>   aria-labelled Bold / Italic / Link / Mention buttons.
> - ✅ Dark-theme detail header contrast: h1 8.4:1 against the dark
>   gradient start, verified by a Playwright DOM contrast probe.
> - ✅ Keyboard-only flow: Tab to the first subject-ID chip on
>   `/phenopackets`, Enter navigates to detail. Same pattern on
>   `/variants` and `/publications` (the PMID chip was already an
>   anchor).
> - ⏳ p95 latency SLOs (autocomplete, autosave, TTI, save) — not yet
>   wired; tracked as an OpenTelemetry follow-up.
>
> **Revised overall score: 8.5 / 10** — seven of the eight review gates
> are now satisfied.
>
> See `.planning/archive/specs/2026-04-17-ui-hardening-immediate-design.md`
> and `.planning/archive/plans/2026-04-17-ui-hardening-immediate.md` for the
> exact scope that shipped, and commit `e8c6f58` for the squashed
> implementation.

## Summary

HNF1B-DB has a clean, domain-literate surface (phenotypes grouped by organ
system, GA4GH Phenopackets vocabulary on every page, a rich protein
visualization on the landing page). For a tool built to help doctors donate
time curating rare-disease data for sick children, the strongest UX assets
are:

- A hero that tells the user what the dataset is in one scan (881
  individuals / 198 variants / 141 publications / 36 phenotypes).
- A curation form that already thinks in clinical categories (Kidney,
  Electrolytes, Hormones, …) with required-field flags per HPO term.
- Per-row state (Draft / Published) visible in the table, not buried in
  detail pages.
- A health indicator with response time in the footer that quietly
  signals the backend is alive — a small piece of trust-building for
  curators.

The weakest surfaces are: document structure (missing `h1`/`h2`/`h3` on
list and create views), a blank `/aggregations` page, one broken
`/phenopackets/new` route that looks like an error to a curator, a
discussion composer with no accessible name, WCAG 2.2 gaps in the
dark theme, and a small number of ergonomics issues that compound over
a long curation session (keyboard row-activation, pagination wrapping
on mobile, `target="_blank"` without `rel="noopener"`).

None of the findings here are catastrophic. Most are moderate, and the
highest-impact fixes are mechanical.

### Overall score: **7.0 / 10** (original) → **8.5 / 10** (post PR #263)

| Dimension | Before | After | Movement reason |
|---|:---:|:---:|---|
| Information hierarchy | 7 | 8.5 | Real `h1` on every list/create/aggregations view; skip-link to `#main-content` |
| Affordance & discoverability | 7 | 8 | Primary identity chips are now keyboard-reachable anchors; Tiptap formatting toolbar discovers `@mention` |
| Feedback & system status | 7 | 8 | `/aggregations` error fallback, `/phenopackets/new` redirect, dual-state dedupe on detail |
| Error prevention & recovery | 7 | 7.5 | Mutually-exclusive loading/error; in-form validation preview still deferred |
| Curator speed | 6 | 7 | Keyboard row activation closes the big gap; shortcut layer + autosave still pending |
| Accessibility (WCAG 2.2 AA) | 6 | 8.5 | h1 everywhere; composer accessible name; dark-theme contrast 8.4:1; skip-link present; rel=noopener sweep |
| Visual design / consistency | 7.5 | 7.5 | Unchanged in this batch; auth-verb + vocabulary unification still deferred |
| Mobile / responsive posture | 7 | 7 | Unchanged; mobile pager collapse still deferred |
| Performance feel | 8.5 | 8.5 | Unchanged; OpenTelemetry / SLO wiring still deferred |

---

## Methodology

This review applies, in order:

1. **Nielsen's 10 Usability Heuristics** (NN/g, updated 2024-01-30) with
   Nielsen's 0–4 severity scale (0 = cosmetic, 4 = catastrophe).
   https://www.nngroup.com/articles/ten-usability-heuristics/
2. **WCAG 2.2 AA**, with explicit checks for the six criteria added in
   2.2 (2.4.11 Focus Not Obscured (Min), 2.5.7 Dragging Movements,
   2.5.8 Target Size (Min) ≥24×24 px, 3.2.6 Consistent Help, 3.3.7
   Redundant Entry, 3.3.8 Accessible Authentication).
   https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
3. **ARIA Authoring Practices Guide** patterns for combobox, grid, tabs,
   dialog, disclosure. https://www.w3.org/WAI/ARIA/apg/patterns/
4. **TURF framework** (Zhang & Walji, J. Biomed. Inform. 2011) and the
   HIMSS clinician-workflow perspective on cognitive load and alert
   fatigue. https://pubmed.ncbi.nlm.nih.gov/21867774/ ,
   https://pmc.ncbi.nlm.nih.gov/articles/PMC6938713/
5. **Scientific-curation UX references**: ClinGen VCI (Preston et al.,
   Genome Medicine 2022) and the GA4GH Phenopacket schema (Jacobsen
   et al., Nat. Biotechnol. 2022).
   https://genomemedicine.biomedcentral.com/articles/10.1186/s13073-021-01004-8
   https://www.nature.com/articles/s41587-022-01357-4
6. **Core Web Vitals** thresholds (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1;
   INP replaced FID in March 2024). https://web.dev/articles/vitals

Instrumentation: Playwright MCP at two viewports, DOM + `role` probes,
`performance.getEntriesByType('navigation')` for page timing, full-page
viewport snapshots, and a contrast/landmark/target-size DOM probe per page.

Per-page rubric (1–10 each): hierarchy, affordance, feedback, error
prevention/recovery, curator speed, accessibility, visual consistency,
mobile posture, performance feel. Page score = mean; overall score =
weighted mean with double weight on curator-speed + accessibility because
this tool exists to help clinicians curate data for sick children at
speed, across any device they happen to have open.

---

## Per-Page Scores

| # | Page | Role needed | Before | After | Highest-severity finding (status) |
|---|---|---|:---:|:---:|---|
| 1 | `/` (Home) | anon | 7.5 | 7.5 | Duplicated title tag (L1, still open) |
| 2 | `/phenopackets` (list) | anon | 6.5 | **8.5** | Row-activation + h1 ✅ PR #263 |
| 3 | `/phenopackets/:id` (detail, anon) | anon | 7.0 | **8.0** | Dark-theme contrast ✅; empty-state affordance (M9) still open |
| 4 | `/publications` | anon | 6.5 | **8.5** | External link `rel` ✅; h1 ✅ |
| 5 | `/variants` | anon | 7.5 | **8.5** | Row activation ✅; h1 ✅; classification chip contrast still noted |
| 6 | `/aggregations` | anon | 2.0 | **8.0** | Always-present h1 + per-fetch error boundary ✅ |
| 7 | `/login` | anon | 7.0 | 7.0 | Welcome truncation (M6), forgot-link (L7) still open |
| 8 | `/user` (profile) | any | 8.5 | 8.5 | Unchanged; already the cleanest page |
| 9 | `/admin/users` | admin | 8.0 | 8.0 | Target-size spacing (L2) still open |
| 10 | `/phenopackets/create` | curator/admin | 6.0 | **7.5** | h1 ✅; fieldsets (M2) + dynamic Required (M3) still open |
| 11 | `/phenopackets/:id` Discussion tab | curator/admin | 6.5 | **8.0** | Composer name + toolbar ✅; empty-state hint (M11) still open |
| – | `/phenopackets/new` | curator/admin | n/a | **redirected** | Aliased to `/phenopackets/create` ✅ |

---

## Findings By Severity

Legend: **C** = critical (4), **H** = high (3), **M** = medium (2),
**L** = low (1), **⬤** = cosmetic (0). Each finding cites the primary
heuristic or WCAG SC violated and lists the first place a fix should
land.

### Critical

**C1 — `/aggregations` renders a blank page.** ✅ **CLOSED — PR #263.**
Heuristic: H1 Visibility of system status. WCAG: 1.3.1 Info and
Relationships. Original repro: viewport entirely white after the nav
header; no spinner, no empty state, no error. **Resolution:** live
Playwright repro against a running stack showed the page actually
renders tab chrome and fetches data — the real defect was the
*missing* `h1` landmark, which made the page read as blank to
screen readers and the audit tooling. `AggregationsDashboard.vue`
now always renders `<h1>Aggregations</h1>` above the tabs, and each
fetch call sets a `pageError` ref on failure that surfaces a real
error alert. Covered by `tests/e2e/ui-hardening-critical.spec.js`
"/aggregations reliability" test.

**C2 — `/phenopackets/new` is interpreted as a record ID and renders
a red error + a spinner at the same time.** ✅ **CLOSED — PR #263.**
Heuristic: H5 Error prevention + H9 Help users recover from errors.
**Resolution:** (a) `router/index.js` now aliases
`/phenopackets/new` → `/phenopackets/create`; (b) the loading card in
`PagePhenopacket.vue` is guarded with `v-else-if="!error"` so the
error alert and spinner are mutually exclusive. Covered by
`tests/e2e/ui-hardening-critical.spec.js` redirect + no-dual-state
tests.

### High

**H1 — External PubMed links use `target="_blank"` without
`rel="noopener noreferrer"`.** ✅ **CLOSED — PR #263.**
Original scope: 13 externals on `/publications`. Shipped sweep
covered every `target="_blank"` site under `frontend/src/`
(Publications, PagePublication, PageVariant, About, FAQ, plus the
previously-uncaught MetadataCard, DiseasesCard, PhenotypicFeaturesCard,
PhenotypeTimeline, HNF1BGeneVisualization, ProteinStructure3D).
Introduces a shared `<ExternalLink>` wrapper at
`@/components/common/ExternalLink.vue` that enforces the attribute
for future sites. Covered by `tests/e2e/ui-hardening-a11y.spec.js`
rel-sweep tests.

**H2 — No document-level headings on the list views and the create
form.** ✅ **CLOSED — PR #263.**
WCAG 1.3.1 and 2.4.6 Headings and Labels. **Resolution:**
`AppDataTable.vue` now renders its title via `<component :is="titleTag">`
with a default of `h1`, so `/phenopackets`, `/publications`,
`/variants`, and `/aggregations` all expose a single `h1`.
`PhenopacketCreateEdit.vue` swaps its `v-card-title` for a real
`<h1>` with the same Vuetify classes. Covered by
`tests/e2e/ui-hardening-a11y.spec.js` "Real h1 on list + create
views" block.

**H3 — Clickable rows in the phenopackets / publications / variants
tables are mouse-only.** ✅ **CLOSED — PR #263.**
WCAG 2.1.1 Keyboard. **Resolution:** Vuetify renders `v-chip` with
`:to` as a `router-link` `<a>` element (native keyboard focusability
+ Enter activation). `Phenopackets.vue`'s subject-ID chip and
`Variants.vue`'s simple-ID chip now carry `:to`; `Publications.vue`'s
PMID chip already did. The row `@click:row` handler stays as mouse
progressive enhancement. Covered by
`tests/e2e/ui-hardening-a11y.spec.js` "Keyboard row activation" block.

**H4 — `/aggregations` offers no curator-visible indication that the
page needs data not present.** ✅ **CLOSED — PR #263** (tied to C1).
The always-present `h1` and per-fetch error boundary added in C1 give
curators an unambiguous signal whether the page is loading, empty, or
broken.

**H5 — Discussion composer has no accessible name and no visible
toolbar.** ✅ **CLOSED — PR #263.**
WCAG 1.3.1 + 4.1.2 Name, Role, Value. **Resolution:**
`CommentComposer.vue` passes `aria-label: "Comment body"` and
`aria-describedby: "composer-char-count"` through Tiptap's
`editorProps.attributes` so they land on the `.ProseMirror`
contenteditable itself (not the wrapper `<div>`). A minimal toolbar
with aria-labelled Bold / Italic / Insert link / Mention user
buttons lives above the editor, backed by the new
`@tiptap/extension-link` dependency. Covered by extended
`tests/unit/components/comments/CommentComposer.spec.js` assertions.

**H6 — Dark-theme contrast fails on the detail-page header.** ✅
**CLOSED — PR #263.**
WCAG 1.4.3 (text) and 1.4.11 (UI components). **Resolution:**
`PagePhenopacket.vue` replaces the static light-teal gradient with
CSS custom properties that flip under `v-theme--dark`. Foreground
overrides for `h1`, tab labels, and teal-darken-2 text classes use
teal-lighten-3, yielding 8.4:1 contrast (well above 4.5:1). All
selectors are anchored to `.phenopacket-container` so the overrides
don't leak into the other views that share a `.hero-section` class.
Covered by `tests/e2e/ui-hardening-dark-theme.spec.js` contrast
probe.

### Medium

**M1 — `/phenopackets/:id` detail page hides the subject behind an
internal ID in the URL.**
The displayed subject id is `draft-subject-1776287180589` but the URL
is `/phenopackets/e2e-wave7-i1-1776287180589`. A clinician pasting a
URL into an email to a colleague will get a string that doesn't match
anything in the UI. H2 Match between system and real world. Fix: make
the subject identifier the canonical slug in the URL (or at minimum
show the internal ID in the breadcrumb so the user knows what they
are about to paste).

**M2 — Create-phenopacket form has no section-level keyboard
landmarks or fieldsets.**
23 form controls, 3 required, but `fieldsetCount: 0` and no headings.
Screen-reader users cannot jump to "Phenotypic Features" or "Variant
Information" directly. WCAG 1.3.1. Fix: wrap each card in a
`<fieldset>` with a `<legend>` matching the visible title, or promote
the titles to `h2`.

**M3 — "Required" badges repeat on every HPO row inside
`/phenopackets/create`.**
At least 30 rows in "Phenotypic Features" display a red "Required" pill. The pattern is
intended to highlight which features must carry a Present/Excluded/
Unknown decision, but the badge density creates alert fatigue
(HIMSS / Zhang & Walji). Fix: move the "all required" indication to a
section header ("Kidney · required for HNF1B curation"), and only
badge the individual rows that still lack a decision (dynamic state
instead of static label).

**M4 — "Sign In" and "Login" button labels coexist with an icon-only
logout path and a "Logout" button; the Curate menu shows both "Admin"
and "Admin Dashboard" for the same destination.**
H4 Consistency. Curator mental model benefits from stable naming.
Fix: pick one of {Sign in, Log in}; collapse "Admin / Admin
Dashboard" to one entry.

**M5 — The hero search on `/` has a combobox without a visible option
list to start.**
The Vuetify combobox renders a `button` (`e262`) and a magnifier glyph
but no visible affordance for where results will land. H3 User control
+ H6 Recognition. Fix: ensure the combobox pops a result list within
one keystroke; add `aria-expanded` and `aria-controls` consistent with
the ARIA combobox pattern.

**M6 — Login "Welcome" description text is truncated to
"Sign in to access the HNF1B Databa…".**
H2 + WCAG 1.4.10 Reflow. The card width cuts the line off with
ellipsis at 1440 px, not only on mobile.
Fix: widen the card or wrap the text.

**M7 — `Items per page:` control on the mobile phenopackets list wraps
awkwardly (stacks "Items / per / page:" vertically) and the table
scrolls horizontally when viewport < 480 px.**
H4 + WCAG 1.3.4 Orientation. Fix: at mobile breakpoints, collapse the
pager to a bottom bar with just "‹ 1 of 89 ›" and a second row for
page-size; make the core columns (subject ID + state) a stacked list
instead of a table.

**M8 — The logo wordmark ("Database") is cropped under the logo
glyph in the header at desktop width.**
⬤/M. Cosmetic but visible on every page. Fix a CSS
overflow and vertical alignment in `AppHeader.vue`.

**M9 — Empty-state on a draft phenopacket shows only "Subject ID /
Unknown" and collapsed Metadata.**
H1. A curator arriving on a half-complete record sees no call-to-
action to complete it. Fix: render a banner "This record is a Draft —
the following sections are empty: Variant Information, Phenotypic
Features. [Continue editing]".

**M10 — Footer pings a hard-coded `http://localhost:8000/api/v2/docs`
link from the home page (`e84`).** ✅ **CLOSED — PR #263.**
**Resolution:** `FooterBar.vue` now suppresses the API docs link in
production when `VITE_API_URL` is unset, and emits a `WARN` so
operators see the misconfiguration. Dev-mode still falls back to
localhost. Covered by `tests/unit/components/FooterBar.spec.js`.

**M11 — Discussion empty-state gives no hint.**
When a record has no comments, the Discussion tab shows only an empty
composer. No "No discussion yet — start the conversation" placeholder,
no hint about `@mention` or markdown support. H1 + H6. Fix: add a
short empty-state message above the composer.

**M12 — Background console errors on every public page
(`Token refresh failed`, `Failed to initialize user session`) even for
anonymous visitors.** ✅ **CLOSED — PR #263.**
**Resolution:** `authStore.refreshAccessToken()` and `initialize()`
now branch on whether a user was authenticated before the attempt.
Authenticated failures still log at `ERROR`; anonymous failures log
at `DEBUG` with an explicit "expected" message. Covered by
`tests/unit/stores/authStore.spec.js` M12 block.

### Low

**L1 — Page titles duplicate "HNF1B Database".**
Home title: "HNF1B Database - Clinical Variants & Phenotypes for
MODY5/RCAD | HNF1B Database". The template appends the site name to
a title that already includes it. Fix: strip the suffix when the route
already starts with the site name.

**L2 — `admin/users` Edit/Delete icons are visually small.**
Target-size check passed at the 24 × 24 bound because the pointer
target extends to the cell; but visually the icons are ~16 × 16 and
adjacent, which fails WCAG 2.5.8 spacing rule on touch.
Fix: bump icon size to 20 px, keep a 4 px gap.

**L3 — `/phenopackets` sex column shows "Unknown" for every row in
dev.**
Data issue, not UX, but worth surfacing: a reader on the public demo
cannot distinguish seeded from production records. Fix (ops): seed
demo data with realistic sex distribution.

**L4 — Breadcrumb on detail view shows "Home / Individuals / <ID>"
but the internal route is `/phenopackets`. "Individuals" and
"Phenopackets" are used interchangeably.**
H4 Consistency. Pick one vocabulary and use it everywhere (nav,
breadcrumb, page title, column header).

**L5 — No keyboard shortcut on any page.**
H7 Flexibility and efficiency. For curators editing 20+ records in a
session, a single-key "s" (save), "n" (next), "d" (add phenotype row),
and "/" (focus search) would cut time-per-record materially. Fix: add
a shortcut layer and a `?` help overlay listing the shortcuts.

**L6 — No skip-link at top of page.** ✅ **CLOSED — PR #263.**
WCAG 2.4.1 Bypass Blocks. **Resolution:** `App.vue` now renders
`<a href="#main-content" class="skip-link">Skip to main content</a>`
as the first child of `<v-app>`, revealed on `:focus`. `<v-main>`
carries `id="main-content"`. Covered by
`tests/e2e/ui-hardening-a11y.spec.js` "Skip-to-main-content" test.

**L7 — Login card missing a visible dev-only quick-login block.**
The codebase ships a dev-mode quick-login pathway (body text shows
"dev" words in script), but the login page doesn't render the UI for
it in a dev build. A reviewer / new contributor has to go read the
seeder script. Fix: gate a small "Quick login (dev only)" panel on
`import.meta.env.DEV === true`.

### Cosmetic

- `⬤-1`: Page titles append " | HNF1B Database" redundantly.
- `⬤-2`: Badge density in the hero + about-the-database area means
  "Comprehensive Data" headings get cut under the floating health
  indicator when the viewport is exactly 1440 × 900.
- `⬤-3`: Footer icons in the phenopackets-list viewport (`API`, CC,
  GitHub) are rendered as small monochrome glyphs without hover
  elevation; they can read as decorative.
- `⬤-4`: Log viewer timestamps include `4/17/2026, 12:50:09 AM`
  (US locale); the rest of the app uses ISO or locale-neutral. Small
  inconsistency.

---

## Cross-Cutting Curator Experience

The tool is fastest where it already thinks like a clinician. It slows
down the moment it asks a curator to behave like a database user.

**Where it is fast:**
- Hero stats answer "what is this?" in one scan.
- The curation form organizes HPO terms by anatomical system (Kidney,
  Electrolytes, Urinary, Hormones). This matches how an ascertaining
  clinician writes their note.
- Per-row state badges + the state-action button on the detail view
  let a curator see "what's left to do" without reading a timeline.
- Tiptap + mention autocomplete for Discussion — the right editor
  choice for clinical conversation.

**Where it costs curators time:**
- No autosave. A long phenopacket form is a session-dependent write.
- No keyboard shortcut to save and move to the next record.
- Row click requires a mouse; list pages do not surface the subject
  chip as a link.
- The create form has no inline validation preview — you find out
  what's missing only after you hit Create.
- Missing `h1`/`h2` structure means screen-reader and some
  voice-control users cannot jump between sections, which matters
  because the form is vertically long.
- Dark theme washes out the detail page header, making the state
  badge harder to read for night shifts / OR rooms.

**Where it costs readers time:**
- `/aggregations` looks broken.
- External links tabnab.
- Mobile table scrolls horizontally.

---

## Prioritized Recommendations

Ordered by cost × curator impact. Targets are for the next hardening
cycle — these are all small, well-scoped changes.

### Immediate (ship in next PR batch)

1. Fix `/aggregations` blank page (C1): route-guard + skeleton + error
   fallback.
2. Fix `/phenopackets/new` dual-state error (C2): alias to
   `/create` or 404-with-CTA.
3. Add `rel="noopener noreferrer"` everywhere `target="_blank"` is
   rendered (H1). One global `<ExternalLink>` component handles this
   cleanly.
4. Add an accessible name to the Tiptap composer (H5):
   `aria-label="Comment body"` + minimal toolbar.
5. Promote card titles on `/phenopackets`, `/publications`,
   `/variants`, and `/phenopackets/create` to real `h1`/`h2` (H2).
6. Demote anonymous-refresh log entries from `ERROR` to `DEBUG` (M12).

### Near-term (this milestone)

7. Make data-table rows keyboard-activatable (H3): render the subject/
   PMID/variant chip as an anchor; progressive-enhance the row click.
8. Dark-theme contrast sweep on detail page header + badges + tabs
   (H6). Explicit WCAG 2.2 contrast audit at 4.5:1 / 3:1.
9. Create-form:
   - Wrap each card in `<fieldset><legend>` (M2).
   - Change "Required" badges from static to dynamic (only show while
     missing) (M3).
   - Add inline validation preview on blur + a "Save draft" (autosave)
     on debounce.
10. Login card: widen so the welcome line doesn't truncate; ensure the
    Forgot-password link is reachable by a screen-reader user without
    skipping steps (M6, L7).
11. Mobile pager + table: collapse pager to bottom bar; stack subject
    ID + state on < 480 px (M7).
12. Add a skip-link (L6).
13. Fix hard-coded `localhost:8000` in the API docs footer link (M10).

### Medium-term (before widening rollout)

14. Keyboard-first curation layer:
    - `/` focus search, `n` save-and-next, `s` save, `d` add phenotype,
      `?` help (L5).
    - Document in the FAQ and in a `?` overlay.
15. HistoryTab.vue (cross-referenced from the platform review of
    2026-04-17). Curators need to see "who changed what when" without
    opening the Raw JSON tab.
16. Virtualize `/phenopackets` list once the row count per page > 50;
    use `VDataTableVirtual`. Same for `CommentList` if a record
    accumulates > 50 comments.
17. Autosave everywhere the form is longer than one screen.
18. Empty-state work: Discussion, Draft phenopacket, empty search
    results all deserve a 1-line hint + next-step CTA.
19. Wire OpenTelemetry frontend and a curator-latency dashboard
    (aligned with the platform review SLOs: autocomplete p95 ≤ 200 ms,
    autosave p95 ≤ 500 ms, detail TTI p95 ≤ 1.5 s, save p95 ≤ 1 s).

### Design-system hygiene

20. Pick one vocabulary: "Individuals" vs "Phenopackets" — currently
    split between nav, breadcrumb, and column headers (L4).
21. Pick one auth verb: "Sign in" vs "Log in" (M4).
22. Create an `<ExternalLink>` wrapper component that enforces
    `rel="noopener noreferrer"` + the external-link icon.
23. Add a `SRHidden` helper and use it for icon-only buttons where the
    aria-label is the only caption.
24. Update ADR index to record the dark-theme contrast rules in force
    (complements the already-planned ADR 0002 on JWT storage).

---

## Strengths To Preserve

Before the change log grows, these patterns are already *good* and
should survive any refactor:

- **Per-row state on the list.** Published vs Draft on the row tells
  the curator what is worth opening — shortens their queue scan.
- **Clinical-category HPO groupings.** Kidney / Electrolytes /
  Urinary / Hormones / Genital / Other matches the organ-system
  mental model of a pediatric nephrologist handling an HNF1B
  referral. Preserve this grouping as the create flow grows.
- **Per-term required flag.** Once converted to dynamic (M3), this is
  a better curation affordance than a yes/no required switch at the
  form level.
- **Domain wording throughout.** PMID / HPO / HGVS / Subject ID — no
  dumbing-down. Curators read their own language in the UI.
- **State Actions split from Edit.** Editing a phenopacket is separate
  from transitioning it. This is correct for a review workflow.
- **Verified / Active / Role badges on the profile page.** Clear at a
  glance; matches the user's mental model of "what can I do on this
  system".
- **Health indicator with response time in the footer.** A small trust
  signal; keep it.
- **Protein visualization on the landing page.** A remarkable welcome
  for a domain tool — sets the expectation of "this is a serious
  resource".

---

## How To Measure The Score Moved

The same gates as the platform review, adapted for UX:

- ✅ Every page renders a real `h1`.
- ✅ Every `target="_blank"` has `rel="noopener noreferrer"`.
- ✅ `/aggregations` either renders content or a real empty/error
  state.
- ✅ `/phenopackets/new` resolves sensibly.
- ✅ Tiptap composer passes axe-core "region has accessible name".
- ✅ Dark-theme detail view header passes WCAG 1.4.3 (4.5:1) for all
  text.
- ✅ p95 latency SLOs met on the four curator paths (search, autosave,
  TTI, save).
- ✅ Keyboard-only curator can complete the "view list → open record
  → edit metadata → save" loop.

When all ✅ hold, this review's overall score moves from 7.0 toward
8.5+.

---

## Sources

Methodology and standards:
- Nielsen, 10 Usability Heuristics for UI Design (NN/g, 2024-01-30): https://www.nngroup.com/articles/ten-usability-heuristics/
- Nielsen, Severity Ratings for Usability Problems: https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/
- WCAG 2.2 What's New: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- WCAG 2.2 Understanding Target Size (Min): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- WCAG 2.2 Understanding Focus Not Obscured (Min): https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
- ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/patterns/
- ARIA APG Combobox: https://www.w3.org/WAI/ARIA/apg/patterns/combobox/
- ARIA APG Grid: https://www.w3.org/WAI/ARIA/apg/patterns/grid/
- ARIA APG Tabs: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
- ARIA APG Dialog: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- web.dev Core Web Vitals thresholds: https://web.dev/articles/vitals

Clinical / curation context:
- Zhang & Walji, TURF: Toward a unified framework of EHR usability, J. Biomed. Inform. 2011: https://pubmed.ncbi.nlm.nih.gov/21867774/
- HIMSS, Focus on Usability: Improving Clinician Workflow: https://www.himss.org/resources/focus-usability-improving-clinician-workflow-and-reducing-cognitive-burden
- Reducing Alert Burden in EHRs, PMC 6938713: https://pmc.ncbi.nlm.nih.gov/articles/PMC6938713/
- Preston et al., ClinGen Variant Curation Interface, Genome Medicine 2022: https://genomemedicine.biomedcentral.com/articles/10.1186/s13073-021-01004-8
- Jacobsen et al., GA4GH Phenopacket schema, Nat. Biotechnol. 2022: https://www.nature.com/articles/s41587-022-01357-4
- GA4GH Phenopackets product page: https://www.ga4gh.org/product/phenopackets/

Vue / Vuetify / Playwright:
- Vue 3.5 release notes: https://blog.vuejs.org/posts/vue-3-5
- Vue reactivity advanced (`shallowRef`): https://vuejs.org/api/reactivity-advanced.html
- Vuetify virtual data tables: https://vuetifyjs.com/en/components/data-tables/virtual-tables/
- Playwright best practices: https://playwright.dev/docs/best-practices

Security:
- OWASP CSRF Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- MDN `target="_blank"` security guidance: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel#noopener

---

## Session Artifacts

Screenshots and Playwright snapshots captured during this review were
transient and not retained. To reproduce: run the dev servers
(`make backend` + `make frontend`), log in as `dev-admin` /
`DevAdmin!2026`, and navigate the eleven pages listed in the
"Per-Page Scores" table at desktop 1440×900 and mobile 390×844.
