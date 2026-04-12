<template>
  <v-dialog
    :model-value="modelValue"
    max-width="500"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title>
        <v-icon class="mr-2">mdi-email-fast</v-icon>
        Invite User
      </v-card-title>
      <v-card-text>
        <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
          Invite sent to {{ email }}
        </v-alert>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>
        <v-form v-if="!success" ref="formRef" @submit.prevent="handleSubmit">
          <v-text-field
            v-model="email"
            label="Email address"
            type="email"
            :rules="[rules.required, rules.email]"
            density="compact"
            class="mb-3"
          />
          <v-select
            v-model="role"
            :items="['viewer', 'curator', 'admin']"
            label="Role"
            density="compact"
          />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="handleClose">
          {{ success ? 'Close' : 'Cancel' }}
        </v-btn>
        <v-btn
          v-if="!success"
          color="primary"
          variant="tonal"
          :loading="loading"
          @click="handleSubmit"
        >
          Send Invite
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref } from 'vue';
import { sendInvite } from '@/api';

defineProps({
  modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'invited']);

const email = ref('');
const role = ref('viewer');
const loading = ref(false);
const success = ref(false);
const error = ref('');

const rules = {
  required: (v) => !!v || 'Required',
  email: (v) => /.+@.+\..+/.test(v) || 'Invalid email',
};

async function handleSubmit() {
  loading.value = true;
  error.value = '';
  try {
    await sendInvite(email.value, role.value);
    success.value = true;
    emit('invited');
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to send invite';
    window.logService?.error('Invite failed', { error: error.value });
  } finally {
    loading.value = false;
  }
}

function handleClose() {
  emit('update:modelValue', false);
  // Reset form after dialog closes
  setTimeout(() => {
    email.value = '';
    role.value = 'viewer';
    success.value = false;
    error.value = '';
  }, 300);
}
</script>
