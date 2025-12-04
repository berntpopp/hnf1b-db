<!-- Distance Category Breakdown for DNA Distance Analysis -->
<template>
  <v-card variant="outlined" class="h-100">
    <v-card-title class="text-subtitle-1 py-2 bg-orange-lighten-5 d-flex align-center">
      <v-icon left color="orange" size="small">mdi-chart-donut</v-icon>
      <span class="flex-grow-1">Distance Categories by Group</span>
      <button class="export-btn" title="Download as SVG" @click="exportSVG">
        <span class="export-icon">⬇</span> Export SVG
      </button>
    </v-card-title>
    <v-card-text>
      <!-- P/LP Distribution -->
      <div class="mb-4">
        <div class="text-body-2 font-weight-medium mb-1">Pathogenic / Likely Pathogenic</div>
        <div class="distance-distribution">
          <div
            v-for="cat in categories"
            :key="'plp-' + cat"
            class="distance-bar"
            :class="cat"
            :style="{ width: getCategoryWidth('pathogenic', cat) + '%' }"
            :title="`${getCategoryLabel(cat)}: ${pathogenicCategories[cat] || 0} variants`"
          >
            <span v-if="pathogenicCategories[cat] > 0">
              {{ pathogenicCategories[cat] }}
            </span>
          </div>
        </div>
      </div>

      <!-- VUS Distribution -->
      <div class="mb-4">
        <div class="text-body-2 font-weight-medium mb-1">Variants of Uncertain Significance</div>
        <div class="distance-distribution">
          <div
            v-for="cat in categories"
            :key="'vus-' + cat"
            class="distance-bar"
            :class="cat"
            :style="{ width: getCategoryWidth('vus', cat) + '%' }"
            :title="`${getCategoryLabel(cat)}: ${vusCategories[cat] || 0} variants`"
          >
            <span v-if="vusCategories[cat] > 0">
              {{ vusCategories[cat] }}
            </span>
          </div>
        </div>
      </div>

      <!-- Legend -->
      <div class="d-flex justify-space-around text-caption text-grey mt-3">
        <span><span class="legend-dot close" /> Close (&lt;5&Aring;)</span>
        <span><span class="legend-dot medium" /> Medium (5-10&Aring;)</span>
        <span><span class="legend-dot far" /> Far (&ge;10&Aring;)</span>
      </div>

      <!-- Interpretation -->
      <v-alert
        v-if="pathogenicStats && vusStats"
        type="info"
        variant="tonal"
        density="compact"
        class="mt-4"
      >
        <div class="text-body-2">
          <strong>Interpretation:</strong>
          Pathogenic/Likely Pathogenic variants have a median distance of
          <strong>{{ pathogenicStats.median.toFixed(1) }} &Aring;</strong>
          to DNA, while VUS have a median of
          <strong>{{ vusStats.median.toFixed(1) }} &Aring;</strong>.
          <span v-if="pValueSignificant">
            This difference is statistically significant (p =
            {{ formatPValueDisplay(mannWhitneyPValue) }}), suggesting that proximity to DNA may
            correlate with pathogenicity.
          </span>
          <span v-else> This difference is not statistically significant at p &lt; 0.05. </span>
        </div>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script>
import { formatPValue } from '@/utils/statistics';

export default {
  name: 'DistanceCategoryBreakdown',
  props: {
    pathogenicCategories: {
      type: Object,
      required: true,
    },
    vusCategories: {
      type: Object,
      required: true,
    },
    pathogenicStats: {
      type: Object,
      default: null,
    },
    vusStats: {
      type: Object,
      default: null,
    },
    mannWhitneyPValue: {
      type: Number,
      default: null,
    },
    pValueSignificant: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      categories: ['close', 'medium', 'far'],
    };
  },
  methods: {
    exportSVG() {
      // Generate SVG programmatically since this component uses HTML/CSS
      const width = 400;
      const height = 200;
      const barHeight = 28;
      const margin = { top: 40, right: 20, bottom: 60, left: 20 };

      const colors = {
        close: '#D32F2F',
        medium: '#FF9800',
        far: '#4CAF50',
      };

      // Create SVG content
      let svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <rect width="100%" height="100%" fill="white"/>

  <!-- Title -->
  <text x="${width / 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#333">
    Distance Categories by Group
  </text>

  <!-- P/LP Label -->
  <text x="${margin.left}" y="${margin.top + 15}" font-size="12" font-weight="500" fill="#333">
    Pathogenic / Likely Pathogenic (n=${this.getGroupTotal('pathogenic')})
  </text>

  <!-- P/LP Bar -->
  <g transform="translate(${margin.left}, ${margin.top + 22})">`;

      // Add P/LP bars
      let xOffset = 0;
      const barWidth = width - margin.left - margin.right;
      for (const cat of this.categories) {
        const catWidth = (this.getCategoryWidth('pathogenic', cat) / 100) * barWidth;
        if (catWidth > 0) {
          svg += `
    <rect x="${xOffset}" y="0" width="${catWidth}" height="${barHeight}" fill="${colors[cat]}"/>`;
          if (this.pathogenicCategories[cat] > 0 && catWidth > 20) {
            svg += `
    <text x="${xOffset + catWidth / 2}" y="${barHeight / 2 + 4}" text-anchor="middle" font-size="11" font-weight="500" fill="white">${this.pathogenicCategories[cat]}</text>`;
          }
          xOffset += catWidth;
        }
      }

      svg += `
  </g>

  <!-- VUS Label -->
  <text x="${margin.left}" y="${margin.top + barHeight + 45}" font-size="12" font-weight="500" fill="#333">
    Variants of Uncertain Significance (n=${this.getGroupTotal('vus')})
  </text>

  <!-- VUS Bar -->
  <g transform="translate(${margin.left}, ${margin.top + barHeight + 52})">`;

      // Add VUS bars
      xOffset = 0;
      for (const cat of this.categories) {
        const catWidth = (this.getCategoryWidth('vus', cat) / 100) * barWidth;
        if (catWidth > 0) {
          svg += `
    <rect x="${xOffset}" y="0" width="${catWidth}" height="${barHeight}" fill="${colors[cat]}"/>`;
          if (this.vusCategories[cat] > 0 && catWidth > 20) {
            svg += `
    <text x="${xOffset + catWidth / 2}" y="${barHeight / 2 + 4}" text-anchor="middle" font-size="11" font-weight="500" fill="white">${this.vusCategories[cat]}</text>`;
          }
          xOffset += catWidth;
        }
      }

      // Add legend
      const legendY = height - 25;
      svg += `
  </g>

  <!-- Legend -->
  <g transform="translate(${margin.left}, ${legendY})">
    <circle cx="8" cy="0" r="5" fill="${colors.close}"/>
    <text x="18" y="4" font-size="10" fill="#666">Close (&lt;5Å)</text>

    <circle cx="${barWidth / 3 + 8}" cy="0" r="5" fill="${colors.medium}"/>
    <text x="${barWidth / 3 + 18}" y="4" font-size="10" fill="#666">Medium (5-10Å)</text>

    <circle cx="${(barWidth * 2) / 3 + 8}" cy="0" r="5" fill="${colors.far}"/>
    <text x="${(barWidth * 2) / 3 + 18}" y="4" font-size="10" fill="#666">Far (≥10Å)</text>
  </g>
</svg>`;

      // Create blob and download
      const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);

      const timestamp = new Date().toISOString().slice(0, 10);
      const filename = `dna-distance-categories-${timestamp}.svg`;

      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    },
    getGroupTotal(group) {
      const categories = group === 'pathogenic' ? this.pathogenicCategories : this.vusCategories;
      return categories.close + categories.medium + categories.far;
    },
    getCategoryWidth(group, category) {
      const categories = group === 'pathogenic' ? this.pathogenicCategories : this.vusCategories;
      const total = categories.close + categories.medium + categories.far;
      if (total === 0) return 0;
      return (categories[category] / total) * 100;
    },
    getCategoryLabel(category) {
      if (category === 'close') return 'Close (<5Å)';
      if (category === 'medium') return 'Medium (5-10Å)';
      return 'Far (≥10Å)';
    },
    formatPValueDisplay(pValue) {
      return formatPValue(pValue);
    },
  },
};
</script>

<style scoped>
.h-100 {
  height: 100%;
}

.distance-distribution {
  display: flex;
  height: 28px;
  border-radius: 4px;
  overflow: hidden;
}

.distance-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  font-weight: 500;
  min-width: 0;
  transition: width 0.3s ease;
}

.distance-bar.close {
  background-color: #d32f2f;
}

.distance-bar.medium {
  background-color: #ff9800;
}

.distance-bar.far {
  background-color: #4caf50;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 4px;
}

.legend-dot.close {
  background-color: #d32f2f;
}

.legend-dot.medium {
  background-color: #ff9800;
}

.legend-dot.far {
  background-color: #4caf50;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-left: 8px;
}

.export-btn:hover {
  background-color: #1565c0;
}

.export-btn:active {
  background-color: #0d47a1;
}

.export-icon {
  font-size: 11px;
}
</style>
