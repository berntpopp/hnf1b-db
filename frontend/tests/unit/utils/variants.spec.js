import { describe, it, expect } from 'vitest';
import {
  HNF1B_START,
  HNF1B_END,
  isCNV,
  getVariantType,
  getVariantSize,
  getCNVDetails,
} from '@/utils/variants';

describe('variants.js [DATA-01]', () => {
  describe('HNF1B coordinates', () => {
    it('uses GRCh38 coordinates for HNF1B_START and HNF1B_END', () => {
      expect(HNF1B_START).toBe(37686431);
      expect(HNF1B_END).toBe(37745059);
    });
  });

  describe('isCNV', () => {
    it('returns true for large CNVs spanning beyond HNF1B', () => {
      expect(isCNV({ hg38: '17:36000000-38000000:DEL' })).toBe(true);
    });

    it('returns true for intragenic multi-exon deletions >= 50bp within HNF1B', () => {
      // 37690000 - 37740000 is inside HNF1B boundaries (37686431 - 37745059)
      expect(isCNV({ hg38: '17:37690000-37740000:DEL' })).toBe(true);
    });

    it('returns true when variant_type or type is explicitly CNV', () => {
      expect(isCNV({ variant_type: 'CNV' })).toBe(true);
      expect(isCNV({ type: 'CNV' })).toBe(true);
    });

    it('returns false for small deletions < 50bp within or outside HNF1B', () => {
      expect(isCNV({ hg38: '17:37700000-37700020:DEL' })).toBe(false);
    });

    it('returns false for SNVs', () => {
      expect(isCNV({ hg38: '17:37686431:A:G' })).toBe(false);
      expect(isCNV({ transcript: 'NM_000458.4:c.544G>T' })).toBe(false);
    });

    it('returns false for falsy or empty inputs', () => {
      expect(isCNV(null)).toBe(false);
      expect(isCNV(undefined)).toBe(false);
      expect(isCNV({})).toBe(false);
      expect(isCNV({ hg38: null })).toBe(false);
      expect(isCNV({ hg38: '' })).toBe(false);
    });
  });

  describe('getVariantType and details', () => {
    it('classifies CNV from hg38 coordinate range', () => {
      expect(getVariantType({ hg38: '17:37686431-37745059:DEL' })).toBe('CNV');
      expect(
        getVariantType({ hg38: '17:37686431-37745059:DEL' }, { specificCNVType: true })
      ).toBe('deletion');
    });

    it('calculates variant size for CNVs', () => {
      expect(getVariantSize({ hg38: '17:37686431-37745059:DEL' })).toBe(58628);
    });

    it('extracts CNV details', () => {
      expect(getCNVDetails({ hg38: '17:37686431-37745059:DEL' })).toEqual({
        chromosome: '17',
        start: '37686431',
        end: '37745059',
        type: 'DEL',
      });
    });
  });
});
