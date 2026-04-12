// src/api/domain/admin.js — Admin API endpoints (requires admin authentication)
import { apiClient } from '../transport';

/**
 * Get admin system status and sync statistics.
 * Requires admin authentication.
 * @returns {Promise} Axios promise with system status
 */
export const getAdminStatus = () => apiClient.get('/admin/status');

/**
 * Get detailed database statistics.
 * Requires admin authentication.
 * @returns {Promise} Axios promise with statistics
 */
export const getAdminStatistics = () => apiClient.get('/admin/statistics');

/**
 * Start publication metadata sync task.
 * Requires admin authentication.
 * @param {boolean} force - If true, re-fetch all publications even if already synced
 * @returns {Promise} Axios promise with task info
 */
export const startPublicationSync = (force = false) =>
  apiClient.post('/admin/sync/publications', null, { params: force ? { force: true } : {} });

/**
 * Get publication sync task progress.
 * Requires admin authentication.
 * @param {string} taskId - Optional task ID
 * @returns {Promise} Axios promise with progress info
 */
export const getPublicationSyncStatus = (taskId = null) =>
  apiClient.get('/admin/sync/publications/status', {
    params: taskId ? { task_id: taskId } : {},
  });

/**
 * Start variant annotation sync task.
 * Requires admin authentication.
 * @param {boolean} force - If true, re-fetch all variant annotations even if already cached
 * @returns {Promise} Axios promise with task info
 */
export const startVariantSync = (force = false) =>
  apiClient.post('/admin/sync/variants', null, { params: force ? { force: true } : {} });

/**
 * Get variant sync task progress.
 * Requires admin authentication.
 * @param {string} taskId - Optional task ID
 * @returns {Promise} Axios promise with progress info
 */
export const getVariantSyncStatus = (taskId = null) =>
  apiClient.get('/admin/sync/variants/status', {
    params: taskId ? { task_id: taskId } : {},
  });

/**
 * Initialize reference data (GRCh38 + HNF1B gene + transcript + domains).
 * Requires admin authentication.
 * @returns {Promise} Axios promise with task info
 */
export const startReferenceInit = () => apiClient.post('/admin/sync/reference/init');

/**
 * Start chr17q12 genes sync from Ensembl REST API.
 * Requires admin authentication.
 * @param {boolean} force - If true, re-sync all genes
 * @returns {Promise} Axios promise with task info
 */
export const startGenesSync = (force = false) =>
  apiClient.post('/admin/sync/genes', null, { params: force ? { force: true } : {} });

/**
 * Get chr17q12 genes sync task progress.
 * Requires admin authentication.
 * @param {string} taskId - Optional task ID
 * @returns {Promise} Axios promise with progress info
 */
export const getGenesSyncStatus = (taskId = null) =>
  apiClient.get('/admin/sync/genes/status', {
    params: taskId ? { task_id: taskId } : {},
  });

/**
 * Get reference data status.
 * Requires admin authentication.
 * @returns {Promise} Axios promise with reference data status
 */
export const getReferenceDataStatus = () => apiClient.get('/admin/reference/status');
