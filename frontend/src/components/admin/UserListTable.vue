<template>
  <v-card elevation="2">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-account-multiple</v-icon>
      Users
      <v-spacer />
      <v-btn size="small" color="primary" variant="tonal" class="mr-2" @click="$emit('refresh')">
        <v-icon start size="small">mdi-refresh</v-icon>
        Refresh
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-row class="mb-3" dense>
        <v-col cols="12" sm="4">
          <v-text-field
            v-model="search"
            prepend-inner-icon="mdi-magnify"
            label="Search users"
            density="compact"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="6" sm="3">
          <v-select
            v-model="roleFilter"
            :items="roleOptions"
            label="Role"
            density="compact"
            hide-details
            clearable
          />
        </v-col>
        <v-col cols="6" sm="3">
          <v-select
            v-model="activeFilter"
            :items="activeOptions"
            label="Active"
            density="compact"
            hide-details
            clearable
          />
        </v-col>
      </v-row>
      <v-data-table
        :headers="headers"
        :items="filteredUsers"
        :search="search"
        density="compact"
        items-per-page="25"
      >
        <template #item.is_active="{ item }">
          <v-icon :color="item.is_active ? 'success' : 'grey'" size="small">
            {{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
          </v-icon>
        </template>
        <template #item.locked_until="{ item }">
          <v-chip v-if="isLocked(item)" size="small" color="error" variant="flat"> Locked </v-chip>
          <span v-else class="text-caption text-grey">--</span>
        </template>
        <template #item.actions="{ item }">
          <v-btn icon size="x-small" variant="text" @click="$emit('edit', item)">
            <v-icon size="small">mdi-pencil</v-icon>
            <v-tooltip activator="parent" location="top">Edit</v-tooltip>
          </v-btn>
          <v-btn
            v-if="isLocked(item)"
            icon
            size="x-small"
            variant="text"
            color="warning"
            @click="$emit('unlock', item)"
          >
            <v-icon size="small">mdi-lock-open</v-icon>
            <v-tooltip activator="parent" location="top">Unlock</v-tooltip>
          </v-btn>
          <v-btn icon size="x-small" variant="text" color="error" @click="$emit('delete', item)">
            <v-icon size="small">mdi-delete</v-icon>
            <v-tooltip activator="parent" location="top">Delete</v-tooltip>
          </v-btn>
        </template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  users: { type: Array, default: () => [] },
});

defineEmits(['edit', 'unlock', 'delete', 'refresh']);

const search = ref('');
const roleFilter = ref(null);
const activeFilter = ref(null);

const roleOptions = ['admin', 'curator', 'viewer'];
const activeOptions = [
  { title: 'Active', value: true },
  { title: 'Inactive', value: false },
];

const headers = [
  { title: 'Username', key: 'username' },
  { title: 'Email', key: 'email' },
  { title: 'Full Name', key: 'full_name' },
  { title: 'Role', key: 'role' },
  { title: 'Active', key: 'is_active', align: 'center' },
  { title: 'Locked', key: 'locked_until', align: 'center' },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' },
];

const isLocked = (user) => {
  if (!user.locked_until) return false;
  return new Date(user.locked_until) > new Date();
};

const filteredUsers = computed(() => {
  let result = props.users;
  if (roleFilter.value) {
    result = result.filter((u) => u.role === roleFilter.value);
  }
  if (activeFilter.value !== null && activeFilter.value !== undefined) {
    result = result.filter((u) => u.is_active === activeFilter.value);
  }
  return result;
});
</script>
