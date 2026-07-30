import { describe, it, expect } from 'vitest';
import { readEncounterAge } from '@/utils/age';

describe('readEncounterAge', () => {
  it('reads the corpus shape (flat iso8601duration)', () => {
    expect(readEncounterAge({ timeAtLastEncounter: { iso8601duration: 'P9Y4M' } })).toBe('P9Y4M');
  });

  it('reads the GA4GH-conformant shape (nested under age)', () => {
    expect(readEncounterAge({ timeAtLastEncounter: { age: { iso8601duration: 'P2Y' } } })).toBe(
      'P2Y'
    );
  });

  it('returns null when no age is present', () => {
    expect(readEncounterAge({ timeAtLastEncounter: {} })).toBeNull();
    expect(readEncounterAge({})).toBeNull();
    expect(readEncounterAge(null)).toBeNull();
  });

  it('returns null for an ontologyClass-only time element', () => {
    expect(
      readEncounterAge({
        timeAtLastEncounter: { ontologyClass: { id: 'HP:0034199', label: 'Prenatal onset' } },
      })
    ).toBeNull();
  });

  it('prefers the conformant shape when both are somehow present', () => {
    expect(
      readEncounterAge({
        timeAtLastEncounter: { iso8601duration: 'P1Y', age: { iso8601duration: 'P2Y' } },
      })
    ).toBe('P2Y');
  });
});
