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
import {
  readEncounterAge,
  readTimeElementAge,
  readTimeElementGestationalAge,
  readEncounterGestationalAge,
  formatGestationalAge,
} from '@/utils/age';

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

/**
 * Curation console Task 9 (design spec §3.5, plan Task 9): rev 2 of the
 * curation spec specified AgeSection.vue's WRITE of the
 * `{gestationalAge: {weeks, days}}` TimeElement variant but forgot the read
 * side, so a fetus saved via the console displayed "N/A" everywhere. These
 * pin the round-trip: the exact shape AgeSection.vue's writer emits
 * (`timeAtLastEncounter: {gestationalAge: {weeks, days}}`, written flat/
 * top-level -- see AgeSection.vue's module doc) must read back as a
 * non-null, rendered value.
 */
describe('readTimeElementGestationalAge', () => {
  it('reads a well-formed {weeks, days} gestational age', () => {
    expect(readTimeElementGestationalAge({ gestationalAge: { weeks: 32, days: 3 } })).toEqual({
      weeks: 32,
      days: 3,
    });
  });

  it('reads a gestational age with days omitted', () => {
    expect(readTimeElementGestationalAge({ gestationalAge: { weeks: 32 } })).toEqual({
      weeks: 32,
    });
  });

  it('returns null for a duration-only TimeElement (no gestationalAge to read)', () => {
    expect(readTimeElementGestationalAge({ iso8601duration: 'P41Y' })).toBeNull();
  });

  it('returns null for a congenital/ontologyClass TimeElement', () => {
    expect(readTimeElementGestationalAge({ ontologyClass: { id: 'HP:0003577' } })).toBeNull();
  });

  it('returns null when gestationalAge.weeks is missing or not a number', () => {
    expect(readTimeElementGestationalAge({ gestationalAge: {} })).toBeNull();
    expect(readTimeElementGestationalAge({ gestationalAge: { weeks: '32' } })).toBeNull();
  });

  it('returns null for null/undefined', () => {
    expect(readTimeElementGestationalAge(null)).toBeNull();
    expect(readTimeElementGestationalAge(undefined)).toBeNull();
  });
});

describe('readEncounterGestationalAge', () => {
  it('reads gestationalAge off subject.timeAtLastEncounter (the shape AgeSection.vue writes)', () => {
    const subject = { timeAtLastEncounter: { gestationalAge: { weeks: 32, days: 3 } } };
    expect(readEncounterGestationalAge(subject)).toEqual({ weeks: 32, days: 3 });
  });

  it('returns null when there is no timeAtLastEncounter', () => {
    expect(readEncounterGestationalAge({})).toBeNull();
    expect(readEncounterGestationalAge(null)).toBeNull();
    expect(readEncounterGestationalAge(undefined)).toBeNull();
  });
});

describe('formatGestationalAge', () => {
  it('formats weeks and days', () => {
    expect(formatGestationalAge({ weeks: 32, days: 3 })).toBe('32 weeks 3 days');
  });

  it('formats a whole-week value (days 0) without a days segment', () => {
    expect(formatGestationalAge({ weeks: 32, days: 0 })).toBe('32 weeks');
  });

  it('formats a whole-week value with days omitted entirely', () => {
    expect(formatGestationalAge({ weeks: 32 })).toBe('32 weeks');
  });

  it('singularizes "1 week" and "1 day"', () => {
    expect(formatGestationalAge({ weeks: 1, days: 1 })).toBe('1 week 1 day');
  });

  it('returns null for a falsy or malformed input', () => {
    expect(formatGestationalAge(null)).toBeNull();
    expect(formatGestationalAge(undefined)).toBeNull();
    expect(formatGestationalAge({})).toBeNull();
  });
});
