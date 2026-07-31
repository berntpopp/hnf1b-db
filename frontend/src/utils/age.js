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

/**
 * Read a `{weeks, days}` gestational age off a raw GA4GH TimeElement.
 *
 * Curation console Task 9 (design spec §3.5, plan Task 9): rev 2 of the
 * curation spec specified AgeSection.vue's WRITE of the standard GA4GH
 * `{gestationalAge: {weeks, days}}` TimeElement variant but forgot the
 * read side -- `readTimeElementAge` above explicitly (and correctly, for
 * its own contract) returns null for this variant, so a fetus saved via
 * the console displayed "N/A" everywhere. This is the lower-level reader
 * for that shape, parallel to `readTimeElementAge`.
 *
 * @param {object|null|undefined} timeElement a GA4GH TimeElement
 * @returns {{weeks: number, days: number}|null} the gestational age, or
 *   null when this TimeElement carries no (well-formed) gestational age
 */
export function readTimeElementGestationalAge(timeElement) {
  const gestationalAge = timeElement?.gestationalAge;
  if (!gestationalAge || typeof gestationalAge.weeks !== 'number') return null;
  return gestationalAge;
}

/**
 * Read the gestational age at last encounter from a GA4GH subject.
 *
 * Parallel to `readEncounterAge`, for `subject.timeAtLastEncounter`'s
 * gestational-age variant (see `readTimeElementGestationalAge` above).
 *
 * @param {object|null|undefined} subject GA4GH Individual
 * @returns {{weeks: number, days: number}|null} the gestational age, or
 *   null when none is recorded
 */
export function readEncounterGestationalAge(subject) {
  return readTimeElementGestationalAge(subject?.timeAtLastEncounter);
}

/**
 * Format a `{weeks, days}` gestational age as a human-readable string, e.g.
 * "32 weeks 3 days" or "32 weeks" when days is 0/absent.
 *
 * Centralized here (curation console Task 9) so SubjectCard.vue and
 * PagePhenopacket.vue share one formatting implementation instead of each
 * growing its own ad-hoc gestational-age reader.
 *
 * @param {{weeks: number, days?: number}|null|undefined} gestationalAge
 * @returns {string|null} formatted string, or null for a falsy input
 */
export function formatGestationalAge(gestationalAge) {
  if (!gestationalAge || typeof gestationalAge.weeks !== 'number') return null;
  const { weeks } = gestationalAge;
  const days = typeof gestationalAge.days === 'number' ? gestationalAge.days : 0;

  const weekPart = `${weeks} week${weeks === 1 ? '' : 's'}`;
  if (days === 0) return weekPart;
  return `${weekPart} ${days} day${days === 1 ? '' : 's'}`;
}
