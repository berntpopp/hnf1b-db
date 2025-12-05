/**
 * Accessibility composables for improved user experience.
 * Provides reactive detection of user preferences and responsive breakpoints.
 */
import { ref, onMounted, onUnmounted } from 'vue';

/**
 * Detect if user prefers reduced motion.
 * Used to disable or reduce animations for accessibility.
 * @returns {import('vue').Ref<boolean>} Reactive boolean indicating preference
 * @example
 * const prefersReducedMotion = usePrefersReducedMotion();
 * const scrollBehavior = computed(() =>
 *   prefersReducedMotion.value ? 'instant' : 'smooth'
 * );
 */
export function usePrefersReducedMotion() {
  const prefersReducedMotion = ref(false);
  let mediaQuery = null;

  const updatePreference = (e) => {
    prefersReducedMotion.value = e.matches;
  };

  onMounted(() => {
    mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    prefersReducedMotion.value = mediaQuery.matches;
    mediaQuery.addEventListener('change', updatePreference);
  });

  onUnmounted(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', updatePreference);
    }
  });

  return prefersReducedMotion;
}

/**
 * Detect if user prefers dark color scheme.
 * Can be used to adjust chart colors or visualizations.
 * @returns {import('vue').Ref<boolean>} Reactive boolean indicating preference
 */
export function usePrefersDarkMode() {
  const prefersDarkMode = ref(false);
  let mediaQuery = null;

  const updatePreference = (e) => {
    prefersDarkMode.value = e.matches;
  };

  onMounted(() => {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    prefersDarkMode.value = mediaQuery.matches;
    mediaQuery.addEventListener('change', updatePreference);
  });

  onUnmounted(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', updatePreference);
    }
  });

  return prefersDarkMode;
}

/**
 * Responsive breakpoint detection.
 * @param {number} breakpoint - Max width in pixels (default: 600 for mobile)
 * @returns {import('vue').Ref<boolean>} Reactive boolean indicating if below breakpoint
 * @example
 * const isMobile = useIsMobile();
 * const isTablet = useIsMobile(960);
 */
export function useIsMobile(breakpoint = 600) {
  const isMobile = ref(false);
  let mediaQuery = null;

  const updateMatch = (e) => {
    isMobile.value = e.matches;
  };

  onMounted(() => {
    mediaQuery = window.matchMedia(`(max-width: ${breakpoint}px)`);
    isMobile.value = mediaQuery.matches;
    mediaQuery.addEventListener('change', updateMatch);
  });

  onUnmounted(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', updateMatch);
    }
  });

  return isMobile;
}

/**
 * Scroll to element with accessibility-aware behavior.
 * Uses instant scroll when user prefers reduced motion.
 * @returns {Object} Object with scrollToElement function
 */
export function useAccessibleScroll() {
  const prefersReducedMotion = usePrefersReducedMotion();

  /**
   * Scroll to an element with accessibility awareness.
   * @param {string|Element} target - CSS selector or DOM element
   * @param {Object} options - Scroll options
   * @param {string} options.block - Vertical alignment ('start', 'center', 'end', 'nearest')
   * @param {string} options.inline - Horizontal alignment
   */
  const scrollToElement = (target, options = {}) => {
    const element = typeof target === 'string' ? document.querySelector(target) : target;

    if (element) {
      element.scrollIntoView({
        behavior: prefersReducedMotion.value ? 'instant' : 'smooth',
        block: options.block || 'start',
        inline: options.inline || 'nearest',
      });
    }
  };

  /**
   * Scroll to top of page with accessibility awareness.
   */
  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: prefersReducedMotion.value ? 'instant' : 'smooth',
    });
  };

  return {
    scrollToElement,
    scrollToTop,
    prefersReducedMotion,
  };
}

/**
 * Announce message to screen readers via ARIA live region.
 * @returns {Object} Object with announce function
 */
export function useAnnouncer() {
  let announcer = null;

  onMounted(() => {
    // Create or find existing announcer element
    announcer = document.getElementById('a11y-announcer');
    if (!announcer) {
      announcer = document.createElement('div');
      announcer.id = 'a11y-announcer';
      announcer.setAttribute('aria-live', 'polite');
      announcer.setAttribute('aria-atomic', 'true');
      announcer.style.cssText =
        'position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;';
      document.body.appendChild(announcer);
    }
  });

  /**
   * Announce a message to screen readers.
   * @param {string} message - Message to announce
   * @param {string} priority - 'polite' (default) or 'assertive'
   */
  const announce = (message, priority = 'polite') => {
    if (announcer) {
      announcer.setAttribute('aria-live', priority);
      // Clear and set to trigger announcement
      announcer.textContent = '';
      requestAnimationFrame(() => {
        announcer.textContent = message;
      });
    }
  };

  return { announce };
}
