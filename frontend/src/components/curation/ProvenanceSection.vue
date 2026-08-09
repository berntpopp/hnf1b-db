<!-- src/components/curation/ProvenanceSection.vue -->
<!--
  Provenance & notes section content for the curation console (curation
  console design spec §3.6; plan Task 8). Renders inside
  PhenopacketCreateEdit.vue's <CurationSection id="provenance">, which
  already provides the section chrome.

  ── THE non-negotiable (read before touching) ───────────────────────────
  `curatedBy` and `curatedAt` are DISPLAY ONLY here -- plain text, never a
  bound input control. There is no `update:curatedBy` / `update:curatedAt`
  event anywhere in this component's `defineEmits` list below (three events
  only, for the three free-text fields): it is structurally impossible to
  wire an input to either of those two paths through this component.

  `curatedBy` is stamped by the PARENT (PhenopacketCreateEdit.vue's
  `stampCuration()`) from the authenticated session's display name;
  `curatedAt` from the client clock at submit time (the backend does not
  stamp either field server-side -- verified by grepping
  backend/app/phenopackets/ for `curated_at`/`curated_by`: the only match is
  the JSON-schema type declaration in schema_validator.py, no CRUD/router
  write path sets it). No email address can reach `hnf1bCuration.curatedBy`
  or `metaData.reviewer` through this UI by any path -- the sheet's
  `ReviewBy` column holds institutional emails (ADR 0003) and this console
  never offers a field for it.

  See tests/unit/components/ProvenanceSection.spec.js's "no reviewer input
  control" describe block for the structural proof (this component's
  compiled `emits` array + a DOM enumeration of every editable control it
  renders), and tests/unit/views/PhenopacketCreateEdit.spec.js for the
  companion full-form test that scans the actual built submission payload
  for stray '@' characters. This is one of the programme's three global
  non-negotiable tests -- do not weaken it.
-->
<template>
  <div class="provenance-section">
    <div class="provenance-section__stamp text-body-2 text-medium-emphasis mb-4">
      <div><strong>Reviewed by:</strong> {{ curatedBy || 'Not yet saved' }}</div>
      <div><strong>Review date:</strong> {{ formattedCuratedAt }}</div>
    </div>

    <v-textarea
      :model-value="caseComment"
      label="Comment"
      rows="2"
      auto-grow
      @update:model-value="(value) => $emit('update:caseComment', value)"
    />

    <v-textarea
      :model-value="problematic"
      label="Problematic"
      rows="2"
      auto-grow
      class="mt-2"
      @update:model-value="(value) => $emit('update:problematic', value)"
    />

    <v-textarea
      :model-value="duplicateCheck"
      label="Duplicate check"
      rows="2"
      auto-grow
      class="mt-2"
      @update:model-value="(value) => $emit('update:duplicateCheck', value)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  caseComment: { type: String, default: null },
  problematic: { type: String, default: null },
  duplicateCheck: { type: String, default: null },
  // Read-only display props -- see the module doc above. Neither is ever
  // written by this component.
  curatedBy: { type: String, default: null },
  curatedAt: { type: String, default: null },
});

defineEmits(['update:caseComment', 'update:problematic', 'update:duplicateCheck']);

const formattedCuratedAt = computed(() => {
  if (!props.curatedAt) return 'Not yet saved';
  const parsed = new Date(props.curatedAt);
  return Number.isNaN(parsed.getTime()) ? props.curatedAt : parsed.toLocaleString();
});
</script>
