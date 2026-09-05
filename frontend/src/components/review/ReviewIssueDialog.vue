<template>
  <v-dialog
    :model-value="modelValue"
    max-width="640"
    aria-labelledby="review-issue-dialog-title"
    @update:model-value="close"
  >
    <v-card>
      <form @submit.prevent="submit">
        <v-card-title id="review-issue-dialog-title">{{ title }}</v-card-title>
        <v-card-text>
          <label v-if="mode === 'resolve'" class="field-label" for="issue-disposition">
            Disposition
          </label>
          <select
            v-if="mode === 'resolve'"
            id="issue-disposition"
            v-model="disposition"
            class="native-field"
            required
          >
            <option value="">Select a disposition</option>
            <option v-for="option in dispositions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>

          <label class="field-label mt-3" for="issue-text">{{ textLabel }}</label>
          <textarea
            id="issue-text"
            v-model="text"
            class="native-field"
            rows="5"
            :maxlength="textLimit"
            required
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn
            data-testid="issue-cancel"
            variant="text"
            :disabled="submitting"
            @click="close(false)"
          >
            Cancel
          </v-btn>
          <v-btn
            data-testid="issue-submit"
            color="primary"
            type="submit"
            :loading="submitting"
            :disabled="!canSubmit || submitting"
          >
            {{ submitLabel }}
          </v-btn>
        </v-card-actions>
      </form>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: {
    type: String,
    required: true,
    validator: (value) => ['create', 'resolve', 'reopen'].includes(value),
  },
  submitting: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'submit']);

const dispositions = [
  { value: 'addressed', label: 'Addressed' },
  { value: 'accepted_with_rationale', label: 'Accepted with rationale' },
  { value: 'retracted', label: 'Retracted' },
  { value: 'superseded', label: 'Superseded' },
];

const disposition = ref('');
const text = ref('');

const title = computed(
  () =>
    ({
      create: 'Create blocking issue',
      resolve: 'Resolve blocking issue',
      reopen: 'Reopen blocking issue',
    })[props.mode]
);
const textLabel = computed(() => (props.mode === 'create' ? 'Issue' : 'Rationale'));
const submitLabel = computed(
  () => ({ create: 'Create issue', resolve: 'Resolve issue', reopen: 'Reopen issue' })[props.mode]
);
const textLimit = computed(() => (props.mode === 'create' ? 10_000 : 500));
const canSubmit = computed(
  () =>
    text.value.trim().length > 0 &&
    text.value.trim().length <= textLimit.value &&
    (props.mode !== 'resolve' || disposition.value !== '')
);

function reset() {
  disposition.value = '';
  text.value = '';
}

function close(value = false) {
  emit('update:modelValue', value);
}

function submit() {
  if (!canSubmit.value) return;
  if (props.mode === 'create') emit('submit', { bodyMarkdown: text.value.trim() });
  else if (props.mode === 'resolve') {
    emit('submit', { disposition: disposition.value, rationale: text.value.trim() });
  } else emit('submit', { rationale: text.value.trim() });
}

watch(
  () => [props.modelValue, props.mode],
  ([open]) => {
    if (open) reset();
  }
);
</script>

<style scoped>
.field-label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.native-field {
  border: 1px solid rgb(var(--v-theme-on-surface));
  border-radius: 4px;
  display: block;
  padding: 0.5rem;
  width: 100%;
}
</style>
