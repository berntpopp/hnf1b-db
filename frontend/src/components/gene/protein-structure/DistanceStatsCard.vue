<!-- Presentational: active-variant distance-to-DNA alert + pathogenicity/domain legend. -->
<template>
  <div>
    <!-- Active Variant Distance Info -->
    <v-alert
      v-if="activeVariantDistanceInfo"
      :type="getDistanceAlertType(activeVariantDistanceInfo.category)"
      density="compact"
      variant="tonal"
      class="mt-3"
    >
      <v-icon size="small" class="mr-1"> mdi-ruler </v-icon>
      <strong>Distance to DNA:</strong>
      {{ activeVariantDistanceInfo.distanceFormatted }} &Aring; ({{
        getDistanceCategoryLabel(activeVariantDistanceInfo.category)
      }})
      <span class="text-caption ml-2">
        Closest DNA atom: {{ activeVariantDistanceInfo.closestDNAAtom?.label }}
      </span>
    </v-alert>

    <!-- Legend Row -->
    <v-row class="mt-2">
      <v-col cols="12">
        <div class="legend-container">
          <span class="text-caption text-grey mr-2">Pathogenicity:</span>
          <v-chip size="x-small" color="red-lighten-1" class="mr-1"> Pathogenic </v-chip>
          <v-chip size="x-small" color="orange-lighten-1" class="mr-1"> Likely Pathogenic </v-chip>
          <v-chip size="x-small" color="yellow-darken-1" class="mr-1"> VUS </v-chip>
          <v-chip size="x-small" color="light-green-lighten-1" class="mr-1"> Likely Benign </v-chip>
          <v-chip size="x-small" color="grey-lighten-1"> Unknown </v-chip>
        </div>
        <!-- Domain Legend (shown when domain coloring is enabled) -->
        <div v-if="colorByDomain" class="legend-container mt-2">
          <span class="text-caption text-grey mr-2">Domains:</span>
          <v-chip size="x-small" style="background-color: #ab47bc; color: white" class="mr-1">
            POU-S (90-173)
          </v-chip>
          <v-chip size="x-small" style="background-color: #26a69a; color: white" class="mr-1">
            POU-H (232-305)
          </v-chip>
          <v-chip size="x-small" style="background-color: #9e9e9e" class="mr-1"> Linker </v-chip>
          <span class="text-caption text-grey-darken-1 ml-2"> (Gap: 187-230 not resolved) </span>
        </div>
      </v-col>
    </v-row>
  </div>
</template>

<script>
// HNF1B protein domains (from UniProt P35680)
// Note: PDB 2H8R only covers residues 90-308 (with gap 187-230)
const PROTEIN_DOMAINS = [
  {
    name: 'Dimerization',
    shortName: 'Dim',
    start: 1,
    end: 31,
    color: 0xffb74d, // Orange - not visible in structure (before res 90)
  },
  {
    name: 'POU-Specific',
    shortName: 'POU-S',
    start: 88,
    end: 173,
    color: 0xab47bc, // Purple - partially visible (90-173)
  },
  {
    name: 'POU-Homeodomain',
    shortName: 'POU-H',
    start: 232,
    end: 305,
    color: 0x26a69a, // Teal - fully visible
  },
  {
    name: 'Transactivation',
    shortName: 'TAD',
    start: 314,
    end: 557,
    color: 0x81c784, // Green - not visible in structure (after res 308)
  },
];

export default {
  name: 'DistanceStatsCard',
  props: {
    activeVariantDistanceInfo: {
      type: Object,
      default: null,
    },
    proteinDomains: {
      type: Array,
      default: () => PROTEIN_DOMAINS,
    },
    colorByDomain: {
      type: Boolean,
      default: false,
    },
  },
  methods: {
    getDistanceAlertType(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },

    getDistanceCategoryLabel(category) {
      if (category === 'close') return 'Close to DNA - likely functional impact';
      if (category === 'medium') return 'Medium distance';
      return 'Far from DNA';
    },
  },
};
</script>

<style scoped>
.legend-container {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
</style>
