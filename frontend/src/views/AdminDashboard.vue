<template>
  <v-container fluid class="pa-4">
    <!-- Page Header -->
    <v-row class="mb-4">
      <v-col cols="12">
        <div class="d-flex align-center">
          <v-icon size="32" color="red" class="mr-3">mdi-shield-crown</v-icon>
          <div>
            <h1 class="text-h4 font-weight-bold">Admin Dashboard</h1>
            <p class="text-body-2 text-grey mt-1">System management and data synchronization</p>
          </div>
        </div>
      </v-col>
    </v-row>

    <!-- Error Alert -->
    <v-row v-if="error">
      <v-col cols="12">
        <v-alert type="error" variant="tonal" closable @click:close="error = null">
          {{ error }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Success Alert -->
    <v-row v-if="successMessage">
      <v-col cols="12">
        <v-alert type="success" variant="tonal" closable @click:close="successMessage = null">
          {{ successMessage }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Loading State -->
    <v-row v-if="loading">
      <v-col cols="12" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48" />
        <p class="text-body-1 mt-4">Loading system status...</p>
      </v-col>
    </v-row>

    <template v-else>
      <!-- Database Statistics Cards -->
      <v-row class="mb-4">
        <v-col cols="12" md="4">
          <v-card elevation="2">
            <v-card-text class="text-center">
              <v-icon size="48" color="teal" class="mb-2">mdi-account-multiple</v-icon>
              <div class="text-h3 font-weight-bold">{{ statistics?.phenopackets?.total || 0 }}</div>
              <div class="text-body-2 text-grey">Phenopackets</div>
              <div
                v-if="statistics?.phenopackets?.with_variants"
                class="text-caption text-grey mt-1"
              >
                {{ statistics.phenopackets.with_variants }} with variants
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="4">
          <v-card elevation="2">
            <v-card-text class="text-center">
              <v-icon size="48" color="blue" class="mb-2">mdi-book-open-variant</v-icon>
              <div class="text-h3 font-weight-bold">
                {{ statistics?.publications?.cached || 0 }}
              </div>
              <div class="text-body-2 text-grey">Publications Cached</div>
              <div class="text-caption text-grey mt-1">
                {{ statistics?.publications?.referenced || 0 }} referenced
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="4">
          <v-card elevation="2">
            <v-card-text class="text-center">
              <v-icon size="48" color="orange" class="mb-2">mdi-account-group</v-icon>
              <div class="text-h3 font-weight-bold">{{ statistics?.users?.total || 0 }}</div>
              <div class="text-body-2 text-grey">Users</div>
              <div class="text-caption text-grey mt-1">
                {{ statistics?.users?.admins || 0 }} admins,
                {{ statistics?.users?.curators || 0 }} curators
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Data Sync Section -->
      <v-row>
        <v-col cols="12">
          <v-card elevation="2">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2">mdi-sync</v-icon>
              Data Synchronization
            </v-card-title>
            <v-card-text>
              <v-table>
                <thead>
                  <tr>
                    <th>Data Type</th>
                    <th class="text-center">Total</th>
                    <th class="text-center">Synced</th>
                    <th class="text-center">Pending</th>
                    <th class="text-center">Progress</th>
                    <th>Last Sync</th>
                    <th class="text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in syncStatus" :key="item.name">
                    <td>
                      <div class="d-flex align-center">
                        <v-icon :color="getSyncIconColor(item)" class="mr-2" size="small">
                          {{ getSyncIcon(item) }}
                        </v-icon>
                        {{ item.name }}
                      </div>
                    </td>
                    <td class="text-center">{{ item.total }}</td>
                    <td class="text-center">
                      <v-chip size="small" color="success" variant="flat">
                        {{ item.synced }}
                      </v-chip>
                    </td>
                    <td class="text-center">
                      <v-chip v-if="item.pending > 0" size="small" color="warning" variant="flat">
                        {{ item.pending }}
                      </v-chip>
                      <v-icon v-else color="success" size="small">mdi-check-circle</v-icon>
                    </td>
                    <td class="text-center" style="width: 150px">
                      <v-progress-linear
                        :model-value="getProgressPercent(item)"
                        :color="item.pending === 0 ? 'success' : 'primary'"
                        height="8"
                        rounded
                      />
                      <span class="text-caption">{{ getProgressPercent(item).toFixed(0) }}%</span>
                    </td>
                    <td>
                      <span v-if="item.last_sync" class="text-caption">
                        {{ formatDate(item.last_sync) }}
                      </span>
                      <span v-else class="text-caption text-grey">Never</span>
                    </td>
                    <td class="text-center">
                      <v-btn
                        v-if="item.name === 'Publication Metadata'"
                        :loading="syncInProgress"
                        :disabled="item.pending === 0 && !syncInProgress"
                        size="small"
                        color="primary"
                        variant="tonal"
                        @click="startSync"
                      >
                        <v-icon start size="small">mdi-sync</v-icon>
                        {{ syncInProgress ? 'Syncing...' : 'Sync Now' }}
                      </v-btn>
                      <span v-else class="text-caption text-grey"> CLI only </span>
                    </td>
                  </tr>
                </tbody>
              </v-table>

              <!-- Sync Progress -->
              <v-expand-transition>
                <div v-if="syncTask" class="mt-4 pa-4 bg-grey-lighten-4 rounded">
                  <div class="d-flex justify-space-between align-center mb-2">
                    <span class="font-weight-medium">Sync Progress</span>
                    <v-chip :color="getSyncStatusColor(syncTask.status)" size="small">
                      {{ syncTask.status }}
                    </v-chip>
                  </div>
                  <v-progress-linear
                    :model-value="syncTask.progress"
                    :color="getSyncStatusColor(syncTask.status)"
                    height="12"
                    rounded
                  />
                  <div class="d-flex justify-space-between mt-2 text-caption">
                    <span>{{ syncTask.processed }} / {{ syncTask.total }} processed</span>
                    <span v-if="syncTask.errors > 0" class="text-error">
                      {{ syncTask.errors }} errors
                    </span>
                  </div>
                </div>
              </v-expand-transition>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Quick Actions -->
      <v-row class="mt-4">
        <v-col cols="12">
          <v-card elevation="2">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2">mdi-lightning-bolt</v-icon>
              Quick Actions
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" sm="6" md="3">
                  <v-btn
                    block
                    color="primary"
                    variant="tonal"
                    :disabled="syncInProgress"
                    @click="startSync"
                  >
                    <v-icon start>mdi-book-sync</v-icon>
                    Sync Publications
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="3">
                  <v-btn block color="secondary" variant="tonal" @click="refreshStatus">
                    <v-icon start>mdi-refresh</v-icon>
                    Refresh Status
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="3">
                  <v-btn
                    block
                    color="info"
                    variant="tonal"
                    href="http://localhost:8000/api/v2/docs"
                    target="_blank"
                  >
                    <v-icon start>mdi-api</v-icon>
                    API Docs
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="3">
                  <v-btn block color="grey" variant="tonal" to="/user">
                    <v-icon start>mdi-account</v-icon>
                    User Profile
                  </v-btn>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- System Info -->
      <v-row class="mt-4">
        <v-col cols="12">
          <v-card elevation="2">
            <v-card-title class="d-flex align-center">
              <v-icon class="mr-2">mdi-information</v-icon>
              System Information
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-list density="compact">
                    <v-list-item>
                      <template #prepend>
                        <v-icon color="success">mdi-check-circle</v-icon>
                      </template>
                      <v-list-item-title>System Status</v-list-item-title>
                      <v-list-item-subtitle>{{
                        systemStatus?.status || 'Unknown'
                      }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template #prepend>
                        <v-icon color="info">mdi-clock</v-icon>
                      </template>
                      <v-list-item-title>Last Updated</v-list-item-title>
                      <v-list-item-subtitle>
                        {{ systemStatus?.timestamp ? formatDate(systemStatus.timestamp) : 'N/A' }}
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
                <v-col cols="12" md="6">
                  <v-list density="compact">
                    <v-list-item>
                      <template #prepend>
                        <v-icon color="primary">mdi-database</v-icon>
                      </template>
                      <v-list-item-title>Database</v-list-item-title>
                      <v-list-item-subtitle>
                        {{ systemStatus?.database?.phenopackets || 0 }} phenopackets,
                        {{ systemStatus?.database?.publications_cached || 0 }} publications
                      </v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template #prepend>
                        <v-icon color="orange">mdi-account-multiple</v-icon>
                      </template>
                      <v-list-item-title>Users</v-list-item-title>
                      <v-list-item-subtitle>
                        {{ systemStatus?.database?.users || 0 }} active users
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import * as API from '@/api';

// State
const loading = ref(true);
const error = ref(null);
const successMessage = ref(null);
const systemStatus = ref(null);
const statistics = ref(null);
const syncTask = ref(null);
const syncInProgress = ref(false);
let pollInterval = null;

// Computed
const syncStatus = computed(() => systemStatus.value?.sync_status || []);

// Methods
const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return date.toLocaleString();
};

const getProgressPercent = (item) => {
  if (item.total === 0) return 100;
  return (item.synced / item.total) * 100;
};

const getSyncIcon = (item) => {
  if (item.name === 'Publication Metadata') return 'mdi-book-open-variant';
  if (item.name === 'VEP Annotations') return 'mdi-dna';
  return 'mdi-sync';
};

const getSyncIconColor = (item) => {
  if (item.pending === 0) return 'success';
  if (item.pending > 10) return 'warning';
  return 'primary';
};

const getSyncStatusColor = (status) => {
  const colors = {
    pending: 'grey',
    running: 'primary',
    completed: 'success',
    failed: 'error',
    idle: 'grey',
  };
  return colors[status] || 'grey';
};

const fetchStatus = async () => {
  try {
    const [statusRes, statsRes] = await Promise.all([
      API.getAdminStatus(),
      API.getAdminStatistics(),
    ]);
    systemStatus.value = statusRes.data;
    statistics.value = statsRes.data;
    error.value = null;
  } catch (err) {
    window.logService.error('Failed to fetch admin status', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to fetch system status';
  }
};

const refreshStatus = async () => {
  loading.value = true;
  await fetchStatus();
  loading.value = false;
  successMessage.value = 'Status refreshed successfully';
  setTimeout(() => {
    successMessage.value = null;
  }, 3000);
};

const startSync = async () => {
  try {
    syncInProgress.value = true;
    const response = await API.startPublicationSync();
    syncTask.value = {
      task_id: response.data.task_id,
      status: response.data.status,
      progress: 0,
      processed: 0,
      total: response.data.items_to_process,
      errors: 0,
    };

    if (response.data.status === 'completed') {
      successMessage.value = response.data.message;
      syncInProgress.value = false;
      syncTask.value = null;
    } else {
      // Start polling for progress
      startPolling();
    }
  } catch (err) {
    window.logService.error('Failed to start publication sync', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to start sync';
    syncInProgress.value = false;
  }
};

const pollSyncStatus = async () => {
  try {
    const response = await API.getPublicationSyncStatus(syncTask.value?.task_id);
    syncTask.value = response.data;

    if (response.data.status === 'completed' || response.data.status === 'failed') {
      stopPolling();
      syncInProgress.value = false;
      if (response.data.status === 'completed') {
        successMessage.value = `Sync completed: ${response.data.processed} publications synced`;
        await fetchStatus(); // Refresh statistics
      } else {
        error.value = 'Sync task failed';
      }
      // Clear task after a delay
      setTimeout(() => {
        syncTask.value = null;
      }, 5000);
    }
  } catch (err) {
    window.logService.error('Failed to poll sync status', { error: err.message });
  }
};

const startPolling = () => {
  if (pollInterval) return;
  pollInterval = setInterval(pollSyncStatus, 2000);
};

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
};

// Lifecycle
onMounted(async () => {
  window.logService.info('Admin dashboard mounted');
  await fetchStatus();
  loading.value = false;
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.v-table th {
  font-weight: 600 !important;
}
</style>
