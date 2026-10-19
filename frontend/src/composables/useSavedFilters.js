/**
 * Composable for managing saved filter presets and shareable URL query synchronization.
 *
 * Persists user-defined filter presets in localStorage with fallback and provides
 * helpers for bidirectional Vue Router query synchronization without infinite loops.
 *
 * @param {string} scopeKey - Identifier for scope (e.g. 'phenopackets', 'variants', 'aggregations')
 * @param {Object} [options] - Configuration options
 * @returns {Object} Reactive presets array, save/delete actions, and URL sync helpers
 */

import { ref, unref, computed, getCurrentInstance } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const STORAGE_PREFIX = 'hnf1b_saved_filters_';

/**
 * Safely parse presets from localStorage
 * @param {string} scopeKey
 * @returns {Array}
 */
export function loadPresetsFromStorage(scopeKey) {
  if (typeof window === 'undefined' || !window.localStorage) {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(`${STORAGE_PREFIX}${scopeKey}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    if (typeof window !== 'undefined' && window.logService) {
      window.logService.warn('Failed to parse saved filters from localStorage', {
        scopeKey,
        error: error.message,
      });
    }
    return [];
  }
}

/**
 * Safely persist presets to localStorage
 * @param {string} scopeKey
 * @param {Array} presets
 */
export function persistPresetsToStorage(scopeKey, presets) {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(`${STORAGE_PREFIX}${scopeKey}`, JSON.stringify(presets));
  } catch (error) {
    if (typeof window !== 'undefined' && window.logService) {
      window.logService.warn('Failed to save filters to localStorage', {
        scopeKey,
        error: error.message,
      });
    }
  }
}

/**
 * Parse route query into a typed state object
 * @param {Object} routeQuery - Current route query object
 * @param {Object} [defaults] - Default filter/state values
 * @returns {Object}
 */
export function syncFromQuery(routeQuery = {}, defaults = {}) {
  const result = { ...defaults };
  if (!routeQuery || typeof routeQuery !== 'object') {
    return result;
  }

  for (const [key, val] of Object.entries(routeQuery)) {
    if (val === undefined || val === null || val === '') continue;
    const defaultVal = defaults[key];

    if (typeof defaultVal === 'number') {
      const num = Number(val);
      result[key] = isNaN(num) ? defaultVal : num;
    } else if (typeof defaultVal === 'boolean') {
      result[key] = val === 'true' || val === true;
    } else {
      result[key] = val;
    }
  }

  return result;
}

/**
 * Sync state object to Vue Router query without triggering infinite loops
 * @param {Object} routerOrState - Router instance or state object
 * @param {Object} [maybeRouteOrOptions] - Route instance or options
 * @param {Object} [maybeState] - State object
 * @param {Object} [maybeOptions] - Options
 * @returns {Promise<void>}
 */
export function syncToQuery(routerOrState, maybeRouteOrOptions, maybeState, maybeOptions) {
  let router, route, stateObj, options;

  if (routerOrState && typeof routerOrState.replace === 'function') {
    router = routerOrState;
    route = maybeRouteOrOptions;
    stateObj = maybeState;
    options = maybeOptions || {};
  } else {
    stateObj = routerOrState;
    options = maybeRouteOrOptions || {};
    router = options.router;
    route = options.route;
  }

  const { defaults = {}, preserveOther = true, replace = true } = options;
  const currentQuery = route?.query || {};
  const newQuery = preserveOther ? { ...currentQuery } : {};

  if (stateObj && typeof stateObj === 'object') {
    for (const [key, value] of Object.entries(stateObj)) {
      const isDefault = defaults && defaults[key] !== undefined && value === defaults[key];
      if (value === null || value === undefined || value === '' || isDefault) {
        delete newQuery[key];
      } else {
        newQuery[key] = String(value);
      }
    }
  }

  // Avoid unnecessary router navigation if query is identical
  const currentKeys = Object.keys(currentQuery).sort();
  const newKeys = Object.keys(newQuery).sort();
  let hasChanged = currentKeys.length !== newKeys.length;

  if (!hasChanged) {
    for (const key of newKeys) {
      if (String(currentQuery[key] ?? '') !== String(newQuery[key] ?? '')) {
        hasChanged = true;
        break;
      }
    }
  }

  if (!hasChanged || !router || typeof router.replace !== 'function') {
    return Promise.resolve();
  }

  const navMethod = replace ? router.replace.bind(router) : router.push.bind(router);
  return navMethod({ query: newQuery }).catch((err) => {
    if (err && err.name !== 'NavigationDuplicated') {
      throw err;
    }
  });
}

/**
 * Main saved filters composable
 * @param {string|Ref<string>} scopeKey - Unique scope name
 * @param {Object} [options]
 * @returns {Object}
 */
export function useSavedFilters(scopeKey, options = {}) {
  let resolvedRoute = null;
  let resolvedRouter = null;

  const instance = getCurrentInstance();
  if (instance && instance.appContext?.config?.globalProperties?.$router) {
    try {
      resolvedRoute = useRoute();
      resolvedRouter = useRouter();
    } catch {
      // Outside component setup or test environment without router
    }
  }

  const keyRef = computed(() => unref(scopeKey));
  const presets = ref(loadPresetsFromStorage(keyRef.value));
  const copied = ref(false);

  /**
   * Save a filter state under a preset name
   * @param {string} name - Preset name
   * @param {Object} filterState - Current filter state
   * @returns {Object|null}
   */
  function savePreset(name, filterState) {
    if (!name || typeof name !== 'string' || !name.trim()) {
      return null;
    }

    const trimmedName = name.trim();
    const sanitizedFilters = {};

    if (filterState && typeof filterState === 'object') {
      for (const [k, v] of Object.entries(filterState)) {
        if (v !== null && v !== undefined && v !== '') {
          sanitizedFilters[k] = v;
        }
      }
    }

    const currentPresets = [...presets.value];
    const existingIndex = currentPresets.findIndex(
      (p) => p.name.trim().toLowerCase() === trimmedName.toLowerCase()
    );

    const preset = {
      name: trimmedName,
      filters: sanitizedFilters,
      updatedAt: new Date().toISOString(),
    };

    if (existingIndex >= 0) {
      preset.createdAt = currentPresets[existingIndex].createdAt || preset.updatedAt;
      currentPresets[existingIndex] = preset;
    } else {
      preset.createdAt = preset.updatedAt;
      currentPresets.push(preset);
    }

    presets.value = currentPresets;
    persistPresetsToStorage(keyRef.value, currentPresets);
    return preset;
  }

  /**
   * Delete a saved preset by name
   * @param {string} name - Name of preset to delete
   */
  function deletePreset(name) {
    if (!name) return;
    const trimmed = String(name).trim().toLowerCase();
    const filtered = presets.value.filter(
      (p) => p.name.trim().toLowerCase() !== trimmed
    );
    presets.value = filtered;
    persistPresetsToStorage(keyRef.value, filtered);
  }

  /**
   * Copy current URL or shareable URL to clipboard
   * @param {string} [customUrl]
   * @returns {Promise<boolean>}
   */
  async function copyShareableUrl(customUrl = null) {
    const url = customUrl || (typeof window !== 'undefined' ? window.location?.href || '' : '');
    if (!url) return false;

    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(url);
        copied.value = true;
        setTimeout(() => {
          copied.value = false;
        }, 2000);
        return true;
      } catch (err) {
        if (typeof window !== 'undefined' && window.logService) {
          window.logService.warn('Failed to copy shareable URL to clipboard', {
            error: err.message,
          });
        }
        return false;
      }
    }
    return false;
  }

  /**
   * Bound syncToQuery helper using injected router/route if available
   */
  function boundSyncToQuery(arg1, arg2, arg3, arg4) {
    if (arg1 && typeof arg1.replace === 'function') {
      return syncToQuery(arg1, arg2, arg3, arg4);
    }
    return syncToQuery(resolvedRouter, resolvedRoute, arg1, {
      ...options,
      ...arg2,
    });
  }

  return {
    presets,
    copied,
    savePreset,
    deletePreset,
    copyShareableUrl,
    syncFromQuery,
    syncToQuery: boundSyncToQuery,
  };
}
