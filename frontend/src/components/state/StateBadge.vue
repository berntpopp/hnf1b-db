<template>
  <v-chip v-if="state" :color="color" size="small" label>{{ label }}</v-chip>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  state: { type: String, default: null },
});

const COLORS = {
  draft: 'grey',
  in_review: 'blue',
  changes_requested: 'orange',
  approved: 'purple',
  published: 'green',
  archived: 'brown',
};

const color = computed(() => COLORS[props.state] ?? 'grey');
const label = computed(() => (props.state ? props.state.replace(/_/g, ' ') : ''));
</script>
