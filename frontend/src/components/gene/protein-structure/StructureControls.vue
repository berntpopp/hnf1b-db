<!-- Structure Controls Component -->
<!-- Representation toggles, DNA/domain switches, and action buttons -->
<template>
  <v-row class="mt-3">
    <!-- Representation Controls -->
    <v-col cols="12" sm="6" md="5">
      <v-btn-toggle
        :model-value="representation"
        mandatory
        density="compact"
        color="primary"
        @update:model-value="$emit('update:representation', $event)"
      >
        <v-btn value="cartoon" size="small">
          <v-icon left size="small"> mdi-waves </v-icon>
          Cartoon
        </v-btn>
        <v-btn value="surface" size="small">
          <v-icon left size="small"> mdi-circle </v-icon>
          Surface
        </v-btn>
        <v-btn value="ball+stick" size="small">
          <v-icon left size="small"> mdi-atom </v-icon>
          Ball+Stick
        </v-btn>
      </v-btn-toggle>
    </v-col>

    <!-- DNA Toggle -->
    <v-col cols="6" sm="3" md="2">
      <v-switch
        :model-value="showDna"
        label="Show DNA"
        density="compact"
        hide-details
        color="primary"
        @update:model-value="$emit('update:showDna', $event)"
      />
    </v-col>

    <!-- Domain Coloring Toggle -->
    <v-col cols="6" sm="3" md="2">
      <v-switch
        :model-value="colorByDomain"
        label="Domain Colors"
        density="compact"
        hide-details
        color="secondary"
        @update:model-value="$emit('update:colorByDomain', $event)"
      />
    </v-col>

    <!-- Action Buttons -->
    <v-col cols="12" sm="3" md="4" class="text-right">
      <v-btn size="small" variant="outlined" class="mr-2" @click="$emit('reset-view')">
        <v-icon left size="small"> mdi-refresh </v-icon>
        Reset View
      </v-btn>
      <v-btn
        v-if="showDistanceButton"
        size="small"
        variant="outlined"
        :color="showDistanceLine ? 'primary' : 'default'"
        @click="$emit('toggle-distance')"
      >
        <v-icon left size="small"> mdi-ruler </v-icon>
        <!-- Use HTML entity for Angstrom symbol -->
        <span v-html="distanceFormatted + ' &#8491;'" />
      </v-btn>
    </v-col>
  </v-row>
</template>

<script>
export default {
  name: 'StructureControls',
  props: {
    /** Current representation type */
    representation: {
      type: String,
      required: true,
    },
    /** Whether DNA is shown */
    showDna: {
      type: Boolean,
      required: true,
    },
    /** Whether domain coloring is enabled */
    colorByDomain: {
      type: Boolean,
      required: true,
    },
    /** Whether to show the distance button */
    showDistanceButton: {
      type: Boolean,
      default: false,
    },
    /** Formatted distance value (e.g., "5.23") */
    distanceFormatted: {
      type: String,
      default: '',
    },
    /** Whether the distance line is currently shown */
    showDistanceLine: {
      type: Boolean,
      default: false,
    },
  },
  emits: [
    'update:representation',
    'update:showDna',
    'update:colorByDomain',
    'reset-view',
    'toggle-distance',
  ],
};
</script>
