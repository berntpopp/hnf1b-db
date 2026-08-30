<template>
  <header class="review-header">
    <v-btn class="back-link" variant="text" :to="backLocation">
      <template #prepend>
        <v-icon aria-hidden="true">mdi-arrow-left</v-icon>
      </template>
      Back to review queue
    </v-btn>

    <div class="review-header__title-row">
      <div>
        <h1 id="phenopacket-review-title" class="text-h4">Review {{ context.phenopacket_id }}</h1>
        <p class="text-body-1 text-medium-emphasis mb-0">{{ context.subject_label }}</p>
      </div>
      <div class="review-header__status">
        <StateBadge :state="context.effective_state" />
        <span class="eligibility-label">
          <v-icon aria-hidden="true">{{ eligibility.icon }}</v-icon>
          {{ eligibility.label }}
        </span>
      </div>
    </div>

    <dl class="review-metadata mt-4">
      <div>
        <dt>Owner</dt>
        <dd>{{ actorName(context.audit?.owner || context.owner) }}</dd>
      </div>
      <div>
        <dt>Submission</dt>
        <dd>{{ auditSummary(context.audit?.submission) }}</dd>
      </div>
      <div>
        <dt>Candidate</dt>
        <dd>
          Candidate revision {{ context.candidate.revision_number }}
          <code class="digest">{{ context.candidate.content_sha256 }}</code>
        </dd>
      </div>
      <div>
        <dt>Public head</dt>
        <dd>
          {{
            context.has_published_head
              ? 'Existing public version retained during review'
              : 'No public version yet'
          }}
        </dd>
      </div>
      <div>
        <dt>Contributors</dt>
        <dd>{{ contributorNames }}</dd>
      </div>
      <div>
        <dt>Approval</dt>
        <dd>{{ auditSummary(context.audit?.approval, true) }}</dd>
      </div>
      <div>
        <dt>Publication</dt>
        <dd>{{ auditSummary(context.audit?.publication, true) }}</dd>
      </div>
    </dl>
  </header>
</template>

<script setup>
import { computed } from 'vue';

import StateBadge from '@/components/state/StateBadge.vue';

const props = defineProps({
  context: { type: Object, required: true },
  returnTo: { type: String, default: '' },
});

const backLocation = computed(() => {
  const candidate = props.returnTo;
  if (!candidate || !candidate.startsWith('/review')) return { name: 'ReviewQueue' };
  try {
    const parsed = new URL(candidate, 'https://review.local');
    if (parsed.origin === 'https://review.local' && parsed.pathname === '/review') return candidate;
  } catch {
    // Malformed return targets use the named internal route below.
  }
  return { name: 'ReviewQueue' };
});

const eligibility = computed(() => {
  const decisions = (props.context.capabilities || []).filter((item) =>
    ['request_changes', 'approve'].includes(item.action)
  );
  if (decisions.some((item) => item.allowed)) {
    return { icon: 'mdi-account-check-outline', label: 'Eligible to review' };
  }
  return { icon: 'mdi-account-lock-outline', label: 'Review actions restricted' };
});

const contributorNames = computed(() => {
  const contributors = props.context.audit?.contributors || [];
  return contributors.length ? contributors.map(actorName).join(', ') : 'No contributors recorded';
});

function actorName(actor) {
  return actor?.display_name || actor?.username || 'Not recorded';
}

function formatTimestamp(value) {
  if (!value) return 'time not recorded';
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(timestamp);
}

function auditSummary(revision, includeRoleFallback = false) {
  if (!revision) return 'Not recorded';
  const revisionLabel = Number.isInteger(revision.revision_number)
    ? `revision ${revision.revision_number}`
    : `revision ID ${revision.id}`;
  const role = revision.actor_role || revision.actor?.role;
  const roleCopy = role
    ? `role at decision: ${role}`
    : includeRoleFallback
      ? 'Role at decision not recorded'
      : null;
  return [actorName(revision.actor), revisionLabel, formatTimestamp(revision.created_at), roleCopy]
    .filter(Boolean)
    .join(' — ');
}
</script>

<style scoped>
.review-header {
  border-bottom: 1px solid rgb(var(--v-theme-surface-variant));
  padding-bottom: 1.5rem;
}

.back-link {
  margin-bottom: 0.75rem;
  min-height: 44px;
}

.review-header__title-row,
.review-header__status {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: space-between;
}

.eligibility-label {
  align-items: center;
  display: inline-flex;
  font-weight: 600;
  gap: 0.35rem;
}

.review-metadata {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  margin-bottom: 0;
}

.review-metadata dt {
  color: rgb(var(--v-theme-on-surface-variant));
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
}

.review-metadata dd {
  margin: 0.2rem 0 0;
}

.digest {
  display: block;
  font-size: 0.7rem;
  overflow-wrap: anywhere;
}
</style>
