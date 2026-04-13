<template>
  <v-alert v-if="editingRevisionId" type="info" variant="tonal" density="comfortable">
    <div>
      Draft in progress by <strong>@{{ draftOwnerUsername }}</strong> — started {{ relative }}
    </div>
    <v-btn v-if="isOwner" size="small" @click="emit('continue')">Continue editing</v-btn>
  </v-alert>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  editingRevisionId: { type: Number, default: null },
  draftOwnerUsername: { type: String, default: null },
  currentUsername: { type: String, default: null },
  startedAt: { type: String, default: null },
});
const emit = defineEmits(['continue']);

const isOwner = computed(
  () => props.draftOwnerUsername && props.draftOwnerUsername === props.currentUsername
);
const relative = computed(() => {
  if (!props.startedAt) return '';
  const mins = Math.round((Date.now() - new Date(props.startedAt)) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  return `${Math.round(mins / 60)}h ago`;
});
</script>
