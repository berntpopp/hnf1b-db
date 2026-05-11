import { saveAs } from 'file-saver';

/**
 * Build a filename in the format hnf1b-db_<kebab-name>_<YYYY-MM-DD>.<ext>.
 * @param {string} chartName - Human-readable chart name (any case, spaces or underscores allowed).
 * @param {string} ext - File extension without the dot ('png', 'csv', 'svg').
 * @returns {string}
 */
export function buildExportFilename(chartName, ext) {
  const kebab = chartName
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[\s_]+/g, '-')
    .toLowerCase();
  const date = new Date().toISOString().slice(0, 10);
  return `hnf1b-db_${kebab}_${date}.${ext}`;
}

const CSV_NEEDS_QUOTING = /[,"\n\r]/;

function escapeCsvField(value) {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (CSV_NEEDS_QUOTING.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Export an array of row objects to a CSV file (RFC 4180, UTF-8 BOM, CRLF).
 * @param {Array<Object>} rows
 * @param {Array<{key:string,label:string}>} columns
 * @param {string} filename
 */
export function exportDataAsCsv(rows, columns, filename) {
  const header = columns.map((c) => escapeCsvField(c.label)).join(',');
  const body = rows
    .map((row) => columns.map((c) => escapeCsvField(row[c.key])).join(','))
    .join('\r\n');
  const csv = `\uFEFF${header}\r\n${body}${rows.length ? '\r\n' : ''}`;
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  saveAs(blob, filename);
}
