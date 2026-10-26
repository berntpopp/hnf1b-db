import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

// Every `mdi-*` name in src/ must exist in the installed @mdi/font. A missing
// name renders as an empty box, and the build-time mdi-subset plugin
// (vite.config.js) keeps only the names it finds here.
const root = path.resolve(__dirname, '../..');
const css = fs.readFileSync(
  path.join(root, 'node_modules/@mdi/font/css/materialdesignicons.css'),
  'utf8'
);
const known = new Set([...css.matchAll(/\.(mdi-[a-z0-9-]+)(?:::before|\s*\{)/g)].map((m) => m[1]));

function namesIn(dir) {
  return fs.readdirSync(dir, { recursive: true }).flatMap((f) => {
    const p = path.join(dir, f);
    if (fs.statSync(p).isDirectory()) return [];
    return [...fs.readFileSync(p, 'utf8').matchAll(/mdi-[a-z0-9]+(?:-[a-z0-9]+)*/g)].map(
      (m) => m[0]
    );
  });
}

describe('MDI icon names', () => {
  it('only references icons that exist in @mdi/font', () => {
    const unknown = [...new Set(namesIn(path.join(root, 'src')))].filter((n) => !known.has(n));
    expect(unknown).toEqual([]);
  });
});
