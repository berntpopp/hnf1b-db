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
