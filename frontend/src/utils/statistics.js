/**
 * Statistical Analysis Utilities
 *
 * Provides statistical functions for data analysis in visualizations.
 * Extracted from DNADistanceAnalysis.vue for reuse across components.
 *
 * @module utils/statistics
 */

/**
 * Calculate descriptive statistics for an array of numeric values.
 *
 * @param {number[]} values - Array of numeric values
 * @returns {Object|null} Statistics object or null if empty array
 *
 * @example
 * calculateDescriptiveStats([1, 2, 3, 4, 5])
 * // Returns: { count: 5, mean: 3, median: 3, stdDev: 1.41, min: 1, max: 5, q1: 2, q3: 4 }
 */
export function calculateDescriptiveStats(values) {
  if (!Array.isArray(values) || values.length === 0) return null;

  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;

  const sum = sorted.reduce((a, b) => a + b, 0);
  const mean = sum / n;

  const mid = Math.floor(n / 2);
  const median = n % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;

  const squaredDiffs = sorted.map((v) => Math.pow(v - mean, 2));
  const avgSquaredDiff = squaredDiffs.reduce((a, b) => a + b, 0) / n;
  const stdDev = Math.sqrt(avgSquaredDiff);

  const q1Index = Math.floor(n * 0.25);
  const q3Index = Math.floor(n * 0.75);

  return {
    count: n,
    mean,
    median,
    stdDev,
    min: sorted[0],
    max: sorted[n - 1],
    q1: sorted[q1Index],
    q3: sorted[q3Index],
    values: sorted,
  };
}

/**
 * Perform Mann-Whitney U test (non-parametric comparison of two groups).
 *
 * @param {number[]} x - First group values
 * @param {number[]} y - Second group values
 * @returns {Object} Test results including U statistic, p-value, and effect size
 *
 * @example
 * mannWhitneyU([1, 2, 3], [4, 5, 6])
 * // Returns: { U: 0, pValue: 0.05, rankBiserial: -1, effectMagnitude: 'large', ... }
 */
export function mannWhitneyU(x, y) {
  // Combine and rank
  const combined = [
    ...x.map((v) => ({ value: v, group: 'x' })),
    ...y.map((v) => ({ value: v, group: 'y' })),
  ];
  combined.sort((a, b) => a.value - b.value);

  // Assign ranks (handling ties) and track tie groups for correction
  const tieGroups = [];
  let rank = 1;
  for (let i = 0; i < combined.length; i++) {
    let j = i;
    while (j < combined.length - 1 && combined[j + 1].value === combined[i].value) {
      j++;
    }
    const tieSize = j - i + 1;
    const avgRank = rank + (tieSize - 1) / 2;
    for (let k = i; k <= j; k++) {
      combined[k].rank = avgRank;
    }
    if (tieSize > 1) {
      tieGroups.push(tieSize);
    }
    rank += tieSize;
    i = j;
  }

  // Calculate U statistic
  const n1 = x.length;
  const n2 = y.length;
  const n = n1 + n2;
  const r1 = combined.filter((c) => c.group === 'x').reduce((sum, c) => sum + c.rank, 0);

  const U1 = r1 - (n1 * (n1 + 1)) / 2;
  const U2 = n1 * n2 - U1;
  const U = Math.min(U1, U2);

  // Calculate p-value
  let pValue;
  let method;
  const mu = (n1 * n2) / 2;

  if (n1 <= 20 && n2 <= 20 && tieGroups.length === 0) {
    // Exact p-value for small samples without ties
    pValue = exactMannWhitneyP(U, n1, n2);
    method = 'exact';
  } else {
    // Normal approximation with tie correction
    const tieCorrection = tieGroups.reduce((sum, t) => sum + (t * t * t - t), 0);
    const variance = (n1 * n2 * (n + 1)) / 12 - (n1 * n2 * tieCorrection) / (12 * n * (n - 1));
    const sigma = Math.sqrt(variance);
    const z = sigma > 0 ? (Math.abs(U - mu) - 0.5) / sigma : 0;
    pValue = 2 * (1 - normalCDF(z));
    method = tieGroups.length > 0 ? 'normal_tie_corrected' : 'normal';
  }

  // Effect size: Rank-biserial correlation
  const rankBiserial = 1 - (2 * U) / (n1 * n2);

  // Interpret effect size magnitude
  const absR = Math.abs(rankBiserial);
  let effectMagnitude;
  if (absR >= 0.5) effectMagnitude = 'large';
  else if (absR >= 0.3) effectMagnitude = 'medium';
  else if (absR >= 0.1) effectMagnitude = 'small';
  else effectMagnitude = 'negligible';

  return {
    U,
    U1,
    U2,
    pValue,
    method,
    tieCount: tieGroups.length,
    rankBiserial,
    effectMagnitude,
    n1,
    n2,
  };
}

/**
 * Calculate exact p-value for Mann-Whitney U test using dynamic programming.
 * @private
 */
function exactMannWhitneyP(U, n1, n2) {
  const memo = new Map();

  const countWays = (i, j, currentU) => {
    if (i === 0 && j === 0) return currentU >= 0 ? 1 : 0;
    if (i < 0 || j < 0 || currentU < 0) return 0;

    const key = `${i},${j},${currentU}`;
    if (memo.has(key)) return memo.get(key);

    const ways = countWays(i - 1, j, currentU - j) + countWays(i, j - 1, currentU);
    memo.set(key, ways);
    return ways;
  };

  const totalArrangements = binomialCoeff(n1 + n2, n1);

  let countLessOrEqual = 0;
  for (let u = 0; u <= U; u++) {
    memo.clear();
    countLessOrEqual += countWays(n1, n2, u);
  }

  const pOneTail = countLessOrEqual / totalArrangements;
  return Math.min(1, 2 * pOneTail);
}

/**
 * Calculate binomial coefficient C(n, k).
 * @private
 */
function binomialCoeff(n, k) {
  if (k > n - k) k = n - k;
  let result = 1;
  for (let i = 0; i < k; i++) {
    result = (result * (n - i)) / (i + 1);
  }
  return Math.round(result);
}

/**
 * Approximation of the standard normal CDF (Abramowitz and Stegun).
 * @param {number} x - Z-score
 * @returns {number} Cumulative probability
 */
export function normalCDF(x) {
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const sign = x < 0 ? -1 : 1;
  const absX = Math.abs(x);

  const t = 1.0 / (1.0 + p * absX);
  const y = 1.0 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX);

  return 0.5 * (1.0 + sign * y);
}

/**
 * Format p-value for display.
 *
 * @param {number|null|undefined} pValue - P-value to format
 * @returns {string} Formatted p-value string
 *
 * @example
 * formatPValue(0.00001) // Returns: '< 0.0001'
 * formatPValue(0.0123) // Returns: '0.012'
 */
export function formatPValue(pValue) {
  if (!pValue && pValue !== 0) return 'N/A';
  if (pValue < 0.0001) return '< 0.0001';
  if (pValue < 0.001) return pValue.toFixed(4);
  return pValue.toFixed(3);
}

/**
 * Get color for rank-biserial correlation effect size.
 *
 * @param {number} r - Rank-biserial correlation coefficient
 * @returns {string} Vuetify color name
 */
export function getRankBiserialColor(r) {
  const absR = Math.abs(r);
  if (absR >= 0.5) return 'error';
  if (absR >= 0.3) return 'warning';
  if (absR >= 0.1) return 'info';
  return 'grey';
}
