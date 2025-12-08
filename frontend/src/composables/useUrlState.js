/**
 * Composable for bidirectional URL query parameter synchronization.
 *
 * Creates reactive refs that automatically sync with URL query parameters,
 * enabling shareable/bookmarkable URLs for component state.
 *
 * @param {Object} schema - Configuration object defining URL parameters
 * @param {Object} options - Configuration options
 * @param {boolean} options.replace - Use replace instead of push (default: true)
 * @returns {Object} Object with reactive refs for each defined parameter
 *
 * @example
 * // Schema definition:
 * const schema = {
 *   tab: { default: 'donut', type: 'string' },
 *   page: { default: 1, type: 'number' },
 *   showAll: { default: false, type: 'boolean' },
 * };
 *
 * // In component:
 * const { tab, page, showAll } = useUrlState(schema);
 *
 * // URL: /aggregations?tab=survival&page=2&showAll=true
 * // tab.value === 'survival'
 * // page.value === 2
 * // showAll.value === true
 */

import { ref, watch, computed, onMounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';

/**
 * Convert a value to URL string representation
 * @param {*} value - The value to serialize
 * @param {string} type - The type of the value
 * @returns {string|undefined} URL-safe string or undefined to omit
 */
function serializeValue(value, type, defaultValue) {
  // Don't include in URL if it equals the default
  if (value === defaultValue) {
    return undefined;
  }

  switch (type) {
    case 'number':
      return String(value);
    case 'boolean':
      return value ? 'true' : 'false';
    case 'string':
    default:
      return value;
  }
}

/**
 * Parse a URL query parameter value to its proper type
 * @param {string|null} value - The URL query value
 * @param {string} type - The expected type
 * @param {*} defaultValue - Default value if parsing fails
 * @returns {*} Parsed value
 */
function parseValue(value, type, defaultValue) {
  if (value === null || value === undefined) {
    return defaultValue;
  }

  switch (type) {
    case 'number': {
      const num = Number(value);
      return isNaN(num) ? defaultValue : num;
    }
    case 'boolean':
      return value === 'true';
    case 'string':
    default:
      return value;
  }
}

/**
 * Main composable for URL state synchronization
 * @param {Object} schema - Parameter schema configuration
 * @param {Object} options - Options
 * @returns {Object} Reactive refs for each parameter
 */
export function useUrlState(schema, options = {}) {
  const route = useRoute();
  const router = useRouter();
  const { replace = true } = options;

  // Create refs for each parameter
  const refs = {};
  const paramKeys = Object.keys(schema);

  // Track if we're currently updating URL to avoid loops
  let isUpdatingUrl = false;
  let isUpdatingFromUrl = false;

  // Initialize refs with URL values or defaults
  for (const key of paramKeys) {
    const config = schema[key];
    const defaultValue = config.default;
    const type = config.type || 'string';

    // Get initial value from URL or use default
    const urlValue = route.query[key];
    const initialValue = parseValue(urlValue, type, defaultValue);

    refs[key] = ref(initialValue);
  }

  /**
   * Update URL with current state of all refs
   */
  const updateUrl = () => {
    if (isUpdatingFromUrl) return;

    isUpdatingUrl = true;

    const newQuery = { ...route.query };

    for (const key of paramKeys) {
      const config = schema[key];
      const value = refs[key].value;
      const serialized = serializeValue(value, config.type || 'string', config.default);

      if (serialized === undefined) {
        // Remove from URL if it's the default
        delete newQuery[key];
      } else {
        newQuery[key] = serialized;
      }
    }

    // Only update if query actually changed
    const currentQuery = JSON.stringify(route.query);
    const updatedQuery = JSON.stringify(newQuery);

    if (currentQuery !== updatedQuery) {
      const navigationMethod = replace ? router.replace : router.push;
      navigationMethod({ query: newQuery }).finally(() => {
        isUpdatingUrl = false;
      });
    } else {
      isUpdatingUrl = false;
    }
  };

  /**
   * Update refs from URL query parameters
   */
  const updateFromUrl = () => {
    if (isUpdatingUrl) return;

    isUpdatingFromUrl = true;

    for (const key of paramKeys) {
      const config = schema[key];
      const urlValue = route.query[key];
      const parsedValue = parseValue(urlValue, config.type || 'string', config.default);

      if (refs[key].value !== parsedValue) {
        refs[key].value = parsedValue;
      }
    }

    nextTick(() => {
      isUpdatingFromUrl = false;
    });
  };

  // Watch each ref for changes and update URL
  for (const key of paramKeys) {
    watch(
      refs[key],
      () => {
        updateUrl();
      },
      { flush: 'post' }
    );
  }

  // Watch route query for external changes (back/forward, direct URL edit)
  watch(
    () => route.query,
    () => {
      updateFromUrl();
    },
    { deep: true }
  );

  // Ensure URL is updated on mount if refs differ from URL
  onMounted(() => {
    // Small delay to ensure router is ready
    nextTick(() => {
      updateUrl();
    });
  });

  /**
   * Reset all parameters to their defaults
   */
  const resetAll = () => {
    isUpdatingFromUrl = true;
    for (const key of paramKeys) {
      refs[key].value = schema[key].default;
    }
    nextTick(() => {
      isUpdatingFromUrl = false;
      updateUrl();
    });
  };

  /**
   * Get a computed that returns true if any param differs from default
   */
  const hasCustomState = computed(() => {
    return paramKeys.some((key) => refs[key].value !== schema[key].default);
  });

  /**
   * Get the current URL with all parameters
   */
  const shareableUrl = computed(() => {
    const url = new URL(window.location.href);
    return url.toString();
  });

  return {
    ...refs,
    resetAll,
    hasCustomState,
    shareableUrl,
  };
}
