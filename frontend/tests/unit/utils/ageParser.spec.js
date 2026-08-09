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
import { parseAge, formatAge, onsetClassToAge, getOrganSystem } from '@/utils/ageParser';

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

describe('getOrganSystem', () => {
  /**
   * C2 (docs/superpowers/plans/2026-07-30-ontology-data-quality.md): migration
   * ca9950e rewrote all 460 stored occurrences of HP:0033133 to HP:0033132
   * ("Renal cortical hypoechogeneity" -> "Renal cortical hyperechogenicity",
   * the correct, characteristic HNF1B ultrasound finding), but this
   * classifier still only keyed on the retired 33133 literal, so every
   * corrected feature fell through to 'other' instead of 'renal'.
   */
  it('classifies the current corpus id HP:0033132 (Renal cortical hyperechogenicity) as renal', () => {
    expect(getOrganSystem('HP:0033132')).toBe('renal');
  });

  it('still classifies the retired id HP:0033133 as renal, for historical documents', () => {
    expect(getOrganSystem('HP:0033133')).toBe('renal');
  });

  /**
   * Reviewer-flagged overlap: the renal numeric range (77-140) previously
   * ran before the genital check, and fully contained the genital range
   * (78-80), so the genital branch could never fire for those ids --
   * getOrganSystem('HP:0000078') returned 'renal' instead of 'genital'.
   * Confirmed by executing this module directly before fixing the branch
   * order (commit be491ca).
   *
   * Reordering the genital check ahead of renal, on its own, introduced a
   * second, independent regression on HP:0000079 ("Abnormality of the
   * urinary system", 329 stored occurrences, one of the six
   * laterality-policy terms): it sits numerically between the two genuinely
   * genital ids 78 and 80, so the naive `78..80` range swept it in as
   * 'genital' too, flipping it from its correct pre-existing 'renal'
   * classification. Caught in review after be491ca landed and fixed by
   * carving 79 out of the genital range explicitly. These four assertions
   * pin every id on that boundary so a future edit to either range cannot
   * silently repeat either mistake.
   */
  it('classifies HP:0000078 (Abnormality of the genital system) as genital', () => {
    expect(getOrganSystem('HP:0000078')).toBe('genital');
  });

  it('classifies HP:0000079 (Abnormality of the urinary system) as renal, not genital', () => {
    expect(getOrganSystem('HP:0000079')).toBe('renal');
  });

  it('classifies HP:0000080 (Abnormality of reproductive system physiology) as genital', () => {
    expect(getOrganSystem('HP:0000080')).toBe('genital');
  });

  it('still classifies HP:0000077 (Abnormality of the kidney) as renal', () => {
    expect(getOrganSystem('HP:0000077')).toBe('renal');
  });

  it('classifies a genital id in the second range (HP:0000811-815) as genital', () => {
    expect(getOrganSystem('HP:0000811')).toBe('genital');
  });

  it('returns other for a falsy or non-HPO id', () => {
    expect(getOrganSystem(null)).toBe('other');
    expect(getOrganSystem('ORPHA:2260')).toBe('other');
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
