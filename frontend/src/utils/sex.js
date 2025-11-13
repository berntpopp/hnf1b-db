/**
 * Sex/Gender display utilities for phenopacket subjects.
 *
 * Provides consistent formatting and color schemes across all components for:
 * - Sex icons (Material Design Icons)
 * - Sex chip colors (Vuetify color classes)
 * - Sex label formatting
 *
 * @module utils/sex
 */

/**
 * Sex icon mapping (Material Design Icons).
 * Maps GA4GH Phenopackets v2 sex values to MDI icons.
 */
const SEX_ICONS = {
  MALE: 'mdi-gender-male',
  FEMALE: 'mdi-gender-female',
  OTHER_SEX: 'mdi-gender-non-binary',
  UNKNOWN_SEX: 'mdi-help-circle',
};

/**
 * Sex chip color mapping (lighten-3 variants for consistency).
 * Used for chip backgrounds in tables and cards.
 */
const SEX_CHIP_COLORS = {
  MALE: 'blue-lighten-3',
  FEMALE: 'pink-lighten-3',
  OTHER_SEX: 'purple-lighten-3',
  UNKNOWN_SEX: 'grey-lighten-2',
};

/**
 * Sex label mapping (human-readable labels).
 * Converts GA4GH Phenopackets v2 sex enum to display text.
 */
const SEX_LABELS = {
  MALE: 'Male',
  FEMALE: 'Female',
  OTHER_SEX: 'Other',
  UNKNOWN_SEX: 'Unknown',
};

/**
 * Get Material Design Icon for a sex value.
 *
 * @param {string|null|undefined} sex - Sex value from phenopacket
 * @returns {string} MDI icon name
 *
 * @example
 * getSexIcon('MALE') // Returns: 'mdi-gender-male'
 * getSexIcon('FEMALE') // Returns: 'mdi-gender-female'
 * getSexIcon(null) // Returns: 'mdi-help-circle'
 */
export function getSexIcon(sex) {
  return SEX_ICONS[sex] ?? 'mdi-help-circle';
}

/**
 * Get Vuetify chip color class for a sex value.
 * Uses lighten-3 variants for consistent pastel appearance.
 *
 * @param {string|null|undefined} sex - Sex value from phenopacket
 * @returns {string} Vuetify color class
 *
 * @example
 * getSexChipColor('MALE') // Returns: 'blue-lighten-3'
 * getSexChipColor('FEMALE') // Returns: 'pink-lighten-3'
 * getSexChipColor(null) // Returns: 'grey-lighten-2'
 */
export function getSexChipColor(sex) {
  return SEX_CHIP_COLORS[sex] ?? 'grey-lighten-2';
}

/**
 * Format sex value as human-readable label.
 *
 * @param {string|null|undefined} sex - Sex value from phenopacket
 * @returns {string} Formatted label
 *
 * @example
 * formatSex('MALE') // Returns: 'Male'
 * formatSex('UNKNOWN_SEX') // Returns: 'Unknown'
 * formatSex(null) // Returns: 'Unknown'
 */
export function formatSex(sex) {
  return SEX_LABELS[sex] ?? 'Unknown';
}
