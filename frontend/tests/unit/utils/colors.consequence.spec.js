/**
 * Unit tests for the molecular-consequence taxonomy added to utils/colors.
 *
 * Guards the normalization (display values AND VEP-style tokens), the
 * key→colour/label lookups, and — importantly — the copy-number buckets that
 * a naive substring normalizer would drop into "other".
 */
import { describe, it, expect } from 'vitest';
import {
  CONSEQUENCE_ORDER,
  getConsequenceHexColor,
  getConsequenceLabel,
  getConsequenceTaxonomy,
  normalizeConsequence,
  normalizePathogenicity,
} from '@/utils/colors';

describe('normalizeConsequence', () => {
  it('maps curated display values to taxonomy keys', () => {
    expect(normalizeConsequence('Missense')).toBe('missense');
    expect(normalizeConsequence('Nonsense')).toBe('nonsense');
    expect(normalizeConsequence('Frameshift')).toBe('frameshift');
    expect(normalizeConsequence('Splice Donor')).toBe('splice');
    expect(normalizeConsequence('Splice Acceptor')).toBe('splice');
    expect(normalizeConsequence('In-frame Deletion')).toBe('inframe_indel');
    expect(normalizeConsequence('Synonymous')).toBe('synonymous');
    expect(normalizeConsequence('Intronic Variant')).toBe('intronic');
    expect(normalizeConsequence('Copy Number Loss')).toBe('cnv_loss');
    expect(normalizeConsequence('Copy Number Gain')).toBe('cnv_gain');
  });

  it('maps VEP-style tokens to taxonomy keys', () => {
    expect(normalizeConsequence('missense_variant')).toBe('missense');
    expect(normalizeConsequence('stop_gained')).toBe('nonsense');
    expect(normalizeConsequence('frameshift_variant')).toBe('frameshift');
    expect(normalizeConsequence('splice_donor_variant')).toBe('splice');
    expect(normalizeConsequence('inframe_deletion')).toBe('inframe_indel');
  });

  it('falls back to "other" for unknown/empty input', () => {
    expect(normalizeConsequence('something weird')).toBe('other');
    expect(normalizeConsequence('')).toBe('other');
    expect(normalizeConsequence(null)).toBe('other');
    expect(normalizeConsequence(undefined)).toBe('other');
  });
});

describe('getConsequenceHexColor', () => {
  it('returns distinct hex colours for the main categories', () => {
    expect(getConsequenceHexColor('Missense')).toBe('#1F77B4');
    expect(getConsequenceHexColor('Frameshift')).toBe('#D62728');
    expect(getConsequenceHexColor('Copy Number Loss')).toBe('#B2182B');
    expect(getConsequenceHexColor('Copy Number Gain')).toBe('#2166AC');
  });

  it('returns a neutral grey for null/unknown', () => {
    expect(getConsequenceHexColor(null)).toBe('#BDBDBD');
    expect(getConsequenceHexColor('nope')).toBe('#BCBD22'); // 'other' bucket colour
  });
});

describe('getConsequenceTaxonomy', () => {
  it('returns one entry per ordered key with label + colour', () => {
    const taxonomy = getConsequenceTaxonomy();
    expect(taxonomy.map((t) => t.key)).toEqual(CONSEQUENCE_ORDER);
    taxonomy.forEach((entry) => {
      expect(entry.label).toBeTruthy();
      expect(entry.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    });
  });

  it('labels the copy-number buckets correctly (regression)', () => {
    const byKey = Object.fromEntries(getConsequenceTaxonomy().map((t) => [t.key, t]));
    expect(byKey.cnv_loss.label).toBe('CN Loss');
    expect(byKey.cnv_gain.label).toBe('CN Gain');
    // getConsequenceLabel re-normalizes raw values; a normalized key must NOT
    // round-trip back to "other".
    expect(getConsequenceLabel('Copy Number Loss')).toBe('CN Loss');
  });
});

describe('normalizePathogenicity', () => {
  it('buckets verdicts into canonical keys', () => {
    expect(normalizePathogenicity('Pathogenic')).toBe('PATHOGENIC');
    expect(normalizePathogenicity('LIKELY_PATHOGENIC')).toBe('LIKELY_PATHOGENIC');
    expect(normalizePathogenicity('Uncertain Significance')).toBe('VUS');
    expect(normalizePathogenicity('VUS')).toBe('VUS');
    expect(normalizePathogenicity('Likely Benign')).toBe('LIKELY_BENIGN');
    expect(normalizePathogenicity('Benign')).toBe('BENIGN');
    expect(normalizePathogenicity(null)).toBeNull();
  });
});
