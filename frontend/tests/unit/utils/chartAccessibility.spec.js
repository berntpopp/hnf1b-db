/**
 * Unit tests for chart accessibility utilities
 *
 * Tests cover:
 * - addChartAccessibility with D3 selection and raw SVG element
 * - generateDonutDescription format and edge cases
 * - generateBarChartDescription format, truncation, and edge cases
 * - generateLineChartDescription format and edge cases
 *
 * @module tests/unit/utils/chartAccessibility
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  addChartAccessibility,
  generateDonutDescription,
  generateBarChartDescription,
  generateLineChartDescription,
} from '@/utils/chartAccessibility';

describe('chartAccessibility utilities', () => {
  beforeEach(() => {
    // Mock window.logService
    window.logService = {
      warn: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      debug: vi.fn(),
    };
  });

  afterEach(() => {
    delete window.logService;
  });

  describe('addChartAccessibility', () => {
    describe('with raw SVG element', () => {
      it('adds role="img" to SVG', () => {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');

        addChartAccessibility(svg, 'title-1', 'desc-1', 'Chart Title', 'Chart description');

        expect(svg.getAttribute('role')).toBe('img');
      });

      it('adds aria-labelledby with title and desc IDs', () => {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');

        addChartAccessibility(svg, 'title-1', 'desc-1', 'Chart Title', 'Chart description');

        expect(svg.getAttribute('aria-labelledby')).toBe('title-1 desc-1');
      });

      it('inserts title element as first child', () => {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');

        addChartAccessibility(svg, 'title-1', 'desc-1', 'Chart Title', 'Chart description');

        const titleElement = svg.querySelector('title');
        expect(titleElement).not.toBeNull();
        expect(titleElement.getAttribute('id')).toBe('title-1');
        expect(titleElement.textContent).toBe('Chart Title');
      });

      it('inserts desc element after title', () => {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');

        addChartAccessibility(svg, 'title-1', 'desc-1', 'Chart Title', 'Chart description');

        const descElement = svg.querySelector('desc');
        expect(descElement).not.toBeNull();
        expect(descElement.getAttribute('id')).toBe('desc-1');
        expect(descElement.textContent).toBe('Chart description');
      });

      it('inserts title before existing content', () => {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        svg.appendChild(rect);

        addChartAccessibility(svg, 'title-1', 'desc-1', 'Chart Title', 'Chart description');

        // Title should be first child
        expect(svg.firstChild.tagName).toBe('title');
      });
    });

    describe('with D3 selection mock', () => {
      it('calls attr method with role and aria-labelledby', () => {
        const mockD3Selection = {
          attr: vi.fn().mockReturnThis(),
          insert: vi.fn().mockReturnValue({
            attr: vi.fn().mockReturnThis(),
            text: vi.fn().mockReturnThis(),
          }),
        };

        addChartAccessibility(
          mockD3Selection,
          'title-1',
          'desc-1',
          'Chart Title',
          'Chart description'
        );

        expect(mockD3Selection.attr).toHaveBeenCalledWith('role', 'img');
        expect(mockD3Selection.attr).toHaveBeenCalledWith('aria-labelledby', 'title-1 desc-1');
      });

      it('calls insert for title and desc elements', () => {
        const mockInsertResult = {
          attr: vi.fn().mockReturnThis(),
          text: vi.fn().mockReturnThis(),
        };
        const mockD3Selection = {
          attr: vi.fn().mockReturnThis(),
          insert: vi.fn().mockReturnValue(mockInsertResult),
        };

        addChartAccessibility(
          mockD3Selection,
          'title-1',
          'desc-1',
          'Chart Title',
          'Chart description'
        );

        expect(mockD3Selection.insert).toHaveBeenCalledWith('title', ':first-child');
        expect(mockD3Selection.insert).toHaveBeenCalledWith('desc', 'title + *');
      });
    });

    it('warns when called with null SVG', () => {
      addChartAccessibility(null, 'title-1', 'desc-1', 'Chart Title', 'Chart description');

      expect(window.logService.warn).toHaveBeenCalledWith(
        'addChartAccessibility called with null SVG'
      );
    });
  });

  describe('generateDonutDescription', () => {
    it('generates description with total and percentages', () => {
      const data = [
        { label: 'Male', count: 50 },
        { label: 'Female', count: 50 },
      ];

      const result = generateDonutDescription(data, 100);

      expect(result).toContain('100 total items');
      expect(result).toContain('Male: 50 (50.0%)');
      expect(result).toContain('Female: 50 (50.0%)');
    });

    it('handles single category', () => {
      const data = [{ label: 'All', count: 100 }];

      const result = generateDonutDescription(data, 100);

      expect(result).toBe('Chart showing 100 total items. All: 100 (100.0%).');
    });

    it('formats percentages to one decimal place', () => {
      const data = [
        { label: 'A', count: 33 },
        { label: 'B', count: 67 },
      ];

      const result = generateDonutDescription(data, 100);

      expect(result).toContain('(33.0%)');
      expect(result).toContain('(67.0%)');
    });

    it('handles empty data array', () => {
      const result = generateDonutDescription([], 0);

      expect(result).toBe('Chart with no data.');
    });

    it('handles null data', () => {
      const result = generateDonutDescription(null, 0);

      expect(result).toBe('Chart with no data.');
    });

    it('handles zero total', () => {
      const data = [{ label: 'Empty', count: 0 }];

      const result = generateDonutDescription(data, 0);

      expect(result).toBe('Chart showing 0 total items.');
    });
  });

  describe('generateBarChartDescription', () => {
    it('generates description with feature count and penetrance', () => {
      const data = [
        { label: 'Kidney abnormality', present: 70, absent: 30 },
        { label: 'Diabetes', present: 50, absent: 50 },
      ];

      const result = generateBarChartDescription(data);

      expect(result).toContain('2 features');
      expect(result).toContain('Kidney abnormality: 70% present');
      expect(result).toContain('Diabetes: 50% present');
    });

    it('truncates to top 10 features', () => {
      const data = Array.from({ length: 15 }, (_, i) => ({
        label: `Feature ${i + 1}`,
        present: 50,
        absent: 50,
      }));

      const result = generateBarChartDescription(data);

      expect(result).toContain('15 features');
      expect(result).toContain('and 5 more features');
      expect(result).toContain('Feature 1');
      expect(result).toContain('Feature 10');
      expect(result).not.toContain('Feature 11:');
    });

    it('does not show "more features" when 10 or less', () => {
      const data = Array.from({ length: 10 }, (_, i) => ({
        label: `Feature ${i + 1}`,
        present: 50,
        absent: 50,
      }));

      const result = generateBarChartDescription(data);

      expect(result).not.toContain('more features');
    });

    it('handles zero total for a feature', () => {
      const data = [{ label: 'Empty', present: 0, absent: 0 }];

      const result = generateBarChartDescription(data);

      expect(result).toContain('Empty: 0% present (0 of 0)');
    });

    it('handles empty data array', () => {
      const result = generateBarChartDescription([]);

      expect(result).toBe('Bar chart with no data.');
    });

    it('handles null data', () => {
      const result = generateBarChartDescription(null);

      expect(result).toBe('Bar chart with no data.');
    });
  });

  describe('generateLineChartDescription', () => {
    it('generates description with group count and sample sizes', () => {
      const groups = [
        { name: 'Group A', n: 100, events: 25 },
        { name: 'Group B', n: 150, events: 40 },
      ];

      const result = generateLineChartDescription(groups);

      expect(result).toContain('2 groups');
      expect(result).toContain('Group A: 100 subjects, 25 events');
      expect(result).toContain('Group B: 150 subjects, 40 events');
    });

    it('handles single group', () => {
      const groups = [{ name: 'All patients', n: 500, events: 100 }];

      const result = generateLineChartDescription(groups);

      expect(result).toBe(
        'Survival chart showing 1 groups. All patients: 500 subjects, 100 events.'
      );
    });

    it('handles empty groups array', () => {
      const result = generateLineChartDescription([]);

      expect(result).toBe('Survival chart with no data.');
    });

    it('handles null groups', () => {
      const result = generateLineChartDescription(null);

      expect(result).toBe('Survival chart with no data.');
    });

    it('handles zero events', () => {
      const groups = [{ name: 'No events', n: 100, events: 0 }];

      const result = generateLineChartDescription(groups);

      expect(result).toContain('0 events');
    });
  });
});
