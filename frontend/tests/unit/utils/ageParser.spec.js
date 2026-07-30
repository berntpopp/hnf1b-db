/**
 * Unit tests for utils/ageParser, focused on the onset-id-to-age map fixed
 * in Task 6 of docs/superpowers/plans/2026-07-30-ontology-data-quality.md.
 *
 * `'HP:0034199': 0.08, // Neonatal onset (approx 1 month)` was wrong three
 * ways at once: HP:0034199 is "Late first trimester onset" (not neonatal),
 * the comment itself disagreed with the id it annotated, and the backend
 * migration efa98cccfa51 eliminated that id from the corpus entirely, so no
 * stored onset value could ever reach this map again anyway.
 */
import { describe, it, expect } from 'vitest';
import { parseAge, formatAge, onsetClassToAge } from '@/utils/ageParser';

describe('onsetClassToAge', () => {
  it('no longer maps the removed, wrong HP:0034199 entry', () => {
    expect(onsetClassToAge('HP:0034199')).toBeNull();
  });

  it('maps HP:0003577 (Congenital onset) to birth, age 0', () => {
    expect(onsetClassToAge('HP:0003577')).toBe(0);
  });

  it('returns null for an unmapped id rather than a guessed value', () => {
    expect(onsetClassToAge('HP:9999999')).toBeNull();
    expect(onsetClassToAge(undefined)).toBeNull();
  });

  it('every mapped onset id resolves to a non-decreasing age as onset gets later', () => {
    // Ontology meaning, coarse-grained: earlier-named onset stages must not
    // map to a strictly later age than a later-named stage. This is the
    // regression fence the task asked for -- it would have caught
    // HP:0034199 mapping "Neonatal" (per its own comment) to 0.08 while
    // HP:0003623 (the real Neonatal onset id) also maps to 0, an internal
    // contradiction between two entries claiming the same clinical stage.
    const orderedStages = [
      'HP:0003577', // Congenital onset
      'HP:0003623', // Neonatal onset
      'HP:0003593', // Infantile onset
      'HP:0410280', // Pediatric onset
      'HP:0003621', // Juvenile onset
      'HP:0011462', // Young adult onset
      'HP:0003581', // Adult onset
      'HP:0003596', // Middle age onset
      'HP:0003584', // Late onset
    ];
    const ages = orderedStages.map((id) => onsetClassToAge(id));
    expect(ages.every((age) => age !== null)).toBe(true);
    for (let i = 1; i < ages.length; i += 1) {
      expect(ages[i]).toBeGreaterThanOrEqual(ages[i - 1]);
    }
  });

  it('congenital and neonatal onset are both birth-adjacent (age 0)', () => {
    // The removed entry's own comment claimed "Neonatal onset (approx 1
    // month)" for HP:0034199 while HP:0003623 (the actual Neonatal onset
    // id, "0-4 weeks") already maps to 0 -- two entries could not both be
    // right about what "neonatal" means. Only one Neonatal-onset id exists
    // in the map now.
    expect(onsetClassToAge('HP:0003577')).toBe(0);
    expect(onsetClassToAge('HP:0003623')).toBe(0);
  });
});

describe('parseAge', () => {
  it('parses a full ISO8601 duration', () => {
    expect(parseAge('P5Y6M')).toBeCloseTo(5.5, 2);
  });

  it('returns null for a falsy input', () => {
    expect(parseAge(null)).toBeNull();
    expect(parseAge('')).toBeNull();
  });
});

describe('formatAge', () => {
  it('formats birth as "Birth"', () => {
    expect(formatAge(0)).toBe('Birth');
  });

  it('formats a whole number of years without decimals', () => {
    expect(formatAge(5)).toBe('5 years');
  });

  it('returns "Unknown" for a missing age', () => {
    expect(formatAge(null)).toBe('Unknown');
    expect(formatAge(undefined)).toBe('Unknown');
  });
});
