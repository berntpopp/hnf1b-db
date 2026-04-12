// src/api/domain/auth.js — Authentication endpoints
import { apiClient } from '../transport';

/**
 * Login user and get JWT token.
 * @param {Object} credentials - User credentials
 *   - username: Username
 *   - password: Password
 * @returns {Promise} Axios promise with token response
 */
export const login = (credentials) => apiClient.post('/auth/login', credentials);

/**
 * Get current user information.
 * @returns {Promise} Axios promise with user data
 */
export const getCurrentUser = () => apiClient.get('/auth/me');

/**
 * Logout user (client-side token removal).
 * @returns {Promise} Axios promise with logout confirmation
 */
export const logout = () => apiClient.post('/auth/logout');
