/**
 * HNF1B Protein Domain Utilities
 *
 * Shared utilities for working with protein domains and amino acid positions.
 * Extracted from HNF1BProteinVisualization.vue for reuse across components.
 *
 * Domain data source: UniProt P35680, fetched from backend API.
 */

import { extractPNotation } from './hgvs';

/**
 * Extract amino acid position from HGVS protein notation.
 * This is extracted from HNF1BProteinVisualization.vue:extractAAPosition()
 *
 * @param {Object} variant - Variant object with 'protein' field
 * @returns {number|null} - Amino acid position or null if cannot be extracted
 *
 * @example
 * extractAAPosition({ protein: "NP_000449.3:p.Arg177Ter" }) // Returns: 177
 * extractAAPosition({ protein: "NP_000449.3:p.Ser546Phe" }) // Returns: 546
 * extractAAPosition({ protein: "NP_000449.3:p.Arg177_Ser178del" }) // Returns: 177 (start position)
 */
export function extractAAPosition(variant) {
  // Parse amino acid position from HGVS protein notation
  if (!variant || !variant.protein) return null;

  const pNotation = extractPNotation(variant.protein);
  if (!pNotation) return null;

  // Match various patterns:
  // - p.Arg177Ter (nonsense)
  // - p.Ser546Phe (missense)
  // - p.Met1? (unknown start)
  // - p.Arg177del (deletion)
  // - p.Arg177_Ser178del (deletion range - use start position)
  // - p.Arg177dup (duplication)
  // - p.Arg177_Ser178dup (duplication range - use start position)
  const match = pNotation.match(
    /p\.([A-Z][a-z]{2})?(\d+)(_[A-Z][a-z]{2}\d+)?(del|dup|ins|Ter|[A-Z][a-z]{2}|\?)?/
  );
  if (match && match[2]) {
    return parseInt(match[2]);
  }

  return null;
}

/**
 * Check if an amino acid position falls within any protein domain.
 *
 * @param {number} position - Amino acid position (1-indexed)
 * @param {Array} domains - Array of domain objects with 'start' and 'end' properties
 * @returns {boolean} - True if position is in any domain
 */
export function isPositionInDomain(position, domains) {
  if (typeof position !== 'number' || !Array.isArray(domains)) {
    return false;
  }

  const pos = parseInt(position);
  return domains.some((domain) => pos >= domain.start && pos <= domain.end);
}

/**
 * Get the specific domain for a given amino acid position.
 *
 * @param {number} position - Amino acid position (1-indexed)
 * @param {Array} domains - Array of domain objects with 'start' and 'end' properties
 * @returns {Object|null} - Domain object or null if not in any domain
 */
export function getDomainForPosition(position, domains) {
  if (typeof position !== 'number' || !Array.isArray(domains)) {
    return null;
  }

  const pos = parseInt(position);
  // Return first matching domain (domains can overlap)
  return domains.find((domain) => pos >= domain.start && pos <= domain.end) || null;
}

/**
 * Get the domain for a variant based on its protein notation.
 *
 * @param {Object} variant - Variant object with 'protein' field
 * @param {Array} domains - Array of domain objects
 * @returns {Object|null} - Domain object or null if not in any domain
 */
export function getVariantDomain(variant, domains) {
  const position = extractAAPosition(variant);
  if (position === null) {
    return null;
  }
  return getDomainForPosition(position, domains);
}

/**
 * Filter variants by protein domain name.
 *
 * @param {Array} variants - Array of variant objects
 * @param {string} domainName - Domain name to filter by
 * @param {Array} domains - Array of domain objects
 * @returns {Array} - Filtered variants
 */
export function filterVariantsByDomain(variants, domainName, domains) {
  if (!Array.isArray(variants) || !domainName || !Array.isArray(domains)) {
    return variants;
  }

  return variants.filter((variant) => {
    const domain = getVariantDomain(variant, domains);
    return domain && domain.name === domainName;
  });
}

/**
 * Get unique domain names from variants (for populating filter dropdowns).
 *
 * @param {Array} variants - Array of variant objects
 * @param {Array} domains - Array of domain objects
 * @returns {Array} - Array of unique domain names
 */
export function getDomainsFromVariants(variants, domains) {
  if (!Array.isArray(variants) || !Array.isArray(domains)) {
    return [];
  }

  const domainNames = new Set();
  variants.forEach((variant) => {
    const domain = getVariantDomain(variant, domains);
    if (domain) {
      domainNames.add(domain.name);
    }
  });

  return Array.from(domainNames).sort();
}
