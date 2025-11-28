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

  return years + months / 12 + days / 365;
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
    'HP:0003577': 0, // Congenital onset
    'HP:0003623': 0, // Neonatal onset (0-4 weeks)
    'HP:0034199': 0.08, // Neonatal onset (approx 1 month)
    'HP:0003593': 0.5, // Infantile onset (1-12 months)
    'HP:0410280': 3, // Pediatric onset (midpoint ~age 3)
    'HP:0003621': 5, // Juvenile onset (midpoint ~age 5)
    'HP:0011462': 12, // Young adult onset (midpoint ~age 12)
    'HP:0003581': 25, // Adult onset (midpoint ~age 25)
    'HP:0003596': 40, // Middle age onset (midpoint ~age 40)
    'HP:0003584': 65, // Late onset (midpoint ~age 65)
  };

  return onsetMapping[hpoId] || null;
}

/**
 * Timeline color scheme for organ systems/categories
 */
export const TIMELINE_COLORS = {
  renal: '#1976D2', // Blue
  diabetes: '#F57C00', // Orange
  genital: '#7B1FA2', // Purple
  hepatic: '#388E3C', // Green
  pancreatic: '#C62828', // Red
  neurological: '#0097A7', // Cyan
  skeletal: '#5D4037', // Brown
  cardiovascular: '#E91E63', // Pink
  endocrine: '#FBC02D', // Yellow
  other: '#757575', // Grey
  unknown: '#BDBDBD', // Light grey
  excluded: '#E0E0E0', // Very light grey
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
  if (!hpoId) return 'other';

  // Handle non-HPO identifiers (e.g., ORPHA)
  if (!hpoId.startsWith('HP:')) {
    return 'other';
  }

  // Extract numeric part for range-based categorization
  const numericId = parseInt(hpoId.replace('HP:', ''));

  // Renal/Urinary System
  // HP:0000077 - Abnormality of the kidney (and all descendants)
  // HP:0000119 - Abnormality of the genitourinary system
  if (
    (numericId >= 77 && numericId <= 140) || // Kidney abnormalities
    (numericId >= 795 && numericId <= 850) || // Ureter/bladder/urethra
    numericId === 3 || // Multicystic kidney dysplasia
    numericId === 2149 || // Hyperuricemia
    numericId === 2900 || // Hypokalemia
    numericId === 2917 || // Hypomagnesemia
    numericId === 3111 || // Abnormal blood electrolyte
    (numericId >= 3774 && numericId <= 3780) || // Stage 5 CKD
    (numericId >= 12210 && numericId <= 12213) || // Abnormal renal morphology/physiology
    (numericId >= 12622 && numericId <= 12626) || // CKD stages
    numericId === 33133 || // Renal cortical hyperechogenicity
    numericId === 100611 // Multiple glomerular cysts
  ) {
    return 'renal';
  }

  // Genital System
  // HP:0000078-0080 - Abnormality of the genital system
  if ((numericId >= 78 && numericId <= 80) || (numericId >= 811 && numericId <= 815)) {
    return 'genital';
  }

  // Neurological/Neurodevelopmental
  // HP:0000707-0750 - Nervous system abnormalities
  // HP:0001250-0001300 - Seizures and neurological
  // HP:0012443 - Brain morphology
  // HP:0012758 - Neurodevelopmental delay
  if (
    (numericId >= 707 && numericId <= 750) ||
    (numericId >= 1250 && numericId <= 1300) ||
    (numericId >= 2011 && numericId <= 2100) ||
    numericId === 12443 ||
    (numericId >= 12758 && numericId <= 12760) ||
    numericId === 100543
  ) {
    return 'neurological';
  }

  // Hepatic System
  // HP:0001392 - Abnormality of the liver
  // HP:0002910 - Elevated hepatic transaminase
  // HP:0031865 - Abnormal liver physiology
  if (
    (numericId >= 1392 && numericId <= 1410) ||
    (numericId >= 2242 && numericId <= 2250) ||
    (numericId >= 2595 && numericId <= 2600) ||
    numericId === 2910 ||
    numericId === 31865
  ) {
    return 'hepatic';
  }

  // Pancreatic System
  // HP:0001732 - Abnormality of the pancreas
  // HP:0001738 - Exocrine pancreatic insufficiency
  // HP:0002594 - Pancreatic hypoplasia
  if (
    (numericId >= 1732 && numericId <= 1740) ||
    (numericId >= 2037 && numericId <= 2040) ||
    numericId === 2594 ||
    numericId === 5233 ||
    numericId === 6280 ||
    numericId === 8388 ||
    numericId === 11026 ||
    numericId === 12090 ||
    numericId === 100732
  ) {
    return 'pancreatic';
  }

  // Endocrine System (including diabetes)
  // HP:0000818 - Abnormality of the endocrine system
  // HP:0000819 - Diabetes mellitus
  // HP:0000843 - Hyperparathyroidism
  // HP:0004904 - MODY
  if (
    (numericId >= 818 && numericId <= 875) ||
    numericId === 2893 ||
    numericId === 3072 ||
    numericId === 3510 ||
    numericId === 4904 ||
    numericId === 4905 ||
    numericId === 8221 ||
    (numericId >= 11732 && numericId <= 11790) ||
    numericId === 12049 ||
    numericId === 30088
  ) {
    return 'endocrine';
  }

  // Cardiovascular System
  // HP:0001626 - Abnormality of the cardiovascular system
  // HP:0001627 - Abnormal heart morphology
  if ((numericId >= 1626 && numericId <= 1680) || numericId === 1997) {
    // HP:0001997 - Gout (related to cardiovascular risk)
    return 'cardiovascular';
  }

  // Skeletal/Musculoskeletal System
  // HP:0000924 - Abnormality of the skeletal system
  // HP:0004322 - Short stature
  // HP:0033127 - Abnormality of the musculoskeletal system
  if (
    (numericId >= 924 && numericId <= 945) ||
    (numericId >= 3011 && numericId <= 3020) ||
    numericId === 4322 ||
    numericId === 33127
  ) {
    return 'skeletal';
  }

  // Eye abnormalities - keep as 'other' (not organ-specific)
  if (numericId >= 478 && numericId <= 590) {
    return 'other';
  }

  // Facial abnormalities - keep as 'other'
  if ((numericId >= 271 && numericId <= 350) || numericId === 1999) {
    return 'other';
  }

  // Prenatal/birth abnormalities - keep as 'other'
  // HP:0001622 - Premature birth
  if (numericId === 1622) {
    return 'other';
  }

  // Default to 'other' for unmapped terms
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
