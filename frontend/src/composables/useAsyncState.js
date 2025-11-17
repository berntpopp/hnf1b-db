/**
 * Composable for handling async operations with loading/error states.
 *
 * Generic wrapper for API calls that provides consistent loading/error handling.
 *
 * @param {Function} asyncFn - Async function to execute
 * @param {*} initialState - Initial value for data (default: null)
 * @returns {{data: Ref, loading: Ref, error: Ref, execute: Function, reset: Function}}
 *
 * @example
 * const { data, loading, error, execute } = useAsyncState(getPhenopackets)
 * await execute({ page: 1, size: 20 })
 */

import { ref } from 'vue';

export function useAsyncState(asyncFn, initialState = null) {
  const data = ref(initialState);
  const loading = ref(false);
  const error = ref(null);

  const execute = async (...args) => {
    loading.value = true;
    error.value = null;

    try {
      data.value = await asyncFn(...args);
      return data.value;
    } catch (e) {
      error.value = e;
      window.logService.error('Async operation failed', {
        error: e.message,
        function: asyncFn.name,
      });
      throw e;
    } finally {
      loading.value = false;
    }
  };

  const reset = () => {
    data.value = initialState;
    loading.value = false;
    error.value = null;
  };

  return { data, loading, error, execute, reset };
}
