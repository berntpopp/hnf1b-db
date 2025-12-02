/**
 * DNA Distance Calculator for HNF1B Protein Structure
 *
 * Calculates distances between variant residues and DNA atoms in PDB 2H8R.
 * Based on the implementation from halbritter-lab/hnf1b-protein-page.
 *
 * PDB 2H8R: HNF1B DNA-binding domain
 * - UniProt P35680 residues 90-308
 * - Contains protein chains A, B (C, D in mmCIF) and DNA chains E, F (A, B in mmCIF)
 * - mmCIF auth_seq_id matches UniProt numbering directly (no offset needed)
 *
 * IMPORTANT: The structure has a GAP at residues 187-230 (linker region between
 * the two homeodomains). Variants in this range cannot have distances calculated.
 */

// Structure boundaries
// PDB 2H8R maps to UniProt P35680 residues 90-308 (author numbering in mmCIF)
// NGL uses auth_seq_id which matches UniProt numbering directly
export const STRUCTURE_START = 90;
export const STRUCTURE_END = 308;

// Gap in structure (linker region not resolved in crystal)
export const STRUCTURE_GAP_START = 187;
export const STRUCTURE_GAP_END = 230;

// Distance thresholds (in Angstroms)
export const DISTANCE_THRESHOLDS = {
  CLOSE: 5, // < 5 Angstroms - very close, likely direct DNA contact
  MEDIUM: 10, // 5-10 Angstroms - medium distance
  // >= 10 Angstroms - far from DNA
};

// Distance category colors
export const DISTANCE_COLORS = {
  close: '#D32F2F', // Red
  medium: '#FF9800', // Orange
  far: '#4CAF50', // Green
};

// DNA residue names
const DNA_RESIDUES = ['DA', 'DT', 'DG', 'DC'];

/**
 * Categorize a distance value
 * @param {number} distance - Distance in Angstroms
 * @returns {string} - 'close', 'medium', or 'far'
 */
export function categorizeDistance(distance) {
  if (distance === null || distance === undefined) return null;
  if (distance < DISTANCE_THRESHOLDS.CLOSE) return 'close';
  if (distance < DISTANCE_THRESHOLDS.MEDIUM) return 'medium';
  return 'far';
}

/**
 * Get color for a distance category
 * @param {string} category - 'close', 'medium', or 'far'
 * @returns {string} - Hex color code
 */
export function getDistanceColor(category) {
  return DISTANCE_COLORS[category] || DISTANCE_COLORS.far;
}

/**
 * Get color for a distance value
 * @param {number} distance - Distance in Angstroms
 * @returns {string} - Hex color code
 */
export function getDistanceColorFromValue(distance) {
  const category = categorizeDistance(distance);
  return getDistanceColor(category);
}

/**
 * Check if a residue position is within the structure gap (linker region)
 * @param {number} position - Amino acid position
 * @returns {boolean}
 */
export function isPositionInStructureGap(position) {
  return position >= STRUCTURE_GAP_START && position <= STRUCTURE_GAP_END;
}

/**
 * Check if a residue position is within the structure range and NOT in the gap
 * @param {number} position - Amino acid position
 * @returns {boolean}
 */
export function isPositionInStructure(position) {
  return (
    position >= STRUCTURE_START && position <= STRUCTURE_END && !isPositionInStructureGap(position)
  );
}

/**
 * Distance Calculator class for NGL structure components
 */
export class DNADistanceCalculator {
  constructor() {
    this.structureComponent = null;
    this.dnaAtoms = [];
    this.proteinAtoms = [];
    this.initialized = false;
  }

  /**
   * Initialize the calculator with an NGL structure component
   * @param {Object} structureComponent - NGL StructureComponent
   */
  initialize(structureComponent) {
    if (!structureComponent || !structureComponent.structure) {
      throw new Error('Invalid structure component');
    }

    this.structureComponent = structureComponent;
    this.dnaAtoms = [];
    this.proteinAtoms = [];

    const structure = structureComponent.structure;

    // Collect all DNA atoms (non-hydrogen)
    structure.eachAtom((atom) => {
      const isDNA = DNA_RESIDUES.includes(atom.resname);
      const isHydrogen = atom.element === 'H';

      if (isDNA && !isHydrogen) {
        this.dnaAtoms.push({
          x: atom.x,
          y: atom.y,
          z: atom.z,
          atomName: atom.atomname,
          resName: atom.resname,
          resNo: atom.resno,
          chainId: atom.chainname,
          element: atom.element,
        });
      }
    });

    // Collect all protein atoms for reference
    structure.eachAtom((atom) => {
      const isProtein = atom.isProtein();
      const isHydrogen = atom.element === 'H';

      if (isProtein && !isHydrogen) {
        this.proteinAtoms.push({
          x: atom.x,
          y: atom.y,
          z: atom.z,
          atomName: atom.atomname,
          resName: atom.resname,
          resNo: atom.resno,
          chainId: atom.chainname,
          element: atom.element,
        });
      }
    });

    this.initialized = true;

    return {
      dnaAtomCount: this.dnaAtoms.length,
      proteinAtomCount: this.proteinAtoms.length,
    };
  }

  /**
   * Calculate Euclidean distance between two 3D points
   * @param {Object} p1 - {x, y, z}
   * @param {Object} p2 - {x, y, z}
   * @returns {number} - Distance in Angstroms
   */
  static calculateDistance(p1, p2) {
    const dx = p1.x - p2.x;
    const dy = p1.y - p2.y;
    const dz = p1.z - p2.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  /**
   * Calculate the minimum distance from a residue to the nearest DNA atom
   * @param {number} residueNumber - Residue number (amino acid position in UniProt numbering)
   * @param {boolean} useSidechainDistance - If true, use all atoms; if false, use only CA
   * @returns {Object|null} - Distance info or null if not found
   */
  calculateResidueToHelixDistance(residueNumber, useSidechainDistance = true) {
    if (!this.initialized) {
      throw new Error('Calculator not initialized. Call initialize() first.');
    }

    if (!isPositionInStructure(residueNumber)) {
      return null;
    }

    // NGL uses auth_seq_id from mmCIF which matches UniProt numbering directly
    // No offset conversion needed
    const residueAtoms = this.proteinAtoms.filter((atom) => {
      if (atom.resNo !== residueNumber) return false;
      // If not using sidechain, only use CA atom
      if (!useSidechainDistance && atom.atomName !== 'CA') return false;
      return true;
    });

    if (residueAtoms.length === 0) {
      return null;
    }

    let minDistance = Infinity;
    let closestDNAAtom = null;
    let closestResidueAtom = null;

    // Find minimum distance between any residue atom and any DNA atom
    for (const resAtom of residueAtoms) {
      for (const dnaAtom of this.dnaAtoms) {
        const distance = DNADistanceCalculator.calculateDistance(resAtom, dnaAtom);
        if (distance < minDistance) {
          minDistance = distance;
          closestDNAAtom = dnaAtom;
          closestResidueAtom = resAtom;
        }
      }
    }

    if (minDistance === Infinity) {
      return null;
    }

    return {
      distance: minDistance,
      distanceFormatted: minDistance.toFixed(2),
      category: categorizeDistance(minDistance),
      color: getDistanceColorFromValue(minDistance),
      closestDNAAtom: {
        ...closestDNAAtom,
        label: `${closestDNAAtom.resName}:${closestDNAAtom.resNo}.${closestDNAAtom.atomName}`,
      },
      closestResidueAtom: {
        ...closestResidueAtom,
        label: `${closestResidueAtom.resName}:${closestResidueAtom.resNo}.${closestResidueAtom.atomName}`,
      },
      residueNumber,
      method: useSidechainDistance ? 'closest_atom' : 'ca_only',
    };
  }

  /**
   * Calculate distances for all variants
   * @param {Array} variants - Array of variant objects with aaPosition
   * @param {boolean} useSidechainDistance - Use sidechain atoms for distance calculation
   * @returns {Map} - Map of variant_id to distance info
   */
  calculateAllDistances(variants, useSidechainDistance = true) {
    const results = new Map();

    for (const variant of variants) {
      if (!variant.aaPosition) continue;

      const distanceInfo = this.calculateResidueToHelixDistance(
        variant.aaPosition,
        useSidechainDistance
      );

      if (distanceInfo) {
        results.set(variant.variant_id || variant.aaPosition.toString(), {
          ...distanceInfo,
          variant,
        });
      }
    }

    return results;
  }

  /**
   * Get coordinates for drawing a distance line between residue and DNA
   * @param {number} residueNumber - Residue number
   * @param {boolean} useSidechainDistance - Use sidechain atoms
   * @returns {Object|null} - {start: {x,y,z}, end: {x,y,z}, distance, color}
   */
  getDistanceLineCoordinates(residueNumber, useSidechainDistance = true) {
    const distanceInfo = this.calculateResidueToHelixDistance(residueNumber, useSidechainDistance);

    if (!distanceInfo) return null;

    return {
      start: {
        x: distanceInfo.closestResidueAtom.x,
        y: distanceInfo.closestResidueAtom.y,
        z: distanceInfo.closestResidueAtom.z,
      },
      end: {
        x: distanceInfo.closestDNAAtom.x,
        y: distanceInfo.closestDNAAtom.y,
        z: distanceInfo.closestDNAAtom.z,
      },
      distance: distanceInfo.distance,
      distanceFormatted: distanceInfo.distanceFormatted,
      category: distanceInfo.category,
      color: distanceInfo.color,
    };
  }

  /**
   * Get statistics about distances for a set of variants
   * @param {Map} distances - Map from calculateAllDistances
   * @returns {Object} - Statistics summary
   */
  static getDistanceStatistics(distances) {
    const values = [];
    const categories = { close: 0, medium: 0, far: 0 };

    distances.forEach((info) => {
      if (info.distance !== null && info.distance !== undefined) {
        values.push(info.distance);
        categories[info.category]++;
      }
    });

    if (values.length === 0) {
      return null;
    }

    values.sort((a, b) => a - b);

    const sum = values.reduce((a, b) => a + b, 0);
    const mean = sum / values.length;

    // Median
    const mid = Math.floor(values.length / 2);
    const median = values.length % 2 !== 0 ? values[mid] : (values[mid - 1] + values[mid]) / 2;

    // Standard deviation
    const squaredDiffs = values.map((v) => Math.pow(v - mean, 2));
    const avgSquaredDiff = squaredDiffs.reduce((a, b) => a + b, 0) / values.length;
    const stdDev = Math.sqrt(avgSquaredDiff);

    // Quartiles
    const q1Index = Math.floor(values.length * 0.25);
    const q3Index = Math.floor(values.length * 0.75);

    return {
      count: values.length,
      min: values[0],
      max: values[values.length - 1],
      mean: mean,
      median: median,
      stdDev: stdDev,
      q1: values[q1Index],
      q3: values[q3Index],
      categories,
    };
  }
}

export default DNADistanceCalculator;
