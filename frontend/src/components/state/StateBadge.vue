<template>
  <v-chip v-if="state" :color="color" size="small" label>{{ label }}</v-chip>
</template>

<script setup>
import { computed } from 'vue';
import { STATE_COLORS, STATE_LABELS } from '@/utils/stateConfig';

const props = defineProps({
  state: { type: String, default: null },
});

const color = computed(() => STATE_COLORS[props.state] ?? 'grey');
const label = computed(() => STATE_LABELS[props.state] ?? '');
</script>
