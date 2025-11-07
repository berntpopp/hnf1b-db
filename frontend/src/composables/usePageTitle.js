/**
 * Composable for managing page title dynamically
 * Follows Single Responsibility Principle - only handles title updates
 *
 * @module composables/usePageTitle
 */

const DEFAULT_TITLE = 'HNF1B Database';
const TITLE_SEPARATOR = ' | ';

/**
 * Updates the document title with optional page-specific title
 *
 * @param {string} [pageTitle] - Optional page-specific title
 * @returns {void}
 *
 * @example
 * // Set page title
 * updatePageTitle('Phenopackets')
 * // Result: "Phenopackets | HNF1B Database"
 *
 * @example
 * // Use default title
 * updatePageTitle()
 * // Result: "HNF1B Database"
 */
export function updatePageTitle(pageTitle = '') {
  if (pageTitle && pageTitle.trim()) {
    document.title = `${pageTitle}${TITLE_SEPARATOR}${DEFAULT_TITLE}`;
  } else {
    document.title = DEFAULT_TITLE;
  }
}

/**
 * Composable hook for page title management
 * Provides reactive page title functionality
 *
 * @returns {Object} Methods for title management
 * @returns {Function} returns.setTitle - Function to update page title
 * @returns {string} returns.defaultTitle - Default application title
 *
 * @example
 * import { usePageTitle } from '@/composables/usePageTitle'
 *
 * export default {
 *   setup() {
 *     const { setTitle } = usePageTitle()
 *     setTitle('My Page')
 *   }
 * }
 */
export function usePageTitle() {
  return {
    setTitle: updatePageTitle,
    defaultTitle: DEFAULT_TITLE,
  };
}
