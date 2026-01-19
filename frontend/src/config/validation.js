/**
 * Configuration Validation
 *
 * Validates app configuration on startup to catch misconfigurations early.
 */

import { API_CONFIG, VIZ_CONFIG } from './app.js';

/**
 * Validation rules for configuration values
 */
const VALIDATION_RULES = [
  {
    name: 'MAX_VARIANTS_FOR_PRIORITY_SORT',
    value: () => API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT,
    validate: (v) => typeof v === 'number' && v > 0 && v <= 10000,
    message: 'Must be a positive number <= 10000',
  },
  {
    name: 'DEFAULT_PAGE_SIZE',
    value: () => API_CONFIG.DEFAULT_PAGE_SIZE,
    validate: (v) => typeof v === 'number' && v > 0 && v <= 1000,
    message: 'Must be a positive number <= 1000',
  },
  {
    name: 'TIMEOUTS.DEFAULT',
    value: () => API_CONFIG.TIMEOUTS.DEFAULT,
    validate: (v) => typeof v === 'number' && v >= 1000 && v <= 300000,
    message: 'Must be between 1000ms and 300000ms',
  },
  {
    name: 'VIZ_CONFIG.DEFAULT_SVG_WIDTH',
    value: () => VIZ_CONFIG.DEFAULT_SVG_WIDTH,
    validate: (v) => typeof v === 'number' && v >= 100 && v <= 5000,
    message: 'Must be between 100 and 5000',
  },
];

/**
 * Validates all configuration values and logs warnings for invalid configs.
 * Does not throw - allows app to continue with warnings in development.
 *
 * @returns {Object} { valid: boolean, errors: string[] }
 */
export function validateConfig() {
  const errors = [];

  for (const rule of VALIDATION_RULES) {
    try {
      const value = rule.value();
      if (!rule.validate(value)) {
        errors.push(`Config ${rule.name}: ${rule.message} (got: ${value})`);
      }
    } catch (e) {
      errors.push(`Config ${rule.name}: Failed to read - ${e.message}`);
    }
  }

  if (errors.length > 0) {
    console.warn('[Config Validation] Issues found:');
    errors.forEach((err) => console.warn(`  - ${err}`));
  }

  return { valid: errors.length === 0, errors };
}

export default { validateConfig };
