<!-- Presentational controls for the 3D structure viewer. -->
<!-- Representation toggle, DNA/domain switches, reset + distance-line buttons. -->
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
        :model-value="showDNA"
        label="Show DNA"
        density="compact"
        hide-details
        color="primary"
        @update:model-value="$emit('update:showDNA', $event)"
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
      <v-btn size="small" variant="outlined" class="mr-2" @click="$emit('reset')">
        <v-icon left size="small"> mdi-refresh </v-icon>
        Reset View
      </v-btn>
      <v-btn
        v-if="hasActiveVariantInStructure && activeVariantDistanceInfo"
        size="small"
        variant="outlined"
        :color="showDistanceLine ? 'primary' : 'default'"
        @click="$emit('toggle-distance-line')"
      >
        <v-icon left size="small"> mdi-ruler </v-icon>
        {{ activeVariantDistanceInfo.distanceFormatted }} &Aring;
      </v-btn>
    </v-col>
  </v-row>
</template>

<script>
export default {
  name: 'StructureControls',
  props: {
    representation: {
      type: String,
      default: 'cartoon',
    },
    showDNA: {
      type: Boolean,
      default: true,
    },
    colorByDomain: {
      type: Boolean,
      default: false,
    },
    showDistanceLine: {
      type: Boolean,
      default: false,
    },
    structureLoaded: {
      type: Boolean,
      default: false,
    },
    hasActiveVariantInStructure: {
      type: Boolean,
      default: false,
    },
    activeVariantDistanceInfo: {
      type: Object,
      default: null,
    },
  },
  emits: [
    'update:representation',
    'update:showDNA',
    'update:colorByDomain',
    'reset',
    'toggle-distance-line',
  ],
};
</script>
