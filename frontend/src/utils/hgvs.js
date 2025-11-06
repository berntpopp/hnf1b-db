/**
 * HGVS (Human Genome Variation Society) notation utility functions.
 *
 * These functions extract components from HGVS-formatted variant strings.
 * HGVS format: NM_000458.4:c.544+1G>T or NP_000449.3:p.Arg177Ter
 *
 * @module utils/hgvs
 */

/**
 * Extract the c. (coding DNA) notation from a transcript HGVS string.
 *
 * @param {string|null|undefined} transcript - Full HGVS transcript notation
 * @returns {string} The c. notation or '-' if not available
 *
 * @example
 * extractCNotation('NM_000458.4:c.544+1G>T') // Returns: 'c.544+1G>T'
 * extractCNotation('c.544+1G>T') // Returns: 'c.544+1G>T'
 * extractCNotation(null) // Returns: '-'
 */
export function extractCNotation(transcript) {
  if (!transcript) return '-';

  // Match everything after the colon (NM_000458.4:c.544+1G>T → c.544+1G>T)
  const match = transcript.match(/:(.+)$/);
  return match?.[1] ?? transcript;
}

/**
 * Extract the p. (protein) notation from a protein HGVS string.
 *
 * @param {string|null|undefined} protein - Full HGVS protein notation
 * @returns {string} The p. notation or '-' if not available
 *
 * @example
 * extractPNotation('NP_000449.3:p.Arg177Ter') // Returns: 'p.Arg177Ter'
 * extractPNotation('p.Arg177Ter') // Returns: 'p.Arg177Ter'
 * extractPNotation(null) // Returns: '-'
 */
export function extractPNotation(protein) {
  if (!protein) return '-';

  // Match everything after the colon (NP_000449.3:p.Arg177Ter → p.Arg177Ter)
  const match = protein.match(/:(.+)$/);
  return match?.[1] ?? protein;
}

/**
 * Extract the transcript ID (e.g., NM_000458.4) from a transcript HGVS string.
 *
 * @param {string|null|undefined} transcript - Full HGVS transcript notation
 * @returns {string|null} The transcript ID or null if not found
 *
 * @example
 * extractTranscriptId('NM_000458.4:c.544+1G>T') // Returns: 'NM_000458.4'
 * extractTranscriptId('c.544+1G>T') // Returns: null
 */
export function extractTranscriptId(transcript) {
  if (!transcript) return null;

  // Match transcript ID before colon (NM_XXXXXX.X)
  const match = transcript.match(/^(NM_[\d.]+):/);
  return match?.[1] ?? null;
}

/**
 * Extract the protein ID (e.g., NP_000449.3) from a protein HGVS string.
 *
 * @param {string|null|undefined} protein - Full HGVS protein notation
 * @returns {string|null} The protein ID or null if not found
 *
 * @example
 * extractProteinId('NP_000449.3:p.Arg177Ter') // Returns: 'NP_000449.3'
 * extractProteinId('p.Arg177Ter') // Returns: null
 */
export function extractProteinId(protein) {
  if (!protein) return null;

  // Match protein ID before colon (NP_XXXXXX.X)
  const match = protein.match(/^(NP_[\d.]+):/);
  return match?.[1] ?? null;
}
