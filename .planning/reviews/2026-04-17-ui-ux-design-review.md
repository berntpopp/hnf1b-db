# HNF1B-DB UI/UX Design Review

Date: 2026-04-17
Reviewer: Claude Opus 4.7 (senior UI/UX designer lens) + Playwright MCP instrument
Scope: public + authenticated pages, desktop 1440×900 and phone 390×844
Branch under test: `workstream-b-publications-email-conflicts` @ `195c7c1`

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

### Overall score: **7.0 / 10**

| Dimension | Score | One-line |
|---|:---:|---|
| Information hierarchy | 7 | Strong on home; list/create pages lack real heading structure |
| Affordance & discoverability | 7 | Primary actions clear; row-activation model is mouse-only |
| Feedback & system status | 7 | Health indicator nice; toasts on save; some loading+error shown simultaneously |
| Error prevention & recovery | 7 | Required badges on form; no in-form validation preview on create |
| Curator speed | 6 | No keyboard shortcuts, no autosave, row clicks not keyboard-reachable |
| Accessibility (WCAG 2.2 AA) | 6 | Strong aria-labels on nav; missing headings; composer has no name; dark-theme contrast issues |
| Visual design / consistency | 7.5 | Vuetify tokens used well; a few hand-styled elements break the system |
| Mobile / responsive posture | 7 | Reader pages work at 390 px; tables scroll horizontally; labels wrap awkwardly |
| Performance feel | 8.5 | DCL 135–271 ms local; health widget honest about latency |

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

| # | Page | Role needed | Score | Highest-severity finding |
|---|---|---|:---:|---|
| 1 | `/` (Home) | anon | **7.5** | Lighthouse-style duplicated title tag; nice-to-fix |
| 2 | `/phenopackets` (list) | anon | **6.5** | Row-activation not keyboard-reachable; no page `h1` |
| 3 | `/phenopackets/:id` (detail, anon) | anon | **7.0** | Empty-state gives no next-step affordance for anon visitors |
| 4 | `/publications` | anon | **6.5** | External links missing `rel="noopener noreferrer"` — security + a11y |
| 5 | `/variants` | anon | **7.5** | Classification chip contrast borderline on some rows |
| 6 | `/aggregations` | anon | **2.0** | Page renders blank on a fresh load — catastrophic per H1 |
| 7 | `/login` | anon | **7.0** | "Sign in to access the HNF1B Databa…" truncated with ellipsis; no forgot-link rendered despite link existing |
| 8 | `/user` (profile) | any | **8.5** | Cleanest page in the app; only gripe is avatar/name echo |
| 9 | `/admin/users` | admin | **8.0** | Edit/delete targets ≤ 24 px (row actions); no bulk actions |
| 10 | `/phenopackets/create` | curator/admin | **6.0** | Zero `h*` landmarks on a 23-control form; "Required" badge repetition |
| 11 | `/phenopackets/:id` Discussion tab | curator/admin | **6.5** | Tiptap composer has no accessible name; dark-theme tab labels washed out |
| – | `/phenopackets/new` | curator/admin | **n/a** | Routes to error — see Finding F3 |

---

## Findings By Severity

Legend: **C** = critical (4), **H** = high (3), **M** = medium (2),
**L** = low (1), **⬤** = cosmetic (0). Each finding cites the primary
heuristic or WCAG SC violated and lists the first place a fix should
land.

### Critical

**C1 — `/aggregations` renders a blank page.**
Heuristic: H1 Visibility of system status. WCAG: 1.3.1 Info and
Relationships. After the nav header, the viewport is entirely white;
no spinner, no empty state, no error. A clinician landing here will
not know whether the tool is broken, slow, or they lack permission.
Reproduce: navigate to `/aggregations` as anonymous user on desktop.
Fix: either route-guard and redirect, or always render a
"Loading aggregations…" skeleton with a timeout fallback to a real
error card.

**C2 — `/phenopackets/new` is interpreted as a record ID and renders
a red error + a spinner at the same time.**
Heuristic: H5 Error prevention + H9 Help users recover from errors.
The UX paints both *Error Loading Phenopacket: Phenopacket 'new' not
found* and *Loading phenopacket…* at once, then stops. The route that
actually creates a phenopacket is `/phenopackets/create`, reached via
the Curate menu. A curator who types "new" (a very reasonable guess
after seeing other apps) will think the tool is broken.
Fix: (a) suppress the contradictory dual state; (b) alias
`/phenopackets/new` → `/phenopackets/create`, or reject it with a 404
view that links to the create page.

### High

**H1 — External PubMed links use `target="_blank"` without
`rel="noopener noreferrer"`.**
All thirteen externals on `/publications` are missing `rel="noopener"`.
This is both a known tabnabbing risk and a Lighthouse best-practice
fail. Fix: add `rel="noopener noreferrer"` wherever `target="_blank"`
is rendered — PubMed links, UniProt link on home (`e350`), GitHub
footer link, License link. Source: OWASP Cross-Site Request Forgery
Cheat Sheet + MDN `target` docs.

**H2 — No document-level headings on the list views and the create
form.**
WCAG 1.3.1 and 2.4.6 Headings and Labels. `/phenopackets`,
`/publications`, `/variants`, and `/phenopackets/create` return
`h1Count: 0` (or no headings at all for create). Screen readers cannot
navigate by heading on any of the main curator pages. The visual
"Phenopacket Registry", "Create New Phenopacket", etc. are styled
`div`s. Fix: promote the card titles to real `h1`/`h2`. The app
already does this correctly on the detail page ("Individual Details")
and profile page ("Dev Admin") — just lift the pattern.

**H3 — Clickable rows in the phenopackets / publications / variants
tables are mouse-only.**
WCAG 2.1.1 Keyboard. The rows carry
`class="v-data-table__tr--clickable"` and a JS handler, but have no
`tabindex`, no `role="link"` or `role="button"`, and no key handler
(`tabindex: null, role: null, hasClick: false`). A curator on
keyboard-only flow cannot reach the row. The subject-ID chip inside
the first cell is not an anchor either (`a` tag check returned none).
Fix: either render the subject-ID chip as an `<a>` linking to the
detail URL (preferred — then the row click becomes a progressive
enhancement), or set `tabindex="0" role="link"` on the row and wire
an Enter/Space handler.

**H4 — `/aggregations` offers no curator-visible indication that the
page needs data not present.**
If the blank page is an empty-state, it is indistinguishable from a
broken page. H1 + H5. Fix tied to C1.

**H5 — Discussion composer has no accessible name and no visible
toolbar.**
WCAG 1.3.1 + 4.1.2 Name, Role, Value. The Tiptap ProseMirror editor
is a `contenteditable="true"` `div` with `aria-label: null`, no
`aria-labelledby`, and no associated `label` element.
`hasPasswordShowToggle` detection aside, the composer is invisible to
screen readers until typed into. Adding `aria-label="Comment body"`
and an `aria-describedby` pointing at the "0 / 10000" counter is
one-line fixes. Also add a minimal formatting toolbar (bold, italic,
link, mention `@`) so the domain convention — mentioning a colleague
by `@username` — is discoverable.

**H6 — Dark-theme contrast fails on the detail-page header.**
WCAG 1.4.3 (text) and 1.4.11 (UI components). On dark mode, the "Individual
Details" heading, the tab labels (OVERVIEW / TIMELINE / RAW JSON), and
the "STATE ACTIONS" button become washed-out teal on teal-gradient.
The top hero band is still rendered with the light-theme teal gradient. Fix: ensure the detail
header respects `v-theme--dark`; recompute focus/text contrast in dark
theme against a darkened gradient (`#102A2B` → `#1E3A3A` instead of
`#B8E5D8` → …).

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
link from the home page (`e84`).**
H4 + operational. Production users will get a broken tab. Fix: use the
`VITE_API_URL` value at render time, not the dev default.

**M11 — Discussion empty-state gives no hint.**
When a record has no comments, the Discussion tab shows only an empty
composer. No "No discussion yet — start the conversation" placeholder,
no hint about `@mention` or markdown support. H1 + H6. Fix: add a
short empty-state message above the composer.

**M12 — Background console errors on every public page
(`Token refresh failed`, `Failed to initialize user session`) even for
anonymous visitors.**
H1. These are logged at `ERROR` level in the app's own log viewer, so
curators who click the footer log icon will see a scary red stream on
an otherwise working page. Fix: demote anonymous refresh failures to
`DEBUG` or `INFO`; only log `ERROR` when the user is authenticated.

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

**L6 — No skip-link at top of page.**
WCAG 2.4.1 Bypass Blocks. Screen-reader and keyboard-only users must
tab through the nav every time. Fix: add a visually-hidden
`a.skip-link` linking to `#main`.

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
