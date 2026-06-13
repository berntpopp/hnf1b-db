/**
 * Unit tests for the shared variant filtering / colour-by-mode logic.
 */
import { describe, it, expect } from 'vitest';
import {
  COLORING_MODES,
  PATHOGENICITY_ORDER,
  buildConsequenceLegend,
  buildPathogenicityLegend,
  createDefaultFilterState,
  getVariantColorByMode,
  isVariantVisibleByFilters,
  withAllConsequence,
  withColoringMode,
  withOnlyConsequence,
  withOnlyPathogenicity,
  withToggledConsequence,
  withToggledPathogenicity,
} from '@/utils/variantFilters';

const variants = [
  { classificationVerdict: 'PATHOGENIC', molecular_consequence: 'Missense' },
  { classificationVerdict: 'LIKELY_PATHOGENIC', molecular_consequence: 'Frameshift' },
  { classificationVerdict: 'VUS', molecular_consequence: 'Missense' },
  { classificationVerdict: 'PATHOGENIC', molecular_consequence: 'Copy Number Loss' },
  { classificationVerdict: 'PATHOGENIC', molecular_consequence: 'Copy Number Gain' },
];

describe('createDefaultFilterState', () => {
  it('defaults to classification colouring with everything visible', () => {
    const state = createDefaultFilterState();
    expect(state.coloringMode).toBe(COLORING_MODES.CLASSIFICATION);
    expect(PATHOGENICITY_ORDER.every((k) => state.pathogenicity[k] === true)).toBe(true);
    expect(state.consequence.missense).toBe(true);
    expect(state.consequence.cnv_loss).toBe(true);
  });
});

describe('isVariantVisibleByFilters', () => {
  it('is AND-logic across pathogenicity and consequence', () => {
    const state = createDefaultFilterState();
    expect(isVariantVisibleByFilters(variants[0], state)).toBe(true);

    // Hide missense -> the missense/PATHOGENIC variant disappears...
    const noMissense = withToggledConsequence(state, 'missense');
    expect(isVariantVisibleByFilters(variants[0], noMissense)).toBe(false);
    // ...but the frameshift one still shows.
    expect(isVariantVisibleByFilters(variants[1], noMissense)).toBe(true);

    // Hide VUS -> the VUS/missense variant disappears even though missense is on.
    const noVus = withToggledPathogenicity(state, 'VUS');
    expect(isVariantVisibleByFilters(variants[2], noVus)).toBe(false);
    expect(isVariantVisibleByFilters(variants[0], noVus)).toBe(true);
  });

  it('shows variants with unknown classification/consequence (never hidden by default)', () => {
    const state = createDefaultFilterState();
    expect(isVariantVisibleByFilters({}, state)).toBe(true);
  });
});

describe('getVariantColorByMode', () => {
  it('colours by ACMG in classification mode', () => {
    const state = createDefaultFilterState();
    expect(getVariantColorByMode(variants[0], state)).toBe('#EF5350'); // PATHOGENIC
  });

  it('colours by consequence in type mode', () => {
    const state = withColoringMode(createDefaultFilterState(), COLORING_MODES.CONSEQUENCE);
    expect(getVariantColorByMode(variants[0], state)).toBe('#1F77B4'); // missense
    expect(getVariantColorByMode(variants[3], state)).toBe('#B2182B'); // cnv_loss
    expect(getVariantColorByMode(variants[4], state)).toBe('#2166AC'); // cnv_gain
  });
});

describe('legend builders', () => {
  it('builds pathogenicity legend with counts, only present categories', () => {
    const legend = buildPathogenicityLegend(variants, createDefaultFilterState());
    const byKey = Object.fromEntries(legend.map((l) => [l.key, l]));
    expect(byKey.PATHOGENIC.count).toBe(3);
    expect(byKey.LIKELY_PATHOGENIC.count).toBe(1);
    expect(byKey.VUS.count).toBe(1);
    expect(byKey.BENIGN).toBeUndefined(); // absent category not rendered
    expect(legend.every((l) => l.visible)).toBe(true);
  });

  it('builds consequence legend with correct labels/colours incl. CNV buckets', () => {
    const legend = buildConsequenceLegend(variants, createDefaultFilterState());
    const byKey = Object.fromEntries(legend.map((l) => [l.key, l]));
    expect(byKey.missense.count).toBe(2);
    expect(byKey.cnv_loss).toMatchObject({ label: 'CN Loss', color: '#B2182B', count: 1 });
    expect(byKey.cnv_gain).toMatchObject({ label: 'CN Gain', color: '#2166AC', count: 1 });
  });

  it('reflects visibility from filter state', () => {
    const state = withToggledConsequence(createDefaultFilterState(), 'missense');
    const legend = buildConsequenceLegend(variants, state);
    const missense = legend.find((l) => l.key === 'missense');
    expect(missense.visible).toBe(false);
  });
});

describe('mutation helpers (immutable)', () => {
  it('toggle returns a new object and flips one key', () => {
    const state = createDefaultFilterState();
    const next = withToggledPathogenicity(state, 'PATHOGENIC');
    expect(next).not.toBe(state);
    expect(next.pathogenicity.PATHOGENIC).toBe(false);
    expect(state.pathogenicity.PATHOGENIC).toBe(true); // original untouched
  });

  it('only isolates a single category', () => {
    const state = withOnlyConsequence(createDefaultFilterState(), 'frameshift');
    expect(state.consequence.frameshift).toBe(true);
    expect(state.consequence.missense).toBe(false);
    expect(state.consequence.cnv_loss).toBe(false);
  });

  it('only + all round-trips back to fully visible', () => {
    const only = withOnlyPathogenicity(createDefaultFilterState(), 'VUS');
    expect(only.pathogenicity.PATHOGENIC).toBe(false);
    const all = withAllConsequence(withColoringMode(only, COLORING_MODES.CLASSIFICATION));
    expect(Object.values(all.consequence).every(Boolean)).toBe(true);
  });
});
