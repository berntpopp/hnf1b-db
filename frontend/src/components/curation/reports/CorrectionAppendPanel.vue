<template>
  <section aria-labelledby="correction-heading" class="correction-panel">
    <h2 id="correction-heading" class="text-h6">Append source correction</h2>
    <p>Corrections preserve the original raw source value and the full correction chain.</p>
    <label>
      Observed field
      <select v-model="selectedPath" :disabled="readonly">
        <option value="">Choose a field</option>
        <option v-for="target in targets" :key="target.jsonPointer" :value="target.jsonPointer">
          {{ target.path }}{{ target.chainValid ? '' : ' (invalid correction chain)' }}
        </option>
      </select>
    </label>
    <dl v-if="correctedTargets.length" class="active-corrections">
      <template v-for="target in correctedTargets" :key="target.jsonPointer">
        <dt>{{ target.path }} active corrected value</dt>
        <dd>
          <code>{{ JSON.stringify(target.value) }}</code>
        </dd>
      </template>
    </dl>
    <label>
      Corrected normalized value (JSON)
      <textarea v-model="postimage" rows="3" :disabled="readonly || !selected" />
    </label>
    <label>
      Correction reason
      <textarea v-model="reason" rows="2" :disabled="readonly || !selected" />
    </label>
    <p v-if="error" role="alert" class="text-error">{{ error }}</p>
    <button type="button" :disabled="readonly || !selected" @click="append">
      Append correction
    </button>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

import { correctionTargets } from '@/utils/curationAdapters';

const props = defineProps({
  observation: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
  corrections: { type: Array, default: () => [] },
});
const emit = defineEmits(['append']);
const selectedPath = ref('');
const postimage = ref('');
const reason = ref('');
const error = ref('');
const targets = computed(() => correctionTargets(props.observation, props.corrections));
const correctedTargets = computed(() =>
  targets.value.filter((target) => target.supersedesCorrectionId)
);
const selected = computed(() =>
  targets.value.find((target) => target.jsonPointer === selectedPath.value)
);

watch(selected, (target) => {
  postimage.value = target ? JSON.stringify(target.value, null, 2) : '';
  error.value = '';
});

function append() {
  if (!selected.value?.chainValid) {
    error.value = 'The correction chain is inconsistent and cannot be extended.';
    return;
  }
  if (reason.value.trim().length < 5) {
    error.value = 'A correction reason of at least 5 characters is required.';
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(postimage.value);
  } catch {
    error.value = 'Corrected value must be valid JSON.';
    return;
  }
  error.value = '';
  emit('append', {
    jsonPointer: selected.value.jsonPointer,
    preimage: selected.value.value,
    postimage: parsed,
    reason: reason.value.trim(),
    supersedesCorrectionId: selected.value.supersedesCorrectionId,
  });
}
</script>

<style scoped>
.correction-panel,
.correction-panel label {
  display: grid;
  gap: 8px;
}

.correction-panel {
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
}

.active-corrections dd {
  margin: 0 0 8px;
}

select,
textarea,
button {
  min-height: 44px;
  padding: 8px;
}
</style>
