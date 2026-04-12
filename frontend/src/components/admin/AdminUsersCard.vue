<template>
  <v-card elevation="2" class="h-100" style="cursor: pointer" @click="$router.push('/admin/users')">
    <v-card-text class="text-center">
      <v-icon size="48" color="red" class="mb-2">mdi-account-group</v-icon>
      <div class="text-h5 font-weight-bold">User Management</div>
      <div class="text-body-2 text-grey mt-2">Create, edit, deactivate, unlock accounts</div>
      <v-btn variant="tonal" color="red" class="mt-3">Open</v-btn>
    </v-card-text>
  </v-card>
</template>
