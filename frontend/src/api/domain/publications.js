// src/api/domain/publications.js — Publication endpoints
import { apiClient } from '../transport';

/**
 * Get a list of publications with JSON:API pagination, filtering, and search.
 *
 * @param {Object} params - Query parameters
 *   - page[number]: Page number (1-indexed, default: 1)
 *   - page[size]: Items per page (default: 20, max: 100)
 *   - filter[year]: Filter by publication year
 *   - filter[year_gte]: Filter by minimum year
 *   - filter[year_lte]: Filter by maximum year
 *   - filter[has_doi]: Filter by DOI presence
 *   - sort: Sort field (prefix with '-' for descending, default: '-phenopacket_count')
 *   - q: Full-text search query (searches title, authors, PMID, DOI)
 * @returns {Promise} Axios promise with JSON:API response { data, meta, links }
 *
 * @example
 * getPublications({
 *   'page[number]': 1,
 *   'page[size]': 20,
 *   'sort': '-phenopacket_count',
 *   'q': 'HNF1B'
 * })
 */
export const getPublications = (params = {}) => apiClient.get('/publications/', { params });

/**
 * Get publication metadata by PMID.
 * Fetches from PubMed API with database caching (90-day TTL).
 * @param {string} pmid - PubMed ID (with or without PMID: prefix)
 * @returns {Promise} Axios promise with publication metadata
 *   - pmid: PubMed ID
 *   - title: Article title
 *   - authors: Array of author objects {name, affiliation}
 *   - journal: Journal name
 *   - year: Publication year
 *   - doi: DOI identifier
 *   - abstract: Article abstract
 *   - data_source: "PubMed"
 *   - fetched_at: ISO timestamp
 */
export const getPublicationMetadata = (pmid) => apiClient.get(`/publications/${pmid}/metadata`);
