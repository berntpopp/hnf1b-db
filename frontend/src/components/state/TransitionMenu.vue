<template>
  <v-menu>
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" data-testid="menu-activator" variant="outlined">
        State actions
      </v-btn>
    </template>
    <v-list>
      <v-list-item
        v-for="item in items"
        :key="item.to"
        data-testid="transition-item"
        @click="emit('transition', item.to)"
      >
        {{ item.label }}
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  currentState: { type: String, required: true },
  role: { type: String, required: true },
  isOwner: { type: Boolean, default: false },
});
const emit = defineEmits(['transition']);

const LABELS = {
  in_review: 'Submit for review',
  changes_requested: 'Request changes',
  approved: 'Approve',
  published: 'Publish',
  archived: 'Archive',
  draft: 'Withdraw',
};

// Mirror of backend transitions.py::allowed_transitions.
const RULES = {
  draft: (role, owner) => (role === 'admin' || owner ? ['in_review'] : []),
  in_review: (role, owner) => {
    const out = [];
    if (role === 'admin' || owner) out.push('draft');
    if (role === 'admin') out.push('changes_requested', 'approved', 'archived');
    return out;
  },
  changes_requested: (role, owner) => (role === 'admin' || owner ? ['in_review'] : []),
  approved: (role) => (role === 'admin' ? ['published', 'archived'] : []),
  published: (role) => (role === 'admin' ? ['archived'] : []),
  archived: () => [],
};

const items = computed(() => {
  if (props.role === 'viewer') return [];
  const fn = RULES[props.currentState] ?? (() => []);
  return fn(props.role, props.isOwner).map((to) => ({ to, label: LABELS[to] }));
});

// Expose items so unit tests can verify role-gating without opening the overlay
// (v-menu overlay requires visualViewport which is unavailable in happy-dom).
defineExpose({ items });
</script>
