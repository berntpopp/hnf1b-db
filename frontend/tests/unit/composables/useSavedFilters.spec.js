/**
 * Unit tests for useSavedFilters composable and query sync helpers.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  useSavedFilters,
  syncFromQuery,
  syncToQuery,
  loadPresetsFromStorage,
  persistPresetsToStorage,
} from '@/composables/useSavedFilters';

describe('useSavedFilters composable', () => {
  const scopeKey = 'test_scope';
  const storageKey = `hnf1b_saved_filters_${scopeKey}`;

  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  describe('Storage persistence helpers', () => {
    it('returns empty array if localStorage is empty', () => {
      expect(loadPresetsFromStorage(scopeKey)).toEqual([]);
    });

    it('returns empty array if corrupted JSON in localStorage', () => {
      window.localStorage.setItem(storageKey, 'invalid JSON{{');
      expect(loadPresetsFromStorage(scopeKey)).toEqual([]);
    });

    it('returns empty array if stored value is not an array', () => {
      window.localStorage.setItem(storageKey, JSON.stringify({ not: 'an array' }));
      expect(loadPresetsFromStorage(scopeKey)).toEqual([]);
    });

    it('loads and saves presets properly', () => {
      const presets = [{ name: 'Cohort A', filters: { sex: 'MALE' } }];
      persistPresetsToStorage(scopeKey, presets);
      expect(loadPresetsFromStorage(scopeKey)).toEqual(presets);
    });
  });

  describe('Preset management', () => {
    it('initializes presets from localStorage', () => {
      window.localStorage.setItem(
        storageKey,
        JSON.stringify([{ name: 'Preset 1', filters: { q: 'HNF1B' } }])
      );

      const { presets } = useSavedFilters(scopeKey);
      expect(presets.value).toHaveLength(1);
      expect(presets.value[0].name).toBe('Preset 1');
      expect(presets.value[0].filters).toEqual({ q: 'HNF1B' });
    });

    it('saves a new preset and updates localStorage', () => {
      const { presets, savePreset } = useSavedFilters(scopeKey);

      const saved = savePreset('Pathogenic SNVs', {
        variant_type: 'SNV',
        classification: 'PATHOGENIC',
        emptyFilter: '',
        nullFilter: null,
      });

      expect(saved).toBeDefined();
      expect(saved.name).toBe('Pathogenic SNVs');
      expect(saved.filters).toEqual({
        variant_type: 'SNV',
        classification: 'PATHOGENIC',
      });
      expect(presets.value).toHaveLength(1);

      const inStorage = JSON.parse(window.localStorage.getItem(storageKey));
      expect(inStorage).toHaveLength(1);
      expect(inStorage[0].name).toBe('Pathogenic SNVs');
    });

    it('updates existing preset when saving with identical name (case-insensitive)', () => {
      const { presets, savePreset } = useSavedFilters(scopeKey);

      savePreset('My Filter', { sex: 'FEMALE' });
      expect(presets.value).toHaveLength(1);
      expect(presets.value[0].filters).toEqual({ sex: 'FEMALE' });

      savePreset('my filter', { sex: 'MALE' });
      expect(presets.value).toHaveLength(1);
      expect(presets.value[0].filters).toEqual({ sex: 'MALE' });
    });

    it('ignores empty preset names', () => {
      const { presets, savePreset } = useSavedFilters(scopeKey);

      expect(savePreset('', { sex: 'MALE' })).toBeNull();
      expect(savePreset('   ', { sex: 'MALE' })).toBeNull();
      expect(savePreset(null, { sex: 'MALE' })).toBeNull();
      expect(presets.value).toHaveLength(0);
    });

    it('deletes an existing preset', () => {
      const { presets, savePreset, deletePreset } = useSavedFilters(scopeKey);

      savePreset('Preset A', { sex: 'MALE' });
      savePreset('Preset B', { sex: 'FEMALE' });
      expect(presets.value).toHaveLength(2);

      deletePreset('Preset A');
      expect(presets.value).toHaveLength(1);
      expect(presets.value[0].name).toBe('Preset B');

      const inStorage = JSON.parse(window.localStorage.getItem(storageKey));
      expect(inStorage).toHaveLength(1);
      expect(inStorage[0].name).toBe('Preset B');
    });
  });

  describe('copyShareableUrl', () => {
    it('copies current URL to clipboard via navigator.clipboard', async () => {
      const mockWriteText = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: mockWriteText,
        },
        configurable: true,
        writable: true,
      });

      const { copied, copyShareableUrl } = useSavedFilters(scopeKey);
      const result = await copyShareableUrl('https://hnf1b.org/variants?type=SNV');

      expect(result).toBe(true);
      expect(mockWriteText).toHaveBeenCalledWith('https://hnf1b.org/variants?type=SNV');
      expect(copied.value).toBe(true);
    });

    it('handles clipboard failure gracefully', async () => {
      const mockWriteText = vi.fn().mockRejectedValue(new Error('Permission denied'));
      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: mockWriteText,
        },
        configurable: true,
        writable: true,
      });

      const { copied, copyShareableUrl } = useSavedFilters(scopeKey);
      const result = await copyShareableUrl('https://hnf1b.org/variants');

      expect(result).toBe(false);
      expect(copied.value).toBe(false);
    });
  });

  describe('syncFromQuery', () => {
    it('parses types correctly from URL query parameters', () => {
      const query = {
        page: '3',
        has_variants: 'true',
        sex: 'FEMALE',
      };
      const defaults = {
        page: 1,
        has_variants: false,
        sex: 'MALE',
      };

      const parsed = syncFromQuery(query, defaults);
      expect(parsed.page).toBe(3);
      expect(parsed.has_variants).toBe(true);
      expect(parsed.sex).toBe('FEMALE');
    });

    it('falls back to default value when query param is absent or invalid number', () => {
      const query = {
        page: 'not-a-number',
      };
      const defaults = {
        page: 1,
        sex: 'ALL',
      };

      const parsed = syncFromQuery(query, defaults);
      expect(parsed.page).toBe(1);
      expect(parsed.sex).toBe('ALL');
    });

    it('returns defaults when routeQuery is null or empty', () => {
      const defaults = { tab: 'donut' };
      expect(syncFromQuery(null, defaults)).toEqual(defaults);
      expect(syncFromQuery({}, defaults)).toEqual(defaults);
    });
  });

  describe('syncToQuery without infinite loops', () => {
    it('omits defaults, nulls, and empty strings from newQuery', async () => {
      const mockRouter = {
        replace: vi.fn().mockResolvedValue(undefined),
      };
      const mockRoute = {
        query: { otherParam: 'keepMe' },
      };

      await syncToQuery(
        mockRouter,
        mockRoute,
        {
          sex: 'MALE',
          tab: 'donut',
          emptyVal: '',
          nullVal: null,
        },
        {
          defaults: { tab: 'donut' },
        }
      );

      expect(mockRouter.replace).toHaveBeenCalledWith({
        query: {
          otherParam: 'keepMe',
          sex: 'MALE',
        },
      });
    });

    it('does NOT call router.replace when query has not changed', async () => {
      const mockRouter = {
        replace: vi.fn().mockResolvedValue(undefined),
      };
      const mockRoute = {
        query: { sex: 'MALE', tab: 'survival' },
      };

      await syncToQuery(
        mockRouter,
        mockRoute,
        {
          sex: 'MALE',
          tab: 'survival',
        },
        {
          defaults: { tab: 'donut' },
        }
      );

      expect(mockRouter.replace).not.toHaveBeenCalled();
    });

    it('ignores NavigationDuplicated error', async () => {
      const duplicateErr = new Error('NavigationDuplicated');
      duplicateErr.name = 'NavigationDuplicated';
      const mockRouter = {
        replace: vi.fn().mockRejectedValue(duplicateErr),
      };
      const mockRoute = {
        query: {},
      };

      await expect(
        syncToQuery(mockRouter, mockRoute, { sex: 'FEMALE' })
      ).resolves.not.toThrow();
    });
  });
});
