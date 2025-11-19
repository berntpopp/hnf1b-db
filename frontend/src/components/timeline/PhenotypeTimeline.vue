<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-green-lighten-5 d-flex align-center">
      <v-icon class="mr-2">mdi-timeline-clock</v-icon>
      Phenotypic Features Timeline
      <v-spacer></v-spacer>
      <v-chip v-if="timelineData" color="success" size="small">
        {{ presentFeatures.length }} Features
      </v-chip>
    </v-card-title>

    <v-card-text>
      <div v-if="loading" class="d-flex justify-center align-center" style="min-height: 200px;">
        <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
      </div>

      <div v-else-if="error" class="d-flex flex-column align-center justify-center" style="min-height: 200px;">
        <v-icon size="64" color="error" class="mb-4">mdi-alert-circle</v-icon>
        <div class="text-h6 text-error mb-2">Failed to load timeline</div>
        <div class="text-body-2 text-grey">{{ error }}</div>
        <v-btn color="primary" class="mt-4" @click="fetchData">
          <v-icon left>mdi-refresh</v-icon>
          Retry
        </v-btn>
      </div>

      <div v-else-if="!timelineData || presentFeatures.length === 0" class="d-flex flex-column align-center justify-center" style="min-height: 200px;">
        <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-timeline-alert</v-icon>
        <div class="text-h6 text-grey mb-2">No timeline data available</div>
        <div class="text-body-2 text-grey">No phenotypic features with onset information found.</div>
      </div>

      <div v-else>
        <!-- Timeline visualization using Vuetify timeline -->
        <v-timeline density="compact" side="end" align="start">
          <v-timeline-item
            v-for="(group, index) in groupedFeatures"
            :key="index"
            dot-color="success"
            size="small"
          >
            <template #opposite>
              <div class="text-caption text-grey font-weight-bold">
                {{ group.onsetLabel }}
              </div>
            </template>
            <div>
              <!-- Onset period header -->
              <div class="text-subtitle-2 font-weight-bold mb-2">
                {{ group.onsetLabel }}
                <v-chip size="x-small" color="success" variant="flat" class="ml-2">
                  {{ group.features.length }} feature{{ group.features.length !== 1 ? 's' : '' }}
                </v-chip>
              </div>

              <!-- Features in this onset period -->
              <v-list density="compact">
                <v-list-item
                  v-for="(feature, fIndex) in group.features"
                  :key="fIndex"
                  class="px-0"
                >
                  <template #prepend>
                    <v-avatar :color="feature.categoryColor" size="24">
                      <v-icon size="x-small" color="white">mdi-check-circle</v-icon>
                    </v-avatar>
                  </template>

                  <v-list-item-title class="text-body-2">
                    {{ feature.label }}
                  </v-list-item-title>

                  <v-list-item-subtitle class="text-caption">
                    <v-chip
                      :href="`https://hpo.jax.org/app/browse/term/${feature.hpo_id}`"
                      target="_blank"
                      color="green-lighten-4"
                      size="x-small"
                      variant="flat"
                      link
                      class="mr-1"
                    >
                      <v-icon left size="x-small">mdi-open-in-new</v-icon>
                      {{ feature.hpo_id }}
                    </v-chip>

                    <span v-if="feature.severity" class="ml-1">
                      • Severity: {{ feature.severity }}
                    </span>

                    <!-- Evidence sources -->
                    <span v-if="feature.evidence && feature.evidence.length > 0" class="ml-1">
                      • Sources:
                      <v-chip
                        v-for="(ev, evIndex) in feature.evidence"
                        :key="evIndex"
                        :to="ev.pmid ? `/publications/${ev.pmid}` : undefined"
                        size="x-small"
                        color="blue-lighten-4"
                        variant="flat"
                        :link="!!ev.pmid"
                        class="ml-1"
                      >
                        <v-icon v-if="ev.pmid" left size="x-small">mdi-file-document</v-icon>
                        PMID:{{ ev.pmid || 'Unknown' }}
                      </v-chip>
                    </span>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </div>
          </v-timeline-item>
        </v-timeline>

        <!-- Legend -->
        <v-divider class="my-4" />
        <div class="text-caption text-grey mb-2">Organ System Categories:</div>
        <div class="d-flex flex-wrap gap-2">
          <v-chip
            v-for="category in ORGAN_SYSTEMS"
            :key="category.value"
            :color="category.color"
            size="small"
            variant="flat"
          >
            {{ category.label }}
          </v-chip>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import API from '@/api';
import { parseAge, formatAge, getCategoryColor, onsetClassToAge, getOrganSystem, ORGAN_SYSTEMS } from '@/utils/ageParser';

const props = defineProps({
  phenopacketId: {
    type: String,
    required: true
  }
});

const loading = ref(true);
const error = ref(null);
const timelineData = ref(null);

// Filter out excluded features (absent phenotypes)
const presentFeatures = computed(() => {
  if (!timelineData.value) return [];
  return timelineData.value.features.filter(f => !f.excluded);
});

// Group features by onset period
const groupedFeatures = computed(() => {
  if (!presentFeatures.value || presentFeatures.value.length === 0) return [];

  // Parse ages and assign onset labels
  const featuresWithAges = presentFeatures.value.map(f => {
    let age = null;
    let onsetLabel = 'Unknown onset';
    let sortOrder = 999; // For unknown/unspecified

    if (f.onset_age) {
      age = parseAge(f.onset_age);
    } else if (f.onset_label) {
      age = onsetClassToAge(f.onset_label);
    }

    // Determine onset label and sort order
    if (f.onset_label) {
      onsetLabel = f.onset_label;

      // Assign sort order based on onset classification
      if (onsetLabel.toLowerCase().includes('prenatal') || onsetLabel.toLowerCase().includes('fetal')) {
        sortOrder = 0;
      } else if (onsetLabel.toLowerCase().includes('congenital') || onsetLabel.toLowerCase().includes('birth')) {
        sortOrder = 1;
      } else if (onsetLabel.toLowerCase().includes('neonatal')) {
        sortOrder = 2;
      } else if (onsetLabel.toLowerCase().includes('infantile') || onsetLabel.toLowerCase().includes('infant')) {
        sortOrder = 3;
      } else if (onsetLabel.toLowerCase().includes('childhood') || onsetLabel.toLowerCase().includes('child')) {
        sortOrder = 4;
      } else if (onsetLabel.toLowerCase().includes('juvenile')) {
        sortOrder = 5;
      } else if (onsetLabel.toLowerCase().includes('adult')) {
        sortOrder = 6;
      } else if (onsetLabel.toLowerCase().includes('late')) {
        sortOrder = 7;
      } else if (onsetLabel.toLowerCase().includes('postnatal')) {
        sortOrder = 8; // Postnatal is general, comes after specific periods
      }
    } else if (age !== null) {
      // If we only have age, create a label
      if (age < 0) {
        onsetLabel = 'Prenatal onset';
        sortOrder = 0;
      } else if (age === 0) {
        onsetLabel = 'Birth';
        sortOrder = 1;
      } else if (age < 1/12) {
        onsetLabel = 'Neonatal onset';
        sortOrder = 2;
      } else if (age < 1) {
        onsetLabel = 'Infantile onset';
        sortOrder = 3;
      } else if (age < 5) {
        onsetLabel = 'Childhood onset';
        sortOrder = 4;
      } else if (age < 16) {
        onsetLabel = 'Juvenile onset';
        sortOrder = 5;
      } else {
        onsetLabel = 'Adult onset';
        sortOrder = 6;
      }
    }

    // Determine proper organ system category from HPO ID
    const category = getOrganSystem(f.hpo_id);
    const categoryColor = getCategoryColor(category);

    return {
      ...f,
      age,
      onsetLabel,
      sortOrder,
      category,
      categoryColor
    };
  });

  // Group by onset label
  const groups = {};
  featuresWithAges.forEach(feature => {
    const key = feature.onsetLabel;
    if (!groups[key]) {
      groups[key] = {
        onsetLabel: key,
        sortOrder: feature.sortOrder,
        features: []
      };
    }
    groups[key].features.push(feature);
  });

  // Convert to array and sort by onset order
  const groupedArray = Object.values(groups);
  groupedArray.sort((a, b) => a.sortOrder - b.sortOrder);

  return groupedArray;
});

async function fetchData() {
  loading.value = true;
  error.value = null;
  try {
    const response = await API.getPhenotypeTimeline(props.phenopacketId);
    timelineData.value = response.data;
    window.logService.debug('Phenotype timeline data received', {
      totalFeatures: timelineData.value.features?.length,
      presentFeatures: presentFeatures.value.length,
    });

    // Debug will be logged after computed properties run
  } catch (err) {
    window.logService.error('Error fetching phenotype timeline', {
      error: err.message,
    });
    error.value = err.message || 'An error occurred while fetching data';
  } finally {
    loading.value = false;
  }
}

// Debug watcher to log category assignments
watch(groupedFeatures, (groups) => {
  if (groups && groups.length > 0) {
    const firstGroup = groups[0];
    if (firstGroup.features && firstGroup.features.length > 0) {
      const sampleFeatures = firstGroup.features.slice(0, 3).map(f => ({
        hpo_id: f.hpo_id,
        label: f.label,
        category: f.category,
        categoryColor: f.categoryColor
      }));
      window.logService.debug('Sample feature categories from first onset group', {
        onsetLabel: firstGroup.onsetLabel,
        sampleFeatures
      });
    }
  }
}, { immediate: true });

onMounted(async () => {
  await fetchData();
});
</script>

<style scoped>
/* Add any custom styles here if needed */
</style>
