<!-- src/components/phenopacket/MeasurementsCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-h6 bg-orange-lighten-5">
      <v-icon
        left
        color="orange"
      >
        mdi-test-tube
      </v-icon>
      Measurements ({{ measurements.length }})
    </v-card-title>
    <v-card-text>
      <v-alert
        v-if="measurements.length === 0"
        type="info"
        density="compact"
      >
        No measurements recorded
      </v-alert>

      <v-list v-else>
        <v-list-item
          v-for="(measurement, index) in measurements"
          :key="index"
          class="mb-2"
        >
          <template #prepend>
            <v-chip
              color="orange"
              variant="flat"
              size="small"
            >
              {{ measurement.assay.id }}
            </v-chip>
          </template>

          <v-list-item-title class="font-weight-bold">
            {{ measurement.assay.label }}
          </v-list-item-title>

          <v-list-item-subtitle v-if="measurement.value">
            <strong>Value:</strong> {{ formatValue(measurement.value) }}
          </v-list-item-subtitle>

          <v-list-item-subtitle v-if="measurement.timeObserved">
            <strong>Observed:</strong> {{ formatTime(measurement.timeObserved) }}
          </v-list-item-subtitle>

          <v-list-item-subtitle v-if="measurement.procedure">
            <strong>Procedure:</strong> {{ measurement.procedure.label || measurement.procedure.id }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'MeasurementsCard',
  props: {
    measurements: {
      type: Array,
      default: () => [],
    },
  },
  methods: {
    formatValue(value) {
      if (value.quantity) {
        const unit = value.quantity.unit?.label || value.quantity.unit?.id || '';
        return `${value.quantity.value} ${unit}`.trim();
      }
      if (value.ontologyClass) {
        return value.ontologyClass.label || value.ontologyClass.id;
      }
      return 'N/A';
    },

    formatTime(timeObserved) {
      if (timeObserved.timestamp) {
        return new Date(timeObserved.timestamp).toLocaleString();
      }
      if (timeObserved.age?.iso8601duration) {
        return this.formatISO8601Duration(timeObserved.age.iso8601duration);
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
