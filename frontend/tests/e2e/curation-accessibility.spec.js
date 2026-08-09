// @ts-check
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';
const columns = [
  'RenalInsufficancy',
  'Hyperechogenicity',
  'RenalCysts',
  'MulticysticDysplasticKidney',
  'KidneyBiopsy',
  'RenalHypoplasia',
  'SolitaryKidney',
  'UrinaryTractMalformation',
  'GenitalTractAbnormality',
  'AntenatalRenalAbnormalities',
  'Hypomagnesemia',
  'Hypokalemia',
  'Hyperuricemia',
  'Gout',
  'MODY',
  'PancreaticHypoplasia',
  'ExocrinePancreaticInsufficiency',
  'Hyperparathyroidism',
  'NeurodevelopmentalDisorder',
  'MentalDisease',
  'Seizures',
  'BrainAbnormality',
  'PrematureBirth',
  'CongenitalCardiacAnomalies',
  'EyeAbnormality',
  'ShortStature',
  'MusculoskeletalFeatures',
  'DysmorphicFeatures',
  'ElevatedHepaticTransaminase',
  'AbnormalLiverPhysiology',
];
const observed = (raw, value) => ({ raw, sourceStatus: 'stated', value, correctionIds: [] });
const report = (id) => ({
  observationId: id,
  origin: 'manual',
  source: {
    provider: 'fixture',
    datasetId: 'registry',
    sheet: 'Individuals',
    manifestSha256: 'sha256:fixture',
  },
  identifiers: {
    individualId: '317',
    sourceSubjectId: '317',
    reportId: id,
    sex: observed('M', 'MALE'),
  },
  publication: {
    sourceKey: observed(id, id),
    publicationType: observed('case', 'case_report'),
    pmid: id === 'RPT-1' ? '123' : '456',
  },
  case: {},
  ages: {},
  variant: null,
  classification: null,
  phenotypes: columns.map((column, index) => ({
    assessmentId: `${id}-${index}`,
    column,
    rawValue: '',
    sourceStatus: 'blank',
    curationStatus: 'UNCURATED',
    assessmentStatus: null,
    findings: [],
    evidence: [],
  })),
  sourceReview: { reviewerDisplayLabel: 'Reviewer', reviewedOn: '2025-01-01' },
  notes: {},
  diseases: [],
});

async function mockLedger(page) {
  const observations = [report('RPT-1'), report('RPT-2')];
  const projection = {
    phenopacket: {
      id: 'PP-317',
      subject: { id: '317' },
      phenotypicFeatures: [],
      interpretations: [],
    },
    observationsDigest: 'sha256:observations',
    outputDigest: 'sha256:output',
    issues: [],
  };
  await page.route('**/api/v2/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (path.endsWith('/auth/refresh')) return json({ access_token: 'e2e-access-token' });
    if (path.endsWith('/auth/me')) return json({ id: 1, username: 'curator', role: 'curator' });
    if (path.includes('/ontology/vocabularies/')) return json({ data: [] });
    if (path.endsWith('/phenopackets/PP-317/curation'))
      return json({
        phenopacketId: 'PP-317',
        revision: 7,
        observations,
        corrections: [],
        resolutions: [],
        projection,
      });
    if (path.endsWith('/phenopackets/PP-317'))
      return json({
        phenopacket: projection.phenopacket,
        revision: 7,
        state: 'draft',
        effective_state: 'draft',
      });
    if (path.endsWith('/curation/preview')) return json({ revision: 7, projection });
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });
}

const presentations = [
  { theme: 'light', viewport: 'desktop', width: 1440, height: 900 },
  { theme: 'light', viewport: 'mobile', width: 390, height: 844 },
  { theme: 'dark', viewport: 'desktop', width: 1440, height: 900 },
  { theme: 'dark', viewport: 'mobile', width: 390, height: 844 },
];

for (const presentation of presentations) {
  test(`ledger is axe-clean in ${presentation.theme} ${presentation.viewport}`, async ({
    context,
    page,
  }) => {
    await context.addCookies([{ name: 'csrf_token', value: 'e2e-csrf', url: BASE_URL }]);
    await page.addInitScript(
      (theme) => localStorage.setItem('hnf1b-theme', theme),
      presentation.theme
    );
    await page.setViewportSize({ width: presentation.width, height: presentation.height });
    await mockLedger(page);
    await page.goto('/phenopackets/PP-317/edit');
    await expect(page.getByRole('heading', { name: 'Report observation ledger' })).toBeVisible();
    await expect(page.locator('.v-application')).toHaveClass(
      new RegExp(`v-theme--${presentation.theme}`)
    );

    const axe = await new AxeBuilder({ page }).include('.ledger-workspace').analyze();
    expect(axe.violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true
    );

    if (presentation.theme === 'light' && presentation.viewport === 'mobile') {
      await page.locator('[name="pmid"]').fill('999');
      await page.getByRole('button', { name: /RPT-2/ }).click();
      const dialog = page.getByRole('dialog', { name: 'Unsaved report changes' });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole('button', { name: 'Keep editing' })).toBeFocused();
      await page.keyboard.press('Shift+Tab');
      await expect(dialog.getByRole('button', { name: 'Discard and switch' })).toBeFocused();
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
    }
  });
}
