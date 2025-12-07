<!-- src/views/PagePhenopacket.vue -->
<template>
  <div class="phenopacket-container">
    <!-- HERO SECTION - Compact Phenopacket Header -->
    <section class="hero-section py-2 px-4 mb-2">
      <v-container>
        <v-row justify="center" align="center">
          <v-col cols="12" xl="10">
            <!-- Compact Header with Breadcrumbs + Title + Stats inline -->
            <div class="d-flex align-center flex-wrap gap-2 mb-2">
              <v-btn
                icon="mdi-arrow-left"
                variant="text"
                size="small"
                aria-label="Go back to previous page"
                @click="$router.back()"
              />
              <v-breadcrumbs :items="breadcrumbs" class="pa-0 flex-grow-0" density="compact" />
            </div>

            <!-- Title Row with Inline Stats Chips -->
            <div class="d-flex flex-wrap align-center gap-3">
              <v-icon color="teal-darken-2" size="large" aria-hidden="true">
                mdi-account-details
              </v-icon>
              <div class="flex-grow-1">
                <div class="d-flex flex-wrap align-center gap-2">
                  <h1 class="text-h6 font-weight-bold text-teal-darken-2 ma-0">
                    Individual Details
                  </h1>
                  <!-- Loading skeleton -->
                  <template v-if="loading">
                    <v-skeleton-loader type="chip" width="80" class="ma-0" />
                    <v-skeleton-loader type="chip" width="60" class="ma-0" />
                  </template>
                  <!-- Loaded: Inline Stats Chips -->
                  <template v-else-if="phenopacket">
                    <v-chip
                      color="teal-lighten-4"
                      size="small"
                      variant="flat"
                      class="font-weight-medium"
                    >
                      {{ phenopacket.id }}
                    </v-chip>
                    <v-chip
                      v-if="subjectSex"
                      :color="getSexChipColor(subjectSex)"
                      size="small"
                      variant="flat"
                    >
                      <v-icon start size="x-small" aria-hidden="true">
                        {{ getSexIcon(subjectSex) }}
                      </v-icon>
                      {{ formatSex(subjectSex) }}
                    </v-chip>
                    <v-chip
                      v-if="ageDisplay !== 'N/A'"
                      color="amber-lighten-4"
                      size="small"
                      variant="flat"
                    >
                      <v-icon start size="x-small" aria-hidden="true">mdi-calendar-clock</v-icon>
                      {{ ageDisplay }}
                    </v-chip>
                    <v-chip color="green-lighten-4" size="small" variant="flat">
                      <v-icon start size="x-small" aria-hidden="true">
                        mdi-format-list-checks
                      </v-icon>
                      {{ phenotypicFeaturesCount }} HPO
                    </v-chip>
                    <v-chip
                      v-if="variantsCount > 0"
                      color="red-lighten-4"
                      size="small"
                      variant="flat"
                    >
                      <v-icon start size="x-small" aria-hidden="true">mdi-dna</v-icon>
                      {{ variantsCount }} Variant{{ variantsCount === 1 ? '' : 's' }}
                    </v-chip>
                  </template>
                </div>
              </div>
            </div>
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- MAIN CONTENT -->
    <v-container class="pb-12">
      <v-row justify="center">
        <v-col cols="12" xl="10">
          <!-- Error State -->
          <v-alert v-if="error" type="error" variant="tonal" prominent class="mb-6">
            <v-alert-title>Error Loading Phenopacket</v-alert-title>
            {{ error }}
          </v-alert>

          <!-- Main Content Card -->
          <v-card v-else-if="phenopacket" variant="outlined" class="border-opacity-12" rounded="lg">
            <!-- Action Bar -->
            <div class="d-flex align-center flex-wrap px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="teal-darken-2" class="mr-2" aria-hidden="true">
                mdi-file-document
              </v-icon>
              <span class="text-h6 font-weight-medium">Phenopacket Data</span>
              <v-spacer />
              <v-btn
                color="teal-darken-2"
                prepend-icon="mdi-download"
                variant="tonal"
                size="small"
                class="mr-2"
                aria-label="Download phenopacket as JSON file"
                @click="downloadJSON"
              >
                Download
              </v-btn>
              <v-btn
                v-if="canEdit"
                color="success"
                prepend-icon="mdi-pencil"
                variant="tonal"
                size="small"
                class="mr-2"
                aria-label="Edit this phenopacket"
                @click="navigateToEdit"
              >
                Edit
              </v-btn>
              <v-btn
                v-if="canDelete"
                color="error"
                prepend-icon="mdi-delete"
                variant="tonal"
                size="small"
                aria-label="Delete this phenopacket"
                @click="confirmDelete"
              >
                Delete
              </v-btn>
            </div>

            <!-- Tabs for different views -->
            <v-tabs
              v-model="activeTab"
              color="teal-darken-2"
              align-tabs="start"
              class="px-4"
              aria-label="Phenopacket data sections"
            >
              <v-tab value="overview" aria-label="Overview tab">Overview</v-tab>
              <v-tab value="timeline" aria-label="Timeline tab">Timeline</v-tab>
              <v-tab value="raw" aria-label="Raw JSON tab">Raw JSON</v-tab>
            </v-tabs>

            <v-card-text class="pa-4">
              <v-tabs-window v-model="activeTab">
                <!-- Overview Tab -->
                <v-tabs-window-item value="overview">
                  <!-- Primary 3-column grid for main cards (Subject, Features, Interpretations) -->
                  <div class="primary-cards-grid">
                    <!-- Subject Card -->
                    <div v-if="phenopacket.subject" class="card-wrapper">
                      <SubjectCard :subject="phenopacket.subject" />
                    </div>

                    <!-- Phenotypic Features Card -->
                    <div v-if="hasPhenotypicFeatures" class="card-wrapper">
                      <PhenotypicFeaturesCard :features="phenopacket.phenotypicFeatures" />
                    </div>

                    <!-- Interpretations Card -->
                    <div v-if="hasInterpretations" class="card-wrapper">
                      <InterpretationsCard :interpretations="phenopacket.interpretations" />
                    </div>
                  </div>

                  <!-- Secondary cards row -->
                  <v-row v-if="hasMeasurements || phenopacket.metaData" class="mt-4">
                    <!-- Measurements Card -->
                    <v-col v-if="hasMeasurements" cols="12" md="6">
                      <MeasurementsCard :measurements="phenopacket.measurements" />
                    </v-col>

                    <!-- Metadata Card -->
                    <v-col cols="12" :md="hasMeasurements ? 6 : 12">
                      <MetadataCard v-if="phenopacket.metaData" :meta-data="phenopacket.metaData" />
                    </v-col>
                  </v-row>
                </v-tabs-window-item>

                <!-- Timeline Tab -->
                <v-tabs-window-item value="timeline">
                  <PhenotypeTimeline :phenopacket-id="phenopacket.id" />
                </v-tabs-window-item>

                <!-- Raw JSON Tab -->
                <v-tabs-window-item value="raw">
                  <v-card variant="outlined" rounded="lg">
                    <div class="d-flex align-center px-4 py-2 bg-grey-lighten-4 border-bottom">
                      <v-icon class="mr-2" aria-hidden="true">mdi-code-json</v-icon>
                      <span class="font-weight-medium">GA4GH Phenopacket v2 JSON</span>
                      <v-spacer />
                      <v-btn
                        size="small"
                        color="teal-darken-2"
                        variant="tonal"
                        prepend-icon="mdi-content-copy"
                        aria-label="Copy JSON to clipboard"
                        @click="copyToClipboard"
                      >
                        Copy
                      </v-btn>
                    </div>
                    <v-card-text class="pa-0">
                      <pre class="json-display">{{ JSON.stringify(phenopacket, null, 2) }}</pre>
                    </v-card-text>
                  </v-card>
                </v-tabs-window-item>
              </v-tabs-window>
            </v-card-text>
          </v-card>

          <!-- Loading State -->
          <v-card v-else variant="outlined" class="border-opacity-12" rounded="lg">
            <v-card-text class="text-center py-12">
              <v-progress-circular
                indeterminate
                color="teal-darken-2"
                size="64"
                aria-label="Loading phenopacket data"
              />
              <div class="mt-4 text-medium-emphasis">Loading phenopacket...</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>

    <!-- Delete Confirmation Dialog -->
    <DeleteConfirmationDialog
      v-if="phenopacket"
      v-model="showDeleteDialog"
      :phenopacket-id="phenopacket.id"
      :subject-id="phenopacket.subject?.id"
      :loading="deleteLoading"
      @confirm="handleDeleteConfirm"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<script>
import { getPhenopacket, deletePhenopacket } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';
import SubjectCard from '@/components/phenopacket/SubjectCard.vue';
import PhenotypicFeaturesCard from '@/components/phenopacket/PhenotypicFeaturesCard.vue';
import InterpretationsCard from '@/components/phenopacket/InterpretationsCard.vue';
import MeasurementsCard from '@/components/phenopacket/MeasurementsCard.vue';
import MetadataCard from '@/components/phenopacket/MetadataCard.vue';
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue';
import PhenotypeTimeline from '@/components/timeline/PhenotypeTimeline.vue';

export default {
  name: 'PagePhenopacket',
  components: {
    SubjectCard,
    PhenotypicFeaturesCard,
    InterpretationsCard,
    MeasurementsCard,
    MetadataCard,
    DeleteConfirmationDialog,
    PhenotypeTimeline,
  },
  data() {
    return {
      phenopacket: null,
      loading: false,
      error: null,
      showDeleteDialog: false,
      deleteLoading: false,
      activeTab: 'overview',
    };
  },
  computed: {
    /**
     * Breadcrumb navigation items.
     */
    breadcrumbs() {
      return [
        { title: 'Home', to: '/' },
        { title: 'Individuals', to: '/phenopackets' },
        {
          title: this.phenopacket?.id || 'Loading...',
          disabled: true,
        },
      ];
    },

    /**
     * Subject sex from phenopacket.
     */
    subjectSex() {
      return this.phenopacket?.subject?.sex || 'UNKNOWN_SEX';
    },

    /**
     * Age display string (age at last encounter or time at last encounter).
     */
    ageDisplay() {
      const subject = this.phenopacket?.subject;
      if (!subject) return 'N/A';

      // Try timeAtLastEncounter first (ISO8601 duration format)
      if (subject.timeAtLastEncounter?.age?.iso8601duration) {
        return this.formatISO8601Duration(subject.timeAtLastEncounter.age.iso8601duration);
      }

      // Try vitalStatus.timeOfDeath if deceased
      if (subject.vitalStatus?.timeOfDeath?.age?.iso8601duration) {
        return this.formatISO8601Duration(subject.vitalStatus.timeOfDeath.age.iso8601duration);
      }

      return 'N/A';
    },

    /**
     * Count of phenotypic features (HPO terms).
     */
    phenotypicFeaturesCount() {
      return this.phenopacket?.phenotypicFeatures?.length || 0;
    },

    /**
     * Count of variants from interpretations.
     */
    variantsCount() {
      if (!this.phenopacket?.interpretations) return 0;

      let count = 0;
      for (const interp of this.phenopacket.interpretations) {
        if (interp.diagnosis?.genomicInterpretations) {
          count += interp.diagnosis.genomicInterpretations.length;
        }
      }
      return count;
    },

    hasPhenotypicFeatures() {
      return this.phenopacket?.phenotypicFeatures && this.phenopacket.phenotypicFeatures.length > 0;
    },
    hasInterpretations() {
      return this.phenopacket?.interpretations && this.phenopacket.interpretations.length > 0;
    },
    hasMeasurements() {
      return this.phenopacket?.measurements && this.phenopacket.measurements.length > 0;
    },
    canEdit() {
      const authStore = useAuthStore();
      const userRole = authStore.user?.role;
      return userRole === 'curator' || userRole === 'admin';
    },
    canDelete() {
      const authStore = useAuthStore();
      const userRole = authStore.user?.role;
      return userRole === 'curator' || userRole === 'admin';
    },
  },
  mounted() {
    this.fetchPhenopacket();
  },
  methods: {
    // Sex utility methods (re-export for template use)
    getSexIcon,
    getSexChipColor,
    formatSex,

    /**
     * Format ISO8601 duration string to human-readable format.
     * E.g., "P32Y" -> "32 years", "P5Y6M" -> "5y 6m"
     *
     * @param {string} duration - ISO8601 duration (e.g., "P32Y", "P5Y6M")
     * @returns {string} Formatted age string
     */
    formatISO8601Duration(duration) {
      if (!duration) return 'N/A';

      // Parse ISO8601 duration format: P[n]Y[n]M[n]D
      const match = duration.match(/P(\d+)Y(?:(\d+)M)?(?:(\d+)D)?/);
      if (match) {
        const years = parseInt(match[1]) || 0;
        const months = parseInt(match[2]) || 0;

        if (months > 0) {
          return `${years}y ${months}m`;
        }
        return `${years} years`;
      }

      // Handle months only: P[n]M
      const monthsMatch = duration.match(/P(\d+)M/);
      if (monthsMatch) {
        return `${monthsMatch[1]} months`;
      }

      // Handle weeks: P[n]W
      const weeksMatch = duration.match(/P(\d+)W/);
      if (weeksMatch) {
        return `${weeksMatch[1]} weeks`;
      }

      // Handle days: P[n]D
      const daysMatch = duration.match(/P(\d+)D/);
      if (daysMatch) {
        return `${daysMatch[1]} days`;
      }

      return duration; // Return as-is if no pattern matched
    },

    async fetchPhenopacket() {
      this.loading = true;
      this.error = null;

      const phenopacketId = this.$route.params.phenopacket_id;
      window.logService.debug('Loading phenopacket detail page', {
        phenopacketId: phenopacketId,
        route: this.$route.path,
      });

      try {
        const response = await getPhenopacket(phenopacketId);
        // Backend returns the GA4GH phenopacket object nested under 'phenopacket' key
        this.phenopacket = response.data.phenopacket;

        window.logService.debug('Phenopacket data received', {
          phenopacketId: phenopacketId,
          dataStructure: Object.keys(this.phenopacket),
          subjectId: this.phenopacket.subject?.id,
          featuresCount: this.phenopacket.phenotypicFeatures?.length || 0,
          interpretationsCount: this.phenopacket.interpretations?.length || 0,
          measurementsCount: this.phenopacket.measurements?.length || 0,
        });

        window.logService.info('Phenopacket loaded successfully', {
          phenopacketId: phenopacketId,
          hasFeatures: this.hasPhenotypicFeatures,
          hasInterpretations: this.hasInterpretations,
          hasMeasurements: this.hasMeasurements,
        });
      } catch (error) {
        window.logService.error('Failed to fetch phenopacket', {
          error: error.message,
          phenopacketId: this.$route.params.phenopacket_id,
          status: error.response?.status,
        });
        this.error =
          error.response?.status === 404
            ? `Phenopacket '${this.$route.params.phenopacket_id}' not found.`
            : 'Failed to load phenopacket. Please try again later.';
      } finally {
        this.loading = false;
      }
    },

    downloadJSON() {
      if (!this.phenopacket) return;

      const dataStr = JSON.stringify(this.phenopacket, null, 2);
      const fileSizeKB = (new Blob([dataStr]).size / 1024).toFixed(2);

      window.logService.debug('Preparing phenopacket JSON download', {
        phenopacketId: this.phenopacket.id,
        fileName: `${this.phenopacket.id}.json`,
        fileSizeKB: fileSizeKB,
        dataStructure: Object.keys(this.phenopacket),
      });

      window.logService.info('Phenopacket JSON downloaded', {
        phenopacketId: this.phenopacket.id,
        fileName: `${this.phenopacket.id}.json`,
      });

      const blob = new Blob([dataStr], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${this.phenopacket.id}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },

    copyToClipboard() {
      if (!this.phenopacket) return;

      const jsonString = JSON.stringify(this.phenopacket, null, 2);
      navigator.clipboard
        .writeText(jsonString)
        .then(() => {
          window.logService.info('Phenopacket JSON copied to clipboard', {
            phenopacketId: this.phenopacket.id,
          });
          // Could add a toast notification here
        })
        .catch((err) => {
          window.logService.error('Failed to copy JSON to clipboard', {
            error: err.message,
          });
        });
    },

    navigateToEdit() {
      if (!this.phenopacket) return;
      window.logService.info('Navigating to edit phenopacket', {
        phenopacketId: this.phenopacket.id,
      });
      this.$router.push(`/phenopackets/${this.phenopacket.id}/edit`);
    },

    confirmDelete() {
      if (!this.phenopacket) return;
      this.showDeleteDialog = true;
    },

    async handleDeleteConfirm(deleteReason) {
      if (!this.phenopacket) return;

      this.deleteLoading = true;

      window.logService.info('Deleting phenopacket', {
        phenopacketId: this.phenopacket.id,
        reasonLength: deleteReason.length,
      });

      try {
        await deletePhenopacket(this.phenopacket.id, deleteReason);

        window.logService.info('Phenopacket deleted successfully', {
          phenopacketId: this.phenopacket.id,
        });

        this.showDeleteDialog = false;

        // Navigate back to list with success message
        this.$router.push({
          path: '/phenopackets',
          query: { deleted: this.phenopacket.id },
        });
      } catch (error) {
        window.logService.error('Failed to delete phenopacket', {
          phenopacketId: this.phenopacket.id,
          error: error.message,
          status: error.response?.status,
        });

        // Show error in dialog or alert
        alert(`Failed to delete phenopacket: ${error.response?.data?.detail || error.message}`);
      } finally {
        this.deleteLoading = false;
      }
    },
  },
};
</script>

<style scoped>
.phenopacket-container {
  min-height: 100vh;
  background-color: #fafafa;
}

.hero-section {
  background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 50%, #f5f7fa 100%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.border-bottom {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.border-opacity-12 {
  border-color: rgba(0, 0, 0, 0.12) !important;
}

.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}

.json-display {
  background-color: #f5f5f5;
  border-radius: 0 0 8px 8px;
  padding: 16px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  overflow-x: auto;
  max-height: 600px;
  overflow-y: auto;
  margin: 0;
}

/* Primary 3-column grid layout for main cards */
.primary-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  align-items: stretch;
}

.card-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Ensure cards fill their wrapper height */
.card-wrapper :deep(.v-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-wrapper :deep(.v-card-text) {
  flex: 1;
  overflow-y: auto;
}

/* Responsive: 2 columns on medium screens */
@media (max-width: 1200px) {
  .primary-cards-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Responsive: 1 column on small screens */
@media (max-width: 768px) {
  .primary-cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
