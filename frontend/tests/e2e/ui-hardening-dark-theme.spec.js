import { test, expect } from '@playwright/test';

/**
 * Parse an "rgb(r, g, b)" or "rgba(r, g, b, a)" string into [r, g, b].
 */
function parseRgb(css) {
  const m = css.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  return m[1]
    .split(',')
    .slice(0, 3)
    .map((s) => Number(s.trim()));
}

function hexToRgb(hex) {
  const h = hex.replace('#', '').trim();
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}

function relativeLuminance([r, g, b]) {
  const toLinear = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const [R, G, B] = [toLinear(r), toLinear(g), toLinear(b)];
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

function contrastRatio(rgb1, rgb2) {
  const L1 = relativeLuminance(rgb1);
  const L2 = relativeLuminance(rgb2);
  const [hi, lo] = L1 > L2 ? [L1, L2] : [L2, L1];
  return (hi + 0.05) / (lo + 0.05);
}

test('PagePhenopacket hero-section uses dark gradient under v-theme--dark', async ({ page }) => {
  await page.goto('/phenopackets');
  await page.waitForLoadState('networkidle');
  const firstChip = page.locator('table a.v-chip').first();
  await firstChip.waitFor({ state: 'visible' });
  await firstChip.click();
  await page.waitForLoadState('networkidle');

  // Force dark theme. Vuetify adds v-theme--light / v-theme--dark to
  // <html> via its theme provider; override directly for the test.
  await page.evaluate(() => {
    const root = document.documentElement;
    root.classList.remove('v-theme--light');
    root.classList.add('v-theme--dark');
    document.body.classList.remove('v-theme--light');
    document.body.classList.add('v-theme--dark');
  });

  const hero = page.locator('.hero-section');
  await hero.waitFor({ state: 'visible' });

  const { heroStart, h1Color } = await hero.evaluate((el) => {
    const cs = getComputedStyle(el);
    const h1 = el.querySelector('h1');
    const h1cs = h1 ? getComputedStyle(h1) : null;
    return {
      heroStart: cs.getPropertyValue('--hero-start').trim(),
      h1Color: h1cs ? h1cs.color : null,
    };
  });

  // Under dark theme, --hero-start should resolve to the dark gradient start.
  expect(heroStart.toLowerCase()).toMatch(/#102a2b/);

  // h1 contrast against the dark gradient start must be ≥ 4.5:1 (WCAG AA text).
  expect(h1Color, 'h1 color must be readable').toBeTruthy();
  const ratio = contrastRatio(parseRgb(h1Color), hexToRgb(heroStart));
  expect(ratio, `h1 contrast against hero start (${ratio.toFixed(2)}:1)`).toBeGreaterThanOrEqual(
    4.5
  );
});
