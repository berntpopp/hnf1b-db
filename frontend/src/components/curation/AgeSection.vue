<!-- src/components/curation/AgeSection.vue -->
<!--
  Age & onset section content for the curation console (curation console
  design spec §3.5; plan Task 8). Renders inside PhenopacketCreateEdit.vue's
  <CurationSection id="age">, which already provides the section chrome --
  this component owns no card of its own, matching ClassificationSection.vue's
  convention.

  Wires two independent TimeElementPicker instances:
    - Onset               -> phenopacket.diseases[0].onset
    - Age reported         -> phenopacket.subject.timeAtLastEncounter
      (at last encounter)

  ── Corpus shapes, verified live via psql 2026-07-31 (not assumed) ─────────
  diseases[].onset (864 records):
    594 {ontologyClass: {id:'HP:0003577', label:'Congenital onset'}}
     54 {ontologyClass: {id:'HP:0003674', label:'Onset'}}   -- generic legacy
                                                                placeholder,
                                                                not one of
                                                                this task's 3
                                                                modes
    216 {age: {iso8601duration}}                             -- NESTED,
                                                                GA4GH-
                                                                conformant
      0 {gestationalAge: {...}}
  subject.timeAtLastEncounter (727 records):
    664 {iso8601duration}                                    -- FLAT
                                                                (ADR 0003 D4)
     46 {ontologyClass: {id:'HP:0003577', ...}}               -- same
                                                                top-level key
                                                                as onset
     17 {ontologyClass: {id:'HP:0003674', ...}}
      0 {gestationalAge: {...}}

  So the ONLY divergence between the two fields is the `age` (ISO-8601)
  variant: onset keeps GA4GH's nested `{age: {iso8601duration}}` wrapper;
  timeAtLastEncounter keeps its flat `{iso8601duration}` convention (ADR 0003
  D4 -- do not "fix" this, it is deliberate debt this programme does not
  pay). `ontologyClass` (congenital) and `gestationalAge` are written
  identically for both fields, so only the `age` case below needs
  converting.

  TimeElementPicker itself is intentionally ignorant of which field it is
  bound to -- it always emits the canonical nested shape; this component is
  the one place that adapts that to `timeAtLastEncounter`'s flat convention
  on the way out.

  ── The "no disease-term control" gap (documented, out of scope) ──────────
  Nothing in this form has a disease-term picker (grepped: DiseasesCard.vue,
  PagePhenopacket.vue, the migration code -- none of them offer curators a
  way to CHOOSE a disease term; the corpus's disease term is uniform, 864/864
  non-empty `diseases[0].term` entries are the identical MONDO:0007669
  "renal cysts and diabetes syndrome"). Inventing a disease-term picker is
  explicitly out of scope for this task. When a curator picks an onset and
  `diseases` is still empty, this component creates a placeholder disease
  entry defaulting `term` to that corpus-standard value rather than
  inventing a control or silently dropping the onset.
-->
<template>
  <div class="age-section">
    <div class="text-subtitle-2 text-medium-emphasis mb-2">Onset</div>
    <TimeElementPicker :model-value="onset" label="Onset" @update:model-value="onOnsetChange" />

    <div class="text-subtitle-2 text-medium-emphasis mt-6 mb-2">
      Age reported (at last encounter)
    </div>
    <TimeElementPicker
      :model-value="timeAtLastEncounter"
      label="Age reported"
      @update:model-value="onTimeAtLastEncounterChange"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue';
import TimeElementPicker from './TimeElementPicker.vue';

const props = defineProps({
  diseases: { type: Array, default: () => [] },
  timeAtLastEncounter: { type: Object, default: null },
});
const emit = defineEmits(['update:diseases', 'update:timeAtLastEncounter']);

// The corpus's sole disease term (864/864 non-empty disease entries,
// verified live via psql 2026-07-31) -- see the module doc above for why
// this component defaults to it instead of inventing a picker.
const DEFAULT_DISEASE_TERM = {
  id: 'MONDO:0007669',
  label: 'renal cysts and diabetes syndrome',
};

const onset = computed(() => props.diseases?.[0]?.onset ?? null);

function onOnsetChange(value) {
  const diseases =
    props.diseases && props.diseases.length > 0
      ? [...props.diseases]
      : [{ term: { ...DEFAULT_DISEASE_TERM } }];
  diseases[0] = { ...diseases[0], onset: value };
  emit('update:diseases', diseases);
}

function onTimeAtLastEncounterChange(value) {
  if (value?.age?.iso8601duration) {
    // ADR 0003 D4: flatten only the ISO-8601 age variant on the way out to
    // timeAtLastEncounter -- congenital/gestational fall through to the
    // plain pass-through below since the corpus already stores those
    // identically for both fields (see the module doc).
    emit('update:timeAtLastEncounter', { iso8601duration: value.age.iso8601duration });
    return;
  }
  emit('update:timeAtLastEncounter', value);
}
</script>
