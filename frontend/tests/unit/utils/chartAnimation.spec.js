/**
 * Unit tests for chart animation utilities
 *
 * Tests cover:
 * - prefersReducedMotion detection
 * - getAnimationDuration returns 0 when reduced motion preferred
 * - getStaggerDelay returns 0 when reduced motion preferred
 * - getAnimationConfig returns complete config object
 *
 * @module tests/unit/utils/chartAnimation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  prefersReducedMotion,
  getAnimationDuration,
  getStaggerDelay,
  getEasingFunction,
  getAnimationConfig,
} from '@/utils/chartAnimation';

describe('chartAnimation utilities', () => {
  let originalMatchMedia;

  beforeEach(() => {
    // Store original matchMedia
    originalMatchMedia = window.matchMedia;
  });

  afterEach(() => {
    // Restore original matchMedia
    window.matchMedia = originalMatchMedia;
  });

  /**
   * Helper to mock matchMedia with specific prefers-reduced-motion value
   */
  function mockReducedMotion(matches) {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? matches : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  }

  describe('prefersReducedMotion', () => {
    it('returns true when reduced motion is preferred', () => {
      mockReducedMotion(true);

      expect(prefersReducedMotion()).toBe(true);
    });

    it('returns false when reduced motion is not preferred', () => {
      mockReducedMotion(false);

      expect(prefersReducedMotion()).toBe(false);
    });

    it('calls matchMedia with correct query', () => {
      mockReducedMotion(false);

      prefersReducedMotion();

      expect(window.matchMedia).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)');
    });

    it('returns false when matchMedia is not available', () => {
      window.matchMedia = undefined;

      expect(prefersReducedMotion()).toBe(false);
    });
  });

  describe('getAnimationDuration', () => {
    it('returns 0 when reduced motion is preferred', () => {
      mockReducedMotion(true);

      expect(getAnimationDuration(400)).toBe(0);
    });

    it('returns default duration when reduced motion is not preferred', () => {
      mockReducedMotion(false);

      expect(getAnimationDuration(400)).toBe(400);
    });

    it('uses 400ms as default duration', () => {
      mockReducedMotion(false);

      expect(getAnimationDuration()).toBe(400);
    });

    it('accepts custom duration', () => {
      mockReducedMotion(false);

      expect(getAnimationDuration(1000)).toBe(1000);
    });

    it('returns 0 for any duration when reduced motion is preferred', () => {
      mockReducedMotion(true);

      expect(getAnimationDuration(1000)).toBe(0);
      expect(getAnimationDuration(2000)).toBe(0);
    });
  });

  describe('getStaggerDelay', () => {
    it('returns 0 when reduced motion is preferred', () => {
      mockReducedMotion(true);

      expect(getStaggerDelay(5, 50)).toBe(0);
    });

    it('returns calculated delay when reduced motion is not preferred', () => {
      mockReducedMotion(false);

      expect(getStaggerDelay(5, 50)).toBe(250); // 5 * 50
    });

    it('uses 50ms as default delay per item', () => {
      mockReducedMotion(false);

      expect(getStaggerDelay(3)).toBe(150); // 3 * 50
    });

    it('returns 0 for first element (index 0)', () => {
      mockReducedMotion(false);

      expect(getStaggerDelay(0, 50)).toBe(0);
    });

    it('accepts custom delay per item', () => {
      mockReducedMotion(false);

      expect(getStaggerDelay(4, 100)).toBe(400); // 4 * 100
    });

    it('returns 0 for any index when reduced motion is preferred', () => {
      mockReducedMotion(true);

      expect(getStaggerDelay(0, 50)).toBe(0);
      expect(getStaggerDelay(10, 100)).toBe(0);
    });
  });

  describe('getEasingFunction', () => {
    it('returns null when reduced motion is preferred', () => {
      mockReducedMotion(true);

      expect(getEasingFunction()).toBeNull();
    });

    it('returns easing function name when reduced motion is not preferred', () => {
      mockReducedMotion(false);

      expect(getEasingFunction()).toBe('easeCubicOut');
    });
  });

  describe('getAnimationConfig', () => {
    it('returns complete config object', () => {
      mockReducedMotion(false);

      const config = getAnimationConfig({ duration: 300, staggerDelay: 30 });

      expect(config).toHaveProperty('duration');
      expect(config).toHaveProperty('delay');
      expect(config).toHaveProperty('easing');
    });

    it('returns correct duration', () => {
      mockReducedMotion(false);

      const config = getAnimationConfig({ duration: 300 });

      expect(config.duration).toBe(300);
    });

    it('returns delay function that calculates correctly', () => {
      mockReducedMotion(false);

      const config = getAnimationConfig({ staggerDelay: 30 });

      expect(config.delay(0)).toBe(0);
      expect(config.delay(5)).toBe(150); // 5 * 30
    });

    it('returns easing function name', () => {
      mockReducedMotion(false);

      const config = getAnimationConfig();

      expect(config.easing).toBe('easeCubicOut');
    });

    it('returns zero duration when reduced motion is preferred', () => {
      mockReducedMotion(true);

      const config = getAnimationConfig({ duration: 300 });

      expect(config.duration).toBe(0);
    });

    it('returns zero delay when reduced motion is preferred', () => {
      mockReducedMotion(true);

      const config = getAnimationConfig({ staggerDelay: 30 });

      expect(config.delay(5)).toBe(0);
    });

    it('returns null easing when reduced motion is preferred', () => {
      mockReducedMotion(true);

      const config = getAnimationConfig();

      expect(config.easing).toBeNull();
    });

    it('uses default values when no options provided', () => {
      mockReducedMotion(false);

      const config = getAnimationConfig();

      expect(config.duration).toBe(400);
      expect(config.delay(2)).toBe(100); // 2 * 50
    });
  });
});
