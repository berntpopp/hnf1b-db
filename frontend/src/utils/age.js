/**
 * Read an ISO-8601 age duration off a raw GA4GH TimeElement.
 *
 * Accepts both shapes on purpose:
 *  - `{age: {iso8601duration}}`  GA4GH-conformant nested wrapper
 *  - `{iso8601duration}`         the corpus's flat convention
 *
 * Returns `null` for a TimeElement that isn't the "age" variant at all (e.g.
 * `{ontologyClass: {...}}` for congenital onset, or `{gestationalAge: {...}}`)
 * -- there is no duration to read off those, by design, not a bug.
 *
 * Curation console Task 8: this is the lower-level helper readEncounterAge
 * delegates to (see below), and the same one TimeElementPicker.vue reads
 * from -- it is bound to BOTH `diseases[].onset` (which stores the nested
 * shape) and `subject.timeAtLastEncounter` (which stores the flat shape,
 * ADR 0003 D4) and needs one lenient reader that works for either without
 * knowing which field it's looking at. See AgeSection.vue's module doc for
 * which shape each field actually WRITES on the way out.
 *
 * @param {object|null|undefined} timeElement a GA4GH TimeElement
 * @returns {string|null} ISO-8601 duration, or null when this TimeElement
 *   carries no age duration
 */
export function readTimeElementAge(timeElement) {
  if (!timeElement) return null;
  return timeElement.age?.iso8601duration ?? timeElement.iso8601duration ?? null;
}

/**
 * Read the age at last encounter from a GA4GH subject.
 *
 * The corpus is not migrated (see docs/adr/0003-ga4gh-conformance-debt.md),
 * so both TimeElement shapes readTimeElementAge accepts must be read until
 * that debt is paid. Accepting both now means the migration needs no second
 * frontend change.
 *
 * @param {object|null|undefined} subject GA4GH Individual
 * @returns {string|null} ISO-8601 duration, or null when no age is recorded
 */
export function readEncounterAge(subject) {
  return readTimeElementAge(subject?.timeAtLastEncounter);
}
