<!-- src/components/curation/TimeElementPicker.vue -->
<!--
  Reusable GA4GH TimeElement editor (curation console design spec §3.5;
  plan Task 8). AgeSection.vue wires two instances of this component: one
  for `diseases[].onset` (AgeOnset), one for `subject.timeAtLastEncounter`
  (AgeReported).

  Three modes, matching the corpus's actual usage (verified live via psql
  against hnf1b_phenopackets on 2026-07-31 -- not assumed):
    - congenital:  a fixed OntologyClass, HP:0003577 "Congenital onset" --
      by far the corpus's dominant onset value (594/864 onset records; 46 of
      timeAtLastEncounter's ontologyClass records use the identical shape).
    - age:         an ISO-8601 duration (e.g. "P5Y3M"), entered as separate
      Years/Months/Days number fields and assembled into the duration
      string. Not built from ageParser.js's parseAge/formatAge: those
      collapse a duration to a single lossy float (or format one for
      display), which can't round-trip back into three editable number
      fields -- a different problem, not a duplicate of the same one.
    - gestational: {weeks, days} for a fetal case. 0 corpus records use this
      today -- the curation console plan's Task 9 (owned separately) fixes
      the READERS for this shape, so what this component WRITES must match
      what Task 9 expects to read: the standard GA4GH
      TimeElement.gestationalAge shape, {weeks: number, days: number}.

  ── Canonical write shape (read before touching) ────────────────────────
  This component always EMITS the GA4GH-conformant, nested representation:
    congenital:  {ontologyClass: {id, label}}
    age:         {age: {iso8601duration}}
    gestational: {gestationalAge: {weeks, days}}
  It READS leniently -- both this nested `age` shape and the corpus's flat
  `{iso8601duration}` convention (via utils/age.js's readTimeElementAge) --
  so it can be bound directly to either storage field without the caller
  pre-converting anything on the way IN.

  `subject.timeAtLastEncounter` deliberately does NOT use the nested `age`
  wrapper on the way OUT (ADR 0003 D4: 664 legacy records are flat, 0 are
  nested) -- AgeSection.vue, not this component, does that flattening, and
  only for that one field. This component has no idea which field it is
  bound to and must stay that way to be genuinely reusable for both.

  Selecting a mode and then clicking it again deselects it (Vuetify
  v-btn-toggle without `mandatory`), which maps to "not yet curated" (null)
  -- distinct from a field the curator has explicitly cleared to some other
  "no answer" value, of which TimeElement (unlike the vocabularies) has none.
-->
<template>
  <div class="time-element-picker">
    <v-btn-toggle
      :model-value="mode"
      density="comfortable"
      variant="outlined"
      divided
      :aria-label="`${label} mode`"
      @update:model-value="onModeChange"
    >
      <v-btn value="congenital">Congenital</v-btn>
      <v-btn value="age">Age</v-btn>
      <v-btn value="gestational">Gestational</v-btn>
    </v-btn-toggle>

    <div v-if="mode === 'congenital'" class="text-body-2 text-medium-emphasis mt-2">
      {{ CONGENITAL_ONSET.id }} {{ CONGENITAL_ONSET.label }}
    </div>

    <v-row v-else-if="mode === 'age'" class="mt-1" dense>
      <v-col cols="4">
        <v-text-field
          :model-value="years"
          type="number"
          min="0"
          :label="`${label} — years`"
          @update:model-value="onYearsChange"
        />
      </v-col>
      <v-col cols="4">
        <v-text-field
          :model-value="months"
          type="number"
          min="0"
          max="11"
          :label="`${label} — months`"
          @update:model-value="onMonthsChange"
        />
      </v-col>
      <v-col cols="4">
        <v-text-field
          :model-value="days"
          type="number"
          min="0"
          max="30"
          :label="`${label} — days`"
          @update:model-value="onDaysChange"
        />
      </v-col>
    </v-row>

    <v-row v-else-if="mode === 'gestational'" class="mt-1" dense>
      <v-col cols="6">
        <v-text-field
          :model-value="weeks"
          type="number"
          min="0"
          max="45"
          :label="`${label} — gestational weeks`"
          @update:model-value="onWeeksChange"
        />
      </v-col>
      <v-col cols="6">
        <v-text-field
          :model-value="gestDays"
          type="number"
          min="0"
          max="6"
          :label="`${label} — gestational days`"
          @update:model-value="onGestDaysChange"
        />
      </v-col>
    </v-row>

    <p v-else class="text-body-2 text-medium-emphasis mt-2 mb-0">Not yet curated.</p>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { readTimeElementAge } from '@/utils/age';

const CONGENITAL_ONSET = { id: 'HP:0003577', label: 'Congenital onset' };

const props = defineProps({
  // A GA4GH TimeElement (see the module doc for the shapes read/written), or
  // null when nothing has been curated yet.
  modelValue: { type: Object, default: null },
  // Distinguishes the two instances AgeSection.vue mounts ("Onset" /
  // "Age reported") in field labels and the mode toggle's aria-label.
  label: { type: String, default: 'Time' },
});
const emit = defineEmits(['update:modelValue']);

const mode = ref(null);
const years = ref(null);
const months = ref(null);
const days = ref(null);
const weeks = ref(null);
const gestDays = ref(null);

// Mirrors the regex already duplicated across DiseasesCard.vue,
// MeasurementsCard.vue, PhenotypicFeaturesCard.vue and SubjectCard.vue's own
// local `formatISO8601Duration` -- none of those parse INTO editable
// components (they only format FOR display), so there was no existing
// "build" counterpart to reuse.
const ISO8601_DURATION_RE = /^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?$/;

function parseIso8601(duration) {
  const m = duration ? ISO8601_DURATION_RE.exec(duration) : null;
  if (!m) return { years: null, months: null, days: null };
  return {
    years: m[1] ? Number(m[1]) : null,
    months: m[2] ? Number(m[2]) : null,
    days: m[3] ? Number(m[3]) : null,
  };
}

/** Omits zero/blank units, matching the corpus's own style ("P16Y", never "P16Y0M0D"). */
function buildIso8601(y, m, d) {
  const yy = Number(y) || 0;
  const mm = Number(m) || 0;
  const dd = Number(d) || 0;
  if (!yy && !mm && !dd) return null;
  return `P${yy ? `${yy}Y` : ''}${mm ? `${mm}M` : ''}${dd ? `${dd}D` : ''}`;
}

function seedFromModelValue(value) {
  if (value?.ontologyClass?.id === CONGENITAL_ONSET.id) {
    mode.value = 'congenital';
    return;
  }
  if (value?.gestationalAge) {
    mode.value = 'gestational';
    weeks.value = value.gestationalAge.weeks ?? null;
    gestDays.value = value.gestationalAge.days ?? null;
    return;
  }
  const duration = readTimeElementAge(value);
  if (duration) {
    mode.value = 'age';
    const parsed = parseIso8601(duration);
    years.value = parsed.years;
    months.value = parsed.months;
    days.value = parsed.days;
    return;
  }
  // Anything else -- including a legacy generic `{ontologyClass: {id:
  // 'HP:0003674', label: 'Onset'}}` placeholder (71 corpus records, neither
  // congenital nor a duration) -- has no representation among this plan's
  // three documented modes. The underlying value is left untouched (this
  // function only ever READS `value`; a mutator only ever fires in direct
  // response to a curator interacting with a mode/field control below), but
  // the picker itself shows as "not yet curated" for it. A known, documented
  // gap, not a silent data loss: nothing here rewrites that record unless
  // the curator explicitly picks a mode.
  mode.value = null;
}

watch(() => props.modelValue, seedFromModelValue, { immediate: true });

function onModeChange(next) {
  mode.value = next ?? null;
  if (mode.value === 'congenital') {
    emit('update:modelValue', { ontologyClass: { ...CONGENITAL_ONSET } });
  } else if (mode.value === 'age') {
    years.value = null;
    months.value = null;
    days.value = null;
    emit('update:modelValue', null);
  } else if (mode.value === 'gestational') {
    weeks.value = null;
    gestDays.value = null;
    emit('update:modelValue', null);
  } else {
    emit('update:modelValue', null);
  }
}

function emitAge() {
  const duration = buildIso8601(years.value, months.value, days.value);
  emit('update:modelValue', duration ? { age: { iso8601duration: duration } } : null);
}

function onYearsChange(v) {
  years.value = v;
  emitAge();
}
function onMonthsChange(v) {
  months.value = v;
  emitAge();
}
function onDaysChange(v) {
  days.value = v;
  emitAge();
}

function emitGestational() {
  const hasWeeks = weeks.value !== null && weeks.value !== '';
  const hasDays = gestDays.value !== null && gestDays.value !== '';
  if (!hasWeeks && !hasDays) {
    emit('update:modelValue', null);
    return;
  }
  emit('update:modelValue', {
    gestationalAge: {
      weeks: hasWeeks ? Number(weeks.value) : 0,
      days: hasDays ? Number(gestDays.value) : 0,
    },
  });
}

function onWeeksChange(v) {
  weeks.value = v;
  emitGestational();
}
function onGestDaysChange(v) {
  gestDays.value = v;
  emitGestational();
}
</script>
