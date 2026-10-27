import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

// index.html pins Vuetify's cascade-layer order before any stylesheet loads
// (production links component CSS ahead of the core reset). If a Vuetify
// upgrade adds or renames a layer, that statement must follow, or the new
// layer silently outranks the rest in production only.
const root = path.resolve(__dirname, '../..');

function vuetifyLayerOrder() {
  const css = fs.readFileSync(path.join(root, 'node_modules/vuetify/lib/styles/main.css'), 'utf8');
  const order = [];
  let parent = null;
  for (const line of css.split('\n').map((l) => l.trim())) {
    let m;
    if (!line) continue;
    if ((m = line.match(/^@layer ([\w-]+) \{$/)) && !parent) {
      parent = m[1];
    } else if ((m = line.match(/^@layer ([\w\s,-]+);$/))) {
      const names = m[1].split(',').map((n) => n.trim());
      order.push(...names.map((n) => (parent ? `${parent}.${n}` : n)));
    } else if (line === '}' && parent) {
      if (!order.some((n) => n.startsWith(`${parent}.`))) order.push(parent);
      parent = null;
    } else {
      break; // end of the layer-order prologue
    }
  }
  return order;
}

describe('Vuetify cascade-layer order', () => {
  it('index.html declares exactly the layers Vuetify defines, in order', () => {
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    const declared = html
      .match(/@layer ([^;{]+);/)[1]
      .split(',')
      .map((n) => n.trim());

    const expected = vuetifyLayerOrder();
    expect(expected.length).toBeGreaterThan(5);
    expect(declared).toEqual(expected);
  });
});
