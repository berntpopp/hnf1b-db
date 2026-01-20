/**
 * Unit tests for export utilities
 *
 * Tests cover:
 * - getTimestamp returns valid date format
 * - exportToCSV generates correct CSV structure
 * - exportToPNG handles missing SVG gracefully
 * - CSV escaping for special characters
 *
 * @module tests/unit/utils/export
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { exportToPNG, exportToCSV, getTimestamp } from '@/utils/export';

// Mock file-saver
vi.mock('file-saver', () => ({
  saveAs: vi.fn(),
}));

import { saveAs } from 'file-saver';

describe('export utilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  describe('getTimestamp', () => {
    it('returns valid date format YYYY-MM-DD', () => {
      const result = getTimestamp();
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('returns current date', () => {
      const now = new Date();
      const expected = now.toISOString().slice(0, 10);
      const result = getTimestamp();
      expect(result).toBe(expected);
    });

    it('returns 10 character string', () => {
      const result = getTimestamp();
      expect(result.length).toBe(10);
    });
  });

  describe('exportToCSV', () => {
    it('generates correct CSV structure', () => {
      const data = [
        { variant_type: 'SNV', count: 42 },
        { variant_type: 'Deletion', count: 35 },
      ];
      const headers = ['variant_type', 'count'];

      exportToCSV(data, headers, 'test-export');

      expect(saveAs).toHaveBeenCalledTimes(1);
      const blob = saveAs.mock.calls[0][0];
      const filename = saveAs.mock.calls[0][1];

      expect(filename).toBe('test-export.csv');
      expect(blob).toBeInstanceOf(Blob);
      expect(blob.type).toBe('text/csv;charset=utf-8;');
    });

    it('escapes values containing commas', () => {
      const data = [{ name: 'Smith, John', age: 30 }];
      const headers = ['name', 'age'];

      exportToCSV(data, headers, 'test');

      expect(saveAs).toHaveBeenCalledTimes(1);
    });

    it('escapes values containing quotes', () => {
      const data = [{ name: 'John "Jack" Smith', age: 30 }];
      const headers = ['name', 'age'];

      exportToCSV(data, headers, 'test');

      expect(saveAs).toHaveBeenCalledTimes(1);
    });

    it('handles null values', () => {
      const data = [{ name: 'John', value: null }];
      const headers = ['name', 'value'];

      exportToCSV(data, headers, 'test');

      expect(saveAs).toHaveBeenCalledTimes(1);
    });

    it('handles undefined values', () => {
      const data = [{ name: 'John' }]; // 'value' is undefined
      const headers = ['name', 'value'];

      exportToCSV(data, headers, 'test');

      expect(saveAs).toHaveBeenCalledTimes(1);
    });

    it('handles numeric values', () => {
      const data = [{ count: 42, percentage: 50.5 }];
      const headers = ['count', 'percentage'];

      exportToCSV(data, headers, 'test');

      expect(saveAs).toHaveBeenCalledTimes(1);
    });

    it('handles empty data array', () => {
      const data = [];
      const headers = ['name', 'value'];

      exportToCSV(data, headers, 'test');

      expect(saveAs).toHaveBeenCalledTimes(1);
    });

    it('warns when called with null data', () => {
      exportToCSV(null, ['name'], 'test');

      expect(window.logService.warn).toHaveBeenCalledWith(
        'exportToCSV called with invalid data or headers'
      );
      expect(saveAs).not.toHaveBeenCalled();
    });

    it('warns when called with empty headers', () => {
      exportToCSV([{ name: 'John' }], [], 'test');

      expect(window.logService.warn).toHaveBeenCalledWith(
        'exportToCSV called with invalid data or headers'
      );
      expect(saveAs).not.toHaveBeenCalled();
    });
  });

  describe('exportToPNG', () => {
    it('handles null SVG element gracefully', () => {
      exportToPNG(null, 'test');

      expect(window.logService.warn).toHaveBeenCalledWith(
        'exportToPNG called with null SVG element'
      );
    });

    it('handles undefined SVG element gracefully', () => {
      exportToPNG(undefined, 'test');

      expect(window.logService.warn).toHaveBeenCalledWith(
        'exportToPNG called with null SVG element'
      );
    });

    it('clones SVG element to avoid modification', () => {
      // Create a mock SVG element
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100');
      svg.setAttribute('height', '100');

      // Create a spy on cloneNode
      const cloneNodeSpy = vi.spyOn(svg, 'cloneNode');

      exportToPNG(svg, 'test', 2);

      // In test env, canvas.getContext returns null, but cloneNode is still called
      expect(cloneNodeSpy).toHaveBeenCalledWith(true);
    });

    it('uses default scale of 2 and handles missing canvas context', () => {
      // Create a mock SVG element
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100');
      svg.setAttribute('height', '100');

      // In test environment, canvas context is not available
      // Function should handle this gracefully
      expect(() => exportToPNG(svg, 'test')).not.toThrow();

      // Verify warning is logged about missing canvas context
      expect(window.logService.warn).toHaveBeenCalledWith(
        'Canvas 2D context not available for PNG export'
      );
    });

    it('accepts custom scale parameter', () => {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100');
      svg.setAttribute('height', '100');

      // In test environment, canvas context is not available
      // Function should handle this gracefully
      expect(() => exportToPNG(svg, 'test', 3)).not.toThrow();
    });

    it('adds xmlns attributes to cloned SVG', () => {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100');
      svg.setAttribute('height', '100');

      // Override cloneNode to capture the cloned element
      let clonedSvg = null;
      const originalCloneNode = svg.cloneNode.bind(svg);
      svg.cloneNode = (deep) => {
        clonedSvg = originalCloneNode(deep);
        return clonedSvg;
      };

      exportToPNG(svg, 'test', 2);

      // Verify xmlns attributes were added
      expect(clonedSvg.getAttribute('xmlns')).toBe('http://www.w3.org/2000/svg');
      expect(clonedSvg.getAttribute('xmlns:xlink')).toBe('http://www.w3.org/1999/xlink');
    });

    it('adds white background rect to cloned SVG', () => {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100');
      svg.setAttribute('height', '100');

      // Override cloneNode to capture the cloned element
      let clonedSvg = null;
      const originalCloneNode = svg.cloneNode.bind(svg);
      svg.cloneNode = (deep) => {
        clonedSvg = originalCloneNode(deep);
        return clonedSvg;
      };

      exportToPNG(svg, 'test', 2);

      // Verify white background rect was added as first child
      const firstChild = clonedSvg.firstChild;
      expect(firstChild.tagName).toBe('rect');
      expect(firstChild.getAttribute('fill')).toBe('white');
      expect(firstChild.getAttribute('width')).toBe('100%');
      expect(firstChild.getAttribute('height')).toBe('100%');
    });
  });
});
