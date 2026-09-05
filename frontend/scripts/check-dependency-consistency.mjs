import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const TIPTAP_VERSION = '3.30.5';
const TIPTAP_PACKAGES = [
  '@tiptap/core',
  '@tiptap/extension-link',
  '@tiptap/extension-mention',
  '@tiptap/starter-kit',
  '@tiptap/vue-3',
];

export function assertTiptapDependencyConsistency(manifest, lock) {
  for (const packageName of TIPTAP_PACKAGES) {
    if (manifest.dependencies?.[packageName] !== TIPTAP_VERSION) {
      throw new Error(
        `${packageName} manifest version must be ${TIPTAP_VERSION}; found ${manifest.dependencies?.[packageName]}`
      );
    }
  }

  for (const [lockPath, packageData] of Object.entries(lock.packages ?? {})) {
    const packageMatch = lockPath.match(/(?:^|\/)node_modules\/(@tiptap\/[^/]+)$/);
    if (packageMatch && packageData.version !== TIPTAP_VERSION) {
      const packageName = packageMatch[1];
      throw new Error(
        `${packageName} lock version must be ${TIPTAP_VERSION}; found ${packageData.version} at ${lockPath}`
      );
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const readJson = (name) => JSON.parse(readFileSync(resolve(frontendRoot, name), 'utf8'));

  assertTiptapDependencyConsistency(readJson('package.json'), readJson('package-lock.json'));
}
