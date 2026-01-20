/**
 * Chart Export Utilities
 *
 * Provides functions for exporting chart data and visualizations.
 * - PNG export with 2x resolution for high-quality images
 * - CSV export with snake_case headers for machine-readable data
 *
 * @module utils/export
 */

import { saveAs } from 'file-saver';

/**
 * Export SVG element to PNG at specified resolution scale.
 *
 * Creates a high-resolution PNG image from an SVG element by:
 * 1. Cloning the SVG and adding a white background
 * 2. Rendering to a canvas at scaled resolution
 * 3. Converting to PNG blob and downloading
 *
 * @param {SVGElement} svgElement - The SVG element to export
 * @param {string} filename - Base filename (without extension)
 * @param {number} [scale=2] - Resolution multiplier (default: 2 for 2x)
 * @returns {void}
 *
 * @example
 * // Export chart at 2x resolution
 * const svg = document.querySelector('svg');
 * exportToPNG(svg, 'variant-types-2026-01-20');
 */
export function exportToPNG(svgElement, filename, scale = 2) {
  if (!svgElement) {
    window.logService?.warn('exportToPNG called with null SVG element');
    return;
  }

  // Clone SVG to avoid modifying original
  const clonedSvg = svgElement.cloneNode(true);
  clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

  // Add white background as first child
  const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  background.setAttribute('width', '100%');
  background.setAttribute('height', '100%');
  background.setAttribute('fill', 'white');
  clonedSvg.insertBefore(background, clonedSvg.firstChild);

  // Get SVG dimensions
  const svgWidth = svgElement.width?.baseVal?.value || svgElement.clientWidth || 800;
  const svgHeight = svgElement.height?.baseVal?.value || svgElement.clientHeight || 600;

  // Serialize SVG to string
  const serializer = new XMLSerializer();
  const svgData = serializer.serializeToString(clonedSvg);

  // Create canvas at scaled resolution
  const canvas = document.createElement('canvas');
  canvas.width = svgWidth * scale;
  canvas.height = svgHeight * scale;

  const ctx = canvas.getContext('2d');

  // Guard for environments where canvas context is not available (e.g., test environments)
  if (!ctx) {
    window.logService?.warn('Canvas 2D context not available for PNG export');
    return;
  }

  // Fill canvas with white background
  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);

  // Create image from SVG data
  const img = new Image();

  img.onload = () => {
    ctx.drawImage(img, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) {
        saveAs(blob, `${filename}.png`);
      }
    }, 'image/png');
  };

  img.onerror = () => {
    window.logService?.error('Failed to load SVG for PNG export');
  };

  // Use base64 encoded data URI for cross-browser compatibility
  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
}

/**
 * Export data array to CSV file.
 *
 * Generates a CSV file with:
 * - Header row from provided headers array
 * - Data rows with proper escaping for quotes and commas
 * - UTF-8 encoding with BOM for Excel compatibility
 *
 * @param {Array<Object>} data - Array of data objects
 * @param {Array<string>} headers - Column headers (snake_case recommended)
 * @param {string} filename - Filename (without extension)
 * @returns {void}
 *
 * @example
 * const data = [
 *   { variant_type: 'SNV', count: 42, percentage: 50.0 },
 *   { variant_type: 'Deletion', count: 35, percentage: 41.7 }
 * ];
 * exportToCSV(data, ['variant_type', 'count', 'percentage'], 'variants-2026-01-20');
 */
export function exportToCSV(data, headers, filename) {
  if (!data || !headers || headers.length === 0) {
    window.logService?.warn('exportToCSV called with invalid data or headers');
    return;
  }

  // Create header row
  const headerRow = headers.join(',');

  // Map data to rows with proper escaping
  const rows = data.map((item) =>
    headers
      .map((h) => {
        const val = item[h];

        // Handle null/undefined
        if (val === null || val === undefined) {
          return '';
        }

        // Convert to string
        const strVal = String(val);

        // Escape quotes and wrap in quotes if contains comma, quote, or newline
        if (strVal.includes(',') || strVal.includes('"') || strVal.includes('\n')) {
          return `"${strVal.replace(/"/g, '""')}"`;
        }

        return strVal;
      })
      .join(',')
  );

  // Join all rows with newline
  const csv = [headerRow, ...rows].join('\n');

  // Create blob with BOM for Excel compatibility
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' });

  saveAs(blob, `${filename}.csv`);
}

/**
 * Generate timestamp for filenames.
 *
 * Returns current date in ISO format (YYYY-MM-DD) suitable for filenames.
 *
 * @returns {string} ISO date string (YYYY-MM-DD)
 *
 * @example
 * getTimestamp(); // Returns: '2026-01-20'
 */
export function getTimestamp() {
  return new Date().toISOString().slice(0, 10);
}
