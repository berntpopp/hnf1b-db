/**
 * Pure helpers to summarize and matrix-ify GA4GH phenotypicFeatures across a
 * variant's affected individuals. No I/O.
 *
 * Feature shape: { type: { id: 'HP:xxxxxxx', label: '...' }, excluded?: boolean }
 */
import { getOrganSystem, getCategoryColor, ORGAN_SYSTEMS } from '@/utils/ageParser';

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

const ORGAN_LABEL = (key) => ORGAN_SYSTEMS.find((s) => s.value === key)?.label || 'Other';
// Stable display order for organ-system groups (matches ORGAN_SYSTEMS, minus the
// never-produced 'diabetes', plus a trailing 'other').
const ORGAN_ORDER = ORGAN_SYSTEMS.map((s) => s.value).filter((v) => v !== 'diabetes');

/**
 * Build a grouped, ordered individual x phenotype matrix.
 * @param {Array<{phenopacketId:string, subjectId:string, features:Array}>} individuals
 * @param {{maxTerms?:number}} [opts]
 * @returns {{
 *   rows: Array<{phenopacketId,subjectId,presentCount}>,
 *   columns: Array<{id,label,organSystem,organLabel,color,frequency}>,
 *   groups: Array<{organSystem,label,color,startIndex,span}>,
 *   cells: Object<string,Object<string,'present'|'excluded'|'not-reported'>>,
 *   conflicts: Set<string>,
 *   totalTerms:number, shownTerms:number, truncated:boolean
 * }}
 */
export function buildPhenotypeMatrix(individuals, opts = {}) {
  const list = individuals || [];
  const conflicts = new Set();

  // Per-individual present/excluded sets (dedupe via summarizePhenotypes).
  const perRow = list.map((ind) => {
    const present = new Set();
    const excluded = new Set();
    const seenPresent = new Set();
    const seenExcluded = new Set();
    for (const feat of ind.features || []) {
      const id = feat?.type?.id;
      if (!id) continue;
      if (feat.excluded) seenExcluded.add(id);
      else seenPresent.add(id);
    }
    for (const id of seenPresent) {
      present.add(id);
      if (seenExcluded.has(id)) conflicts.add(`${ind.phenopacketId}::${id}`);
    }
    for (const id of seenExcluded) if (!seenPresent.has(id)) excluded.add(id);
    return { ind, present, excluded };
  });

  // Term metadata + present frequency across the cohort.
  const termMeta = new Map(); // id -> { id, label, organSystem, organLabel, color, frequency }
  for (const { ind, present, excluded } of perRow) {
    for (const feat of ind.features || []) {
      const id = feat?.type?.id;
      if (!id || termMeta.has(id)) continue;
      const organSystem = getOrganSystem(id);
      termMeta.set(id, {
        id,
        label: feat.type.label || id,
        organSystem,
        organLabel: ORGAN_LABEL(organSystem),
        color: getCategoryColor(organSystem),
        frequency: 0,
      });
    }
    for (const id of present) {
      const meta = termMeta.get(id);
      if (meta) meta.frequency += 1;
    }
    // ensure excluded-only terms still have meta (frequency 0)
    for (const id of excluded) {
      if (!termMeta.get(id)) continue;
    }
  }

  const totalTerms = termMeta.size;

  // Order columns: by organ-system group order, then present-frequency desc, then label.
  let columns = [...termMeta.values()].sort((a, b) => {
    const ga = ORGAN_ORDER.indexOf(a.organSystem);
    const gb = ORGAN_ORDER.indexOf(b.organSystem);
    if (ga !== gb) return ga - gb;
    if (b.frequency !== a.frequency) return b.frequency - a.frequency;
    return a.label.localeCompare(b.label);
  });

  // Cap to maxTerms by global present frequency (keep most-frequent terms).
  const maxTerms = opts.maxTerms;
  let truncated = false;
  if (typeof maxTerms === 'number' && columns.length > maxTerms) {
    const keep = new Set(
      [...columns]
        .sort((a, b) => b.frequency - a.frequency || a.label.localeCompare(b.label))
        .slice(0, maxTerms)
        .map((c) => c.id)
    );
    columns = columns.filter((c) => keep.has(c.id));
    truncated = true;
  }

  // Groups (contiguous runs of the same organ system in the ordered columns).
  const groups = [];
  columns.forEach((col, i) => {
    const last = groups[groups.length - 1];
    if (last && last.organSystem === col.organSystem) {
      last.span += 1;
    } else {
      groups.push({
        organSystem: col.organSystem,
        label: col.organLabel,
        color: col.color,
        startIndex: i,
        span: 1,
      });
    }
  });

  // Cells.
  const shownIds = new Set(columns.map((c) => c.id));
  const cells = {};
  for (const { ind, present, excluded } of perRow) {
    const row = {};
    for (const id of shownIds) {
      if (present.has(id)) row[id] = 'present';
      else if (excluded.has(id)) row[id] = 'excluded';
      else row[id] = 'not-reported';
    }
    cells[ind.phenopacketId] = row;
  }

  // Rows ordered by present count desc, subjectId tiebreak.
  const rows = perRow
    .map(({ ind, present }) => ({
      phenopacketId: ind.phenopacketId,
      subjectId: ind.subjectId,
      presentCount: present.size,
    }))
    .sort(
      (a, b) =>
        b.presentCount - a.presentCount || String(a.subjectId).localeCompare(String(b.subjectId))
    );

  return {
    rows,
    columns,
    groups,
    cells,
    conflicts,
    totalTerms,
    shownTerms: columns.length,
    truncated,
  };
}
