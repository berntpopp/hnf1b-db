/**
 * Read the age at last encounter from a GA4GH subject.
 *
 * Accepts both shapes on purpose:
 *  - `{age: {iso8601duration}}`  GA4GH-conformant; 0 records use it today
 *  - `{iso8601duration}`         the corpus convention; 664 records
 *
 * The corpus is not migrated (see docs/adr/0003-ga4gh-conformance-debt.md),
 * so both must be read until that debt is paid. Accepting both now means the
 * migration needs no second frontend change.
 *
 * @param {object|null|undefined} subject GA4GH Individual
 * @returns {string|null} ISO-8601 duration, or null when no age is recorded
 */
export function readEncounterAge(subject) {
  const t = subject?.timeAtLastEncounter;
  if (!t) return null;
  return t.age?.iso8601duration ?? t.iso8601duration ?? null;
}
