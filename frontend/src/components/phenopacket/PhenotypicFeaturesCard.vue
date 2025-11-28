<!-- src/components/phenopacket/PhenotypicFeaturesCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-green-lighten-5">
      <v-icon left color="success" size="small"> mdi-medical-bag </v-icon>
      Phenotypic Features ({{ presentFeatures.length }})
    </v-card-title>
    <v-card-text class="pa-2">
      <v-alert v-if="presentFeatures.length === 0" type="info" density="compact">
        No phenotypic features recorded
      </v-alert>

      <v-list v-else>
        <v-list-item v-for="(feature, index) in presentFeatures" :key="index" class="mb-2">
          <template #prepend>
            <v-chip
              :href="getHpoUrl(feature.type.id)"
              target="_blank"
              color="green"
              variant="flat"
              size="small"
            >
              <v-icon left size="x-small"> mdi-open-in-new </v-icon>
              {{ feature.type.id }}
            </v-chip>
          </template>

          <v-list-item-title class="font-weight-bold">
            {{ feature.type.label }}
          </v-list-item-title>

          <v-list-item-subtitle v-if="feature.severity">
            <strong>Severity:</strong> {{ feature.severity.label || feature.severity.id }}
          </v-list-item-subtitle>

          <v-list-item-subtitle v-if="feature.onset">
            <strong>Onset:</strong> {{ formatOnset(feature.onset) }}
          </v-list-item-subtitle>

          <v-list-item-subtitle v-if="feature.modifiers && feature.modifiers.length > 0">
            <strong>Modifiers:</strong>
            <v-chip
              v-for="(modifier, modIndex) in feature.modifiers"
              :key="modIndex"
              size="x-small"
              class="ml-1"
            >
              {{ modifier.label || modifier.id }}
            </v-chip>
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'PhenotypicFeaturesCard',
  props: {
    features: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    // Filter out excluded phenotypes (those marked as "No" or absent)
    // Only show features that are actually present (excluded !== true)
    presentFeatures() {
      return this.features.filter((feature) => !feature.excluded);
    },
  },
  methods: {
    getHpoUrl(hpoId) {
      // Convert HP:0003774 to https://hpo.jax.org/app/browse/term/HP:0003774
      if (hpoId && hpoId.startsWith('HP:')) {
        return `https://hpo.jax.org/app/browse/term/${hpoId}`;
      }
      return '#';
    },

    formatOnset(onset) {
      // Helper to extract ISO8601 duration from age field
      const extractAgeDuration = (age) => {
        if (typeof age === 'string') return age;
        if (age.iso8601duration) return age.iso8601duration;
        // age might contain ontologyClass instead of duration (e.g., prenatal onset)
        if (age.ontologyClass) return null;
        return null;
      };

      // Handle combined onset (e.g., postnatal + specific age)
      if (onset.ontologyClass && onset.age) {
        const classification = (onset.ontologyClass.label || onset.ontologyClass.id).toLowerCase();
        const ageDuration = extractAgeDuration(onset.age);
        if (ageDuration) {
          const formattedAge = this.formatISO8601Duration(ageDuration);
          return `${classification}, reported: age ${formattedAge}`;
        }
        // age contains ontologyClass but no duration - just show the classification
        return classification;
      }

      // Handle age-only onset (string format)
      if (onset.iso8601duration) {
        return `reported: age ${this.formatISO8601Duration(onset.iso8601duration)}`;
      }

      // Handle age object
      if (onset.age) {
        const ageDuration = extractAgeDuration(onset.age);
        if (ageDuration) {
          return `reported: age ${this.formatISO8601Duration(ageDuration)}`;
        }
        // age contains ontologyClass instead of duration
        if (onset.age.ontologyClass) {
          return onset.age.ontologyClass.label || onset.age.ontologyClass.id;
        }
        return 'Unknown';
      }

      // Handle ontology class only (prenatal/postnatal without specific age)
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
