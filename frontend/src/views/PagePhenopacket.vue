<!-- src/views/PagePhenopacket.vue -->
<template>
  <v-container fluid>
    <!-- Loading State -->
    <v-row v-if="loading" justify="center">
      <v-col cols="12" class="text-center">
        <v-progress-circular indeterminate color="primary" size="64" />
        <div class="mt-4">Loading phenopacket...</div>
      </v-col>
    </v-row>

    <!-- Error State -->
    <v-row v-else-if="error" justify="center">
      <v-col cols="12" md="8">
        <v-alert type="error" variant="tonal" prominent>
          <v-alert-title>Error Loading Phenopacket</v-alert-title>
          {{ error }}
        </v-alert>
        <v-btn class="mt-4" color="primary" @click="$router.push('/phenopackets')">
          Back to List
        </v-btn>
      </v-col>
    </v-row>

    <!-- Main Content -->
    <div v-else-if="phenopacket">
      <!-- Header -->
      <v-row>
        <v-col cols="12">
          <v-card flat class="mb-4">
            <v-card-title class="text-h4">
              <v-icon left color="primary" size="large"> mdi-file-document </v-icon>
              {{ phenopacket.id }}
            </v-card-title>
            <v-card-subtitle class="text-h6">
              Subject: {{ phenopacket.subject?.id || 'N/A' }}
            </v-card-subtitle>
            <v-card-actions>
              <v-btn
                color="primary"
                prepend-icon="mdi-download"
                variant="tonal"
                @click="downloadJSON"
              >
                Download JSON
              </v-btn>
              <!-- Edit button (curator/admin only) -->
              <v-btn
                v-if="canEdit"
                class="ml-2"
                color="success"
                prepend-icon="mdi-pencil"
                variant="tonal"
                @click="navigateToEdit"
              >
                Edit
              </v-btn>
              <!-- Delete button (curator/admin only) -->
              <v-btn
                v-if="canDelete"
                class="ml-2"
                color="error"
                prepend-icon="mdi-delete"
                variant="tonal"
                @click="confirmDelete"
              >
                Delete
              </v-btn>
              <v-spacer />
              <v-btn
                class="ml-2"
                prepend-icon="mdi-arrow-left"
                @click="$router.push('/phenopackets')"
              >
                Back to List
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>

      <!-- Content Cards in Compact Layout -->
      <v-row dense>
        <!-- Subject Card -->
        <v-col cols="12" md="6" class="py-1">
          <SubjectCard v-if="phenopacket.subject" :subject="phenopacket.subject" />
        </v-col>

        <!-- Phenotypic Features Card (if present) -->
        <v-col v-if="hasPhenotypicFeatures" cols="12" md="6" class="py-1">
          <PhenotypicFeaturesCard :features="phenopacket.phenotypicFeatures" />
        </v-col>

        <!-- Interpretations Card (if present) -->
        <v-col
          v-if="hasInterpretations"
          cols="12"
          :md="hasPhenotypicFeatures ? 6 : 12"
          class="py-1"
        >
          <InterpretationsCard :interpretations="phenopacket.interpretations" />
        </v-col>

        <!-- Measurements Card (if present) -->
        <v-col v-if="hasMeasurements" cols="12" md="6" class="py-1">
          <MeasurementsCard :measurements="phenopacket.measurements" />
        </v-col>

        <!-- Metadata Card (full width) -->
        <v-col cols="12" class="py-1">
          <MetadataCard v-if="phenopacket.metaData" :meta-data="phenopacket.metaData" />
        </v-col>
      </v-row>
    </div>

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
  </v-container>
</template>

<script>
import { getPhenopacket, deletePhenopacket } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import SubjectCard from '@/components/phenopacket/SubjectCard.vue';
import PhenotypicFeaturesCard from '@/components/phenopacket/PhenotypicFeaturesCard.vue';
import InterpretationsCard from '@/components/phenopacket/InterpretationsCard.vue';
import MeasurementsCard from '@/components/phenopacket/MeasurementsCard.vue';
import MetadataCard from '@/components/phenopacket/MetadataCard.vue';
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue';

export default {
  name: 'PagePhenopacket',
  components: {
    SubjectCard,
    PhenotypicFeaturesCard,
    InterpretationsCard,
    MeasurementsCard,
    MetadataCard,
    DeleteConfirmationDialog,
  },
  data() {
    return {
      phenopacket: null,
      loading: false,
      error: null,
      showDeleteDialog: false,
      deleteLoading: false,
    };
  },
  computed: {
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
        // Backend returns the GA4GH phenopacket object directly
        this.phenopacket = response.data;

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
/* Add any custom styles here if needed */
</style>
