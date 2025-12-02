<template>
  <div v-if="visible && data" ref="tooltip" class="timeline-tooltip" :style="tooltipStyle">
    <div class="tooltip-header">
      <strong>{{ data.label }}</strong>
      <v-chip
        v-if="data.category"
        :color="getCategoryColor(data.category)"
        size="x-small"
        class="ml-2"
      >
        {{ data.category }}
      </v-chip>
    </div>

    <div class="tooltip-body">
      <div v-if="data.hpoId" class="tooltip-row">
        <span class="tooltip-label">HPO ID:</span>
        <span class="tooltip-value">{{ data.hpoId }}</span>
      </div>

      <div v-if="data.age !== undefined && data.age !== null" class="tooltip-row">
        <span class="tooltip-label">Onset Age:</span>
        <span class="tooltip-value">{{ formatAge(data.age) }}</span>
      </div>

      <div v-if="data.onsetLabel" class="tooltip-row">
        <span class="tooltip-label">Onset Type:</span>
        <span class="tooltip-value">{{ data.onsetLabel }}</span>
      </div>

      <div v-if="data.severity" class="tooltip-row">
        <span class="tooltip-label">Severity:</span>
        <span class="tooltip-value">{{ data.severity }}</span>
      </div>

      <div v-if="data.excluded" class="tooltip-row">
        <span class="tooltip-label">Status:</span>
        <span class="tooltip-value excluded-badge">Excluded</span>
      </div>

      <div v-if="data.evidence && data.evidence.length > 0" class="tooltip-section">
        <div class="tooltip-label mb-1">Evidence:</div>
        <div v-for="(ev, idx) in data.evidence" :key="idx" class="evidence-item">
          <v-icon size="x-small" class="mr-1">mdi-file-document</v-icon>
          <span v-if="ev.pmid" class="evidence-link"> PMID: {{ ev.pmid }} </span>
          <span v-if="ev.description" class="evidence-desc">
            {{ ev.description }}
          </span>
          <span v-if="ev.recordedAt" class="evidence-date">
            ({{ formatDate(ev.recordedAt) }})
          </span>
        </div>
      </div>

      <!-- For publication timeline -->
      <div v-if="data.count !== undefined" class="tooltip-row">
        <span class="tooltip-label">Count:</span>
        <span class="tooltip-value">{{ data.count }}</span>
      </div>

      <div v-if="data.cumulative !== undefined" class="tooltip-row">
        <span class="tooltip-label">Cumulative:</span>
        <span class="tooltip-value">{{ data.cumulative }}</span>
      </div>

      <div v-if="data.year !== undefined" class="tooltip-row">
        <span class="tooltip-label">Year:</span>
        <span class="tooltip-value">{{ data.year }}</span>
      </div>
    </div>

    <div v-if="data.clickHint" class="tooltip-footer">
      <small class="text-muted">{{ data.clickHint }}</small>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { formatAge, getCategoryColor } from '@/utils/ageParser';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  data: {
    type: Object,
    default: null,
  },
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
  },
});

const tooltip = ref(null);

const tooltipStyle = computed(() => {
  return {
    left: `${props.position.x}px`,
    top: `${props.position.y}px`,
    position: 'fixed',
    zIndex: 9999,
  };
});

function formatDate(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}
</script>

<style scoped>
.timeline-tooltip {
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 12px;
  max-width: 320px;
  pointer-events: none;
  font-size: 13px;
}

.tooltip-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.tooltip-body {
  margin-bottom: 8px;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  gap: 8px;
}

.tooltip-label {
  color: #666;
  font-weight: 500;
  flex-shrink: 0;
}

.tooltip-value {
  text-align: right;
  color: #333;
}

.excluded-badge {
  background-color: #ffebee;
  color: #c62828;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.tooltip-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.evidence-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  font-size: 12px;
}

.evidence-link {
  color: #1976d2;
  font-weight: 500;
  margin-right: 4px;
}

.evidence-desc {
  color: #666;
  margin-right: 4px;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.evidence-date {
  color: #999;
  font-size: 11px;
}

.tooltip-footer {
  padding-top: 8px;
  border-top: 1px solid #eee;
  text-align: center;
}

.text-muted {
  color: #999;
}
</style>
