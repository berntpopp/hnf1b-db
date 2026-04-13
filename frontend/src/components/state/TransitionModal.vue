<template>
  <v-dialog
    :model-value="modelValue"
    max-width="500"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title>Transition to {{ toState.replace('_', ' ') }}</v-card-title>
      <v-card-text>
        <v-textarea v-model="reason" label="Reason (required)" rows="3" autofocus />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="close">Cancel</v-btn>
        <v-btn data-testid="confirm-btn" color="primary" :disabled="!canConfirm" @click="confirm">
          Confirm
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  toState: { type: String, required: true },
});
const emit = defineEmits(['update:modelValue', 'confirm']);

const reason = ref('');
const canConfirm = computed(() => reason.value.trim().length > 0);

watch(
  () => props.modelValue,
  (open) => {
    if (!open) reason.value = '';
  }
);

const confirm = () => emit('confirm', { reason: reason.value.trim() });
const close = () => emit('update:modelValue', false);

// Expose reactive state so unit tests can verify logic without traversing
// teleported overlay DOM (v-dialog teleports to document.body).
defineExpose({ reason, canConfirm, confirm });
</script>
