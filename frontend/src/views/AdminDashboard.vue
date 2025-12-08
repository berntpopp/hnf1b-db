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
              <v-icon size="48" color="purple" class="mb-2">mdi-dna</v-icon>
              <div class="text-h3 font-weight-bold">{{ statistics?.variants?.cached || 0 }}</div>
              <div class="text-body-2 text-grey">Variants Annotated</div>
              <div class="text-caption text-grey mt-1">
                {{ statistics?.variants?.unique || 0 }} unique variants
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Second Row Statistics -->
      <v-row class="mb-4">
        <v-col cols="12" md="6">
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
        <v-col cols="12" md="6">
          <v-card elevation="2">
            <v-card-text class="text-center">
              <v-icon size="48" color="green" class="mb-2">mdi-check-decagram</v-icon>
              <div class="text-h3 font-weight-bold">
                {{ getSyncCompletionPercent().toFixed(0) }}%
              </div>
              <div class="text-body-2 text-grey">Data Sync Progress</div>
              <div class="text-caption text-grey mt-1">Publications + Variants annotated</div>
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
                      <template v-if="item.name === 'Publication Metadata'">
                        <v-btn-group v-if="!pubSyncInProgress" density="compact">
                          <v-btn
                            size="small"
                            color="primary"
                            variant="tonal"
                            @click="startPublicationSync(false)"
                          >
                            <v-icon start size="small">mdi-sync</v-icon>
                            {{ item.pending > 0 ? 'Sync Now' : 'Refresh' }}
                          </v-btn>
                          <v-menu>
                            <template #activator="{ props }">
                              <v-btn
                                v-bind="props"
                                size="small"
                                color="primary"
                                variant="tonal"
                                icon
                              >
                                <v-icon size="small">mdi-chevron-down</v-icon>
                              </v-btn>
                            </template>
                            <v-list density="compact">
                              <v-list-item @click="startPublicationSync(true)">
                                <v-list-item-title>
                                  <v-icon size="small" class="mr-1">mdi-refresh</v-icon>
                                  Force Re-sync All
                                </v-list-item-title>
                              </v-list-item>
                            </v-list>
                          </v-menu>
                        </v-btn-group>
                        <v-btn v-else loading size="small" color="primary" variant="tonal" disabled>
                          Syncing...
                        </v-btn>
                      </template>
                      <template v-else-if="item.name === 'VEP Annotations'">
                        <v-btn-group v-if="!varSyncInProgress" density="compact">
                          <v-btn
                            size="small"
                            color="purple"
                            variant="tonal"
                            @click="startVariantSync(false)"
                          >
                            <v-icon start size="small">mdi-sync</v-icon>
                            {{ item.pending > 0 ? 'Sync Now' : 'Refresh' }}
                          </v-btn>
                          <v-menu>
                            <template #activator="{ props }">
                              <v-btn
                                v-bind="props"
                                size="small"
                                color="purple"
                                variant="tonal"
                                icon
                              >
                                <v-icon size="small">mdi-chevron-down</v-icon>
                              </v-btn>
                            </template>
                            <v-list density="compact">
                              <v-list-item @click="startVariantSync(true)">
                                <v-list-item-title>
                                  <v-icon size="small" class="mr-1">mdi-refresh</v-icon>
                                  Force Re-sync All
                                </v-list-item-title>
                              </v-list-item>
                            </v-list>
                          </v-menu>
                        </v-btn-group>
                        <v-btn v-else loading size="small" color="purple" variant="tonal" disabled>
                          Syncing...
                        </v-btn>
                      </template>
                      <span v-else class="text-caption text-grey"> CLI only </span>
                    </td>
                  </tr>
                </tbody>
              </v-table>

              <!-- Publication Sync Progress -->
              <v-expand-transition>
                <div v-if="pubSyncTask" class="mt-4 pa-4 bg-grey-lighten-4 rounded">
                  <div class="d-flex justify-space-between align-center mb-2">
                    <span class="font-weight-medium">
                      <v-icon size="small" class="mr-1">mdi-book-open-variant</v-icon>
                      Publication Sync Progress
                    </span>
                    <v-chip :color="getSyncStatusColor(pubSyncTask.status)" size="small">
                      {{ pubSyncTask.status }}
                    </v-chip>
                  </div>
                  <v-progress-linear
                    :model-value="pubSyncTask.progress"
                    :color="getSyncStatusColor(pubSyncTask.status)"
                    height="12"
                    rounded
                  />
                  <div class="d-flex justify-space-between mt-2 text-caption">
                    <span>{{ pubSyncTask.processed }} / {{ pubSyncTask.total }} processed</span>
                    <span v-if="pubSyncTask.errors > 0" class="text-error">
                      {{ pubSyncTask.errors }} errors
                    </span>
                  </div>
                </div>
              </v-expand-transition>

              <!-- Variant Sync Progress -->
              <v-expand-transition>
                <div v-if="varSyncTask" class="mt-4 pa-4 bg-purple-lighten-5 rounded">
                  <div class="d-flex justify-space-between align-center mb-2">
                    <span class="font-weight-medium">
                      <v-icon size="small" class="mr-1">mdi-dna</v-icon>
                      VEP Annotation Sync Progress
                    </span>
                    <v-chip :color="getSyncStatusColor(varSyncTask.status)" size="small">
                      {{ varSyncTask.status }}
                    </v-chip>
                  </div>
                  <v-progress-linear
                    :model-value="varSyncTask.progress"
                    color="purple"
                    height="12"
                    rounded
                  />
                  <div class="d-flex justify-space-between mt-2 text-caption">
                    <span>{{ varSyncTask.processed }} / {{ varSyncTask.total }} processed</span>
                    <span v-if="varSyncTask.errors > 0" class="text-error">
                      {{ varSyncTask.errors }} errors
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
                <v-col cols="12" sm="6" md="4" lg="2">
                  <v-btn
                    block
                    color="primary"
                    variant="tonal"
                    :disabled="pubSyncInProgress"
                    @click="startPublicationSync"
                  >
                    <v-icon start>mdi-book-sync</v-icon>
                    Sync Publications
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="4" lg="2">
                  <v-btn
                    block
                    color="purple"
                    variant="tonal"
                    :disabled="varSyncInProgress"
                    @click="startVariantSync"
                  >
                    <v-icon start>mdi-dna</v-icon>
                    Sync Variants
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="4" lg="2">
                  <v-btn block color="secondary" variant="tonal" @click="refreshStatus">
                    <v-icon start>mdi-refresh</v-icon>
                    Refresh Status
                  </v-btn>
                </v-col>
                <v-col cols="12" sm="6" md="6" lg="3">
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
                <v-col cols="12" sm="6" md="6" lg="3">
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
                      <v-list-item-subtitle>
                        {{ systemStatus?.status || 'Unknown' }}
                      </v-list-item-subtitle>
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

// Publication sync state
const pubSyncTask = ref(null);
const pubSyncInProgress = ref(false);
let pubPollInterval = null;

// Variant sync state
const varSyncTask = ref(null);
const varSyncInProgress = ref(false);
let varPollInterval = null;

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

const getSyncCompletionPercent = () => {
  const pubItem = syncStatus.value.find((s) => s.name === 'Publication Metadata');
  const varItem = syncStatus.value.find((s) => s.name === 'VEP Annotations');

  let totalItems = 0;
  let syncedItems = 0;

  if (pubItem) {
    totalItems += pubItem.total;
    syncedItems += pubItem.synced;
  }
  if (varItem) {
    totalItems += varItem.total;
    syncedItems += varItem.synced;
  }

  if (totalItems === 0) return 100;
  return (syncedItems / totalItems) * 100;
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

// Publication sync methods
const startPublicationSync = async (force = false) => {
  try {
    pubSyncInProgress.value = true;
    const response = await API.startPublicationSync(force);
    pubSyncTask.value = {
      task_id: response.data.task_id,
      status: response.data.status,
      progress: 0,
      processed: 0,
      total: response.data.items_to_process,
      errors: 0,
    };

    if (response.data.status === 'completed') {
      successMessage.value = response.data.message;
      pubSyncInProgress.value = false;
      pubSyncTask.value = null;
      await fetchStatus();
    } else {
      startPubPolling();
    }
  } catch (err) {
    window.logService.error('Failed to start publication sync', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to start publication sync';
    pubSyncInProgress.value = false;
  }
};

const pollPubSyncStatus = async () => {
  try {
    const response = await API.getPublicationSyncStatus(pubSyncTask.value?.task_id);
    pubSyncTask.value = response.data;

    if (response.data.status === 'completed' || response.data.status === 'failed') {
      stopPubPolling();
      pubSyncInProgress.value = false;
      if (response.data.status === 'completed') {
        successMessage.value = `Publication sync completed: ${response.data.processed} publications`;
        await fetchStatus();
      } else {
        error.value = 'Publication sync task failed';
      }
      setTimeout(() => {
        pubSyncTask.value = null;
      }, 5000);
    }
  } catch (err) {
    window.logService.error('Failed to poll publication sync status', { error: err.message });
  }
};

const startPubPolling = () => {
  if (pubPollInterval) return;
  pubPollInterval = setInterval(pollPubSyncStatus, 2000);
};

const stopPubPolling = () => {
  if (pubPollInterval) {
    clearInterval(pubPollInterval);
    pubPollInterval = null;
  }
};

// Variant sync methods
const startVariantSync = async (force = false) => {
  try {
    varSyncInProgress.value = true;
    const response = await API.startVariantSync(force);
    varSyncTask.value = {
      task_id: response.data.task_id,
      status: response.data.status,
      progress: 0,
      processed: 0,
      total: response.data.items_to_process,
      errors: 0,
    };

    if (response.data.status === 'completed') {
      successMessage.value = response.data.message;
      varSyncInProgress.value = false;
      varSyncTask.value = null;
      await fetchStatus();
    } else {
      startVarPolling();
    }
  } catch (err) {
    window.logService.error('Failed to start variant sync', { error: err.message });
    error.value = err.response?.data?.detail || 'Failed to start variant sync';
    varSyncInProgress.value = false;
  }
};

const pollVarSyncStatus = async () => {
  try {
    const response = await API.getVariantSyncStatus(varSyncTask.value?.task_id);
    varSyncTask.value = response.data;

    if (response.data.status === 'completed' || response.data.status === 'failed') {
      stopVarPolling();
      varSyncInProgress.value = false;
      if (response.data.status === 'completed') {
        successMessage.value = `VEP annotation completed: ${response.data.processed} variants`;
        await fetchStatus();
      } else {
        error.value = 'VEP annotation task failed';
      }
      setTimeout(() => {
        varSyncTask.value = null;
      }, 5000);
    }
  } catch (err) {
    window.logService.error('Failed to poll variant sync status', { error: err.message });
  }
};

const startVarPolling = () => {
  if (varPollInterval) return;
  varPollInterval = setInterval(pollVarSyncStatus, 2000);
};

const stopVarPolling = () => {
  if (varPollInterval) {
    clearInterval(varPollInterval);
    varPollInterval = null;
  }
};

// Lifecycle
onMounted(async () => {
  window.logService.info('Admin dashboard mounted');
  await fetchStatus();
  loading.value = false;
});

onUnmounted(() => {
  stopPubPolling();
  stopVarPolling();
});
</script>

<style scoped>
.v-table th {
  font-weight: 600 !important;
}
</style>
