<template>
  <v-card variant="outlined" class="mb-4">
    <v-card-title class="bg-blue-lighten-5 d-flex align-center">
      <v-icon class="mr-2">mdi-timeline-clock</v-icon>
      Phenotypic Features Timeline
      <v-spacer></v-spacer>
      <v-chip v-if="timelineData" color="primary" size="small">
        {{ filteredFeatures.length }} Features
      </v-chip>
    </v-card-title>

    <v-card-text>
      <div v-if="loading" class="d-flex justify-center align-center" style="height: 400px;">
        <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
      </div>

      <div v-else-if="error" class="d-flex flex-column align-center justify-center" style="height: 400px;">
        <v-icon size="64" color="error" class="mb-4">mdi-alert-circle</v-icon>
        <div class="text-h6 text-error mb-2">Failed to load timeline</div>
        <div class="text-body-2 text-grey">{{ error }}</div>
        <v-btn color="primary" class="mt-4" @click="fetchData">
          <v-icon left>mdi-refresh</v-icon>
          Retry
        </v-btn>
      </div>

      <div v-else-if="!timelineData || timelineData.features.length === 0" class="d-flex flex-column align-center justify-center" style="height: 400px;">
        <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-timeline-alert</v-icon>
        <div class="text-h6 text-grey mb-2">No timeline data available</div>
        <div class="text-body-2 text-grey">No phenotypic features with onset information found.</div>
      </div>

      <div v-else>
        <!-- Timeline visualization -->
        <div ref="chartContainer" class="timeline-chart"></div>

        <!-- Legend -->
        <v-row class="mt-4">
          <v-col>
            <div class="d-flex flex-wrap gap-2">
              <v-chip
                v-for="category in ORGAN_SYSTEMS"
                :key="category.value"
                :color="category.color"
                size="small"
              >
                {{ category.label }}
              </v-chip>
            </div>
          </v-col>
        </v-row>

        <!-- Feature list -->
        <v-expansion-panels class="mt-4">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon class="mr-2">mdi-format-list-bulleted</v-icon>
              Feature Details ({{ filteredFeatures.length }})
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-list dense>
                <v-list-item
                  v-for="(feature, idx) in filteredFeatures"
                  :key="idx"
                  :class="{ 'excluded-feature': feature.excluded }"
                >
                  <template #prepend>
                    <v-avatar :color="getCategoryColor(feature.category)" size="32">
                      <v-icon size="small" color="white">
                        {{ feature.excluded ? 'mdi-minus-circle' : 'mdi-check-circle' }}
                      </v-icon>
                    </v-avatar>
                  </template>
                  <v-list-item-title>{{ feature.label }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ feature.hpo_id }}
                    <span v-if="feature.onset_age"> • Onset: {{ formatAge(parseAge(feature.onset_age)) }}</span>
                    <span v-if="feature.onset_label"> ({{ feature.onset_label }})</span>
                    <span v-if="feature.severity"> • Severity: {{ feature.severity }}</span>
                  </v-list-item-subtitle>
                  <template #append v-if="feature.evidence && feature.evidence.length > 0">
                    <v-chip size="x-small" color="blue-lighten-4">
                      {{ feature.evidence.length }} evidence
                    </v-chip>
                  </template>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </div>
    </v-card-text>

    <!-- Tooltip -->
    <TimelineTooltip
      :visible="tooltip.visible"
      :data="tooltip.data"
      :position="tooltip.position"
    />
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import * as d3 from 'd3';
import API from '@/api';
import TimelineTooltip from './TimelineTooltip.vue';
import { parseAge, formatAge, getCategoryColor, onsetClassToAge, ORGAN_SYSTEMS } from '@/utils/ageParser';

const props = defineProps({
  phenopacketId: {
    type: String,
    required: true
  }
});

const loading = ref(true);
const error = ref(null);
const timelineData = ref(null);
const chartContainer = ref(null);
const selectedCategories = ref([]);
const tooltip = ref({
  visible: false,
  data: null,
  position: { x: 0, y: 0 }
});

let resizeObserver = null;

const filteredFeatures = computed(() => {
  if (!timelineData.value) return [];
  
  let features = timelineData.value.features;
  
  // Always filter out excluded features (absent phenotypes)
  features = features.filter(f => !f.excluded);
  
  // Filter by category
  if (selectedCategories.value.length > 0) {
    features = features.filter(f => selectedCategories.value.includes(f.category));
  }
  
  return features;
});

async function fetchData() {
  loading.value = true;
  error.value = null;
  try {
    const response = await API.getPhenotypeTimeline(props.phenopacketId);
    timelineData.value = response.data;
    console.log('Timeline data received:', timelineData.value);
    console.log('Total features:', timelineData.value.features?.length);
    console.log('Features with onset_age:', timelineData.value.features?.filter(f => f.onset_age).length);
    console.log('Features with onset_label:', timelineData.value.features?.filter(f => f.onset_label).length);
    console.log('Sample feature:', timelineData.value.features?.[0]);
    await nextTick();
    renderChart();
  } catch (err) {
    console.error('Error fetching timeline:', err);
    error.value = err.message || 'An error occurred while fetching data';
  } finally {
    loading.value = false;
  }
}

function renderChart() {
  if (!chartContainer.value || !filteredFeatures.value || filteredFeatures.value.length === 0) {
    console.log('Render chart skipped. Conditions not met:', {
      hasChartContainer: !!chartContainer.value,
      filteredFeaturesCount: filteredFeatures.value?.length || 0
    });
    return;
  }

  // Clear existing chart
  d3.select(chartContainer.value).selectAll('*').remove();

  const container = chartContainer.value;
  const containerWidth = container.clientWidth;
  const margin = { top: 20, right: 30, bottom: 50, left: 200 };
  const width = containerWidth - margin.left - margin.right;
  const rowHeight = 40;
  const height = Math.max(300, filteredFeatures.value.length * rowHeight);

  // Create SVG
  const svg = d3.select(container)
    .append('svg')
    .attr('width', containerWidth)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  // Process features with ages
  const featuresWithAges = filteredFeatures.value.map((f, index) => {
    let age = null;
    if (f.onset_age) {
      age = parseAge(f.onset_age);
      console.log(`Feature "${f.label}" has onset_age: ${f.onset_age} -> parsed to ${age} years`);
    } else if (f.onset_label) {
      // Try to infer age from onset label using HPO onset class
      const inferredAge = onsetClassToAge(f.onset_label);
      if (inferredAge !== null) {
        age = inferredAge;
        console.log(`Feature "${f.label}" has onset_label: ${f.onset_label} -> inferred age ${age} years`);
      }
    }
    return { ...f, age, originalIndex: index };
  });
  
  console.log('Features processed:', featuresWithAges.length);
  console.log('Features with ages:', featuresWithAges.filter(f => f.age !== null).length);
  console.log('Features without ages:', featuresWithAges.filter(f => f.age === null).length);

  // Separate features with and without ages
  const withAges = featuresWithAges.filter(f => f.age !== null);
  const withoutAges = featuresWithAges.filter(f => f.age === null);

  if (featuresWithAges.length === 0) {
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', height / 2)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .style('fill', '#999')
      .text('No features available');
    return;
  }

  // Scales
  const maxAge = d3.max(withAges, d => d.age) || 50;
  const xScale = d3.scaleLinear()
    .domain([0, Math.max(maxAge * 1.1, 10)])
    .range([0, width]);

  const yScale = d3.scaleBand()
    .domain(featuresWithAges.map((f, i) => i))
    .range([0, featuresWithAges.length * rowHeight])
    .padding(0.2);

  // X-axis
  const xAxis = d3.axisBottom(xScale)
    .ticks(10)
    .tickFormat(d => `${d}y`);

  svg.append('g')
    .attr('class', 'x-axis')
    .attr('transform', `translate(0,${featuresWithAges.length * rowHeight})`)
    .call(xAxis)
    .append('text')
    .attr('x', width / 2)
    .attr('y', 40)
    .attr('fill', 'black')
    .attr('text-anchor', 'middle')
    .style('font-size', '12px')
    .text(withAges.length > 0 ? 'Age at Onset (years)' : 'No temporal information available');

  // Y-axis labels (feature names)
  featuresWithAges.forEach((feature, i) => {
    const y = yScale(i) + yScale.bandwidth() / 2;
    
    svg.append('text')
      .attr('x', -10)
      .attr('y', y)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'middle')
      .style('font-size', '11px')
      .style('fill', feature.excluded ? '#999' : '#333')
      .style('text-decoration', feature.excluded ? 'line-through' : 'none')
      .text(feature.label.length > 30 ? feature.label.substring(0, 27) + '...' : feature.label);
  });

  // Draw timeline points and lines for features WITH ages
  withAges.forEach((feature, i) => {
    const idx = feature.originalIndex;
    const y = yScale(idx) + yScale.bandwidth() / 2;
    const xOnset = xScale(feature.age);
    const xEnd = width; // Line extends to the right edge (continuing to present)
    const color = getCategoryColor(feature.category);

    // Line from onset to present (continuing forward)
    svg.append('line')
      .attr('x1', xOnset)
      .attr('y1', y)
      .attr('x2', xEnd)
      .attr('y2', y)
      .attr('stroke', feature.excluded ? '#E0E0E0' : color)
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', feature.excluded ? '5,5' : 'none')
      .attr('opacity', 0.6);

    // Onset marker (circle at the start of the line)
    svg.append('circle')
      .attr('cx', xOnset)
      .attr('cy', y)
      .attr('r', 6)
      .attr('fill', feature.excluded ? '#E0E0E0' : color)
      .attr('stroke', 'white')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseover', function(event) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', 8);
        
        tooltip.value = {
          visible: true,
          data: {
            label: feature.label,
            hpoId: feature.hpo_id,
            age: feature.age,
            onsetLabel: feature.onset_label,
            category: feature.category,
            severity: feature.severity,
            excluded: feature.excluded,
            evidence: feature.evidence.map(ev => ({
              pmid: ev.pmid,
              description: ev.description,
              recordedAt: ev.recorded_at
            })),
            clickHint: 'Click to view HPO term'
          },
          position: {
            x: event.pageX + 10,
            y: event.pageY - 10
          }
        };
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', 6);
        
        tooltip.value.visible = false;
      })
      .on('click', () => {
        window.open(`https://hpo.jax.org/app/browse/term/${feature.hpo_id}`, '_blank');
      });
  });

  // Draw markers for features WITHOUT ages (at the right edge with a different symbol)
  withoutAges.forEach((feature) => {
    const idx = feature.originalIndex;
    const y = yScale(idx) + yScale.bandwidth() / 2;
    const x = width - 30; // Position near right edge
    const color = getCategoryColor(feature.category);

    // Dashed line to indicate unknown onset
    svg.append('line')
      .attr('x1', 0)
      .attr('y1', y)
      .attr('x2', x)
      .attr('y2', y)
      .attr('stroke', feature.excluded ? '#E0E0E0' : color)
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '2,4')
      .attr('opacity', 0.3);

    // Question mark symbol for unknown onset
    svg.append('text')
      .attr('x', x)
      .attr('y', y)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .style('font-size', '14px')
      .style('font-weight', 'bold')
      .style('fill', feature.excluded ? '#999' : color)
      .style('cursor', 'pointer')
      .text('?')
      .on('mouseover', function(event) {
        d3.select(this)
          .transition()
          .duration(200)
          .style('font-size', '18px');
        
        tooltip.value = {
          visible: true,
          data: {
            label: feature.label,
            hpoId: feature.hpo_id,
            age: null,
            onsetLabel: feature.onset_label || 'Unknown',
            category: feature.category,
            severity: feature.severity,
            excluded: feature.excluded,
            evidence: feature.evidence.map(ev => ({
              pmid: ev.pmid,
              description: ev.description,
              recordedAt: ev.recorded_at
            })),
            clickHint: 'Click to view HPO term (onset age unknown)'
          },
          position: {
            x: event.pageX + 10,
            y: event.pageY - 10
          }
        };
      })
      .on('mouseout', function() {
        d3.select(this)
          .transition()
          .duration(200)
          .style('font-size', '14px');
        
        tooltip.value.visible = false;
      })
      .on('click', () => {
        window.open(`https://hpo.jax.org/app/browse/term/${feature.hpo_id}`, '_blank');
      });
  });

  // Add grid lines
  svg.append('g')
    .attr('class', 'grid')
    .attr('opacity', 0.1)
    .call(d3.axisBottom(xScale)
      .tickSize(featuresWithAges.length * rowHeight)
      .tickFormat('')
    );
}

function handleResize() {
  if (timelineData.value && filteredFeatures.value.length > 0) {
    renderChart();
  }
}

watch([selectedCategories], () => {
  console.log('Filters changed, filtered features:', JSON.stringify(filteredFeatures.value, null, 2));
  nextTick(() => renderChart());
});

onMounted(async () => {
  await fetchData();
  
  // Setup resize observer
  if (chartContainer.value) {
    resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainer.value);
  }
});

onUnmounted(() => {
  if (resizeObserver && chartContainer.value) {
    resizeObserver.unobserve(chartContainer.value);
  }
});
</script>

<style scoped>
.timeline-chart {
  min-height: 300px;
  width: 100%;
  overflow-x: auto;
}

.excluded-feature {
  opacity: 0.6;
}

:deep(.x-axis text) {
  font-size: 11px;
  fill: #666;
}

:deep(.x-axis line),
:deep(.x-axis path) {
  stroke: #ccc;
}
</style>
