/**
 * Unit tests for the ACMG / ClinGen-CNV classification-criteria parser.
 *
 * Tests cover: ACMG token parsing (code + strength + direction + label),
 * pathogenic/benign grouping, ClinGen CNV section parsing with points + total,
 * unknown codes, and empty/null input.
 */
import { describe, it, expect } from 'vitest';
import {
  parseClassificationCriteria,
  acmgChipColor,
  cnvChipColor,
  ACMG_CRITERIA,
} from '@/utils/acmgCriteria';

describe('parseClassificationCriteria — ACMG', () => {
  it('parses a multi-criterion ACMG string into grouped pathogenic/benign entries', () => {
    const r = parseClassificationCriteria(
      'PM1_Moderate, PM2_Supporting, PP3_Supporting, PS2_Strong, BP4_Supporting',
      'ACMG'
    );
    expect(r.guideline).toBe('ACMG');
    expect(r.pathogenic.map((c) => c.code)).toEqual(['PM1', 'PM2', 'PP3', 'PS2']);
    expect(r.benign.map((c) => c.code)).toEqual(['BP4']);
    const ps2 = r.pathogenic.find((c) => c.code === 'PS2');
    expect(ps2).toMatchObject({ code: 'PS2', strength: 'Strong', direction: 'pathogenic' });
    expect(ps2.label).toBe(ACMG_CRITERIA.PS2);
    expect(r.label).toBeUndefined(); // sanity: no stray field
  });

  it('parses a single benign criterion with no pathogenic entries', () => {
    const r = parseClassificationCriteria('BP4_Supporting', 'ACMG');
    expect(r.pathogenic).toEqual([]);
    expect(r.benign).toHaveLength(1);
    expect(r.benign[0]).toMatchObject({ code: 'BP4', strength: 'Supporting', direction: 'benign' });
  });

  it('handles an unknown ACMG code without throwing and with empty label', () => {
    const r = parseClassificationCriteria('ZZ9_Strong', 'ACMG');
    expect(r.pathogenic[0]).toMatchObject({ code: 'ZZ9', strength: 'Strong', label: '' });
  });

  it('handles a criterion with no strength suffix', () => {
    const r = parseClassificationCriteria('BP4', 'ACMG');
    expect(r.benign[0]).toMatchObject({ code: 'BP4', strength: '', direction: 'benign' });
  });
});

describe('parseClassificationCriteria — ClinGen CNV', () => {
  it('parses sections with counts and points and sums the total', () => {
    const r = parseClassificationCriteria('1A, 2A, 3A, 4Cx1(0.15), 4Lx1(0.15)', 'ClinGen CNV');
    expect(r.guideline).toBe('ClinGen CNV');
    expect(r.pathogenic).toEqual([]);
    expect(r.benign).toEqual([]);
    expect(r.cnv.map((c) => c.section)).toEqual(['1A', '2A', '3A', '4C', '4L']);
    const fourC = r.cnv.find((c) => c.section === '4C');
    expect(fourC).toMatchObject({ section: '4C', count: 1, points: 0.15 });
    expect(r.totalPoints).toBeCloseTo(0.3, 5);
  });

  it('treats the parenthesized value as the section total (not per-occurrence)', () => {
    const r = parseClassificationCriteria('4Cx6(0.9)', 'ClinGen CNV');
    expect(r.cnv[0]).toMatchObject({ section: '4C', count: 6, points: 0.9 });
    expect(r.totalPoints).toBeCloseTo(0.9, 5);
  });
});

describe('parseClassificationCriteria — empty/null', () => {
  it('returns empty groups for empty string', () => {
    const r = parseClassificationCriteria('', 'ACMG');
    expect(r.pathogenic).toEqual([]);
    expect(r.benign).toEqual([]);
    expect(r.cnv).toEqual([]);
    expect(r.raw).toBe('');
  });

  it('returns empty groups for null criteria', () => {
    const r = parseClassificationCriteria(null, null);
    expect(r.guideline).toBe('ACMG'); // default guideline
    expect(r.pathogenic).toEqual([]);
  });
});

describe('chip color helpers', () => {
  it('colors pathogenic by strength and benign green', () => {
    expect(acmgChipColor({ direction: 'pathogenic', strength: 'Strong' })).toBe('red');
    expect(acmgChipColor({ direction: 'pathogenic', strength: 'Moderate' })).toBe('deep-orange');
    expect(acmgChipColor({ direction: 'pathogenic', strength: 'Supporting' })).toBe('orange');
    expect(acmgChipColor({ direction: 'benign', strength: 'Strong' })).toBe('green');
  });

  it('colors CNV chips by point sign', () => {
    expect(cnvChipColor(0.15)).toBe('orange');
    expect(cnvChipColor(-0.3)).toBe('green');
    expect(cnvChipColor(null)).toBe('grey');
  });
});
