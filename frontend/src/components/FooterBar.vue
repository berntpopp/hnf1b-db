<template>
  <v-footer
    app
    height="44"
    class="d-flex align-center justify-center text-caption"
    :class="xs ? 'footer-compact px-1' : 'px-4'"
  >
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
        <span v-if="!xs" class="status-text">
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

      <!-- MCP Access (internal page) — sits next to the API docs link -->
      <v-tooltip
        location="top"
        text="Connect an AI agent (MCP)"
        aria-label="Connect an AI agent (MCP)"
      >
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            to="/mcp"
            icon
            variant="text"
            size="small"
            class="mx-1"
            aria-label="MCP access"
          >
            <v-icon size="small">mdi-robot-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>

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
import { useDisplay } from 'vuetify';
import { useLogStore } from '@/stores/logStore';
import { healthService } from '@/services/healthService';

// Extra-small screens get a compact footer (tighter icons, no "| Nms" suffix)
// so the status text + link icons fit within 360px without clipping.
const { xs } = useDisplay();

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

// Keep the API docs link last among external links so the internal MCP button
// (rendered immediately after the external-link loop) is always adjacent to it,
// regardless of footerConfig.json ordering.
const sortApiDocsLast = (links) => {
  const apiIndex = links.findIndex((link) => link.id === 'api-docs');
  if (apiIndex === -1) {
    return links;
  }
  const reordered = [...links];
  reordered.push(reordered.splice(apiIndex, 1)[0]);
  return reordered;
};

const loadFooterConfig = async () => {
  const rawApi = import.meta.env.VITE_API_URL || '';
  const isProd = import.meta.env.PROD === true;

  let apiDocsUrl = null;
  if (rawApi) {
    apiDocsUrl = rawApi.replace(/\/+$/, '') + '/docs';
  } else if (!isProd) {
    // Dev fallback — acceptable because localhost:8000 is the dev backend.
    apiDocsUrl = 'http://localhost:8000/api/v2/docs';
  } else {
    window.logService.warn('API docs URL not configured (VITE_API_URL unset)', {
      env: 'production',
    });
  }

  try {
    const response = await fetch('/config/footerConfig.json');
    const config = await response.json();

    footerLinks.value = sortApiDocsLast(
      config
        .filter((link) => link.enabled)
        .map((link) => ({
          ...link,
          url: link.url === '__API_DOCS_URL__' ? apiDocsUrl : link.url,
        }))
        .filter((link) => link.url) // drop entries with null URL (unconfigured API docs)
    );

    window.logService.info('Footer configuration loaded', {
      linksCount: footerLinks.value.length,
    });
  } catch (error) {
    window.logService.error('Failed to load footer configuration', {
      error: error.message,
      path: '/config/footerConfig.json',
    });
    // Fallback to default links; API docs entry is filtered if unconfigured.
    footerLinks.value = sortApiDocsLast([
      {
        id: 'github',
        title: 'GitHub Repository',
        icon: 'mdi-github',
        url: 'https://github.com/berntpopp/hnf1b-db',
      },
      {
        id: 'license',
        title: 'CC BY 4.0 License',
        icon: 'mdi-creative-commons',
        url: 'https://creativecommons.org/licenses/by/4.0/',
      },
      ...(apiDocsUrl
        ? [
            {
              id: 'api-docs',
              title: 'API Documentation',
              icon: 'mdi-api',
              url: apiDocsUrl,
            },
          ]
        : []),
    ]);
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

/* Compact footer for xs: tighten icon spacing and divider so the status text
   and all link icons fit within 360px with no clipping. */
.footer-compact :deep(.v-btn.mx-1) {
  margin-left: 1px !important;
  margin-right: 1px !important;
}

.footer-compact :deep(.v-divider) {
  margin-left: 2px !important;
  margin-right: 2px !important;
}
</style>
