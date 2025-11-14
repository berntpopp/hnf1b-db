/**
 * Composable for autosaving form data to localStorage.
 *
 * Prevents data loss from browser crashes or accidental navigation.
 *
 * @param {Ref} data - Reactive data to autosave
 * @param {string} key - localStorage key
 * @param {number} delay - Debounce delay in ms (default: 2000)
 * @returns {{restore: Function, clear: Function}}
 *
 * @example
 * const phenopacket = ref({})
 * const { restore, clear } = useAutosave(phenopacket, 'phenopacket-draft', 2000)
 *
 * // On mount
 * const draft = restore()
 * if (draft) phenopacket.value = draft
 *
 * // On submit
 * clear()
 */

import { watch } from 'vue';
import { debounce } from 'lodash-es';

export function useAutosave(data, key, delay = 2000) {
  const save = debounce(() => {
    try {
      localStorage.setItem(key, JSON.stringify(data.value));
      window.logService.debug('Form autosaved', { key });
    } catch (e) {
      window.logService.error('Autosave failed', { key, error: e.message });
    }
  }, delay);

  watch(data, save, { deep: true });

  const restore = () => {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      window.logService.error('Autosave restore failed', { key, error: e.message });
    }
    return null;
  };

  const clear = () => {
    localStorage.removeItem(key);
    window.logService.debug('Autosave cleared', { key });
  };

  return { restore, clear };
}
