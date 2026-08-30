<template>
  <section class="history-tab" aria-label="Revision history">
    <p v-if="loading" class="history-tab__status">Loading history</p>
    <p v-else-if="error" class="history-tab__status history-tab__status--error">
      {{ error }}
    </p>
    <p v-else-if="entries.length === 0" class="history-tab__status">
      No revision history is available yet.
    </p>
    <template v-else>
      <p class="history-tab__summary">
        {{ entries.length }} of {{ displayTotal }} revisions loaded.
      </p>
      <table class="history-tab__table">
        <thead>
          <tr>
            <th scope="col">Revision</th>
            <th scope="col">State</th>
            <th scope="col">Actor</th>
            <th scope="col">Changed</th>
            <th scope="col">Reason</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in entries" :key="entry.id">
            <td>{{ formatRevision(entry.revisionNumber) }}</td>
            <td>{{ entry.state || 'Unknown' }}</td>
            <td>{{ entry.actor || 'Unknown' }}</td>
            <td>{{ formatTimestamp(entry.timestamp) }}</td>
            <td>{{ entry.summary || 'No summary provided' }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  entries: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: [String, Object],
    default: null,
  },
  total: {
    type: Number,
    default: 0,
  },
});

const displayTotal = computed(() => props.total || props.entries.length);

function formatRevision(revisionNumber) {
  if (revisionNumber == null) {
    return 'Revision unknown';
  }

  return `Revision ${revisionNumber}`;
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return 'Unknown';
  }

  const value = new Date(timestamp);
  if (Number.isNaN(value.getTime())) {
    return String(timestamp);
  }

  return value.toLocaleString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  });
}
</script>

<style scoped>
.history-tab {
  padding: 16px 0;
}

.history-tab__status {
  margin: 0;
}

.history-tab__status--error {
  color: rgb(var(--v-theme-error, 176 0 32));
}

.history-tab__summary {
  margin: 0 0 8px;
}

.history-tab__table {
  width: 100%;
  border-collapse: collapse;
}

.history-tab__table th,
.history-tab__table td {
  padding: 12px 8px;
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  vertical-align: top;
}
</style>
