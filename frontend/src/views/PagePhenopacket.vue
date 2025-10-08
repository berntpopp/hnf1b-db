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
              <v-icon left color="primary" size="large">
                mdi-file-document
              </v-icon>
              {{ phenopacket.phenopacket_id }}
            </v-card-title>
            <v-card-subtitle class="text-h6">
              Subject: {{ phenopacket.phenopacket?.subject?.id || 'N/A' }}
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

      <!-- Content Cards in 2-Column Grid -->
      <v-row>
        <!-- Subject Card -->
        <v-col cols="12" md="6">
          <SubjectCard v-if="phenopacket.phenopacket?.subject" :subject="phenopacket.phenopacket.subject" />
        </v-col>

        <!-- Diseases Card -->
        <v-col cols="12" md="6">
          <DiseasesCard
            v-if="phenopacket.phenopacket?.diseases"
            :diseases="phenopacket.phenopacket.diseases"
          />
        </v-col>

        <!-- Phenotypic Features Card (if present) -->
        <v-col v-if="hasPhenotypicFeatures" cols="12" md="6">
          <PhenotypicFeaturesCard :features="phenopacket.phenopacket.phenotypicFeatures" />
        </v-col>

        <!-- Interpretations Card (if present) -->
        <v-col v-if="hasInterpretations" cols="12" :md="hasPhenotypicFeatures ? 6 : 12">
          <InterpretationsCard :interpretations="phenopacket.phenopacket.interpretations" />
        </v-col>

        <!-- Measurements Card (if present) -->
        <v-col v-if="hasMeasurements" cols="12" md="6">
          <MeasurementsCard :measurements="phenopacket.phenopacket.measurements" />
        </v-col>

        <!-- Metadata Card (full width) -->
        <v-col cols="12">
          <MetadataCard v-if="phenopacket.phenopacket?.metaData" :meta-data="phenopacket.phenopacket.metaData" />
        </v-col>
      </v-row>
    </div>
  </v-container>
</template>

<script>
import { getPhenopacket } from '@/api';
import SubjectCard from '@/components/phenopacket/SubjectCard.vue';
import PhenotypicFeaturesCard from '@/components/phenopacket/PhenotypicFeaturesCard.vue';
import DiseasesCard from '@/components/phenopacket/DiseasesCard.vue';
import InterpretationsCard from '@/components/phenopacket/InterpretationsCard.vue';
import MeasurementsCard from '@/components/phenopacket/MeasurementsCard.vue';
import MetadataCard from '@/components/phenopacket/MetadataCard.vue';

export default {
  name: 'PagePhenopacket',
  components: {
    SubjectCard,
    PhenotypicFeaturesCard,
    DiseasesCard,
    InterpretationsCard,
    MeasurementsCard,
    MetadataCard,
  },
  data() {
    return {
      phenopacket: null,
      loading: false,
      error: null,
    };
  },
  computed: {
    hasPhenotypicFeatures() {
      return (
        this.phenopacket?.phenopacket?.phenotypicFeatures &&
        this.phenopacket.phenopacket.phenotypicFeatures.length > 0
      );
    },
    hasInterpretations() {
      return (
        this.phenopacket?.phenopacket?.interpretations &&
        this.phenopacket.phenopacket.interpretations.length > 0
      );
    },
    hasMeasurements() {
      return (
        this.phenopacket?.phenopacket?.measurements &&
        this.phenopacket.phenopacket.measurements.length > 0
      );
    },
  },
  mounted() {
    this.fetchPhenopacket();
  },
  methods: {
    async fetchPhenopacket() {
      this.loading = true;
      this.error = null;

      try {
        const phenopacketId = this.$route.params.phenopacket_id;
        const response = await getPhenopacket(phenopacketId);
        this.phenopacket = response.data;
      } catch (error) {
        console.error('Error fetching phenopacket:', error);
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
      const blob = new Blob([dataStr], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${this.phenopacket.phenopacket_id}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
  },
};
</script>

<style scoped>
/* Add any custom styles here if needed */
</style>
