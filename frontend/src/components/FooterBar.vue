<template>
  <v-footer app height="44" class="d-flex align-center justify-center px-4 text-caption">
    <!-- Backend Status -->
    <div class="d-flex align-center mr-auto">
      <v-btn
        variant="text"
        size="small"
        :aria-label="healthTooltip"
        :title="healthTooltip"
        @click="refreshHealth"
      >
        <v-icon :color="healthStatus.color" size="16" class="mr-2">
          {{ healthStatus.icon }}
        </v-icon>
        <span class="status-text">
          {{ healthStatus.text }}
          <span v-if="backendConnected" class="version-text"> | {{ responseTime }}ms </span>
        </span>
      </v-btn>
    </div>

    <!-- Footer Links -->
    <div class="d-flex align-center ml-auto">
      <!-- Internal Page Links (About, FAQ) -->
      <v-tooltip location="top" text="About HNF1B Database" aria-label="About HNF1B Database">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            to="/about"
            icon
            variant="text"
            size="small"
            class="mx-1"
            aria-label="About"
          >
            <v-icon size="small">mdi-information-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>

      <v-tooltip
        location="top"
        text="Frequently Asked Questions"
        aria-label="Frequently Asked Questions"
      >
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            to="/faq"
            icon
            variant="text"
            size="small"
            class="mx-1"
            aria-label="FAQ"
          >
            <v-icon size="small">mdi-frequently-asked-questions</v-icon>
          </v-btn>
        </template>
      </v-tooltip>

      <v-divider vertical class="mx-1" />

      <!-- External Links -->
      <v-btn
        v-for="link in footerLinks"
        :key="link.id"
        :href="link.url"
        :title="link.title"
        :aria-label="link.title"
        target="_blank"
        rel="noopener noreferrer"
        icon
        variant="text"
        size="small"
        class="mx-1"
      >
        <v-icon size="small">{{ link.icon }}</v-icon>
      </v-btn>

      <!-- Log Viewer Toggle -->
      <v-btn
        icon="mdi-text-box-search-outline"
        variant="text"
        size="small"
        aria-label="Open application logs"
        title="Open application logs"
        class="mx-1"
        @click="toggleLogViewer"
      />
    </div>
  </v-footer>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useLogStore } from '@/stores/logStore';
import { healthService } from '@/services/healthService';

// No need for frontend version or current year anymore

// Pinia store
const logStore = useLogStore();

// Reactive state
const footerLinks = ref([]);
const backendHealth = ref({
  connected: false,
  version: null,
  responseTime: null,
  lastCheck: null,
  error: null,
});

// Health service subscription
let unsubscribeHealth = null;

// Computed properties
const backendConnected = computed(() => backendHealth.value.connected);

const responseTime = computed(() => backendHealth.value.responseTime || 0);

const healthStatus = computed(() => {
  if (backendHealth.value.connected) {
    const rt = backendHealth.value.responseTime;
    if (rt < 100) {
      return {
        color: 'success',
        icon: 'mdi-check-circle',
        text: 'Excellent',
      };
    } else if (rt < 500) {
      return {
        color: 'success',
        icon: 'mdi-check-circle',
        text: 'Good',
      };
    } else {
      return {
        color: 'warning',
        icon: 'mdi-alert-circle',
        text: 'Slow',
      };
    }
  } else {
    return {
      color: 'error',
      icon: 'mdi-close-circle',
      text: 'Offline',
    };
  }
});

const healthTooltip = computed(() => {
  if (backendHealth.value.connected) {
    const lastCheck = backendHealth.value.lastCheck
      ? new Date(backendHealth.value.lastCheck).toLocaleTimeString()
      : 'Never';
    return `${healthStatus.value.text}, ${responseTime.value}ms response time, last check ${lastCheck}`;
  } else {
    const error = backendHealth.value.error || 'Unknown error';
    return `Backend Offline - ${error}`;
  }
});

// Methods
const toggleLogViewer = () => {
  logStore.toggleViewer();
};

const refreshHealth = async () => {
  await healthService.checkBackendHealth();
};

const loadFooterConfig = async () => {
  // Get API URL from environment variable, fallback to localhost for development
  const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v2';
  // Docs are mounted at /api/v2/docs in FastAPI, so append /docs to the base URL
  const apiDocsUrl = apiBaseUrl + '/docs';

  try {
    const response = await fetch('/config/footerConfig.json');
    const config = await response.json();

    // Replace placeholders with actual URLs
    footerLinks.value = config
      .filter((link) => link.enabled)
      .map((link) => ({
        ...link,
        url: link.url === '__API_DOCS_URL__' ? apiDocsUrl : link.url,
      }));

    window.logService.info('Footer configuration loaded', {
      linksCount: footerLinks.value.length,
    });
  } catch (error) {
    window.logService.error('Failed to load footer configuration', {
      error: error.message,
      path: '/config/footerConfig.json',
    });
    // Fallback to default links with environment-aware API docs URL
    footerLinks.value = [
      {
        id: 'github',
        title: 'GitHub Repository',
        icon: 'mdi-github',
        url: 'https://github.com/berntpopp/hnf1b-db',
      },
      {
        id: 'api-docs',
        title: 'API Documentation',
        icon: 'mdi-api',
        url: apiDocsUrl,
      },
      {
        id: 'license',
        title: 'CC BY 4.0 License',
        icon: 'mdi-creative-commons',
        url: 'https://creativecommons.org/licenses/by/4.0/',
      },
    ];
  }
};

// Lifecycle hooks
onMounted(() => {
  // Load footer configuration
  loadFooterConfig();

  // Subscribe to health service updates
  unsubscribeHealth = healthService.subscribe((status) => {
    backendHealth.value = status.backend;
  });

  // Get initial health status
  backendHealth.value = healthService.getStatus().backend;
});

onBeforeUnmount(() => {
  // Cleanup health subscription
  if (unsubscribeHealth) {
    unsubscribeHealth();
  }
});
</script>

<style scoped>
.status-text {
  font-size: 0.75rem;
}

.version-text {
  opacity: 0.7;
  font-weight: 500;
}
</style>
