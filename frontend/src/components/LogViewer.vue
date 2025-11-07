<template>
  <v-navigation-drawer v-model="isOpen" location="right" temporary width="600" class="log-viewer">
    <!-- Toolbar -->
    <v-toolbar color="grey-darken-3" dark density="compact">
      <v-toolbar-title class="text-subtitle-1">
        <v-icon start>mdi-text-box-search-outline</v-icon>
        Application Logs
        <v-chip v-if="logStore.logs.length > 0" size="small" color="primary" class="ml-2">
          {{ logStore.logs.length }}
        </v-chip>
      </v-toolbar-title>

      <v-spacer />

      <!-- Toolbar Actions -->
      <v-btn
        icon="mdi-download"
        size="small"
        variant="text"
        :disabled="logStore.logs.length === 0"
        aria-label="Download logs as JSON"
        title="Download logs as JSON"
        @click="exportLogs"
      />

      <v-btn
        icon="mdi-delete-sweep"
        size="small"
        variant="text"
        :disabled="logStore.logs.length === 0"
        aria-label="Clear all logs"
        title="Clear all logs"
        @click="clearAllLogs"
      />

      <v-btn
        icon="mdi-close"
        size="small"
        variant="text"
        aria-label="Close log viewer"
        title="Close log viewer"
        @click="closeViewer"
      />
    </v-toolbar>

    <!-- Filter Controls -->
    <v-container class="py-2" fluid>
      <v-row dense>
        <!-- Minimum Display Level -->
        <v-col cols="6">
          <v-select
            v-model="minDisplayLevel"
            :items="minLevelOptions"
            label="Min Level"
            prepend-inner-icon="mdi-filter-variant"
            variant="outlined"
            density="compact"
            hide-details
            @update:model-value="updateMinLevel"
          />
        </v-col>

        <!-- Console Logging Toggle -->
        <v-col cols="6" class="d-flex align-center">
          <v-switch
            v-model="consoleLogging"
            label="Console"
            color="primary"
            density="compact"
            hide-details
            @update:model-value="toggleConsoleLogging"
          />
        </v-col>

        <!-- Search Filter -->
        <v-col cols="12">
          <v-text-field
            v-model="searchQuery"
            label="Search logs..."
            prepend-inner-icon="mdi-magnify"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>

        <!-- Specific Level Filter -->
        <v-col cols="6">
          <v-select
            v-model="selectedLevel"
            :items="logLevels"
            label="Specific level"
            prepend-inner-icon="mdi-filter"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>

        <!-- Component Filter -->
        <v-col cols="6">
          <v-select
            v-model="selectedComponent"
            :items="componentNames"
            label="Component"
            prepend-inner-icon="mdi-view-module"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
      </v-row>
    </v-container>

    <v-divider />

    <!-- Log Entries -->
    <v-container class="log-entries pa-2" fluid>
      <div v-if="filteredLogs.length === 0" class="text-center py-8 text-grey">
        <v-icon size="48" class="mb-2">mdi-text-box-remove-outline</v-icon>
        <p>{{ logStore.logs.length === 0 ? 'No logs available' : 'No logs match your filters' }}</p>
      </div>

      <v-card
        v-for="(log, index) in filteredLogs"
        :key="`${log.timestamp}-${index}`"
        class="mb-2 log-entry"
        variant="outlined"
        :color="getLevelColor(log.level)"
      >
        <v-card-text class="py-2">
          <!-- Log Header -->
          <div class="d-flex align-center justify-space-between mb-1">
            <div class="d-flex align-center gap-2">
              <v-chip :color="getLevelColor(log.level)" size="x-small" variant="flat">
                {{ log.level }}
              </v-chip>
              <v-chip size="x-small" variant="outlined">
                {{ log.component }}
              </v-chip>
            </div>
            <span class="text-caption text-grey">
              {{ formatTimestamp(log.timestamp) }}
            </span>
          </div>

          <!-- Log Message -->
          <div class="log-message">{{ log.message }}</div>

          <!-- Context (if present) -->
          <div v-if="hasContext(log)" class="mt-2">
            <v-expansion-panels variant="accordion" density="compact">
              <v-expansion-panel>
                <v-expansion-panel-title class="text-caption">
                  View Context
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <pre class="context-data">{{ JSON.stringify(log.context, null, 2) }}</pre>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
        </v-card-text>
      </v-card>
    </v-container>
  </v-navigation-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useLogStore } from '@/stores/logStore';

const logStore = useLogStore();

// Local state
const searchQuery = ref('');
const selectedLevel = ref(null);
const selectedComponent = ref(null);
const minDisplayLevel = ref('INFO'); // Default: INFO
const consoleLogging = ref(false); // Default: OFF

// Computed properties
const isOpen = computed({
  get: () => logStore.isViewerOpen,
  set: (value) => {
    if (!value) {
      logStore.isViewerOpen = false;
    }
  },
});

const filteredLogs = computed(() => logStore.filteredLogs);

const logLevels = computed(() => ['DEBUG', 'INFO', 'WARN', 'ERROR']);

const minLevelOptions = computed(() => [
  { title: 'DEBUG (All)', value: 'DEBUG' },
  { title: 'INFO+', value: 'INFO' },
  { title: 'WARN+', value: 'WARN' },
  { title: 'ERROR Only', value: 'ERROR' },
]);

const componentNames = computed(() => logStore.componentNames);

// Watchers to sync with store filters
watch(searchQuery, (value) => {
  logStore.setFilter('search', value);
});

watch(selectedLevel, (value) => {
  logStore.setFilter('level', value);
});

watch(selectedComponent, (value) => {
  logStore.setFilter('component', value);
});

// Methods
const closeViewer = () => {
  logStore.toggleViewer();
};

const clearAllLogs = () => {
  if (confirm('Are you sure you want to clear all logs?')) {
    logStore.clearLogs();
  }
};

const exportLogs = () => {
  logStore.exportLogs();
};

const updateMinLevel = (levelName) => {
  window.logService.setMinLevel(levelName);
};

const toggleConsoleLogging = (enabled) => {
  window.logService.setConsoleEnabled(enabled);
};

const formatTimestamp = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleString();
};

const getLevelColor = (level) => {
  const colors = {
    DEBUG: 'grey',
    INFO: 'blue',
    WARN: 'orange',
    ERROR: 'red',
  };
  return colors[level] || 'grey';
};

const hasContext = (item) => {
  return item.context && Object.keys(item.context).length > 0;
};
</script>

<style scoped>
.log-viewer {
  z-index: 1000;
}

.log-entries {
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

.log-message {
  font-size: 0.875rem;
  line-height: 1.4;
  word-break: break-word;
}

.context-data {
  font-size: 0.75rem;
  font-family: 'Courier New', monospace;
  background-color: rgba(0, 0, 0, 0.05);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 200px;
}

.gap-2 {
  gap: 8px;
}
</style>
