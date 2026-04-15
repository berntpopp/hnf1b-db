// src/composables/useAppTheme.js
//
// App-level theme management.
//
// Wraps Vuetify 4's `useTheme()` composable with three behaviours the
// framework does not give you for free:
//
//   1. A three-way user preference ('light' | 'dark' | 'system') that
//      persists to localStorage under `hnf1b-theme`.
//   2. When the preference is 'system', watches the OS
//      prefers-color-scheme media query and re-applies the matching
//      theme on change.
//   3. Mirrors the active theme into the <html> element's
//      `color-scheme` CSS property so scrollbars, text-fields and
//      native form controls render consistently.
//
// Consumers call `useAppTheme()` once (typically from a root-ish
// component like ThemeSwitcher or AppBar) and receive:
//   - preference:     'light' | 'dark' | 'system' (writable ref)
//   - resolvedTheme:  'light' | 'dark' (computed — what is *actually*
//                                       showing, after resolving system)
//   - setPreference(value): persist + apply
//   - toggle():             flip light ↔ dark (collapses 'system' to
//                                               the opposite of what's
//                                               currently showing)
//
// Multiple call sites share state via a module-local ref, so any
// component can read `preference.value` without prop drilling.

import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useTheme } from 'vuetify';
import { DARK_THEME, LIGHT_THEME, THEME_STORAGE_KEY } from '@/plugins/vuetify';

const PREFERENCE_VALUES = ['light', 'dark', 'system'];
const DARK_MEDIA_QUERY = '(prefers-color-scheme: dark)';

// Module-local singleton so every call site sees the same state.
const preference = ref(readStoredPreference());

function readStoredPreference() {
  if (typeof window === 'undefined') return 'light';
  const stored = window.localStorage?.getItem(THEME_STORAGE_KEY);
  if (stored === 'light' || stored === LIGHT_THEME) return 'light';
  if (stored === 'dark' || stored === DARK_THEME) return 'dark';
  if (stored === 'system') return 'system';
  // Default to light (brand choice). Users who want system-follow can
  // pick it explicitly; see ThemeSwitcher for the entry point.
  return 'light';
}

function systemPrefersDark() {
  if (typeof window === 'undefined') return false;
  return !!window.matchMedia?.(DARK_MEDIA_QUERY).matches;
}

/**
 * Resolve a preference ('light' | 'dark' | 'system') to an actual
 * Vuetify theme name.
 */
function resolveThemeName(pref) {
  if (pref === 'light') return LIGHT_THEME;
  if (pref === 'dark') return DARK_THEME;
  return systemPrefersDark() ? DARK_THEME : LIGHT_THEME;
}

/**
 * Apply a theme name to Vuetify + update <html>.color-scheme. Pulled
 * out so the media-query listener can call it without knowing about
 * the stored preference.
 *
 * Uses `theme.change(name)` — the `theme.global.name.value = x`
 * assignment was deprecated in Vuetify 4.
 */
function applyTheme(vuetifyTheme, themeName) {
  vuetifyTheme.change(themeName);
  if (typeof document !== 'undefined') {
    const scheme = themeName === DARK_THEME ? 'dark' : 'light';
    document.documentElement.style.colorScheme = scheme;
  }
}

/**
 * Composable entry point. Registers a media-query listener when called
 * inside a component so system-preference changes update the UI live.
 */
export function useAppTheme() {
  const vuetifyTheme = useTheme();

  /** What the app is actually rendering right now. */
  const resolvedTheme = computed(() =>
    resolveThemeName(preference.value) === DARK_THEME ? 'dark' : 'light'
  );

  /** Set and persist the user's preference, apply immediately. */
  function setPreference(value) {
    if (!PREFERENCE_VALUES.includes(value)) return;
    preference.value = value;
    try {
      window.localStorage?.setItem(THEME_STORAGE_KEY, value);
    } catch {
      // Incognito / quota / disabled storage — ignore, memory state
      // is still correct for this tab.
    }
    applyTheme(vuetifyTheme, resolveThemeName(value));
  }

  /**
   * Flip between light and dark. If the current preference is
   * 'system', this pins the user to the opposite of whatever the
   * system currently says (matches typical product behaviour — one
   * click overrides the auto-follow).
   */
  function toggle() {
    setPreference(resolvedTheme.value === 'dark' ? 'light' : 'dark');
  }

  // Live-update when the OS preference changes while the user is on
  // 'system'. Only one listener per component instance; cleaned up on
  // unmount to avoid leaks on hot reload.
  let mediaQuery = null;
  const onSystemChange = () => {
    if (preference.value === 'system') {
      applyTheme(vuetifyTheme, resolveThemeName('system'));
    }
  };

  onMounted(() => {
    if (typeof window === 'undefined') return;
    mediaQuery = window.matchMedia(DARK_MEDIA_QUERY);
    mediaQuery.addEventListener('change', onSystemChange);
    // Make sure color-scheme on <html> agrees with whatever theme
    // Vuetify booted with — the pre-boot script in index.html sets
    // this too, but covering the case where it was absent.
    applyTheme(vuetifyTheme, resolveThemeName(preference.value));
  });

  onUnmounted(() => {
    mediaQuery?.removeEventListener('change', onSystemChange);
  });

  return {
    preference,
    resolvedTheme,
    setPreference,
    toggle,
  };
}
