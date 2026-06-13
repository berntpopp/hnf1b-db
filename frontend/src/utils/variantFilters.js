/**
 * Shared variant filtering + colour-by-mode logic for the variant
 * visualizations (protein lollipop and gene-structure plots).
 *
 * Both plots historically coloured variants only by ACMG pathogenicity and
 * offered (at most) a single-select pathogenicity filter. This module is the
 * single source of truth for the richer, SysNDD-style controls:
 *
 *  - a colour-by toggle (ACMG classification ⇄ molecular consequence / type)
 *  - independent multi-select filters for pathogenicity AND consequence
 *  - AND-logic visibility (a variant must pass both dimensions)
 *  - count-aware legend builders
 *
 * State is treated as immutable: every mutation helper returns a NEW filter
 * state object so it can flow cleanly through `v-model` without prop mutation.
 *
 * @module utils/variantFilters
 */

import {
  getConsequenceHexColor,
  getConsequenceTaxonomy,
  getPathogenicityHexColor,
  normalizeConsequence,
  normalizePathogenicity,
} from './colors';

/** Ordered consequence taxonomy keys (mirrors colors.CONSEQUENCE_ORDER). */
const CONSEQUENCE_ORDER = getConsequenceTaxonomy().map((entry) => entry.key);

/** Pathogenicity classes in canonical (most→least severe) display order. */
export const PATHOGENICITY_ORDER = [
  'PATHOGENIC',
  'LIKELY_PATHOGENIC',
  'VUS',
  'LIKELY_BENIGN',
  'BENIGN',
];

/** Human-readable labels for pathogenicity classes. */
export const PATHOGENICITY_LABELS = {
  PATHOGENIC: 'Pathogenic',
  LIKELY_PATHOGENIC: 'Likely pathogenic',
  VUS: 'VUS',
  LIKELY_BENIGN: 'Likely benign',
  BENIGN: 'Benign',
};

/** Colour-by modes for variant markers. */
export const COLORING_MODES = Object.freeze({
  CLASSIFICATION: 'classification',
  CONSEQUENCE: 'consequence',
});

function allTrue(keys) {
  return keys.reduce((acc, key) => {
    acc[key] = true;
    return acc;
  }, {});
}

/**
 * Build a fresh filter state with every category visible and colouring by
 * ACMG classification (the established default for both plots).
 *
 * @returns {{coloringMode: string, pathogenicity: Object, consequence: Object}}
 */
export function createDefaultFilterState() {
  return {
    coloringMode: COLORING_MODES.CLASSIFICATION,
    pathogenicity: allTrue(PATHOGENICITY_ORDER),
    consequence: allTrue(CONSEQUENCE_ORDER),
  };
}

/**
 * Read the pathogenicity verdict from a variant, tolerating the two field
 * names used across the app (`classificationVerdict` and `pathogenicity`).
 */
function variantVerdict(variant) {
  return variant?.classificationVerdict ?? variant?.pathogenicity ?? null;
}

/**
 * Whether a variant's pathogenicity passes the current filter.
 * Unrecognized/absent classifications are always shown (never hidden).
 */
export function isPathogenicityVisible(variant, state) {
  const key = normalizePathogenicity(variantVerdict(variant));
  if (!key) return true;
  return state?.pathogenicity?.[key] !== false;
}

/**
 * Whether a variant's molecular consequence passes the current filter.
 */
export function isConsequenceVisible(variant, state) {
  const key = normalizeConsequence(variant?.molecular_consequence);
  return state?.consequence?.[key] !== false;
}

/**
 * AND-logic visibility: a variant is shown only when it passes BOTH the
 * pathogenicity and consequence filters.
 */
export function isVariantVisibleByFilters(variant, state) {
  if (!state) return true;
  return isPathogenicityVisible(variant, state) && isConsequenceVisible(variant, state);
}

/**
 * Mode-aware marker colour for a variant.
 * - classification mode → ACMG pathogenicity hex colour
 * - consequence mode    → molecular-consequence hex colour
 *
 * @returns {string} Hex colour
 */
export function getVariantColorByMode(variant, state) {
  if (state?.coloringMode === COLORING_MODES.CONSEQUENCE) {
    return getConsequenceHexColor(variant?.molecular_consequence);
  }
  return getPathogenicityHexColor(variantVerdict(variant));
}

/**
 * Build the pathogenicity legend/filter rows for a set of variants.
 * Only categories actually present (count > 0) are returned, so plots never
 * render dead chips (e.g. the gene has no benign curated variants).
 *
 * @returns {Array<{key,label,color,visible,count}>}
 */
export function buildPathogenicityLegend(variants, state) {
  const counts = {};
  for (const variant of variants) {
    const key = normalizePathogenicity(variantVerdict(variant));
    if (key) counts[key] = (counts[key] || 0) + 1;
  }
  return PATHOGENICITY_ORDER.filter((key) => counts[key] > 0).map((key) => ({
    key,
    label: PATHOGENICITY_LABELS[key],
    color: getPathogenicityHexColor(key),
    visible: state?.pathogenicity?.[key] !== false,
    count: counts[key],
  }));
}

/**
 * Build the consequence (variant-type) legend/filter rows for a set of
 * variants. Only present categories (count > 0) are returned and they follow
 * the canonical taxonomy order.
 *
 * @returns {Array<{key,label,color,visible,count}>}
 */
export function buildConsequenceLegend(variants, state) {
  const counts = {};
  for (const variant of variants) {
    const key = normalizeConsequence(variant?.molecular_consequence);
    counts[key] = (counts[key] || 0) + 1;
  }
  // Use the taxonomy entries directly (key → label/color) — passing a
  // normalized key back through getConsequenceLabel/Color would re-normalize it
  // and mislabel the copy-number buckets (e.g. 'cnv_loss' → 'other').
  return getConsequenceTaxonomy()
    .filter((entry) => counts[entry.key] > 0)
    .map((entry) => ({
      key: entry.key,
      label: entry.label,
      color: entry.color,
      visible: state?.consequence?.[entry.key] !== false,
      count: counts[entry.key],
    }));
}

// --- Immutable mutation helpers (return a new state) -----------------------

/** Return a new state with the colouring mode set. */
export function withColoringMode(state, mode) {
  return { ...state, coloringMode: mode };
}

/** Return a new state with one pathogenicity category toggled on/off. */
export function withToggledPathogenicity(state, key) {
  return {
    ...state,
    pathogenicity: { ...state.pathogenicity, [key]: state.pathogenicity?.[key] === false },
  };
}

/** Return a new state with one consequence category toggled on/off. */
export function withToggledConsequence(state, key) {
  return {
    ...state,
    consequence: { ...state.consequence, [key]: state.consequence?.[key] === false },
  };
}

/** Return a new state showing ONLY the given pathogenicity category. */
export function withOnlyPathogenicity(state, key) {
  const pathogenicity = {};
  for (const k of PATHOGENICITY_ORDER) pathogenicity[k] = k === key;
  return { ...state, pathogenicity };
}

/** Return a new state showing ONLY the given consequence category. */
export function withOnlyConsequence(state, key) {
  const consequence = {};
  for (const k of CONSEQUENCE_ORDER) consequence[k] = k === key;
  return { ...state, consequence };
}

/** Return a new state with all pathogenicity categories visible. */
export function withAllPathogenicity(state) {
  return { ...state, pathogenicity: allTrue(PATHOGENICITY_ORDER) };
}

/** Return a new state with all consequence categories visible. */
export function withAllConsequence(state) {
  return { ...state, consequence: allTrue(CONSEQUENCE_ORDER) };
}
