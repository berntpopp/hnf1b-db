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

// Wave 5b Task 14: admin user management
/**
 * List all users (admin only).
 * @param {Object} [params] - Optional query parameters (skip, limit, role)
 * @returns {Promise} Axios promise with user list
 */
export const listUsers = (params = {}) => apiClient.get('/auth/users', { params });

/**
 * Create a new user (admin only).
 * @param {Object} userData - User creation data
 * @returns {Promise} Axios promise with created user
 */
export const createUser = (userData) => apiClient.post('/auth/users', userData);

/**
 * Get user by ID (admin only).
 * @param {number} id - User ID
 * @returns {Promise} Axios promise with user data
 */
export const getUser = (id) => apiClient.get(`/auth/users/${id}`);

/**
 * Update user by ID (admin only).
 * @param {number} id - User ID
 * @param {Object} userData - Fields to update
 * @returns {Promise} Axios promise with updated user
 */
export const updateUser = (id, userData) => apiClient.put(`/auth/users/${id}`, userData);

/**
 * Delete user by ID (admin only).
 * @param {number} id - User ID
 * @returns {Promise} Axios promise
 */
export const deleteUser = (id) => apiClient.delete(`/auth/users/${id}`);

/**
 * Unlock a locked user account (admin only).
 * @param {number} id - User ID
 * @returns {Promise} Axios promise with unlocked user
 */
export const unlockUser = (id) => apiClient.patch(`/auth/users/${id}/unlock`);

/**
 * Request a password reset email.
 * @param {string} email
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function requestPasswordReset(email) {
  return apiClient.post('/auth/password-reset/request', { email });
}

/**
 * Confirm a password reset with token and new password.
 * @param {string} token
 * @param {string} newPassword
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function confirmPasswordReset(token, newPassword) {
  return apiClient.post(`/auth/password-reset/confirm/${token}`, {
    new_password: newPassword,
  });
}
