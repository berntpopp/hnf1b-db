<template>
  <v-dialog v-model="dialog" max-width="500" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-account-plus</v-icon>
        Create User
      </v-card-title>
      <v-card-text>
        <v-alert
          v-if="error"
          type="error"
          variant="tonal"
          class="mb-3"
          closable
          @click:close="error = null"
        >
          {{ error }}
        </v-alert>
        <v-form ref="formRef" @submit.prevent="handleSubmit">
          <v-text-field
            v-model="form.username"
            label="Username"
            :rules="[rules.required]"
            class="mb-2"
          />
          <v-text-field
            v-model="form.email"
            label="Email"
            type="email"
            :rules="[rules.required, rules.email]"
            class="mb-2"
          />
          <v-text-field
            v-model="form.password"
            label="Password"
            type="password"
            :rules="[rules.required, rules.minLength]"
            class="mb-2"
          />
          <v-text-field v-model="form.full_name" label="Full Name" class="mb-2" />
          <v-select
            v-model="form.role"
            :items="['admin', 'curator', 'viewer']"
            label="Role"
            :rules="[rules.required]"
          />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="saving" @click="close">Cancel</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" @click="handleSubmit">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { createUser } from '@/api';

const emit = defineEmits(['created']);

const dialog = defineModel('modelValue', { type: Boolean, default: false });
const formRef = ref(null);
const saving = ref(false);
const error = ref(null);

const defaultForm = () => ({
  username: '',
  email: '',
  password: '',
  full_name: '',
  role: 'viewer',
});
const form = ref(defaultForm());

const rules = {
  required: (v) => !!v || 'Required',
  email: (v) => /.+@.+\..+/.test(v) || 'Invalid email',
  minLength: (v) => (v && v.length >= 8) || 'Min 8 characters',
};

watch(dialog, (val) => {
  if (val) {
    form.value = defaultForm();
    error.value = null;
  }
});

const close = () => {
  dialog.value = false;
};

const handleSubmit = async () => {
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  saving.value = true;
  error.value = null;
  try {
    await createUser(form.value);
    window.logService.info('User created', { username: form.value.username });
    emit('created');
    close();
  } catch (err) {
    window.logService.error('Failed to create user', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to create user';
  } finally {
    saving.value = false;
  }
};
</script>
