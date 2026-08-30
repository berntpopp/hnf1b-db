<template>
  <v-dialog
    :model-value="modelValue"
    max-width="680"
    :retain-focus="true"
    aria-labelledby="review-decision-dialog-title"
    @update:model-value="close"
    @after-leave="emit('closed')"
  >
    <v-card>
      <form @submit.prevent="submit">
        <v-card-title id="review-decision-dialog-title">{{ copy.title }}</v-card-title>
        <v-card-text>
          <p class="mb-3">{{ copy.description }}</p>
          <p v-if="snapshot" class="snapshot-identity mb-4">
            <strong>{{ copy.snapshotLabel }} revision {{ snapshot.id }}</strong>
            <code>{{ snapshot.content_sha256 }}</code>
          </p>

          <v-alert
            v-if="action === 'approve' && unresolvedCount !== 0"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            {{ issueStatusCopy }}
          </v-alert>

          <label class="field-label" for="decision-rationale">Decision rationale</label>
          <textarea
            id="decision-rationale"
            v-model="rationale"
            class="native-field"
            rows="5"
            maxlength="500"
            required
          />

          <fieldset v-if="action === 'approve'" class="attestations mt-4">
            <legend>Required attestations</legend>
            <label class="checkbox-label" for="attest-independent-review">
              <!-- eslint-disable-next-line vue/html-self-closing -->
              <input id="attest-independent-review" v-model="independentReview" type="checkbox" />
              I independently reviewed this exact candidate revision.
            </label>
            <label class="checkbox-label" for="attest-no-conflict">
              <!-- eslint-disable-next-line vue/html-self-closing -->
              <input id="attest-no-conflict" v-model="noUnmanagedConflict" type="checkbox" />
              I have no unmanaged conflict of interest for this decision.
            </label>
          </fieldset>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn class="dialog-action" variant="text" :disabled="submitting" @click="close(false)">
            Cancel
          </v-btn>
          <v-btn
            data-testid="decision-submit"
            class="dialog-action"
            color="primary"
            type="submit"
            :loading="submitting"
            :disabled="!canSubmit || submitting"
          >
            <template #prepend>
              <v-icon aria-hidden="true">{{ copy.icon }}</v-icon>
            </template>
            {{ copy.submitLabel }}
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
  action: {
    type: String,
    required: true,
    validator: (value) =>
      ['approve', 'request_changes', 'reopen_approved', 'publish', 'withdraw'].includes(value),
  },
  submitting: { type: Boolean, default: false },
  snapshot: { type: Object, default: null },
  unresolvedCount: { type: Number, default: null },
});

const emit = defineEmits(['update:modelValue', 'submit', 'closed']);

const rationale = ref('');
const independentReview = ref(false);
const noUnmanagedConflict = ref(false);

const ACTION_COPY = {
  approve: {
    title: 'Approve exact candidate',
    description: 'Confirm an independent review of the immutable candidate shown here.',
    snapshotLabel: 'Candidate',
    submitLabel: 'Approve candidate',
    icon: 'mdi-check-decagram-outline',
  },
  request_changes: {
    title: 'Request changes',
    description: 'Return this candidate to its owner with a recorded rationale.',
    snapshotLabel: 'Candidate',
    submitLabel: 'Request changes',
    icon: 'mdi-file-edit-outline',
  },
  reopen_approved: {
    title: 'Reopen approved review',
    description: 'Move this approved record back to changes requested with a recorded rationale.',
    snapshotLabel: 'Approved',
    submitLabel: 'Reopen review',
    icon: 'mdi-lock-open-variant-outline',
  },
  publish: {
    title: 'Publish approved revision',
    description: `Approved revision ${props.snapshot?.id ?? 'unknown'} will become public.`,
    snapshotLabel: 'Approved',
    submitLabel: 'Publish revision',
    icon: 'mdi-publish',
  },
  withdraw: {
    title: 'Withdraw from review',
    description: 'Return this candidate to draft with a recorded rationale.',
    snapshotLabel: 'Candidate',
    submitLabel: 'Withdraw review',
    icon: 'mdi-undo-variant',
  },
};

const copy = computed(() => {
  if (props.action !== 'publish') return ACTION_COPY[props.action];
  return {
    ...ACTION_COPY.publish,
    description: `Approved revision ${props.snapshot?.id ?? 'unknown'} will become public.`,
  };
});
const issueStatusCopy = computed(() => {
  if (!Number.isInteger(props.unresolvedCount)) {
    return 'Blocking issue status is unavailable. Reload before approving.';
  }
  const label = props.unresolvedCount === 1 ? 'issue remains' : 'issues remain';
  return `${props.unresolvedCount} unresolved blocking ${label}.`;
});
const canSubmit = computed(() => {
  const reasonValid = rationale.value.trim().length > 0 && rationale.value.trim().length <= 500;
  if (props.action !== 'approve') return reasonValid;
  return (
    reasonValid &&
    props.unresolvedCount === 0 &&
    independentReview.value &&
    noUnmanagedConflict.value
  );
});

function reset() {
  rationale.value = '';
  independentReview.value = false;
  noUnmanagedConflict.value = false;
}

function close(value = false) {
  emit('update:modelValue', value);
}

function submit() {
  if (!canSubmit.value) return;
  const payload = { rationale: rationale.value.trim() };
  if (props.action === 'approve') {
    Object.assign(payload, { independentReview: true, noUnmanagedConflict: true });
  }
  emit('submit', payload);
}

watch(
  () => [props.modelValue, props.action],
  ([open]) => {
    if (open) reset();
  }
);
</script>

<style scoped>
.snapshot-identity {
  display: grid;
  gap: 0.25rem;
}

.snapshot-identity code {
  overflow-wrap: anywhere;
}

.field-label,
.attestations legend {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.native-field {
  border: 1px solid rgb(var(--v-theme-on-surface));
  border-radius: 4px;
  display: block;
  min-height: 7rem;
  padding: 0.5rem;
  width: 100%;
}

.attestations {
  border: 0;
  margin: 0;
  padding: 0;
}

.checkbox-label {
  align-items: flex-start;
  display: flex;
  gap: 0.75rem;
  min-height: 44px;
  padding: 0.5rem 0;
}

.checkbox-label input {
  height: 1.25rem;
  margin-top: 0.125rem;
  width: 1.25rem;
}

.dialog-action {
  min-height: 44px;
}
</style>
