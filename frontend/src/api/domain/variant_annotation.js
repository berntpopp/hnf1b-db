// src/api/domain/variant_annotation.js — VEP variant annotation endpoints
import { apiClient } from '../transport';

/**
 * Annotate a variant using Ensembl Variant Effect Predictor (VEP).
 * Returns comprehensive variant annotations including consequence predictions,
 * impact severity, CADD scores, and gnomAD frequencies.
 *
 * @param {string} variant - Variant notation in one of these formats:
 *   - HGVS: "NM_000458.4:c.544+1G>A" or "NC_000017.11:g.36459258A>G"
 *   - VCF: "17-36459258-A-G" or "chr17-36459258-A-G"
 *   - rsID: "rs56116432"
 * @returns {Promise} Axios promise with VEP annotation data
 *   - id: Variant identifier
 *   - input: Original input notation
 *   - allele_string: Reference/alternate alleles
 *   - most_severe_consequence: Most severe predicted consequence (e.g., "missense_variant")
 *   - transcript_consequences: Array of transcript annotations
 *   - colocated_variants: Array of known variants (rsIDs, gnomAD)
 *   - cadd: CADD scores object (PHRED, raw) if available
 *   - gnomad: gnomAD allele frequency object if available
 *   - impact: Impact severity (HIGH, MODERATE, LOW, MODIFIER)
 */
export const annotateVariant = (variant) =>
  apiClient.post('/variants/annotate', null, {
    params: { variant },
  });
