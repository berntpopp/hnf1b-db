<template>
  <v-container fluid class="pa-4">
    <v-row class="mb-4">
      <v-col cols="12">
        <div class="d-flex align-center">
          <v-btn icon variant="text" class="mr-2" to="/admin">
            <v-icon>mdi-arrow-left</v-icon>
          </v-btn>
          <v-icon size="32" color="red" class="mr-3">mdi-account-group</v-icon>
          <div>
            <h1 class="text-h4 font-weight-bold">User Management</h1>
            <p class="text-body-2 text-grey mt-1">
              Create, edit, deactivate, and unlock user accounts
            </p>
          </div>
          <v-spacer />
          <v-btn color="primary" variant="flat" @click="showCreate = true">
            <v-icon start>mdi-account-plus</v-icon>
            Create User
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <v-row v-if="error">
      <v-col cols="12">
        <v-alert type="error" variant="tonal" closable @click:close="error = null">
          {{ error }}
        </v-alert>
      </v-col>
    </v-row>

    <v-row v-if="success">
      <v-col cols="12">
        <v-alert type="success" variant="tonal" closable @click:close="success = null">
          {{ success }}
        </v-alert>
      </v-col>
    </v-row>

    <v-row v-if="loading">
      <v-col cols="12" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48" />
        <p class="text-body-1 mt-4">Loading users...</p>
      </v-col>
    </v-row>

    <v-row v-else>
      <v-col cols="12">
        <UserListTable
          :users="users"
          @edit="openEdit"
          @unlock="handleUnlock"
          @delete="confirmDelete"
          @refresh="fetchUsers"
        />
      </v-col>
    </v-row>

    <UserCreateDialog v-model="showCreate" @created="onCreated" />
    <UserEditDialog v-model="showEdit" :user="editTarget" @updated="onUpdated" />

    <v-dialog v-model="showDeleteConfirm" max-width="400">
      <v-card>
        <v-card-title>Confirm Delete</v-card-title>
        <v-card-text>
          Are you sure you want to delete user
          <strong>{{ deleteTarget?.username }}</strong
          >? This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDeleteConfirm = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" :loading="deleting" @click="handleDelete">
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { listUsers, deleteUser, unlockUser } from '@/api';
import UserListTable from '@/components/admin/UserListTable.vue';
import UserCreateDialog from '@/components/admin/UserCreateDialog.vue';
import UserEditDialog from '@/components/admin/UserEditDialog.vue';

const users = ref([]);
const loading = ref(true);
const error = ref(null);
const success = ref(null);

const showCreate = ref(false);
const showEdit = ref(false);
const editTarget = ref(null);
const showDeleteConfirm = ref(false);
const deleteTarget = ref(null);
const deleting = ref(false);

const fetchUsers = async () => {
  try {
    const response = await listUsers();
    users.value = (response.data || []).filter((u) => u.username !== '_system_migration_');
    error.value = null;
  } catch (err) {
    window.logService.error('Failed to fetch users', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to load users';
  }
};

const openEdit = (user) => {
  editTarget.value = user;
  showEdit.value = true;
};

const confirmDelete = (user) => {
  deleteTarget.value = user;
  showDeleteConfirm.value = true;
};

const handleDelete = async () => {
  deleting.value = true;
  try {
    await deleteUser(deleteTarget.value.id);
    window.logService.info('User deleted', { userId: deleteTarget.value.id });
    success.value = `User "${deleteTarget.value.username}" deleted`;
    showDeleteConfirm.value = false;
    await fetchUsers();
  } catch (err) {
    window.logService.error('Failed to delete user', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to delete user';
  } finally {
    deleting.value = false;
  }
};

const handleUnlock = async (user) => {
  try {
    await unlockUser(user.id);
    window.logService.info('User unlocked', { userId: user.id });
    success.value = `User "${user.username}" unlocked`;
    await fetchUsers();
  } catch (err) {
    window.logService.error('Failed to unlock user', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to unlock user';
  }
};

const onCreated = async () => {
  success.value = 'User created successfully';
  await fetchUsers();
};

const onUpdated = async () => {
  success.value = 'User updated successfully';
  await fetchUsers();
};

onMounted(async () => {
  window.logService.info('AdminUsers view mounted');
  await fetchUsers();
  loading.value = false;
});
</script>
