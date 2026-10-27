// src/api/domain/reference.js — Reference genome endpoints
import { apiClient } from '../transport';

/**
 * Get list of all available genome assemblies.
 * @returns {Promise} Axios promise with genome assemblies
 */
export const getReferenceGenomes = () => apiClient.get('/reference/genomes');

/**
 * Query genes by symbol or chromosome.
 * @param {Object} params - Query parameters
 *   - symbol: Gene symbol to filter (e.g., "HNF1B")
 *   - chromosome: Chromosome to filter (e.g., "17")
 *   - genome_build: Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with genes array
 */
export const getReferenceGenes = (params = {}) => apiClient.get('/reference/genes', { params });

/**
 * Get gene details with transcripts.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with gene details
 */
export const getReferenceGene = (symbol, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/genes/${symbol}`, {
    params: { genome_build: genomeBuild },
  });

/**
 * Get all transcript isoforms for a gene with exon coordinates.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with transcripts array
 */
export const getReferenceGeneTranscripts = (symbol, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/genes/${symbol}/transcripts`, {
    params: { genome_build: genomeBuild },
  });

/**
 * Get protein domains for a gene's canonical transcript.
 * Returns empty domains array gracefully if reference data is unavailable.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with protein domains
 *   - gene: Gene symbol
 *   - protein: RefSeq protein ID
 *   - uniprot: UniProt accession
 *   - length: Protein length (amino acids)
 *   - domains: Array of domain objects with name, start, end, function
 *   - genome_build: Genome assembly
 *   - updated_at: Last update timestamp
 */
export const getReferenceGeneDomains = async (symbol, genomeBuild = 'GRCh38') => {
  try {
    return await apiClient.get(`/reference/genes/${symbol}/domains`, {
      params: { genome_build: genomeBuild },
    });
  } catch (error) {
    // Handle 404 gracefully - reference data may not be populated
    if (error.response?.status === 404) {
      window.logService?.debug('Reference domains not available', { symbol, genomeBuild });
      return { data: { domains: [], gene: symbol, genome_build: genomeBuild } };
    }
    throw error;
  }
};

/**
 * Get all genes in a genomic region.
 * @param {string} region - Genomic region in format "chr:start-end" (e.g., "17:36000000-37000000")
 * @param {string} genomeBuild - Genome assembly name (default: GRCh38)
 * @returns {Promise} Axios promise with genes in region
 */
export const getReferenceGenomicRegion = (region, genomeBuild = 'GRCh38') =>
  apiClient.get(`/reference/regions/${region}`, {
    params: { genome_build: genomeBuild },
  });

/**
 * URL of the gene's experimental structure (mmCIF), for 3D viewers that fetch
 * by URL. Served by the API with a 24 h Cache-Control.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @returns {string} Absolute or base-relative URL
 */
export const getReferenceGeneStructureUrl = (symbol) =>
  `${apiClient.defaults.baseURL}/reference/genes/${symbol}/structure`;

const dnaDistanceRequests = new Map();

/**
 * Per-residue distance to DNA in the gene's experimental structure.
 * Static reference data, so one request per session per gene; a failed
 * request is dropped from the cache so the next call retries.
 * @param {string} symbol - Gene symbol (e.g., "HNF1B")
 * @returns {Promise} Axios promise with { gene, pdb_id, method, residues: [{residue, distance}] }
 */
export const getReferenceGeneDnaDistances = (symbol) => {
  if (!dnaDistanceRequests.has(symbol)) {
    const request = apiClient
      .get(`/reference/genes/${symbol}/structure/dna-distances`)
      .catch((error) => {
        dnaDistanceRequests.delete(symbol);
        throw error;
      });
    dnaDistanceRequests.set(symbol, request);
  }
  return dnaDistanceRequests.get(symbol);
};
