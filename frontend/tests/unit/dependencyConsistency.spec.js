import { describe, expect, it } from 'vitest';

import { assertTiptapDependencyConsistency } from '../../scripts/check-dependency-consistency.mjs';

const tiptapPackages = [
  '@tiptap/core',
  '@tiptap/extension-link',
  '@tiptap/extension-mention',
  '@tiptap/starter-kit',
  '@tiptap/vue-3',
];

function lockWith(version) {
  return {
    packages: Object.fromEntries(
      tiptapPackages.map((name) => [`node_modules/${name}`, { version }])
    ),
  };
}

describe('Tiptap dependency consistency', () => {
  it('accepts manifest and root lock versions aligned at 3.30.1', () => {
    const manifest = {
      dependencies: Object.fromEntries(tiptapPackages.map((name) => [name, '3.30.1'])),
    };

    expect(() => assertTiptapDependencyConsistency(manifest, lockWith('3.30.1'))).not.toThrow();
  });

  it('rejects a direct package that drifts from the aligned Tiptap version', () => {
    const manifest = {
      dependencies: {
        ...Object.fromEntries(tiptapPackages.map((name) => [name, '3.30.1'])),
        '@tiptap/vue-3': '3.27.1',
      },
    };

    expect(() => assertTiptapDependencyConsistency(manifest, lockWith('3.30.1'))).toThrow(
      '@tiptap/vue-3 manifest version must be 3.30.1'
    );
  });

  it('rejects a nested lockfile Tiptap package that creates a split graph', () => {
    const manifest = {
      dependencies: Object.fromEntries(tiptapPackages.map((name) => [name, '3.30.1'])),
    };
    const lock = {
      ...lockWith('3.30.1'),
      packages: {
        ...lockWith('3.30.1').packages,
        'node_modules/legacy-editor/node_modules/@tiptap/core': { version: '3.27.1' },
      },
    };

    expect(() => assertTiptapDependencyConsistency(manifest, lock)).toThrow(
      'nested lock version must be 3.30.1'
    );
  });
});
