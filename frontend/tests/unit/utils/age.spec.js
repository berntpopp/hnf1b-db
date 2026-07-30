/**
 * Unit tests for src/utils/age.js.
 *
 * `readTimeElementAge` (curation console plan Task 8) is the lower-level
 * helper `readEncounterAge` was refactored to delegate to, so
 * TimeElementPicker.vue can read an ISO-8601 duration off a raw GA4GH
 * TimeElement (not just a `subject`) with the same "accept both shapes"
 * leniency documented at the top of this module.
 */
import { describe, it, expect } from 'vitest';
import { readEncounterAge, readTimeElementAge } from '@/utils/age';

describe('readTimeElementAge', () => {
  it('reads the flat corpus convention {iso8601duration}', () => {
    expect(readTimeElementAge({ iso8601duration: 'P41Y' })).toBe('P41Y');
  });

  it('reads the GA4GH-conformant nested {age: {iso8601duration}}', () => {
    expect(readTimeElementAge({ age: { iso8601duration: 'P5Y3M' } })).toBe('P5Y3M');
  });

  it('prefers the nested shape when (hypothetically) both are present', () => {
    expect(readTimeElementAge({ age: { iso8601duration: 'P5Y' }, iso8601duration: 'P1Y' })).toBe(
      'P5Y'
    );
  });

  it('returns null for a congenital/ontologyClass TimeElement (no duration to read)', () => {
    expect(readTimeElementAge({ ontologyClass: { id: 'HP:0003577' } })).toBeNull();
  });

  it('returns null for a gestational TimeElement (no duration to read)', () => {
    expect(readTimeElementAge({ gestationalAge: { weeks: 32, days: 3 } })).toBeNull();
  });

  it('returns null for null/undefined', () => {
    expect(readTimeElementAge(null)).toBeNull();
    expect(readTimeElementAge(undefined)).toBeNull();
  });
});

describe('readEncounterAge (unchanged behavior, now delegates to readTimeElementAge)', () => {
  it('reads the flat shape off subject.timeAtLastEncounter', () => {
    expect(readEncounterAge({ timeAtLastEncounter: { iso8601duration: 'P41Y' } })).toBe('P41Y');
  });

  it('reads the nested shape off subject.timeAtLastEncounter', () => {
    expect(readEncounterAge({ timeAtLastEncounter: { age: { iso8601duration: 'P5Y' } } })).toBe(
      'P5Y'
    );
  });

  it('returns null when there is no timeAtLastEncounter', () => {
    expect(readEncounterAge({})).toBeNull();
    expect(readEncounterAge(null)).toBeNull();
    expect(readEncounterAge(undefined)).toBeNull();
  });
});
