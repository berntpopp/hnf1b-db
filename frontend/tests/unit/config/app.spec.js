import { describe, it, expect } from 'vitest';
import { API_CONFIG, FEATURES, VIZ_CONFIG } from '@/config/app';

describe('API_CONFIG', () => {
  it('has required configuration keys', () => {
    expect(API_CONFIG).toHaveProperty('MAX_VARIANTS_FOR_PRIORITY_SORT');
    expect(API_CONFIG).toHaveProperty('DEFAULT_PAGE_SIZE');
    expect(API_CONFIG).toHaveProperty('MAX_PAGE_SIZE');
  });

  it('has sensible default values', () => {
    expect(API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT).toBe(1000);
    expect(API_CONFIG.DEFAULT_PAGE_SIZE).toBe(100);
    expect(API_CONFIG.MAX_PAGE_SIZE).toBe(1000);
  });

  it('MAX_VARIANTS_FOR_PRIORITY_SORT is a positive number', () => {
    expect(API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT).toBeGreaterThan(0);
    expect(typeof API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT).toBe('number');
  });
});

describe('FEATURES', () => {
  it('has debug logging flag', () => {
    expect(FEATURES).toHaveProperty('DEBUG_LOGGING');
    expect(typeof FEATURES.DEBUG_LOGGING).toBe('boolean');
  });
});

describe('VIZ_CONFIG', () => {
  it('has default SVG width', () => {
    expect(VIZ_CONFIG).toHaveProperty('DEFAULT_SVG_WIDTH');
    expect(VIZ_CONFIG.DEFAULT_SVG_WIDTH).toBeGreaterThan(0);
  });

  it('has HNF1B gene configuration', () => {
    expect(VIZ_CONFIG.HNF1B_GENE).toBeDefined();
    expect(VIZ_CONFIG.HNF1B_GENE.chromosome).toBe('17');
    expect(VIZ_CONFIG.HNF1B_GENE.start).toBe(37680000);
    expect(VIZ_CONFIG.HNF1B_GENE.end).toBe(37750000);
    expect(VIZ_CONFIG.HNF1B_GENE.strand).toBe('-');
  });

  it('has valid HNF1B gene coordinate range', () => {
    expect(VIZ_CONFIG.HNF1B_GENE.start).toBeLessThan(VIZ_CONFIG.HNF1B_GENE.end);
    expect(VIZ_CONFIG.HNF1B_GENE.end - VIZ_CONFIG.HNF1B_GENE.start).toBeGreaterThan(0);
  });
});
