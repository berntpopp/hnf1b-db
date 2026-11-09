// @ts-check
/**
 * Publication medical_specialty curation (issue #11).
 *
 * The three specialty-related endpoints are served by a stateful in-browser
 * fake so the spec is deterministic in CI (the real GET calls NCBI live; the
 * backend contract is covered by backend/tests/test_publications_specialty_api.py).
 * The monkey test drives seeded random UI actions, injects 500s / degraded NCBI
 * / latency, and checks invariants after every step.
 */
import { expect, test } from '@playwright/test';

import { loginAsCuratorA, primeAuthSession } from './helpers/auth';

const API_BASE = process.env.VITE_API_URL || 'http://localhost:8000/api/v2';
const PMID = '12345678';
const VOCAB = [
  'nephrology',
  'diabetology',
  'genetics',
  'pediatrics',
  'pathology',
  'radiology',
  'obstetrics',
  'gynecology',
];
const SUGGESTIONS = [
  { specialty: 'nephrology', score: 3, evidence: ['journal', 'first_author'] },
  { specialty: 'pediatrics', score: 2, evidence: ['first_author', 'last_author'] },
  { specialty: 'genetics', score: 1, evidence: ['last_author'] },
];

/** Small seeded PRNG so a failing monkey run can be replayed. */
function mulberry32(seed) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Install the fake backend for one publication.
 * @param {import('@playwright/test').Page} page
 * @param {{ saved?: string[], rnd?: () => number, failRate?: number, maxDelay?: number }} opts
 */
async function installFakeApi(
  page,
  { saved = [], rnd = () => 1, failRate = 0, maxDelay = 0 } = {}
) {
  const state = { saved: [...saved], puts: [], violations: [] };
  const delay = () => new Promise((r) => setTimeout(r, Math.floor(rnd() * maxDelay)));

  await page.route(`**/publications/${PMID}/metadata`, (route) =>
    route.fulfill({
      json: {
        pmid: `PMID:${PMID}`,
        title: 'HNF1B nephropathy in a paediatric cohort',
        authors: [{ name: 'Doe J', affiliation: 'Department of Pediatric Nephrology' }],
        journal: 'Kidney International',
        year: 2020,
        doi: null,
        abstract: null,
        data_source: 'PubMed',
        fetched_at: '2026-11-09T00:00:00Z',
        medical_specialty: state.saved,
      },
    })
  );

  await page.route(`**/publications/${PMID}/specialty`, async (route) => {
    const req = route.request();
    await delay();
    if (rnd() < failRate) {
      return route.fulfill({ status: 500, json: { detail: 'Injected server error' } });
    }
    if (req.method() === 'GET') {
      const degraded = rnd() < failRate;
      return route.fulfill({
        json: {
          pmid: `PMID:${PMID}`,
          medical_specialty: state.saved,
          vocabulary: VOCAB,
          suggestions: degraded ? [] : SUGGESTIONS,
          suggestion_error: degraded ? 'NCBI unavailable, suggestions could not be loaded' : null,
        },
      });
    }
    // PUT: validate exactly like the backend and record anything the UI should never send.
    const body = req.postDataJSON();
    const value = body?.medical_specialty;
    state.puts.push(value);
    if (
      !Array.isArray(value) ||
      value.length > 8 ||
      value.some((v) => !VOCAB.includes(v)) ||
      new Set(value).size !== value.length
    ) {
      state.violations.push(`invalid PUT body ${JSON.stringify(body)}`);
      return route.fulfill({ status: 422, json: { detail: 'invalid' } });
    }
    state.saved = [...value];
    return route.fulfill({ json: { medical_specialty: state.saved } });
  });
  return state;
}

async function loginCurator(page, request) {
  const auth = await loginAsCuratorA(request, API_BASE);
  await primeAuthSession(page, auth);
}

const block = (page) => page.getByTestId('publication-specialty');
const editor = (page) => page.getByTestId('specialty-editor');

async function shownChips(page) {
  return (await block(page).locator('.v-chip').allInnerTexts()).map((t) => t.trim().toLowerCase());
}

test.describe('publication medical specialty', () => {
  test('public visitors see saved specialties read-only', async ({ page }) => {
    await installFakeApi(page, { saved: ['nephrology', 'pediatrics'] });
    await page.goto(`/publications/${PMID}`);
    await expect(block(page)).toBeVisible();
    expect(await shownChips(page)).toEqual(['nephrology', 'pediatrics']);
    await expect(page.getByTestId('specialty-edit-btn')).toHaveCount(0);
  });

  test('public visitors see nothing when no specialty is curated', async ({ page }) => {
    await installFakeApi(page);
    await page.goto(`/publications/${PMID}`);
    await expect(page.getByText('Kidney International').first()).toBeVisible();
    await expect(block(page)).toHaveCount(0);
  });

  test('curator accepts suggestions, saves, and the value survives a reload', async ({
    page,
    request,
  }) => {
    await loginCurator(page, request);
    const state = await installFakeApi(page);
    await page.goto(`/publications/${PMID}`);

    await expect(block(page)).toContainText('Not yet curated');
    await page.getByTestId('specialty-edit-btn').click();
    await expect(page.getByTestId('specialty-suggestions')).toBeVisible();

    // Evidence is explained on hover.
    await page.getByTestId('specialty-suggestion-nephrology').hover();
    await expect(page.getByText('From journal, first author (score 3)')).toBeVisible();

    await page.getByTestId('specialty-suggestion-nephrology').click();
    await page.getByTestId('specialty-suggestion-pediatrics').click();
    await expect(page.getByTestId('specialty-suggestion-nephrology')).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    await page.getByTestId('specialty-save-btn').click();

    await expect(editor(page)).toHaveCount(0);
    expect(await shownChips(page)).toEqual(['nephrology', 'pediatrics']);
    expect(state.puts).toEqual([['nephrology', 'pediatrics']]);

    await page.reload();
    await expect(block(page)).toBeVisible();
    expect(await shownChips(page)).toEqual(['nephrology', 'pediatrics']);
  });

  test('curator can pick manually when NCBI is down, and Cancel discards edits', async ({
    page,
    request,
  }) => {
    await loginCurator(page, request);
    const state = await installFakeApi(page, { saved: ['genetics'], rnd: () => 0, failRate: 0 });
    // Force the degraded GET branch only.
    await page.unroute(`**/publications/${PMID}/specialty`);
    await page.route(`**/publications/${PMID}/specialty`, (route) =>
      route.request().method() === 'GET'
        ? route.fulfill({
            json: {
              pmid: `PMID:${PMID}`,
              medical_specialty: state.saved,
              vocabulary: VOCAB,
              suggestions: [],
              suggestion_error: 'NCBI unavailable, suggestions could not be loaded',
            },
          })
        : route.fulfill({
            json: { medical_specialty: route.request().postDataJSON().medical_specialty },
          })
    );
    await page.goto(`/publications/${PMID}`);

    await page.getByTestId('specialty-edit-btn').click();
    await expect(page.getByTestId('specialty-error')).toContainText('NCBI unavailable');

    await page.getByTestId('specialty-select').click();
    await page.getByRole('option', { name: 'diabetology' }).click();
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Cancel' }).click();
    expect(await shownChips(page)).toEqual(['genetics']);

    await page.getByTestId('specialty-edit-btn').click();
    await page.getByTestId('specialty-select').click();
    await page.getByRole('option', { name: 'diabetology' }).click();
    await page.keyboard.press('Escape');
    await page.getByTestId('specialty-save-btn').click();
    await expect(editor(page)).toHaveCount(0);
    expect(await shownChips(page)).toEqual(['genetics', 'diabetology']);
  });

  test('monkey: random actions with injected failures keep the UI consistent', async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const seed = Number(process.env.MONKEY_SEED || 20261109);
    const steps = Number(process.env.MONKEY_STEPS || 120);
    const rnd = mulberry32(seed);
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(e.message));

    await loginCurator(page, request);
    const state = await installFakeApi(page, { rnd, failRate: 0.15, maxDelay: 250 });
    await page.goto(`/publications/${PMID}`);
    await expect(block(page)).toBeVisible();

    const visible = async (loc) => (await loc.count()) > 0 && loc.first().isVisible();
    const actions = {
      async edit() {
        const btn = page.getByTestId('specialty-edit-btn');
        if (await visible(btn)) await btn.click();
      },
      async suggestion() {
        const chips = page.locator('[data-testid^="specialty-suggestion-"]');
        const n = await chips.count();
        if (n) await chips.nth(Math.floor(rnd() * n)).click();
      },
      async useAll() {
        const btn = page.getByTestId('specialty-use-all');
        if (await visible(btn)) await btn.click();
      },
      async pickVocab() {
        const select = page.getByTestId('specialty-select');
        if (!(await visible(select))) return;
        await select.click();
        const options = page.getByRole('option');
        const n = await options.count();
        if (n) await options.nth(Math.floor(rnd() * n)).click();
        await page.keyboard.press('Escape');
      },
      async removeChip() {
        const close = page.getByTestId('specialty-select').locator('.v-chip__close');
        const n = await close.count();
        if (n) await close.nth(Math.floor(rnd() * n)).click();
      },
      async typeJunk() {
        const input = page.getByTestId('specialty-select').locator('input');
        if (!(await visible(input))) return;
        await input.fill(
          ['<script>x</script>', '💥', 'nephro', "'; DROP", ''][Math.floor(rnd() * 5)]
        );
        await page.keyboard.press('Escape');
      },
      async cancel() {
        const btn = page.getByRole('button', { name: 'Cancel' });
        if (await visible(btn)) await btn.click();
      },
      async save() {
        const btn = page.getByTestId('specialty-save-btn');
        if ((await visible(btn)) && (await btn.isEnabled())) await btn.click();
      },
      async doubleSave() {
        const btn = page.getByTestId('specialty-save-btn');
        if ((await visible(btn)) && (await btn.isEnabled())) await btn.dblclick();
      },
      async reload() {
        if (rnd() < 0.3) await page.reload();
      },
    };
    const names = Object.keys(actions);
    const log = [];

    for (let i = 0; i < steps; i += 1) {
      const name = names[Math.floor(rnd() * names.length)];
      log.push(name);
      await actions[name]();
      // Let in-flight requests (<=250 ms fake latency) settle before checking.
      await expect(
        page.locator('[data-testid="specialty-editor"] .v-progress-linear--active')
      ).toHaveCount(0);
      await expect(page.getByTestId('specialty-save-btn').locator('.v-btn__loader')).toHaveCount(0);

      const context = `seed=${seed} step=${i} actions=${log.slice(-8).join(',')}`;
      await expect(block(page), context).toHaveCount(1);
      expect(await editor(page).count(), context).toBeLessThanOrEqual(1);
      const text = await block(page).innerText();
      expect(text, context).not.toMatch(/\[object Object\]|undefined|NaN/);
      // Every chip (read-only, selected, suggested) must carry a label.
      const chipTexts = await block(page).locator('.v-chip').allInnerTexts();
      expect(
        chipTexts.filter((t) => !t.trim()),
        `${context} empty chips`
      ).toEqual([]);
      if ((await editor(page).count()) === 0) {
        // Read-only view must always mirror what the server has stored.
        const chips = await shownChips(page);
        expect(chips, context).toEqual(state.saved);
      }
    }

    expect(state.violations, `seed=${seed}`).toEqual([]);
    expect(pageErrors, `seed=${seed}`).toEqual([]);
    expect(state.puts.length, 'monkey should have exercised saving').toBeGreaterThan(0);
  });
});
