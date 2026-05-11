import { describe, it, expect, vi } from 'vitest';
import { buildExportFilename } from '@/utils/chartExport';

describe('buildExportFilename', () => {
  it('formats as hnf1b-db_<kebab>_<date>.<ext>', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T12:00:00Z'));
    expect(buildExportFilename('Sex Distribution', 'png')).toBe(
      'hnf1b-db_sex-distribution_2026-05-11.png'
    );
    vi.useRealTimers();
  });

  it('kebab-cases multi-word names with mixed case and underscores', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T00:00:00Z'));
    expect(buildExportFilename('Kaplan_Meier survivalCurve', 'csv')).toBe(
      'hnf1b-db_kaplan-meier-survival-curve_2026-05-11.csv'
    );
    vi.useRealTimers();
  });
});
