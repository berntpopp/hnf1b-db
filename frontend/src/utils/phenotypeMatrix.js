/**
 * Pure helpers to summarize and matrix-ify GA4GH phenotypicFeatures across a
 * variant's affected individuals. No I/O.
 *
 * Feature shape: { type: { id: 'HP:xxxxxxx', label: '...' }, excluded?: boolean }
 */

/**
 * Summarize one individual's features.
 * Dedupe by HPO id; if a term is both present and excluded, present wins.
 * @param {Array} features
 * @returns {{presentCount:number, present:Array<{id,label}>, excluded:Array<{id,label}>}}
 */
export function summarizePhenotypes(features) {
  const present = new Map();
  const excluded = new Map();
  for (const feat of features || []) {
    const id = feat?.type?.id;
    if (!id) continue;
    const term = { id, label: feat.type.label || id };
    if (feat.excluded) {
      if (!present.has(id)) excluded.set(id, term);
    } else {
      present.set(id, term);
      excluded.delete(id); // present wins
    }
  }
  return {
    presentCount: present.size,
    present: [...present.values()],
    excluded: [...excluded.values()],
  };
}
