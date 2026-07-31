// @ts-check
/**
 * Curation console end-to-end verification.
 *
 * Curation console plan (docs/superpowers/plans/2026-07-30-curation-console.md)
 * Task 10 — "End-to-end verification against real sheet rows". Design spec:
 * docs/superpowers/specs/2026-07-30-curation-console-design.md §3.5, §5, §7.
 *
 * Tasks 1-9 (already landed) built the console at /phenopackets/create and
 * /phenopackets/:id/edit: six collapsible <CurationSection> blocks (Case,
 * Variant, Classification, Phenotypes, Age & Onset, Provenance & Notes) plus
 * a sticky <CompletenessRail>. This spec drives that console through the
 * browser exactly as a curator would and diffs the result against real rows
 * from the source spreadsheet (HNF1B_DataCuration.xlsx, sheet "Individuals",
 * 939 rows x 60 cols, extracted 2026-07-31 via a one-off openpyxl script --
 * not read at runtime, hardcoded below as SHEET_ROWS per the controller's
 * instruction).
 *
 * ── The central semantic this whole programme protects ─────────────────────
 * "Absence != not_reported." Absent means "not yet curated"; the literal
 * string 'not_reported' (selected from a vocabulary that has that member --
 * familyHistory, detectionMethod, segregation; NOT cohort, which has no such
 * member because the sheet states cohort for all 939 rows) means "the source
 * publication is silent". Area 5's test is the direct proof of this; every
 * other area is written to never conflate the two either (a real 'not
 * reported' sheet cell for a not_reported-capable field is always curated by
 * EXPLICITLY selecting "Not reported", never by leaving the control
 * untouched).
 *
 * ── Fields the console genuinely cannot express (documented, not silently
 *    skipped -- see the per-row `notes` and the assertions tied to them) ────
 *   D1. `Publication` -- the sheet stores an internal key ("pub021"), not a
 *       real PMID; the console's publication editor requires a numeric PMID.
 *       A synthetic, clearly-fake PMID is substituted per row.
 *   D2. `allelicState` (GENO zygosity) has no source column at all (design
 *       spec §3.2 marks it "--"); left unset for every acceptance row.
 *   D3. `hg19_INFO`/`hg38_INFO` land on the `coordinates` extension, which
 *       curationFields.js marks "derived, read-only" -- the console has no
 *       control that writes it, ever, even when the sheet carries a value.
 *   D4. A bare category onset value ("prenatal") has no TimeElement shape --
 *       TimeElementPicker only offers congenital / ISO-8601 age / gestational.
 *   D5. TimeElement has no not_reported concept at all (curationFields.js's
 *       own documented exception to "absence != not_reported" -- GA4GH does
 *       not model "the source is silent about onset" as a selectable value).
 *   D6. No disease-term control exists anywhere in the console; whenever an
 *       onset IS entered, AgeSection.vue defaults `diseases[].term` to the
 *       corpus's sole disease term (MONDO:0007669).
 *   D7. A CNV row's Varsome cell ("NA") is not a real hgvs.c value -- left
 *       blank rather than typed literally.
 *   D8. The ACMG criteria picker only recognises ACMG tokens (PM1, PP2, ...);
 *       a ClinGen CNV numeric-scoring string doesn't match any picker item,
 *       but the free-text field underneath it is the actual write path and
 *       stores the verbatim string regardless.
 *   D9. No email address reaches the phenopacket by any path, despite every
 *       one of the 3 real rows carrying a real institutional email in its
 *       `ReviewBy` column -- curatedBy/reviewer are stamped from the session
 *       display name, never from a form field.
 *  D10. The sheet's `Varsome` cell is a Varsome *display* string
 *       ("HNF1B(NM_000458.4):c.443C>T (p.Ser148Leu)"), not a coding-HGVS
 *       value. The migration parsed it down to "NM_000458.4:c.443C>T", which
 *       is what the migrated record stores and what the "Varsome (hgvs.c)"
 *       control asks for, so that is what is typed here. The verbatim cell
 *       is not lost -- `VariantReported` is the field that keeps the
 *       curator's own wording untouched.
 *  D11. No sheet column holds an ISCN karyotype, yet the backend rejects any
 *       structural variant that carries none, and it cannot be derived (the
 *       sheet's CNV coordinate has a start but no end). The curator supplies
 *       it; the value used here is the one the migrated record stores.
 */

import { test, expect } from '@playwright/test';
import { loginAsAdmin, primeAuthSession } from './helpers/auth';

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';

const SECTION_IDS = ['case', 'variant', 'classification', 'phenotypes', 'age', 'provenance'];

// ---------------------------------------------------------------------------
// Generic curation-console / Vuetify helpers
//
// `.v-select` scoped by visible label text, opened via .click() then picked
// via getByRole('option', ...), is the proven-working pattern already used
// by tests/e2e/aggregations.spec.js (`aggregationSelect` there) -- reused
// here rather than inventing a new interaction style.
// ---------------------------------------------------------------------------

function sectionLocator(page, id) {
  return page.locator(`#curation-section-${id}`);
}

async function expandSection(page, id) {
  const header = sectionLocator(page, id).locator('button.curation-section__header');
  await header.waitFor({ state: 'visible' });
  if ((await header.getAttribute('aria-expanded')) !== 'true') {
    await header.click();
  }
}

async function expandAllSections(page) {
  for (const id of SECTION_IDS) {
    await expandSection(page, id);
  }
}

function sectionBadge(page, id) {
  return sectionLocator(page, id).locator('.curation-section__badge');
}

/** A labeled Vuetify control (.v-input wrapper) scoped to one curation section. */
function sectionControl(page, sectionId, labelText) {
  return sectionLocator(page, sectionId).locator('.v-input', { hasText: labelText }).first();
}

/** A labeled control OUTSIDE any section (Phenopacket ID, Change Reason). */
function pageControl(page, labelText) {
  return page.locator('.v-input', { hasText: labelText }).first();
}

async function fillText(locator, value) {
  await locator.locator('input, textarea').first().fill(value);
}

/** Open a v-select/-combobox control and pick the option whose accessible name matches EXACTLY. */
async function selectExact(page, controlLocator, optionText) {
  await controlLocator.click();
  await page.getByRole('option', { name: optionText, exact: true }).click();
}

/**
 * Same, but substring match -- needed only for the CKD-stage picker, whose
 * custom #item template also renders the term's hpo_id as a subtitle, so its
 * accessible name is NOT just the label text.
 */
async function selectContains(page, controlLocator, optionSubstring) {
  await controlLocator.click();
  const escaped = optionSubstring.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  await page.getByRole('option', { name: new RegExp(escaped) }).click();
}

async function addChip(locator, value) {
  const input = locator.locator('input').first();
  await input.click();
  await input.fill(value);
  await input.press('Enter');
}

// ── Case section ─────────────────────────────────────────────────────────
async function addPublication(page) {
  await sectionLocator(page, 'case').getByRole('button', { name: 'Add Publication' }).click();
}

function pmidRows(page) {
  return sectionLocator(page, 'case').locator('.v-text-field', { hasText: 'PubMed ID (PMID)' });
}

// ── Variant section ──────────────────────────────────────────────────────
/**
 * Commit the detailed variant editor, and prove the commit happened.
 *
 * Committing clears the editor, so an empty "Variant as reported" is the
 * observable effect. Asserting it matters because the click is not guaranteed
 * to land: that field is an `auto-grow` textarea, so a long value makes the
 * form thousands of pixels tall and the button can still be settling when the
 * click is dispatched — this file's own 10,000-character case failed exactly
 * that way on CI's slower runner while passing locally every time.
 * `toPass` re-clicks if needed; a second click on an already-empty editor is
 * a no-op (VariantAnnotationForm returns early when there is nothing to add).
 */
async function saveDetailedVariant(page) {
  const section = sectionLocator(page, 'variant');
  const button = section.locator('[data-testid="save-detailed-variant-btn"]');
  const reported = section
    .locator('.v-input', { hasText: 'Variant as reported' })
    .first()
    .locator('textarea:not([aria-hidden="true"])');

  await expect(async () => {
    await button.click();
    await expect(reported).toHaveValue('', { timeout: 2_000 });
  }).toPass({ timeout: 20_000 });
}

// ── Phenotypes section ───────────────────────────────────────────────────
function phenotypeRow(page, hpoId) {
  return page.locator('.phenotype-item', { hasText: hpoId });
}

async function setPhenotypePresent(page, hpoId, laterality) {
  const row = phenotypeRow(page, hpoId);
  await row.scrollIntoViewIfNeeded();
  await row.locator('button').first().click(); // unknown -> present
  if (laterality) {
    await selectExact(page, row.locator('.v-select'), laterality);
  }
}

/** From a fresh "unknown" state (2 clicks: unknown -> present -> excluded). */
async function setPhenotypeExcluded(page, hpoId) {
  const row = phenotypeRow(page, hpoId);
  await row.scrollIntoViewIfNeeded();
  const btn = row.locator('button').first();
  await btn.click(); // unknown -> present
  await btn.click(); // present -> excluded
}

/**
 * A SINGLE click on an already-"present" term's cycle button.
 * cycleState's 3-state machine is unknown -> present -> excluded -> (removed,
 * back to unknown) -- so clicking a term that is ALREADY present needs
 * exactly one click to reach "excluded", never two (two would cycle it all
 * the way through excluded and back out to removed/unknown). Kept distinct
 * from setPhenotypeExcluded, which assumes the opposite starting point.
 */
async function clickPresentToExcluded(page, hpoId) {
  const row = phenotypeRow(page, hpoId);
  await row.scrollIntoViewIfNeeded();
  await row.locator('button').first().click();
}

async function setCkdStage(page, label) {
  const control = sectionControl(page, 'phenotypes', 'Select CKD Stage');
  await selectContains(page, control, label);
}

// ── Age & onset section ──────────────────────────────────────────────────
/** @param {'Onset'|'Age reported'} pickerLabel */
function timeElementPicker(page, pickerLabel) {
  return sectionLocator(page, 'age').locator('.time-element-picker', {
    has: page.locator(`[aria-label="${pickerLabel} mode"]`),
  });
}

/**
 * Select a picker mode, idempotently.
 *
 * The mode toggle is a v-btn-toggle *without* `mandatory` on purpose: clicking
 * the active mode clears it, which is how the picker expresses "not yet
 * curated" (TimeElementPicker.vue:42). So a blind .click() on an already-active
 * mode does the opposite of what the caller wants and hides the value inputs.
 * This matters on the edit route, where the picker arrives pre-populated.
 */
async function ensureTimeMode(picker, modeLabel) {
  const button = picker.getByRole('button', { name: modeLabel, exact: true });
  const classes = (await button.getAttribute('class')) || '';
  if (!classes.includes('v-btn--active')) {
    await button.click();
  }
}

async function setTimeElementGestational(picker, weeks) {
  await ensureTimeMode(picker, 'Gestational');
  await fillText(picker.locator('.v-input', { hasText: 'gestational weeks' }), String(weeks));
}

async function setTimeElementAgeYears(picker, years) {
  await ensureTimeMode(picker, 'Age');
  await fillText(picker.locator('.v-input', { hasText: 'years' }), String(years));
}

// ---------------------------------------------------------------------------
// API helpers (mirrors the pattern already used by dual-read-invariant.spec.js
// and ui-hardening-dark-theme.spec.js: raw request.* calls, not the frontend
// apiClient wrapper, since Playwright's `request` fixture is what talks to
// the backend from the test, independent of the browser page).
// ---------------------------------------------------------------------------

async function login(page, request) {
  const tokens = await loginAsAdmin(request, API_BASE);
  await primeAuthSession(page, tokens);
  return tokens;
}

async function fetchPhenopacket(request, token, id) {
  const resp = await request.get(`${API_BASE}/phenopackets/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.ok(), `GET /phenopackets/${id} failed: ${await resp.text()}`).toBeTruthy();
  const body = await resp.json();
  return body.phenopacket;
}

async function gotoCreate(page) {
  await page.goto('/phenopackets/create', { waitUntil: 'networkidle' });
  await expect(page.locator('h1')).toContainText('Create New Phenopacket');
}

// ---------------------------------------------------------------------------
// Document-side accessors (mirror frontend/src/utils/curationFields.js's own
// accessors, so a verification bug here can be cross-checked against that
// file rather than re-deriving the path independently).
// ---------------------------------------------------------------------------

function firstVariationDescriptor(pp) {
  return pp?.interpretations?.[0]?.diagnosis?.genomicInterpretations?.[0]?.variantInterpretation
    ?.variationDescriptor;
}

function firstGenomicInterpretation(pp) {
  return pp?.interpretations?.[0]?.diagnosis?.genomicInterpretations?.[0];
}

function findExtension(extensions, name) {
  return (extensions || []).find((e) => e.name === name);
}

function findPhenotype(pp, hpoId) {
  return (pp.phenotypicFeatures || []).find((f) => f.type?.id === hpoId);
}

function findExpression(descriptor, predicate) {
  return (descriptor?.expressions || []).find(predicate);
}

/** No '@' anywhere in the serialized document -- the strongest form of D9. */
function containsEmail(pp) {
  return JSON.stringify(pp).includes('@');
}

// ---------------------------------------------------------------------------
// SHEET_ROWS -- 3 real rows extracted 2026-07-31 from
// HNF1B_DataCuration.xlsx, sheet "Individuals" (939 rows x 60 cols), via:
//   uv run --with openpyxl python -c "..."
// `sheet` holds the raw cell values (for traceability); the rest of each
// entry is how THIS test enters that row through the console UI, and what it
// expects the saved record to contain.
// ---------------------------------------------------------------------------

const SHEET_ROWS = [
  {
    key: 'row1-snv-case-report',
    description: 'SNV, PublicationType=case_report, born (Mayer_1, report_id 87)',
    sheet: {
      report_id: 87,
      Publication: 'pub021',
      PublicationType: 'case_report',
      IndividualIdentifier: 'Mayer_1',
      Cohort: 'born',
      Sex: 'male',
      AgeOnset: 'prenatal',
      AgeReported: '23y',
      VariantType: 'SNV',
      VariantReported: 'S148L (C443T)',
      ID: null,
      hg19: 'chr17-36099532-G-A',
      hg38: 'chr17-37739541-G-A',
      verdict_classification: 'Pathogenic',
      criteria_classification:
        'PM1_Moderate, PM2_Supporting, PP2_Supporting, PP3_Supporting, PP1_Strong, PS2_Strong',
      system_classification: 'ACMG sequence variants interpretation guidelines',
      date_classification: '2022-06-06',
      Varsome: 'HNF1B(NM_000458.4):c.443C>T\n (p.Ser148Leu)',
      DetecionMethod: 'Sanger',
      Segregation: 'de novo',
      FamilyHistory: 'negative',
      Comment:
        'Low birth weight (2250 g; gestational age, 39 weeks). Tertiary hyperparathyroidism.',
      DupCheck: 'duplicate, report_id 86',
      ReviewBy: 'bernt.popp@gmail.com',
    },
    case: {
      cohortLabel: 'Born',
      cohortValue: 'born',
      sexLabel: 'Male',
      sexValue: 'MALE',
      identifier: 'Mayer_1',
      pmid: '19000087', // D1: synthetic, sheet's Publication cell is the internal key 'pub021'
      publicationTypeLabel: 'Case report',
      publicationTypeValue: 'case_report',
      familyHistoryLabel: 'Negative',
      familyHistoryValue: 'negative',
    },
    variant: {
      reported: 'S148L (C443T)',
      variantType: { label: 'SNV', id: 'SO:0001483' },
      isStructural: false,
      hg38: 'chr17-37739541-G-A',
      hg19: 'chr17-36099532-G-A',
      // D7 sibling: the sheet's own embedded newline (a copy/paste artefact
      // in the Varsome cell, not part of the HGVS notation) is collapsed to
      // a single space -- Varsome is not covered by VariantReported's
      // verbatim guarantee.
      varsome: 'NM_000458.4:c.443C>T', // D10
      dbVarId: null,
      segregationLabel: 'De novo',
      segregationValue: 'de_novo',
      detectionMethodLabel: 'Sanger sequencing',
      detectionMethodValue: 'sanger',
    },
    classification: {
      verdictLabel: 'Pathogenic',
      verdictValue: 'PATHOGENIC',
      criteria:
        'PM1_Moderate, PM2_Supporting, PP2_Supporting, PP3_Supporting, PP1_Strong, PS2_Strong',
      systemLabel: 'ACMG',
      systemValue: 'acmg',
      date: '2022-06-06',
      comment: null,
    },
    phenotypes: {
      ckdStage: null,
      present: [
        { hpoId: 'HP:0033132', laterality: 'Bilateral' }, // Hyperechogenicity
        { hpoId: 'HP:0000107', laterality: 'Bilateral' }, // RenalCysts
        { hpoId: 'HP:0000003', laterality: 'Bilateral' }, // MulticysticDysplasticKidney
        { hpoId: 'HP:0000089', laterality: 'Bilateral' }, // RenalHypoplasia
        { hpoId: 'HP:0004904' }, // MODY
        { hpoId: 'HP:0002594' }, // PancreaticHypoplasia
        { hpoId: 'HP:0000843' }, // Hyperparathyroidism
      ],
      excluded: [
        'HP:0000122', // SolitaryKidney
        'HP:0000079', // UrinaryTractMalformation
        'HP:0000078', // GenitalTractAbnormality
        'HP:0001738', // ExocrinePancreaticInsufficiency
        'HP:0012758', // NeurodevelopmentalDisorder
        'HP:0000708', // MentalDisease
        'HP:0001250', // Seizures
        'HP:0012443', // BrainAbnormality
        'HP:0002910', // ElevatedHepaticTransaminase
      ],
      // RenalInsufficancy='Stage 5 chronic kidney disease' -> HP:0003774 via
      // the CKD-Stages picker, not the RenalInsufficancy loop above.
      renalInsufficancyCkd: { label: 'Stage 5 chronic kidney disease', hpoId: 'HP:0003774' },
      // Representative "not reported" columns -- spot-checked for absence,
      // not exhaustively re-asserted for all ~13 (KidneyBiopsy,
      // AntenatalRenalAbnormalities, Hypomagnesemia..Gout, PrematureBirth,
      // CongenitalCardiacAnomalies, EyeAbnormality, ShortStature,
      // MusculoskeletalFeatures, DysmorphicFeatures, AbnormalLiverPhysiology).
      absentChecks: ['HP:0100611', 'HP:0012210', 'HP:0002917', 'HP:0001622'],
    },
    // D4: AgeOnset='prenatal' has no TimeElement shape -- left uncurated.
    age: { onset: null, reportedYears: 23 },
    provenance: {
      comment:
        'Low birth weight (2250 g; gestational age, 39 weeks). Tertiary hyperparathyroidism.',
      duplicateCheck: 'duplicate, report_id 86',
    },
  },
  {
    key: 'row2-17q12-deletion',
    description: '17q11-q12 deletion, CNV-shaped fields, born (sanna-cherchi_ITA_7, report_id 3)',
    sheet: {
      report_id: 3,
      Publication: 'pub107',
      PublicationType: 'case_series',
      IndividualIdentifier: 'sanna-cherchi_ITA_7',
      Cohort: 'born',
      Sex: 'unspecified',
      AgeOnset: 'not reported',
      AgeReported: 'not reported',
      VariantType: 'Deletion',
      VariantReported: '17q11-q12 deletion',
      ID: 'dbVar:nssv1184554',
      hg19_INFO: 'IMPRECISE;SVTYPE=DEL;END=36192489;SVLEN=-1377417',
      hg19: 'chr17-34815071-T-<DEL>',
      hg38_INFO: 'IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610',
      hg38: 'chr17-36459258-T-<DEL>',
      verdict_classification: 'Pathogenic',
      criteria_classification: '1A, 2A, 3A, 4Cx6(0.9), 4Lx1(0.15)',
      system_classification: 'ClinGen CNV Interpretation Guidelines',
      date_classification: '2022-06-06',
      Varsome: 'NA',
      DetecionMethod: 'NGS',
      Segregation: 'not reported',
      FamilyHistory: 'not reported',
      Comment: 'To phenotype: bilateral or unilateral cysts unspecified',
      DupCheck: 'done',
      ReviewBy: 'Georgia.Vasileiou@uk-erlangen.de',
    },
    case: {
      cohortLabel: 'Born',
      cohortValue: 'born',
      sexLabel: 'Unknown',
      sexValue: 'UNKNOWN_SEX',
      identifier: 'sanna-cherchi_ITA_7',
      pmid: '19000003', // D1: synthetic, sheet's Publication cell is 'pub107'
      publicationTypeLabel: 'Case series',
      publicationTypeValue: 'case_series',
      // Real sheet value 'not reported' -> curated as the explicit
      // not_reported vocabulary member, never left absent (design spec's
      // central semantic: absence != not_reported).
      familyHistoryLabel: 'Not reported',
      familyHistoryValue: 'not_reported',
    },
    variant: {
      reported: '17q11-q12 deletion',
      variantType: { label: 'deletion', id: 'SO:0000159' },
      isStructural: true,
      // D11: no sheet column holds ISCN, but the backend rejects any
      // structural variant without one and nothing can derive it (the
      // sheet's CNV coordinate has a start, no end). This is the value the
      // migrated record stores for this individual.
      iscn: 'del(17)(q12)',
      hg38: 'chr17-36459258-T-<DEL>',
      hg19: 'chr17-34815071-T-<DEL>',
      // D7: 'NA' is not a real hgvs.c value -- left blank.
      varsome: null,
      dbVarId: 'dbVar:nssv1184554',
      segregationLabel: 'Not reported',
      segregationValue: 'not_reported',
      detectionMethodLabel: 'Next-generation sequencing',
      detectionMethodValue: 'ngs',
    },
    classification: {
      verdictLabel: 'Pathogenic',
      verdictValue: 'PATHOGENIC',
      // D8: ClinGen CNV numeric scoring -- the ACMG criteria picker
      // recognises none of these tokens, but the free-text field is the
      // actual write path and stores it verbatim regardless.
      criteria: '1A, 2A, 3A, 4Cx6(0.9), 4Lx1(0.15)',
      systemLabel: 'ClinGen CNV',
      systemValue: 'clingen_cnv',
      date: '2022-06-06',
      comment: null,
    },
    phenotypes: {
      present: [
        { hpoId: 'HP:0000107', laterality: 'Bilateral' }, // RenalCysts
        { hpoId: 'HP:0000079', laterality: 'Unilateral' }, // UrinaryTractMalformation
        { hpoId: 'HP:0004904' }, // MODY
        { hpoId: 'HP:0012758' }, // NeurodevelopmentalDisorder
      ],
      excluded: [],
      renalInsufficancyCkd: null, // RenalInsufficancy='not reported' -> no CKD entry at all
      absentChecks: ['HP:0033132', 'HP:0100611', 'HP:0000089'],
    },
    // D5: both onset and age-reported are 'not reported' in the sheet --
    // TimeElement has no not_reported representation, so this collapses to
    // "absent" (the one documented exception to absence != not_reported).
    age: { onset: null, reportedYears: null },
    provenance: {
      comment: 'To phenotype: bilateral or unilateral cysts unspecified',
      duplicateCheck: 'done',
    },
  },
  {
    key: 'row3-fetus-gestational',
    description: 'SNV fetus with gestational age (Case 3 / pub045, report_id 195)',
    sheet: {
      report_id: 195,
      Publication: 'pub045',
      PublicationType: 'case_series',
      IndividualIdentifier: 'Case 3',
      Cohort: 'fetus',
      Sex: 'male',
      AgeOnset: '28w',
      AgeReported: '35wks',
      VariantType: 'SNV',
      VariantReported: 'exon 4 (c.827G > A–p. R276Q)',
      ID: null,
      hg19: 'chr17-36091804-C-T',
      hg38: 'chr17-37731813-C-T',
      verdict_classification: 'Pathogenic',
      criteria_classification: 'PM2_Supporting, PP2_Supporting, PP3_Supporting, PS2_VeryStrong',
      comment_classification: '4 independent de novo descriptions',
      system_classification: 'ACMG sequence variants interpretation guidelines',
      date_classification: '2022-06-06',
      Varsome: 'HNF1B(NM_000458.4):c.827G>A\n (p.Arg276Gln)',
      DetecionMethod: 'Sanger',
      Segregation: 'de novo',
      FamilyHistory: 'negative',
      Comment: 'premature birth: Stillborn (35 weeks)',
      DupCheck: 'duplicate, report_id 193',
      ReviewBy: 'Jonathan.deFallois@medizin.uni-leipzig.de',
    },
    case: {
      cohortLabel: 'Fetus',
      cohortValue: 'fetus',
      sexLabel: 'Male',
      sexValue: 'MALE',
      identifier: 'Case 3',
      pmid: '19000195', // D1: synthetic, sheet's Publication cell is 'pub045'
      publicationTypeLabel: 'Case series',
      publicationTypeValue: 'case_series',
      familyHistoryLabel: 'Negative',
      familyHistoryValue: 'negative',
    },
    variant: {
      reported: 'exon 4 (c.827G > A–p. R276Q)',
      variantType: { label: 'SNV', id: 'SO:0001483' },
      isStructural: false,
      hg38: 'chr17-37731813-C-T',
      hg19: 'chr17-36091804-C-T',
      varsome: 'NM_000458.4:c.827G>A', // D10
      dbVarId: null,
      segregationLabel: 'De novo',
      segregationValue: 'de_novo',
      detectionMethodLabel: 'Sanger sequencing',
      detectionMethodValue: 'sanger',
    },
    classification: {
      verdictLabel: 'Pathogenic',
      verdictValue: 'PATHOGENIC',
      criteria: 'PM2_Supporting, PP2_Supporting, PP3_Supporting, PS2_VeryStrong',
      systemLabel: 'ACMG',
      systemValue: 'acmg',
      date: '2022-06-06',
      comment: '4 independent de novo descriptions',
    },
    phenotypes: {
      present: [
        { hpoId: 'HP:0033132', laterality: 'Bilateral' }, // Hyperechogenicity
        { hpoId: 'HP:0000107', laterality: 'Bilateral' }, // RenalCysts
        { hpoId: 'HP:0000003', laterality: 'Bilateral' }, // MulticysticDysplasticKidney
        { hpoId: 'HP:0012210' }, // AntenatalRenalAbnormalities
        { hpoId: 'HP:0002594' }, // PancreaticHypoplasia
        { hpoId: 'HP:0001622' }, // PrematureBirth
        { hpoId: 'HP:0004322' }, // ShortStature
      ],
      excluded: [
        'HP:0100611', // KidneyBiopsy
        'HP:0000089', // RenalHypoplasia
        'HP:0000122', // SolitaryKidney
        'HP:0001627', // CongenitalCardiacAnomalies
        'HP:0000478', // EyeAbnormality
        'HP:0033127', // MusculoskeletalFeatures
      ],
      // RenalInsufficancy='chronic kidney disease, not specified' ->
      // HP:0012622, a REGULAR tri-state item, NOT the CKD-Stages picker:
      // the backend's CKD_STAGE_IDS set (app/ontology/routers.py) only
      // covers the five numbered stages, not the unspecified-stage term.
      renalInsufficancy: 'HP:0012622',
      renalInsufficancyCkd: null,
      absentChecks: ['HP:0000079', 'HP:0004904', 'HP:0001999'],
    },
    // The fetus row: both onset and age-reported are gestational-week
    // values with no day component in the sheet -- this is the row that
    // exercises Task 9's gestational-age fix end to end.
    age: { onsetGestationalWeeks: 28, reportedGestationalWeeks: 35 },
    provenance: {
      comment: 'premature birth: Stillborn (35 weeks)',
      duplicateCheck: 'duplicate, report_id 193',
    },
  },
];

// ---------------------------------------------------------------------------
// Section fillers, shared by the acceptance test and (partially) the
// round-trip test.
// ---------------------------------------------------------------------------

async function fillCaseSection(page, row, phenopacketId, subjectId) {
  await fillText(pageControl(page, 'Phenopacket ID'), phenopacketId);
  await expandSection(page, 'case');
  await fillText(sectionControl(page, 'case', 'Subject ID'), subjectId);
  await selectExact(page, sectionControl(page, 'case', 'Sex'), row.case.sexLabel);
  await selectExact(page, sectionControl(page, 'case', 'Cohort'), row.case.cohortLabel);
  await addChip(sectionControl(page, 'case', 'Individual identifiers'), row.case.identifier);
  await selectExact(
    page,
    sectionControl(page, 'case', 'Publication type'),
    row.case.publicationTypeLabel
  );
  await selectExact(
    page,
    sectionControl(page, 'case', 'Family history'),
    row.case.familyHistoryLabel
  );
  await addPublication(page);
  await fillText(pmidRows(page).first(), row.case.pmid);
}

async function fillVariantSection(page, row) {
  await expandSection(page, 'variant');
  await selectExact(
    page,
    sectionControl(page, 'variant', 'Detection method'),
    row.variant.detectionMethodLabel
  );
  await fillText(sectionControl(page, 'variant', 'Variant as reported'), row.variant.reported);
  await selectExact(
    page,
    sectionControl(page, 'variant', 'Variant type'),
    row.variant.variantType.label
  );
  if (row.variant.iscn) {
    await fillText(sectionControl(page, 'variant', 'Karyotype (ISCN)'), row.variant.iscn);
  }
  await fillText(sectionControl(page, 'variant', 'hg38 (GRCh38)'), row.variant.hg38);
  await fillText(sectionControl(page, 'variant', 'hg19 (GRCh37)'), row.variant.hg19);
  if (row.variant.varsome) {
    await fillText(sectionControl(page, 'variant', 'Varsome (hgvs.c)'), row.variant.varsome);
  }
  if (row.variant.dbVarId) {
    await addChip(sectionControl(page, 'variant', 'dbVar ID(s)'), row.variant.dbVarId);
  }
  await selectExact(
    page,
    sectionControl(page, 'variant', 'Segregation'),
    row.variant.segregationLabel
  );
  await saveDetailedVariant(page);
}

async function fillClassificationSection(page, row) {
  await expandSection(page, 'classification');
  await selectExact(
    page,
    sectionControl(page, 'classification', 'ACMG verdict'),
    row.classification.verdictLabel
  );
  await fillText(
    sectionControl(page, 'classification', 'Classification criteria (free text)'),
    row.classification.criteria
  );
  await selectExact(
    page,
    sectionControl(page, 'classification', 'Classification system'),
    row.classification.systemLabel
  );
  await fillText(
    sectionControl(page, 'classification', 'Classification date'),
    row.classification.date
  );
  if (row.classification.comment) {
    await fillText(
      sectionControl(page, 'classification', 'Classification comment'),
      row.classification.comment
    );
  }
}

async function fillPhenotypesSection(page, row) {
  await expandSection(page, 'phenotypes');
  await expect(page.locator('.phenotype-item').first()).toBeVisible({ timeout: 15_000 });

  if (row.phenotypes.renalInsufficancyCkd) {
    await setCkdStage(page, row.phenotypes.renalInsufficancyCkd.label);
  }
  if (row.phenotypes.renalInsufficancy) {
    await setPhenotypePresent(page, row.phenotypes.renalInsufficancy);
  }
  for (const entry of row.phenotypes.present) {
    await setPhenotypePresent(page, entry.hpoId, entry.laterality);
  }
  for (const hpoId of row.phenotypes.excluded) {
    await setPhenotypeExcluded(page, hpoId);
  }
}

async function fillAgeSection(page, row) {
  await expandSection(page, 'age');
  if (row.age.onsetGestationalWeeks !== undefined) {
    await setTimeElementGestational(
      timeElementPicker(page, 'Onset'),
      row.age.onsetGestationalWeeks
    );
  }
  if (row.age.reportedGestationalWeeks !== undefined) {
    await setTimeElementGestational(
      timeElementPicker(page, 'Age reported'),
      row.age.reportedGestationalWeeks
    );
  }
  if (row.age.reportedYears) {
    await setTimeElementAgeYears(timeElementPicker(page, 'Age reported'), row.age.reportedYears);
  }
}

async function fillProvenanceSection(page, row) {
  await expandSection(page, 'provenance');
  await fillText(sectionControl(page, 'provenance', 'Comment'), row.provenance.comment);
  await fillText(
    sectionControl(page, 'provenance', 'Duplicate check'),
    row.provenance.duplicateCheck
  );
}

/**
 * Click Save and wait for the success redirect to THAT record's detail page.
 *
 * The expected id is required, not optional: a bare `/\/phenopackets\/[^/]+$/`
 * also matches `/phenopackets/create`, so it resolves instantly on the page we
 * are still sitting on and reports success for a save that never happened.
 * Every later assertion then fails somewhere unrelated (a 404 on GET, a
 * missing section on the edit route) and hides the real cause.
 *
 * On timeout, surface the app's own error alert instead of a bare Playwright
 * timeout — a rejected save is a fact about the app, and the message is the
 * evidence.
 */
async function submitForm(page, phenopacketId) {
  if (!phenopacketId) {
    throw new Error('submitForm requires the expected phenopacket id');
  }
  await page.locator('button[type="submit"]').click();
  try {
    await page.waitForURL(`**/phenopackets/${phenopacketId}`, { timeout: 30_000 });
  } catch {
    const alerts = page.locator('.v-alert');
    const count = await alerts.count();
    const rendered = count ? (await alerts.allInnerTexts()).join(' | ') : '(no .v-alert rendered)';
    throw new Error(
      `Save did not redirect to /phenopackets/${phenopacketId}.\n` +
        `  still at: ${page.url()}\n` +
        `  app said: ${rendered}`
    );
  }
}

/** Full console fill for one SHEET_ROWS entry, returns the created phenopacket_id. */
async function enterRow(page, row) {
  const ts = Date.now();
  const phenopacketId = `e2e-curation-${row.key}-${ts}`;
  const subjectId = `${phenopacketId}-subject`;

  await gotoCreate(page);
  await fillCaseSection(page, row, phenopacketId, subjectId);
  await fillVariantSection(page, row);
  await fillClassificationSection(page, row);
  await fillPhenotypesSection(page, row);
  await fillAgeSection(page, row);
  await fillProvenanceSection(page, row);
  await submitForm(page, phenopacketId);

  return { phenopacketId, subjectId };
}

/** Field-by-field diff of a fetched phenopacket against the SHEET_ROWS entry it was entered from. */
function assertRowMatches(pp, row, subjectId) {
  // -- Case --
  expect(pp.subject.id).toBe(subjectId);
  expect(pp.subject.sex).toBe(row.case.sexValue);
  expect(pp.subject.alternateIds).toContain(row.case.identifier);
  expect(pp.hnf1bCuration.cohort).toBe(row.case.cohortValue);
  expect(pp.hnf1bCuration.publicationType).toBe(row.case.publicationTypeValue);
  expect(pp.hnf1bCuration.familyHistory).toBe(row.case.familyHistoryValue);
  expect(pp.metaData.externalReferences).toContainEqual({ id: `PMID:${row.case.pmid}` });

  // -- Variant -- VariantReported is stored verbatim, byte for byte
  // (the defect this whole programme exists to end).
  const descriptor = firstVariationDescriptor(pp);
  expect(descriptor.description).toBe(row.variant.reported);
  // VariantType lands on structuralType for deletion/duplication and on
  // molecularConsequences for SNV/indel, exactly as the corpus partitions
  // them (soTerms.js::STRUCTURAL_TYPE_IDS).
  if (row.variant.isStructural) {
    expect(descriptor.structuralType).toMatchObject(row.variant.variantType);
    expect(descriptor.molecularConsequences ?? []).toHaveLength(0);
  } else {
    expect(descriptor.structuralType).toBeUndefined();
    expect(descriptor.molecularConsequences).toContainEqual(row.variant.variantType);
  }
  // The sheet's hg38/hg19 columns are VCF-style dash notation and land on
  // syntax 'vcf' -- hg38 untagged (byte-identical to the migrated shape),
  // hg19 tagged version 'GRCh37'.
  const hg38 = findExpression(descriptor, (e) => e.syntax === 'vcf' && e.version !== 'GRCh37');
  const hg19 = findExpression(descriptor, (e) => e.syntax === 'vcf' && e.version === 'GRCh37');
  expect(hg38?.value).toBe(row.variant.hg38);
  expect(hg19?.value).toBe(row.variant.hg19);
  if (row.variant.varsome) {
    const varsome = findExpression(descriptor, (e) => e.syntax === 'hgvs.c');
    expect(varsome?.value).toBe(row.variant.varsome);
  } else {
    // D7
    expect(findExpression(descriptor, (e) => e.syntax === 'hgvs.c')).toBeUndefined();
  }
  if (row.variant.dbVarId) {
    expect(descriptor.xrefs).toContain(row.variant.dbVarId);
  }
  expect(findExtension(descriptor.extensions, 'segregation')?.value?.origin).toBe(
    row.variant.segregationValue
  );
  expect(pp.hnf1bCuration.detectionMethod).toBe(row.variant.detectionMethodValue);
  // D2: no sheet column for allelicState -- never set.
  expect(descriptor.allelicState).toBeUndefined();
  // D3: coordinates is derived/read-only -- the console never writes it,
  // even for a row whose sheet cell (hg19_INFO/hg38_INFO) carries a value.
  expect(findExtension(descriptor.extensions, 'coordinates')).toBeUndefined();

  // -- Classification --
  const gi = firstGenomicInterpretation(pp);
  expect(gi.interpretationStatus).toBe(row.classification.verdictValue);
  expect(
    findExtension(gi.variantInterpretation.extensions, 'classification_criteria')?.value?.criteria
  ).toBe(row.classification.criteria);
  expect(pp.hnf1bCuration.classificationSystem).toBe(row.classification.systemValue);
  expect(pp.hnf1bCuration.classificationDate).toBe(row.classification.date);
  if (row.classification.comment) {
    expect(pp.hnf1bCuration.classificationComment).toBe(row.classification.comment);
  } else {
    expect(pp.hnf1bCuration.classificationComment ?? null).toBeNull();
  }
  // ADR 0003 D1 non-negotiable: the conformant field must never be written.
  expect(gi.variantInterpretation.acmgPathogenicityClassification).toBeUndefined();

  // -- Phenotypes --
  if (row.phenotypes.renalInsufficancyCkd) {
    const feature = findPhenotype(pp, row.phenotypes.renalInsufficancyCkd.hpoId);
    expect(feature, 'CKD stage feature').toBeTruthy();
    expect(feature.excluded).toBeFalsy();
  }
  if (row.phenotypes.renalInsufficancy) {
    const feature = findPhenotype(pp, row.phenotypes.renalInsufficancy);
    expect(feature, 'RenalInsufficancy feature').toBeTruthy();
    expect(feature.excluded).toBeFalsy();
  }
  for (const entry of row.phenotypes.present) {
    const feature = findPhenotype(pp, entry.hpoId);
    expect(feature, `present feature ${entry.hpoId}`).toBeTruthy();
    expect(feature.excluded).toBeFalsy();
    if (entry.laterality) {
      const modifierLabels = { Bilateral: 'HP:0012832', Unilateral: 'HP:0012833' };
      expect(feature.modifiers?.[0]?.id).toBe(modifierLabels[entry.laterality]);
    }
  }
  for (const hpoId of row.phenotypes.excluded) {
    const feature = findPhenotype(pp, hpoId);
    expect(feature, `excluded feature ${hpoId}`).toBeTruthy();
    expect(feature.excluded).toBe(true);
  }
  for (const hpoId of row.phenotypes.absentChecks) {
    // "not reported" in the sheet -> no entry at all (the grid's own
    // tri-state convention: "unknown" IS absence, matching the migration
    // importer's own behaviour of skipping 'not reported' cells entirely).
    expect(findPhenotype(pp, hpoId), `${hpoId} must be absent, not excluded`).toBeUndefined();
  }

  // -- Age & onset --
  if (row.age.onsetGestationalWeeks !== undefined) {
    // D6: no disease-term control exists -- defaults to the corpus's sole term.
    expect(pp.diseases?.[0]?.term).toEqual({
      id: 'MONDO:0007669',
      label: 'renal cysts and diabetes syndrome',
    });
    expect(pp.diseases[0].onset.gestationalAge).toEqual({
      weeks: row.age.onsetGestationalWeeks,
      days: 0,
    });
  } else {
    // D4/D5: no expressible onset -- diseases never gets created at all.
    expect(pp.diseases ?? []).toHaveLength(0);
  }
  if (row.age.reportedGestationalWeeks !== undefined) {
    expect(pp.subject.timeAtLastEncounter.gestationalAge).toEqual({
      weeks: row.age.reportedGestationalWeeks,
      days: 0,
    });
  } else if (row.age.reportedYears) {
    expect(pp.subject.timeAtLastEncounter.iso8601duration).toBe(`P${row.age.reportedYears}Y`);
  } else {
    expect(pp.subject.timeAtLastEncounter ?? null).toBeNull();
  }

  // -- Provenance --
  expect(pp.hnf1bCuration.caseComment).toBe(row.provenance.comment);
  expect(pp.hnf1bCuration.duplicateCheck).toBe(row.provenance.duplicateCheck);
  expect(pp.hnf1bCuration.problematic ?? null).toBeNull(); // sheet cell was blank for all 3 rows

  // D9: no email anywhere, despite the real sheet row carrying one.
  expect(pp.hnf1bCuration.curatedBy).not.toContain('@');
  expect(pp.hnf1bCuration.curatedBy).not.toBe(row.sheet.ReviewBy);
  expect(pp.metaData.reviewer).not.toContain('@');
  expect(containsEmail(pp)).toBe(false);
}

// =============================================================================
// 1. Acceptance test -- 3 real sheet rows
// =============================================================================

test.describe('1. Acceptance test — 3 real sheet rows', () => {
  for (const row of SHEET_ROWS) {
    test(`${row.key}: ${row.description}`, async ({ page, request }) => {
      test.setTimeout(120_000);
      const tokens = await login(page, request);
      const { phenopacketId, subjectId } = await enterRow(page, row);

      const pp = await fetchPhenopacket(request, tokens.accessToken, phenopacketId);
      assertRowMatches(pp, row, subjectId);

      if (row.age.reportedGestationalWeeks !== undefined) {
        // Task 9: the gestational-age reader must round-trip onto the
        // display page, not show N/A.
        await page.goto(`/phenopackets/${phenopacketId}`, { waitUntil: 'networkidle' });
        await expect(
          page.getByText(`${row.age.reportedGestationalWeeks} weeks`).first()
        ).toBeVisible();
        await expect(page.getByText('N/A')).toHaveCount(0);
      }
    });
  }
});

// =============================================================================
// 2. Round-trip: create -> save -> reload -> edit -> save -> reload
// =============================================================================

test.describe('2. Round-trip', () => {
  test('create, save, reload, edit one field per section, save, reload — every dimension persists', async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);
    const tokens = await login(page, request);
    const ts = Date.now();
    const phenopacketId = `e2e-curation-roundtrip-${ts}`;
    const subjectId = `${phenopacketId}-subject`;

    // ---- Create, touching all six sections ----
    await gotoCreate(page);
    await fillText(pageControl(page, 'Phenopacket ID'), phenopacketId);
    await expandSection(page, 'case');
    await fillText(sectionControl(page, 'case', 'Subject ID'), subjectId);
    await selectExact(page, sectionControl(page, 'case', 'Sex'), 'Female');
    await selectExact(page, sectionControl(page, 'case', 'Cohort'), 'Born');
    await addChip(sectionControl(page, 'case', 'Individual identifiers'), 'RT-subject-1');
    await selectExact(page, sectionControl(page, 'case', 'Publication type'), 'Research');
    await selectExact(page, sectionControl(page, 'case', 'Family history'), 'Positive');
    await addPublication(page);
    await fillText(pmidRows(page).first(), '19999001');

    await expandSection(page, 'variant');
    await selectExact(page, sectionControl(page, 'variant', 'Detection method'), 'qPCR');
    await fillText(sectionControl(page, 'variant', 'Variant as reported'), 'c.1A>G synthetic');
    await selectExact(page, sectionControl(page, 'variant', 'Variant type'), 'indel');
    await fillText(sectionControl(page, 'variant', 'hg38 (GRCh38)'), 'chr17-11111111-A-G');
    await fillText(sectionControl(page, 'variant', 'hg19 (GRCh37)'), 'chr17-22222222-A-G');
    await fillText(sectionControl(page, 'variant', 'Varsome (hgvs.c)'), 'NM_000458.4:c.1A>G');
    await addChip(sectionControl(page, 'variant', 'dbVar ID(s)'), 'dbVar:synthetic1');
    await selectExact(page, sectionControl(page, 'variant', 'Segregation'), 'Inherited, maternal');
    await selectExact(page, sectionControl(page, 'variant', 'Allelic state'), 'heterozygous');
    await saveDetailedVariant(page);

    await expandSection(page, 'classification');
    await selectExact(
      page,
      sectionControl(page, 'classification', 'ACMG verdict'),
      'Likely pathogenic'
    );
    await fillText(
      sectionControl(page, 'classification', 'Classification criteria (free text)'),
      'PM2_Supporting, PP3_Supporting'
    );
    await selectExact(
      page,
      sectionControl(page, 'classification', 'Classification system'),
      'ACMG'
    );
    await fillText(sectionControl(page, 'classification', 'Classification date'), '2023-01-15');
    await fillText(
      sectionControl(page, 'classification', 'Classification comment'),
      'synthetic classification comment'
    );

    await expandSection(page, 'phenotypes');
    await expect(page.locator('.phenotype-item').first()).toBeVisible({ timeout: 15_000 });
    await setPhenotypePresent(page, 'HP:0000107', 'Left'); // Renal cyst
    await setPhenotypeExcluded(page, 'HP:0000122'); // Unilateral renal agenesis

    await expandSection(page, 'age');
    await timeElementPicker(page, 'Onset')
      .getByRole('button', { name: 'Congenital', exact: true })
      .click();
    await setTimeElementAgeYears(timeElementPicker(page, 'Age reported'), 2);

    await expandSection(page, 'provenance');
    await fillText(sectionControl(page, 'provenance', 'Comment'), 'synthetic case comment');
    await fillText(sectionControl(page, 'provenance', 'Problematic'), 'synthetic problematic note');
    await fillText(sectionControl(page, 'provenance', 'Duplicate check'), 'synthetic dup check');

    await submitForm(page, phenopacketId);

    // ---- Reload: fresh navigation to the edit route, re-fetching from the server ----
    await page.goto(`/phenopackets/${phenopacketId}/edit`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('Edit Phenopacket');
    await expandAllSections(page);

    // Every dimension entered above must have survived the round-trip.
    await expect(sectionControl(page, 'case', 'Subject ID').locator('input')).toHaveValue(
      subjectId
    );
    await expect(page.getByText('RT-subject-1')).toBeVisible();
    await expect(pmidRows(page).first().locator('input')).toHaveValue('19999001');

    // The detailed editor is an add/edit form, not a always-bound view of the
    // saved variant: reopening the saved variant is what runs
    // editorFromDescriptor, which is the round-trip actually under test here.
    await sectionLocator(page, 'variant').locator('[data-testid="edit-variant-btn-0"]').click();
    await expect(
      sectionControl(page, 'variant', 'Variant as reported').locator(
        'textarea:not([aria-hidden="true"])'
      )
    ).toHaveValue('c.1A>G synthetic');
    await expect(sectionControl(page, 'variant', 'hg38 (GRCh38)').locator('input')).toHaveValue(
      'chr17-11111111-A-G'
    );
    await expect(
      sectionControl(page, 'classification', 'Classification criteria (free text)').locator(
        'textarea:not([aria-hidden="true"])'
      )
    ).toHaveValue('PM2_Supporting, PP3_Supporting');
    await expect(
      sectionControl(page, 'provenance', 'Comment').locator('textarea:not([aria-hidden="true"])')
    ).toHaveValue('synthetic case comment');
    await expect(
      sectionControl(page, 'provenance', 'Problematic').locator(
        'textarea:not([aria-hidden="true"])'
      )
    ).toHaveValue('synthetic problematic note');

    // ---- Edit one field per section ----
    await selectExact(page, sectionControl(page, 'case', 'Family history'), 'Negative');
    await fillText(sectionControl(page, 'variant', 'hg38 (GRCh38)'), 'chr17-33333333-A-G');
    // The detailed editor is a sub-form; committing it is what puts the edit
    // into the phenopacket. Submitting without this is now refused outright
    // (see the "unsaved variant editor" adversarial test) rather than
    // silently dropping the change.
    await saveDetailedVariant(page);
    await selectExact(page, sectionControl(page, 'classification', 'ACMG verdict'), 'Pathogenic');
    // HP:0000107 is already "present" (from the create phase) after reload --
    // one click, not setPhenotypeExcluded's two (see that helper's doc).
    await clickPresentToExcluded(page, 'HP:0000107'); // was present -> now excluded
    await setTimeElementAgeYears(timeElementPicker(page, 'Age reported'), 3);
    await fillText(
      sectionControl(page, 'provenance', 'Comment'),
      'synthetic case comment (edited)'
    );

    await fillText(pageControl(page, 'Change Reason'), 'E2E round-trip edit (Task 10)');
    await submitForm(page, phenopacketId);

    // ---- Reload once more and assert BOTH the edited AND untouched fields ----
    const pp = await fetchPhenopacket(request, tokens.accessToken, phenopacketId);
    expect(pp.hnf1bCuration.familyHistory).toBe('negative'); // edited
    expect(pp.hnf1bCuration.cohort).toBe('born'); // untouched
    expect(pp.subject.sex).toBe('FEMALE'); // untouched
    expect(pp.subject.alternateIds).toContain('RT-subject-1'); // untouched
    expect(pp.metaData.externalReferences).toContainEqual({ id: 'PMID:19999001' }); // untouched

    const descriptor = firstVariationDescriptor(pp);
    expect(descriptor.description).toBe('c.1A>G synthetic'); // untouched
    const hg38 = findExpression(descriptor, (e) => e.syntax === 'vcf' && e.version !== 'GRCh37');
    expect(hg38.value).toBe('chr17-33333333-A-G'); // edited
    const hg19 = findExpression(descriptor, (e) => e.syntax === 'vcf' && e.version === 'GRCh37');
    expect(hg19.value).toBe('chr17-22222222-A-G'); // untouched
    expect(descriptor.allelicState?.label).toBe('heterozygous'); // untouched
    expect(descriptor.xrefs).toContain('dbVar:synthetic1'); // untouched

    const gi = firstGenomicInterpretation(pp);
    expect(gi.interpretationStatus).toBe('PATHOGENIC'); // edited
    expect(
      findExtension(gi.variantInterpretation.extensions, 'classification_criteria')?.value?.criteria
    ).toBe('PM2_Supporting, PP3_Supporting'); // untouched
    expect(pp.hnf1bCuration.classificationComment).toBe('synthetic classification comment'); // untouched

    const renalCyst = findPhenotype(pp, 'HP:0000107');
    expect(renalCyst.excluded).toBe(true); // edited (was present)
    const solitaryKidney = findPhenotype(pp, 'HP:0000122');
    expect(solitaryKidney.excluded).toBe(true); // untouched

    expect(pp.diseases?.[0]?.onset?.ontologyClass?.id).toBe('HP:0003577'); // untouched (congenital)
    expect(pp.subject.timeAtLastEncounter.iso8601duration).toBe('P3Y'); // edited (2 -> 3)

    expect(pp.hnf1bCuration.caseComment).toBe('synthetic case comment (edited)'); // edited
    expect(pp.hnf1bCuration.problematic).toBe('synthetic problematic note'); // untouched
    expect(pp.hnf1bCuration.duplicateCheck).toBe('synthetic dup check'); // untouched
  });
});

// =============================================================================
// 3. Adversarial pass
// =============================================================================

test.describe('3. Adversarial pass', () => {
  test('submit with all fields empty: blocked client-side, no phantom save', async ({
    page,
    request,
  }) => {
    await login(page, request);
    await gotoCreate(page);
    await page.locator('button[type="submit"]').click();

    // Client-side v-form validation blocks the submit (Phenopacket ID and
    // Subject ID are both required and empty) -- no navigation, no POST,
    // and a visible, specific error rather than a silent no-op.
    await expect(
      page.locator('.v-alert', { hasText: 'Please fix validation errors' })
    ).toBeVisible();
    await expect(page).toHaveURL(/\/phenopackets\/create$/);
  });

  test("whitespace-only Subject ID: the app's naive required-rule accepts it (documented finding)", async ({
    page,
    request,
  }) => {
    // `rules.required = (value) => !!value || 'Required field'` treats any
    // non-empty string -- including one made only of spaces -- as valid.
    // Neither the client rule nor the backend's `minLength: 1` schema check
    // trims, so whitespace-only input is NOT rejected: it round-trips
    // verbatim. This test documents that behaviour rather than asserting a
    // rejection this app does not actually implement.
    const tokens = await login(page, request);
    const ts = Date.now();
    const phenopacketId = `e2e-curation-whitespace-${ts}`;
    await gotoCreate(page);
    await fillText(pageControl(page, 'Phenopacket ID'), phenopacketId);
    await expandSection(page, 'case');
    await fillText(sectionControl(page, 'case', 'Subject ID'), '   ');
    await expandSection(page, 'phenotypes');
    await expect(page.locator('.phenotype-item').first()).toBeVisible({ timeout: 15_000 });
    await setPhenotypePresent(page, 'HP:0000107');
    await submitForm(page, phenopacketId);

    const pp = await fetchPhenopacket(request, tokens.accessToken, phenopacketId);
    expect(pp.subject.id).toBe('   ');
  });

  test('10,000-character VariantReported: accepted and round-trips verbatim', async ({
    page,
    request,
  }) => {
    // No maxLength is imposed anywhere in the stack (schema_validator.py's
    // hnf1bCuration/variationDescriptor declarations have no length bound on
    // `description`) -- verified by reading the schema rather than probing
    // for a boundary that does not exist.
    const tokens = await login(page, request);
    const ts = Date.now();
    const phenopacketId = `e2e-curation-longvariant-${ts}`;
    const subjectId = `${phenopacketId}-subject`;
    const longVariant = 'X'.repeat(10_000);

    await gotoCreate(page);
    await fillText(pageControl(page, 'Phenopacket ID'), phenopacketId);
    await expandSection(page, 'case');
    await fillText(sectionControl(page, 'case', 'Subject ID'), subjectId);
    await expandSection(page, 'variant');
    await fillText(sectionControl(page, 'variant', 'Variant as reported'), longVariant);
    await saveDetailedVariant(page);
    await expandSection(page, 'phenotypes');
    await expect(page.locator('.phenotype-item').first()).toBeVisible({ timeout: 15_000 });
    await setPhenotypePresent(page, 'HP:0000107');
    await submitForm(page, phenopacketId);

    const pp = await fetchPhenopacket(request, tokens.accessToken, phenopacketId);
    const descriptor = firstVariationDescriptor(pp);
    expect(descriptor.description).toHaveLength(10_000);
    expect(descriptor.description).toBe(longVariant);
  });

  test('20 publications added then removed: empty final state, no phantom rows, no crash', async ({
    page,
    request,
  }) => {
    await login(page, request);
    await gotoCreate(page);
    await expandSection(page, 'case');

    for (let i = 0; i < 20; i += 1) {
      await addPublication(page);
    }
    await expect(pmidRows(page)).toHaveCount(20);

    const deleteButton = sectionLocator(page, 'case').locator('button:has(.mdi-delete)');
    for (let i = 0; i < 20; i += 1) {
      await deleteButton.first().click();
    }
    await expect(pmidRows(page)).toHaveCount(0);
    await expect(deleteButton).toHaveCount(0);
    // No crash: the page is still the create form, not an error boundary.
    await expect(page.locator('h1')).toContainText('Create New Phenopacket');
  });

  test('cycling a phenotype through all 3 states sticks after save', async ({ page, request }) => {
    const tokens = await login(page, request);
    const ts = Date.now();
    const phenopacketId = `e2e-curation-cycle-${ts}`;
    const subjectId = `${phenopacketId}-subject`;

    await gotoCreate(page);
    await fillText(pageControl(page, 'Phenopacket ID'), phenopacketId);
    await expandSection(page, 'case');
    await fillText(sectionControl(page, 'case', 'Subject ID'), subjectId);
    await expandSection(page, 'phenotypes');
    await expect(page.locator('.phenotype-item').first()).toBeVisible({ timeout: 15_000 });

    const row = phenotypeRow(page, 'HP:0000107');
    const btn = row.locator('button').first();
    await btn.click(); // unknown -> present
    await btn.click(); // present -> excluded
    await btn.click(); // excluded -> unknown
    await btn.click(); // unknown -> present (final state)

    await submitForm(page, phenopacketId);

    const pp = await fetchPhenopacket(request, tokens.accessToken, phenopacketId);
    const feature = findPhenotype(pp, 'HP:0000107');
    expect(feature, 'feature must exist after cycling back to present').toBeTruthy();
    expect(feature.excluded).toBeFalsy();
  });

  test('navigate away with unsaved changes: the in-app confirm() guard fires', async ({
    page,
    request,
  }) => {
    await login(page, request);

    // Scenario 1: dismiss the dialog -> navigation is cancelled, form stays.
    await gotoCreate(page);
    await expandSection(page, 'case');
    await fillText(sectionControl(page, 'case', 'Subject ID'), 'unsaved-changes-probe');

    let dialogMessage = null;
    page.once('dialog', (dialog) => {
      dialogMessage = dialog.message();
      dialog.dismiss();
    });
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect.poll(() => dialogMessage).toContain('unsaved changes');
    await expect(page).toHaveURL(/\/phenopackets\/create$/);

    // Scenario 2: accept the dialog -> navigation proceeds.
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.waitForURL(/\/phenopackets$/, { timeout: 10_000 });
  });

  test('unsaved variant editor: submit is refused, not silently discarded', async ({
    page,
    request,
  }) => {
    // The detailed variant editor only reaches the phenopacket via its own
    // "Save variant" button. A record used to save happily with typed-but-
    // uncommitted variant fields, dropping them without a word.
    await login(page, request);
    const phenopacketId = `e2e-curation-pending-variant-${Date.now()}`;

    await gotoCreate(page);
    await fillText(pageControl(page, 'Phenopacket ID'), phenopacketId);
    await expandSection(page, 'case');
    await fillText(sectionControl(page, 'case', 'Subject ID'), `${phenopacketId}-subject`);
    await expandSection(page, 'phenotypes');
    await expect(page.locator('.phenotype-item').first()).toBeVisible({ timeout: 15_000 });
    await setPhenotypePresent(page, 'HP:0000107');

    // Type into the variant editor, deliberately WITHOUT clicking Save variant.
    await expandSection(page, 'variant');
    await fillText(sectionControl(page, 'variant', 'Variant as reported'), 'uncommitted variant');

    await page.locator('button[type="submit"]').click();
    await expect(
      page.locator('.v-alert', { hasText: 'variant editor has unsaved changes' }).first()
    ).toBeVisible();
    await expect(page).toHaveURL(/\/phenopackets\/create$/);

    // A recoverable error must NOT take the form down with it. The form used
    // to be `v-else-if="!error"`, so any validation or save failure unmounted
    // every section and left the curator staring at an alert with a fully
    // entered case irrecoverable behind it.
    await expect(sectionLocator(page, 'case')).toBeVisible();
    await expect(sectionControl(page, 'case', 'Subject ID').locator('input')).toHaveValue(
      `${phenopacketId}-subject`
    );

    // Committing the sub-form clears the block and the record saves.
    await saveDetailedVariant(page);
    await submitForm(page, phenopacketId);

    const tokens = await loginAsAdmin(request, API_BASE);
    const pp = await fetchPhenopacket(request, tokens.accessToken, phenopacketId);
    expect(firstVariationDescriptor(pp).description).toBe('uncommitted variant');
  });
});

// =============================================================================
// 4. Visual / theme pass
// =============================================================================

test.describe('4. Visual / theme pass', () => {
  test('dark mode across every section, 1440px and 390px: zero console errors, no horizontal scroll at 390', async ({
    page,
    request,
  }) => {
    test.setTimeout(90_000);
    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', (err) => consoleErrors.push(String(err)));

    // Matches the existing suite's own idiom (ui-hardening-dark-theme.spec.js):
    // Vuetify's theme provider toggles v-theme--light/v-theme--dark on
    // <html>; forcing it directly is the established, already-working
    // technique in this repo rather than hunting for a live toggle control.
    async function forceDarkTheme() {
      await page.evaluate(() => {
        const root = document.documentElement;
        root.classList.remove('v-theme--light');
        root.classList.add('v-theme--dark');
        document.body.classList.remove('v-theme--light');
        document.body.classList.add('v-theme--dark');
      });
    }

    await login(page, request);

    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoCreate(page);
    await forceDarkTheme();
    await expandAllSections(page);
    // Every section must actually be open (not a silent no-op under dark mode).
    for (const id of SECTION_IDS) {
      await expect(
        sectionLocator(page, id).locator('button.curation-section__header')
      ).toHaveAttribute('aria-expanded', 'true');
    }
    await expect(sectionLocator(page, 'provenance')).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await forceDarkTheme();
    await expect(sectionLocator(page, 'provenance')).toBeVisible();
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth, 'no horizontal body scroll at 390px').toBeLessThanOrEqual(clientWidth + 1);

    expect(
      consoleErrors,
      `console errors accumulated during the flow:\n${consoleErrors.join('\n')}`
    ).toEqual([]);
  });
});

// =============================================================================
// 5. Completeness rail semantic — absence vs not_reported
// =============================================================================

test.describe('5. Completeness rail semantic', () => {
  test('a not_reported field counts as filled; an absent field does not', async ({
    page,
    request,
  }) => {
    // This is "the single most important semantic in this domain" (design
    // spec §2.1): absent means "not yet curated"; the selected value
    // 'not_reported' means "the source publication is silent". The rail
    // must never conflate the two.
    await login(page, request);
    await gotoCreate(page);
    await expandSection(page, 'case');

    const badge = sectionBadge(page, 'case');
    // Baseline: subject.sex defaults to 'UNKNOWN_SEX' the instant the form
    // mounts (a real, selectable GA4GH enum member, not a placeholder) --
    // so the rail starts at 1/6, before the curator has touched anything.
    await expect(badge).toHaveText('1/6');

    // `cohort` is deliberately left completely untouched for the rest of
    // this test: cohort_values has NO not_reported member (the sheet states
    // cohort for all 939 rows), so an absent cohort unambiguously means
    // "not yet curated" and must never be counted as filled.
    await selectExact(page, sectionControl(page, 'case', 'Family history'), 'Not reported');

    // 2/6, not 3/6: sex (default) + familyHistory (just set to the explicit
    // not_reported value) are filled; cohort -- still untouched -- is
    // correctly NOT counted. The total staying at 6 while filled is exactly
    // 2 is the proof that "absent" and "not_reported" land in different
    // buckets.
    await expect(badge).toHaveText('2/6');
  });
});
