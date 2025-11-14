<template>
  <v-autocomplete
    :model-value="modelValue"
    :items="terms"
    :loading="loading"
    :search="searchQuery"
    item-title="title"
    item-value="id"
    :label="label"
    :hint="hint"
    :persistent-hint="!!hint"
    :error-messages="errorMessages"
    :disabled="disabled"
    :clearable="clearable"
    :density="density"
    :variant="variant"
    return-object
    no-filter
    @update:search="handleSearch"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #item="{ props, item }">
      <v-list-item
        v-bind="props"
        :title="item.raw.label"
        :subtitle="`${item.raw.id} • ${item.raw.category || 'HPO term'}`"
      >
        <template #append>
          <v-chip
            v-if="item.raw.recommendation === 'required'"
            size="x-small"
            color="error"
            variant="flat"
          >
            Required
          </v-chip>
          <v-chip
            v-else-if="item.raw.recommendation === 'recommended'"
            size="x-small"
            color="warning"
            variant="flat"
          >
            Recommended
          </v-chip>
        </template>
      </v-list-item>
    </template>

    <template #chip="{ item }">
      <v-chip size="small" closable>
        {{ item.raw.label }}
      </v-chip>
    </template>

    <template #no-data>
      <v-list-item>
        <v-list-item-title v-if="searchQuery && searchQuery.length < 2">
          Type at least 2 characters to search...
        </v-list-item-title>
        <v-list-item-title v-else-if="loading"> Searching HPO terms... </v-list-item-title>
        <v-list-item-title v-else-if="error"> Error loading HPO terms </v-list-item-title>
        <v-list-item-title v-else> No HPO terms found </v-list-item-title>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>

<script setup>
import { ref } from 'vue';
import { useHPOAutocomplete } from '@/composables/useHPOAutocomplete';

defineProps({
  modelValue: {
    type: Object,
    default: null,
  },
  label: {
    type: String,
    default: 'HPO Term',
  },
  hint: {
    type: String,
    default: '',
  },
  errorMessages: {
    type: [String, Array],
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  clearable: {
    type: Boolean,
    default: true,
  },
  density: {
    type: String,
    default: 'default',
  },
  variant: {
    type: String,
    default: 'outlined',
  },
});

defineEmits(['update:modelValue']);

const { terms, loading, error, search } = useHPOAutocomplete();
const searchQuery = ref('');

const handleSearch = (value) => {
  searchQuery.value = value;
  if (value && value.length >= 2) {
    search(value);
  }
};
</script>
