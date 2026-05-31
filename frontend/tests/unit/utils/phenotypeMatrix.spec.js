/**
 * Unit tests for phenotype summarization + matrix building.
 *
 * Tests cover: present-only counting, present/excluded split, per-individual
 * dedupe with present-wins precedence, and (in the next task) matrix grouping.
 */
import { describe, it, expect } from 'vitest';
import { summarizePhenotypes } from '@/utils/phenotypeMatrix';

const f = (id, label, excluded = false) => ({ type: { id, label }, excluded });

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
