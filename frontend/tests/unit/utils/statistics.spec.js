/**
 * Unit tests for src/utils/statistics.js.
 *
 * The Mann-Whitney U test feeds the DNA-distance analysis (P/LP vs VUS), so
 * both p-value paths are pinned to reference values from R's `wilcox.test`
 * and `pnorm`: the normal approximation must use the standard normal CDF,
 * and the exact branch must not sum cumulative counts twice.
 */
import { describe, it, expect } from 'vitest';
import { mannWhitneyU, normalCDF } from '@/utils/statistics';

describe('normalCDF', () => {
  it('matches the standard normal CDF', () => {
    expect(normalCDF(0)).toBeCloseTo(0.5, 6);
    expect(normalCDF(1.96)).toBeCloseTo(0.975, 5);
    expect(normalCDF(-1.96)).toBeCloseTo(0.025, 5);
    expect(normalCDF(1)).toBeCloseTo(0.8413, 4);
  });
});

describe('mannWhitneyU', () => {
  it('uses the exact null distribution without cumulative double counting', () => {
    const p1 = mannWhitneyU([1, 2, 3], [4, 5, 6]);
    expect(p1).toMatchObject({ U: 0, method: 'exact' });
    expect(p1.pValue).toBeCloseTo(0.1, 10);

    const p2 = mannWhitneyU([1, 2, 4], [3, 5, 6]);
    expect(p2).toMatchObject({ U: 1, method: 'exact' });
    expect(p2.pValue).toBeCloseTo(0.2, 10);

    const p3 = mannWhitneyU([1, 3, 4], [2, 5, 6]);
    expect(p3).toMatchObject({ U: 2, method: 'exact' });
    expect(p3.pValue).toBeCloseTo(0.4, 10);
  });

  it('reports the normal-approximation p-value on the standard normal scale', () => {
    const x = Array.from({ length: 25 }, (_, i) => i);
    const y = Array.from({ length: 25 }, (_, i) => 8.5 + i);
    const result = mannWhitneyU(x, y);
    expect(result).toMatchObject({ U: 136, method: 'normal' });
    // R: wilcox.test(x, y, exact = FALSE)$p.value == 6.3815e-04
    expect(result.pValue).toBeCloseTo(6.3815e-4, 6);
  });
});
