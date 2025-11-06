<!-- src/components/phenopacket/DiseasesCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-red-lighten-5">
      <v-icon left color="error" size="small"> mdi-virus </v-icon>
      Diseases ({{ diseases.length }})
    </v-card-title>
    <v-card-text class="pa-2">
      <v-alert v-if="diseases.length === 0" type="info" density="compact">
        No diseases recorded
      </v-alert>

      <v-list v-else>
        <v-list-item v-for="(disease, index) in diseases" :key="index" class="mb-2">
          <template #prepend>
            <v-chip
              :href="getMondoUrl(disease.term.id)"
              target="_blank"
              color="red"
              variant="flat"
              size="small"
            >
              <v-icon left size="x-small"> mdi-open-in-new </v-icon>
              {{ disease.term.id }}
            </v-chip>
          </template>

          <v-list-item-title class="font-weight-bold">
            {{ disease.term.label }}
          </v-list-item-title>

          <v-list-item-subtitle v-if="disease.onset">
            <strong>Onset:</strong> {{ formatOnset(disease.onset) }}
          </v-list-item-subtitle>

          <v-list-item-subtitle v-if="disease.diseaseStage && disease.diseaseStage.length > 0">
            <strong>Stage:</strong>
            <v-chip
              v-for="(stage, stageIndex) in disease.diseaseStage"
              :key="stageIndex"
              size="x-small"
              class="ml-1"
            >
              {{ stage.label || stage.id }}
            </v-chip>
          </v-list-item-subtitle>

          <v-list-item-subtitle
            v-if="disease.clinicalTnmFinding && disease.clinicalTnmFinding.length > 0"
          >
            <strong>TNM Finding:</strong>
            <v-chip
              v-for="(tnm, tnmIndex) in disease.clinicalTnmFinding"
              :key="tnmIndex"
              size="x-small"
              class="ml-1"
            >
              {{ tnm.label || tnm.id }}
            </v-chip>
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'DiseasesCard',
  props: {
    diseases: {
      type: Array,
      default: () => [],
    },
  },
  methods: {
    getMondoUrl(mondoId) {
      // Convert MONDO:0018874 to https://monarchinitiative.org/disease/MONDO:0018874
      if (mondoId && mondoId.startsWith('MONDO:')) {
        return `https://monarchinitiative.org/disease/${mondoId}`;
      }
      return '#';
    },

    formatOnset(onset) {
      if (onset.age?.iso8601duration) {
        return this.formatISO8601Duration(onset.age.iso8601duration);
      }
      if (onset.ontologyClass) {
        return onset.ontologyClass.label || onset.ontologyClass.id;
      }
      return 'Unknown';
    },

    formatISO8601Duration(duration) {
      const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
      const matches = duration.match(regex);
      if (!matches) return duration;

      const parts = [];
      if (matches[1]) parts.push(`${matches[1]} year${matches[1] > 1 ? 's' : ''}`);
      if (matches[2]) parts.push(`${matches[2]} month${matches[2] > 1 ? 's' : ''}`);
      if (matches[3]) parts.push(`${matches[3]} day${matches[3] > 1 ? 's' : ''}`);

      return parts.join(', ') || duration;
    },
  },
};
</script>
