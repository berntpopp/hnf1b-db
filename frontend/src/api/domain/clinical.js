// src/api/domain/clinical.js — Clinical feature endpoints
import { apiClient } from '../transport';

/**
 * Get phenopackets with renal insufficiency.
 * @returns {Promise} Axios promise with clinical data
 */
export const getRenalInsufficiencyCases = () => apiClient.get('/clinical/renal-insufficiency');

/**
 * Get phenopackets with genital abnormalities.
 * @returns {Promise} Axios promise with clinical data
 */
export const getGenitalAbnormalitiesCases = () => apiClient.get('/clinical/genital-abnormalities');

/**
 * Get phenopackets with diabetes.
 * @returns {Promise} Axios promise with clinical data
 */
export const getDiabetesCases = () => apiClient.get('/clinical/diabetes');

/**
 * Get phenopackets with hypomagnesemia.
 * @returns {Promise} Axios promise with clinical data
 */
export const getHypomagnesemiaCases = () => apiClient.get('/clinical/hypomagnesemia');
