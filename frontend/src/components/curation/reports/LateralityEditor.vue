<template>
  <label>
    Laterality
    <select
      :data-laterality="assessmentId"
      :value="modelValue"
      @change="$emit('update:modelValue', $event.target.value)"
    >
      <option v-for="option in LATERALITY_OPTIONS" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </label>
</template>

<script setup>
import { LATERALITY_OPTIONS } from '@/utils/curationAdapters';

defineProps({
  modelValue: { type: String, default: 'none' },
  assessmentId: { type: String, required: true },
});
defineEmits(['update:modelValue']);
</script>

<style scoped>
label {
  display: grid;
  gap: 4px;
}

select {
  min-height: 44px;
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}
</style>
