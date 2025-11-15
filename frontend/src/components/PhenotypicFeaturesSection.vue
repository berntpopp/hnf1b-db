<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-green-lighten-5">
      <v-icon left>mdi-dna</v-icon>
      Phenotypic Features
    </v-card-title>

    <v-card-text>
      <div v-for="(feature, index) in modelValue" :key="index" class="mb-3">
        <v-row>
          <v-col cols="12" md="8">
            <HPOAutocomplete
              v-model="feature.type"
              label="HPO Term *"
              :error-messages="!feature.type?.id && formSubmitted ? ['Required field'] : []"
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-checkbox
              v-model="feature.excluded"
              label="Excluded"
              density="compact"
              hide-details
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-btn color="error" icon="mdi-delete" variant="text" @click="removeFeature(index)" />
          </v-col>
        </v-row>
      </div>

      <v-btn color="primary" prepend-icon="mdi-plus" @click="addFeature">
        Add Phenotypic Feature
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import HPOAutocomplete from '@/components/HPOAutocomplete.vue';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  formSubmitted: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['update:modelValue']);

const addFeature = () => {
  const updated = [...props.modelValue, { type: { id: '', label: '' }, excluded: false }];
  emit('update:modelValue', updated);
};

const removeFeature = (index) => {
  const updated = [...props.modelValue];
  updated.splice(index, 1);
  emit('update:modelValue', updated);
};
</script>
