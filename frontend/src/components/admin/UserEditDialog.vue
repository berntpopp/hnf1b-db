<template>
  <v-dialog v-model="dialog" max-width="500" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-account-edit</v-icon>
        Edit User
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
          <v-text-field :model-value="user?.username" label="Username" disabled class="mb-2" />
          <v-text-field
            v-model="form.email"
            label="Email"
            type="email"
            :rules="[rules.required, rules.email]"
            class="mb-2"
          />
          <v-text-field v-model="form.full_name" label="Full Name" class="mb-2" />
          <v-select
            v-model="form.role"
            :items="['admin', 'curator', 'viewer']"
            label="Role"
            :rules="[rules.required]"
            class="mb-2"
          />
          <v-switch
            v-model="form.is_active"
            label="Active"
            color="success"
            hide-details
            class="mb-2"
          />
          <v-text-field
            v-model="form.password"
            label="New Password (optional)"
            type="password"
            :rules="form.password ? [rules.minLength] : []"
          />
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="saving" @click="close">Cancel</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" @click="handleSubmit">Save</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { updateUser } from '@/api';

const props = defineProps({
  user: { type: Object, default: null },
});

const emit = defineEmits(['updated']);

const dialog = defineModel('modelValue', { type: Boolean, default: false });
const formRef = ref(null);
const saving = ref(false);
const error = ref(null);

const form = ref({ email: '', full_name: '', role: 'viewer', is_active: true, password: '' });

const rules = {
  required: (v) => !!v || 'Required',
  email: (v) => /.+@.+\..+/.test(v) || 'Invalid email',
  minLength: (v) => (v && v.length >= 8) || 'Min 8 characters',
};

watch(
  () => props.user,
  (u) => {
    if (u) {
      form.value = {
        email: u.email || '',
        full_name: u.full_name || '',
        role: u.role || 'viewer',
        is_active: u.is_active ?? true,
        password: '',
      };
      error.value = null;
    }
  },
  { immediate: true }
);

const close = () => {
  dialog.value = false;
};

const handleSubmit = async () => {
  const { valid } = await formRef.value.validate();
  if (!valid) return;
  saving.value = true;
  error.value = null;
  try {
    const payload = {
      email: form.value.email,
      full_name: form.value.full_name,
      role: form.value.role,
      is_active: form.value.is_active,
    };
    if (form.value.password) {
      payload.password = form.value.password;
    }
    await updateUser(props.user.id, payload);
    window.logService.info('User updated', { userId: props.user.id });
    emit('updated');
    close();
  } catch (err) {
    window.logService.error('Failed to update user', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to update user';
  } finally {
    saving.value = false;
  }
};
</script>
