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

/**
 * Export an SVG element as a raw .svg file (vector, editable in Illustrator/Inkscape).
 * @param {SVGElement} svgEl
 * @param {string} filename
 */
export function exportSvgAsSvg(svgEl, filename) {
  const serialized = new XMLSerializer().serializeToString(svgEl);
  const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
  saveAs(blob, filename);
}

/**
 * Inline computed styles from the live DOM onto a cloned SVG subtree so that
 * the serialized SVG renders identically when loaded into a canvas.
 * D3 sets some styles via .style() (inline) and some via class rules; only
 * inline styles survive cloneNode. This walk transfers the rest.
 * @param {Element} liveRoot - The original element still in the DOM.
 * @param {Element} clonedRoot - The cloned element to mutate.
 */
function inlineComputedStyles(liveRoot, clonedRoot) {
  const liveNodes = [liveRoot, ...liveRoot.querySelectorAll('*')];
  const clonedNodes = [clonedRoot, ...clonedRoot.querySelectorAll('*')];
  for (let i = 0; i < liveNodes.length; i++) {
    const computed = window.getComputedStyle(liveNodes[i]);
    let inline = '';
    for (let j = 0; j < computed.length; j++) {
      const prop = computed[j];
      inline += `${prop}:${computed.getPropertyValue(prop)};`;
    }
    clonedNodes[i].setAttribute('style', inline);
  }
}

/**
 * Export an SVG element as a PNG via canvas. No external dependencies for
 * rasterization; uses file-saver for the download trigger.
 * @param {SVGElement} svgEl
 * @param {{filename:string, scale?:number, background?:string}} options
 * @returns {Promise<void>}
 */
export function exportSvgAsPng(svgEl, { filename, scale = 2, background = '#ffffff' }) {
  return new Promise((resolve, reject) => {
    const bbox = {
      width: parseFloat(svgEl.getAttribute('width')) || svgEl.clientWidth,
      height: parseFloat(svgEl.getAttribute('height')) || svgEl.clientHeight,
    };

    const clone = svgEl.cloneNode(true);
    inlineComputedStyles(svgEl, clone);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', bbox.width);
    clone.setAttribute('height', bbox.height);

    const serialized = new XMLSerializer().serializeToString(clone);
    const svgBlob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = bbox.width * scale;
      canvas.height = bbox.height * scale;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((pngBlob) => {
        saveAs(pngBlob, filename);
        resolve();
      }, 'image/png');
    };
    img.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };
    img.src = url;
  });
}
