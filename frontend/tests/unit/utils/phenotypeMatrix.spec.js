/**
 * Unit tests for phenotype summarization + matrix building.
 *
 * Tests cover: present-only counting, present/excluded split, per-individual
 * dedupe with present-wins precedence, and (in the next task) matrix grouping.
 */
import { describe, it, expect } from 'vitest';
import { summarizePhenotypes, buildPhenotypeMatrix } from '@/utils/phenotypeMatrix';

const f = (id, label, excluded = false) => ({ type: { id, label }, excluded });
const ind = (phenopacketId, subjectId, features) => ({ phenopacketId, subjectId, features });

describe('summarizePhenotypes', () => {
  it('counts present-only and splits present vs excluded', () => {
    const s = summarizePhenotypes([
      f('HP:0000107', 'Renal cyst'),
      f('HP:0004904', 'MODY'),
      f('HP:0000365', 'Hearing impairment', true),
    ]);
    expect(s.presentCount).toBe(2);
    expect(s.present.map((p) => p.id)).toEqual(['HP:0000107', 'HP:0004904']);
    expect(s.excluded.map((p) => p.id)).toEqual(['HP:0000365']);
  });

  it('dedupes a repeated term within one individual (present wins over excluded)', () => {
    const s = summarizePhenotypes([
      f('HP:0000107', 'Renal cyst'),
      f('HP:0000107', 'Renal cyst', true),
    ]);
    expect(s.presentCount).toBe(1);
    expect(s.present).toHaveLength(1);
    expect(s.excluded).toHaveLength(0);
  });

  it('handles empty / missing input', () => {
    expect(summarizePhenotypes([]).presentCount).toBe(0);
    expect(summarizePhenotypes(undefined).present).toEqual([]);
  });
});

describe('buildPhenotypeMatrix', () => {
  const individuals = [
    ind('p-1', '56', [f('HP:0000107', 'Renal cyst'), f('HP:0004904', 'MODY')]),
    ind('p-2', '288', [f('HP:0000107', 'Renal cyst'), f('HP:0000078', 'Genital', true)]),
    ind('p-3', '399', [f('HP:0000107', 'Renal cyst')]),
  ];

  it('orders rows by descending present count', () => {
    const m = buildPhenotypeMatrix(individuals);
    expect(m.rows.map((r) => r.subjectId)).toEqual(['56', '288', '399']);
    expect(m.rows[0].presentCount).toBe(2);
  });

  it('builds columns grouped by organ system, ranked by present frequency', () => {
    const m = buildPhenotypeMatrix(individuals);
    const renalCol = m.columns.find((c) => c.id === 'HP:0000107');
    expect(renalCol.organSystem).toBe('renal');
    expect(renalCol.frequency).toBe(3); // present in all three
    expect(m.columns[0].id).toBe('HP:0000107'); // most frequent first
    // each column carries an organ-system color + label
    expect(renalCol.color).toMatch(/^#/);
    expect(renalCol.organLabel).toBe('Renal');
  });

  it('encodes cell status present/excluded/not-reported', () => {
    const m = buildPhenotypeMatrix(individuals);
    expect(m.cells['p-2']['HP:0000107']).toBe('present');
    expect(m.cells['p-2']['HP:0000078']).toBe('excluded');
    expect(m.cells['p-1']['HP:0000078']).toBe('not-reported');
  });

  it('flags present+excluded conflicts and lets present win', () => {
    const m = buildPhenotypeMatrix([
      ind('p-x', 'X', [f('HP:0000107', 'Renal cyst'), f('HP:0000107', 'Renal cyst', true)]),
    ]);
    expect(m.cells['p-x']['HP:0000107']).toBe('present');
    expect(m.conflicts.has('p-x::HP:0000107')).toBe(true);
  });

  it('caps to maxTerms by frequency and reports truncation', () => {
    const many = ind(
      'p-z',
      'Z',
      Array.from({ length: 5 }, (_, i) => f(`HP:000010${i}`, `Term ${i}`))
    );
    const m = buildPhenotypeMatrix([many], { maxTerms: 2 });
    expect(m.columns).toHaveLength(2);
    expect(m.totalTerms).toBe(5);
    expect(m.shownTerms).toBe(2);
    expect(m.truncated).toBe(true);
  });

  it('returns an empty-but-valid structure for no phenotypes', () => {
    const m = buildPhenotypeMatrix([ind('p-0', '0', [])]);
    expect(m.columns).toEqual([]);
    expect(m.groups).toEqual([]);
    expect(m.truncated).toBe(false);
  });
});
