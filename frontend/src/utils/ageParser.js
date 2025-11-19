/**
 * Timeline utilities for parsing ages and providing consistent styling
 */

/**
 * Parse ISO8601 duration string to numeric age in years
 * @param {string} iso8601duration - Duration string like "P5Y6M", "P10Y", "P6M"
 * @returns {number} Age in years (e.g., 5.5 for "P5Y6M")
 */
export function parseAge(iso8601duration) {
  if (!iso8601duration) return null;
  
  const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
  const matches = iso8601duration.match(regex);
  
  if (!matches) return null;
  
  const years = parseInt(matches[1] || 0);
  const months = parseInt(matches[2] || 0);
  const days = parseInt(matches[3] || 0);
  
  return years + (months / 12) + (days / 365);
}

/**
 * Format numeric age to readable string
 * @param {number} age - Age in years
 * @returns {string} Formatted age (e.g., "5.5 years", "6 months")
 */
export function formatAge(age) {
  if (age === null || age === undefined) return 'Unknown';
  
  if (age === 0) return 'Birth';
  if (age < 1) {
    const months = Math.round(age * 12);
    return `${months} month${months !== 1 ? 's' : ''}`;
  }
  if (age === Math.floor(age)) {
    return `${age} year${age !== 1 ? 's' : ''}`;
  }
  return `${age.toFixed(1)} years`;
}

/**
 * Map HPO onset ontology class to age
 * @param {string} hpoId - HPO term ID for onset
 * @returns {number|null} Age in years or null
 */
export function onsetClassToAge(hpoId) {
  const onsetMapping = {
    'HP:0003577': 0,         // Congenital onset
    'HP:0003623': 0,         // Neonatal onset (0-4 weeks)
    'HP:0034199': 0.08,      // Neonatal onset (approx 1 month)
    'HP:0003593': 0.5,       // Infantile onset (1-12 months)
    'HP:0410280': 3,         // Pediatric onset (midpoint ~age 3)
    'HP:0003621': 5,         // Juvenile onset (midpoint ~age 5)
    'HP:0011462': 12,        // Young adult onset (midpoint ~age 12)
    'HP:0003581': 25,        // Adult onset (midpoint ~age 25)
    'HP:0003596': 40,        // Middle age onset (midpoint ~age 40)
    'HP:0003584': 65,        // Late onset (midpoint ~age 65)
  };
  
  return onsetMapping[hpoId] || null;
}

/**
 * Timeline color scheme for organ systems/categories
 */
export const TIMELINE_COLORS = {
  renal: '#1976D2',           // Blue
  diabetes: '#F57C00',        // Orange
  genital: '#7B1FA2',         // Purple
  hepatic: '#388E3C',         // Green
  pancreatic: '#C62828',      // Red
  neurological: '#0097A7',    // Cyan
  skeletal: '#5D4037',        // Brown
  cardiovascular: '#E91E63',  // Pink
  endocrine: '#FBC02D',       // Yellow
  other: '#757575',           // Grey
  unknown: '#BDBDBD',         // Light grey
  excluded: '#E0E0E0',        // Very light grey
};

/**
 * Get color for a category/organ system
 * @param {string} category - Category name (lowercase)
 * @returns {string} Hex color code
 */
export function getCategoryColor(category) {
  const normalized = (category || 'unknown').toLowerCase();
  return TIMELINE_COLORS[normalized] || TIMELINE_COLORS.other;
}

/**
 * Organ system categories for filtering
 */
export const ORGAN_SYSTEMS = [
  { label: 'Renal', value: 'renal', color: TIMELINE_COLORS.renal },
  { label: 'Diabetes', value: 'diabetes', color: TIMELINE_COLORS.diabetes },
  { label: 'Genital', value: 'genital', color: TIMELINE_COLORS.genital },
  { label: 'Hepatic', value: 'hepatic', color: TIMELINE_COLORS.hepatic },
  { label: 'Pancreatic', value: 'pancreatic', color: TIMELINE_COLORS.pancreatic },
  { label: 'Neurological', value: 'neurological', color: TIMELINE_COLORS.neurological },
  { label: 'Skeletal', value: 'skeletal', color: TIMELINE_COLORS.skeletal },
  { label: 'Cardiovascular', value: 'cardiovascular', color: TIMELINE_COLORS.cardiovascular },
  { label: 'Endocrine', value: 'endocrine', color: TIMELINE_COLORS.endocrine },
  { label: 'Other', value: 'other', color: TIMELINE_COLORS.other },
];

/**
 * Determine organ system from HPO ID
 * @param {string} hpoId - HPO term ID
 * @returns {string} Organ system category
 */
export function getOrganSystem(hpoId) {
  // Basic mapping - can be expanded with HPO hierarchy
  const prefixMapping = {
    'HP:0000079': 'genital',       // Abnormality of the genital system
    'HP:0000107': 'renal',          // Renal cyst
    'HP:0000119': 'genital',       // Abnormality of the genitourinary system
    'HP:0000822': 'cardiovascular', // Hypertension
    'HP:0001507': 'skeletal',      // Growth abnormality
    'HP:0001627': 'cardiovascular', // Abnormal heart morphology
    'HP:0001871': 'other',         // Abnormality of blood and blood-forming tissues
    'HP:0002086': 'renal',         // Abnormality of the respiratory system
    'HP:0002242': 'hepatic',       // Abnormality of the hepatobiliary system
    'HP:0002595': 'hepatic',       // Abnormality of the hepatic vasculature
    'HP:0003111': 'renal',         // Abnormal blood electrolyte concentration
    'HP:0004322': 'skeletal',      // Short stature
    'HP:0004904': 'diabetes',      // Maturity-onset diabetes of the young (MODY)
    'HP:0100543': 'neurological',  // Cognitive impairment
  };
  
  // Check for exact match first
  for (const [prefix, system] of Object.entries(prefixMapping)) {
    if (hpoId.startsWith(prefix)) {
      return system;
    }
  }
  
  return 'other';
}

export default {
  parseAge,
  formatAge,
  onsetClassToAge,
  getCategoryColor,
  getOrganSystem,
  TIMELINE_COLORS,
  ORGAN_SYSTEMS,
};
