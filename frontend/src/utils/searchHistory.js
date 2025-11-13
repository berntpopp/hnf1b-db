const RECENT_SEARCHES_KEY = 'hnf1b_recent_searches';
const MAX_RECENT_SEARCHES = 5;

/**
 * Gets the list of recent searches from localStorage.
 * @returns {string[]} An array of recent search strings.
 */
export const getRecentSearches = () => {
  try {
    const searches = localStorage.getItem(RECENT_SEARCHES_KEY);
    return searches ? JSON.parse(searches) : [];
  } catch (error) {
    console.error('Failed to retrieve recent searches:', error);
    return [];
  }
};

/**
 * Adds a new search term to the list of recent searches.
 * @param {string} searchTerm The search term to add.
 */
export const addRecentSearch = (searchTerm) => {
  if (!searchTerm) return;

  try {
    let searches = getRecentSearches();
    // Remove the term if it already exists to move it to the top
    searches = searches.filter((s) => s.toLowerCase() !== searchTerm.toLowerCase());
    // Add the new term to the beginning
    searches.unshift(searchTerm);
    // Limit the number of recent searches
    if (searches.length > MAX_RECENT_SEARCHES) {
      searches.pop();
    }
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(searches));
  } catch (error) {
    console.error('Failed to save recent search:', error);
  }
};

/**
 * Clears all recent searches from localStorage.
 */
export const clearRecentSearches = () => {
  try {
    localStorage.removeItem(RECENT_SEARCHES_KEY);
    if (window.logService) {
      window.logService.info('Cleared recent searches');
    }
  } catch (error) {
    console.error('Failed to clear recent searches:', error);
  }
};
