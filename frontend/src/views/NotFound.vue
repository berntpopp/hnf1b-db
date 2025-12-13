<!-- src/views/NotFound.vue -->
<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="6" lg="4">
        <v-card class="elevation-12 text-center pa-8" rounded="lg">
          <!-- 404 Icon -->
          <v-avatar color="error" size="100" class="mb-6">
            <v-icon size="60" color="white">mdi-alert-circle-outline</v-icon>
          </v-avatar>

          <!-- Error Code -->
          <h1 class="text-h2 font-weight-bold text-error mb-2">404</h1>

          <!-- Error Title -->
          <h2 class="text-h5 font-weight-medium text-grey-darken-2 mb-4">Page Not Found</h2>

          <!-- Error Description -->
          <p class="text-body-1 text-grey-darken-1 mb-6">
            The page you're looking for doesn't exist or has been moved. This might happen if:
          </p>

          <v-list density="compact" class="text-left mx-auto mb-6" style="max-width: 300px">
            <v-list-item>
              <template #prepend>
                <v-icon size="small" color="grey">mdi-chevron-right</v-icon>
              </template>
              <v-list-item-title class="text-body-2 text-grey-darken-1">
                The URL was typed incorrectly
              </v-list-item-title>
            </v-list-item>
            <v-list-item>
              <template #prepend>
                <v-icon size="small" color="grey">mdi-chevron-right</v-icon>
              </template>
              <v-list-item-title class="text-body-2 text-grey-darken-1">
                The resource has been deleted
              </v-list-item-title>
            </v-list-item>
            <v-list-item>
              <template #prepend>
                <v-icon size="small" color="grey">mdi-chevron-right</v-icon>
              </template>
              <v-list-item-title class="text-body-2 text-grey-darken-1">
                You followed an outdated link
              </v-list-item-title>
            </v-list-item>
          </v-list>

          <!-- Navigation Buttons -->
          <div class="d-flex flex-column flex-sm-row justify-center gap-3">
            <v-btn color="primary" size="large" variant="elevated" :to="{ name: 'Home' }">
              <v-icon left>mdi-home</v-icon>
              Go Home
            </v-btn>
            <v-btn color="secondary" size="large" variant="outlined" @click="goBack">
              <v-icon left>mdi-arrow-left</v-icon>
              Go Back
            </v-btn>
          </div>

          <!-- Additional Help -->
          <v-divider class="my-6" />

          <p class="text-caption text-grey">Looking for something specific? Try these:</p>

          <div class="d-flex flex-wrap justify-center gap-2 mt-3">
            <v-chip :to="{ name: 'Phenopackets' }" color="teal" variant="outlined" size="small">
              <v-icon left size="small">mdi-card-account-details</v-icon>
              Phenopackets
            </v-chip>
            <v-chip :to="{ name: 'Variants' }" color="pink" variant="outlined" size="small">
              <v-icon left size="small">mdi-dna</v-icon>
              Variants
            </v-chip>
            <v-chip :to="{ name: 'Publications' }" color="blue" variant="outlined" size="small">
              <v-icon left size="small">mdi-file-document</v-icon>
              Publications
            </v-chip>
            <v-chip :to="{ name: 'Aggregations' }" color="purple" variant="outlined" size="small">
              <v-icon left size="small">mdi-chart-bar</v-icon>
              Statistics
            </v-chip>
          </div>
        </v-card>

        <!-- Requested Path (for debugging) -->
        <p v-if="requestedPath" class="text-center text-caption text-grey mt-4">
          Requested: <code class="text-error">{{ requestedPath }}</code>
        </p>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { useHead, useSeoMeta } from '@unhead/vue';
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

export default {
  name: 'NotFound',
  setup() {
    const route = useRoute();
    const router = useRouter();

    const requestedPath = computed(() => route.fullPath);

    // SEO: Tell crawlers not to index 404 pages
    // This is the proper client-side solution for SPAs
    useSeoMeta({
      title: 'Page Not Found | HNF1B Database',
      description: 'The requested page could not be found.',
      robots: 'noindex, nofollow',
    });

    // Add prerender status code hint for prerendering services
    useHead({
      meta: [
        { name: 'prerender-status-code', content: '404' },
      ],
    });

    // Log the 404 event
    window.logService.warn('404 Page Not Found', {
      path: route.fullPath,
      referrer: document.referrer || 'direct',
    });

    const goBack = () => {
      // Go back in history, or go home if no history
      if (window.history.length > 2) {
        router.go(-1);
      } else {
        router.push({ name: 'Home' });
      }
    };

    return {
      requestedPath,
      goBack,
    };
  },
};
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}
</style>
