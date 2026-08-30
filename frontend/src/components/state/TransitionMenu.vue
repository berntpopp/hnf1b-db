<template>
  <v-menu v-if="items.length">
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" data-testid="menu-activator" variant="outlined">
        State actions
      </v-btn>
    </template>
    <v-list>
      <v-list-item
        v-for="item in items"
        :key="item.action"
        data-testid="transition-item"
        :data-action="item.action"
        :aria-disabled="item.allowed ? 'false' : 'true'"
        tabindex="0"
        @click="select(item)"
      >
        <v-list-item-title>{{ item.label }}</v-list-item-title>
        <v-list-item-subtitle v-if="item.denials.length">
          {{ item.denials.join(' ') }}
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  capabilities: { type: Array, required: true },
});
const emit = defineEmits(['transition', 'open-review']);

const PRESENTATION = {
  submit: { label: 'Submit for review', target: 'in_review' },
  resubmit: { label: 'Resubmit for review', target: 'in_review' },
  withdraw: { label: 'Withdraw from review', target: 'draft' },
  archive: { label: 'Archive', target: 'archived' },
  request_changes: { label: 'Request changes', exact: true },
  approve: { label: 'Approve candidate', exact: true },
  publish: { label: 'Publish approved revision', exact: true },
};

const BLOCKER_COPY = {
  forbidden_role: 'Only an administrator can perform this action.',
  forbidden_not_owner: 'Only the draft owner can perform this action.',
  self_review_forbidden: 'You own this draft and cannot independently review it.',
  reviewer_submitted: 'You submitted this candidate and cannot independently review it.',
  reviewer_contributed: 'You contributed to this review cycle.',
  review_author_unknown: 'Reviewer independence cannot be verified.',
  unresolved_review_issues: 'Resolve all blocking issues before approval.',
  review_closed: 'This review action is no longer available.',
};

const items = computed(() =>
  props.capabilities.flatMap((capability) => {
    const presentation = PRESENTATION[capability?.action];
    if (!presentation) return [];
    return [
      {
        ...capability,
        ...presentation,
        denials: (capability.blocked_by || []).map(
          (code) => BLOCKER_COPY[code] || code.replaceAll('_', ' ')
        ),
      },
    ];
  })
);

function select(item) {
  if (!item.allowed) return;
  if (item.exact) emit('open-review', item.action);
  else emit('transition', item.target);
}
</script>
