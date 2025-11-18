<!-- HNF1B Gene Structure Visualization -->
<template>
  <v-card class="gene-viz-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left :color="effectiveViewMode === 'cnv' ? 'error' : 'primary'">
        {{ effectiveViewMode === 'cnv' ? 'mdi-chart-box-outline' : 'mdi-dna' }}
      </v-icon>
      {{
        effectiveViewMode === 'cnv'
          ? '17q12 Region - Copy Number Variants'
          : 'HNF1B Gene - SNVs and Small Variants'
      }}
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn
            icon
            size="x-small"
            variant="text"
            v-bind="props"
            :href="
              effectiveViewMode === 'cnv'
                ? 'https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr17%3A36458167-37854616'
                : 'https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr17%3A37686430-37745059'
            "
            target="_blank"
            class="ml-1"
          >
            <v-icon size="small"> mdi-open-in-new </v-icon>
          </v-btn>
        </template>
        <span>{{
          effectiveViewMode === 'cnv'
            ? 'View 17q12 region in UCSC (GRCh38)'
            : 'View HNF1B in UCSC (GRCh38)'
        }}</span>
      </v-tooltip>
      <v-spacer />
      <v-chip size="small" color="info">
        {{ variantsWithPositions.length }} variant{{
          variantsWithPositions.length !== 1 ? 's' : ''
        }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- View Mode Toggle -->
      <v-row v-if="hasExtendedCNV" class="mb-3">
        <v-col cols="12">
          <v-alert type="warning" density="compact" variant="tonal">
            <v-icon left> mdi-alert </v-icon>
            CNV extends beyond HNF1B gene ({{ formatCNVSize() }})
          </v-alert>
          <!-- Toggle button: only show when not in forced mode (i.e., when used standalone) -->
          <v-btn-group v-if="showViewModeToggle" mandatory class="mt-2">
            <v-btn
              :variant="effectiveViewMode === 'gene' ? 'flat' : 'outlined'"
              color="primary"
              @click="viewMode = 'gene'"
            >
              <v-icon left> mdi-dna </v-icon>
              HNF1B Detail
            </v-btn>
            <v-btn
              :variant="effectiveViewMode === 'cnv' ? 'flat' : 'outlined'"
              color="warning"
              @click="viewMode = 'cnv'"
            >
              <v-icon left> mdi-chart-box-outline </v-icon>
              17q12 Region ({{ formatRegionSize() }})
            </v-btn>
          </v-btn-group>
        </v-col>
      </v-row>

      <!-- Legend -->
      <v-row class="mb-2">
        <v-col cols="12">
          <div class="legend-container">
            <v-chip size="small" color="blue">
              <v-icon left size="small"> mdi-square </v-icon>
              Exon (click to zoom)
            </v-chip>
            <v-chip size="small" color="grey">
              <v-icon left size="small"> mdi-minus </v-icon>
              Intron
            </v-chip>
            <v-chip size="small" color="red-lighten-3">
              <v-icon left size="small"> mdi-circle </v-icon>
              Pathogenic
            </v-chip>
            <v-chip size="small" color="orange-lighten-3">
              <v-icon left size="small"> mdi-circle </v-icon>
              Likely Pathogenic
            </v-chip>
            <v-chip size="small" color="yellow-darken-1">
              <v-icon left size="small"> mdi-circle </v-icon>
              VUS
            </v-chip>
            <v-chip v-if="indelVariants.length > 0" size="small" color="deep-orange">
              <v-icon left size="small"> mdi-rectangle-outline </v-icon>
              Small Variant (&lt;50bp)
            </v-chip>
            <v-chip v-if="spliceVariants.length > 0" size="small" color="teal">
              <v-icon left size="small"> mdi-rhombus </v-icon>
              Splice Variant
            </v-chip>
            <!-- "Current" chip: only show when there are multiple variants to distinguish from -->
            <v-chip
              v-if="currentVariantId && variantsWithPositions.length > 1"
              size="small"
              color="purple"
            >
              <v-icon left size="small"> mdi-star </v-icon>
              Current
            </v-chip>
          </div>
        </v-col>
      </v-row>

      <!-- SVG Visualization -->
      <div ref="svgContainer" class="svg-container">
        <svg
          ref="geneSvg"
          :width="svgWidth"
          :height="dynamicSvgHeight"
          class="gene-visualization"
          @mouseleave="hideTooltip"
        >
          <!-- Chromosome label -->
          <text :x="margin.left" :y="20" class="chromosome-label">
            {{
              effectiveViewMode === 'cnv'
                ? `Chromosome ${chr17q12Region.cytoBand} • ${chr17q12Region.name}`
                : 'Chromosome 17q12 • HNF1B (TCF2) • chr17:37,686,430-37,745,059 (58.6 kb)'
            }}
          </text>

          <!-- Gene coordinates (showing visible range) -->
          <text :x="margin.left" :y="dynamicSvgHeight - 10" class="coordinate-label">
            {{ formatCoordinate(visibleGeneStart) }}
          </text>
          <text
            :x="svgWidth - margin.right"
            :y="dynamicSvgHeight - 10"
            text-anchor="end"
            class="coordinate-label"
          >
            {{ formatCoordinate(visibleGeneEnd) }}
          </text>
          <!-- Zoom indicator -->
          <text
            v-if="zoomedExon"
            :x="svgWidth / 2"
            :y="dynamicSvgHeight - 10"
            text-anchor="middle"
            class="zoom-indicator-label"
          >
            Zoomed to Exon {{ zoomedExon.number }} ({{ zoomedExon.size }} bp) - Click exon again or
            Reset to zoom out
          </text>

          <!-- Zoom Group: All visualization content that should zoom/pan -->
          <g id="zoom-group">
            <!-- Intron line (backbone) -->
            <line
              :x1="margin.left"
              :y1="hnf1bTrackY"
              :x2="svgWidth - margin.right"
              :y2="hnf1bTrackY"
              stroke="#9E9E9E"
              stroke-width="3"
            />

            <!-- Exons -->
            <g v-for="exon in exons" :key="`exon-${exon.number}`">
              <rect
                :x="scalePosition(exon.start)"
                :y="hnf1bTrackY - exonHeight / 2"
                :width="Math.max(scalePosition(exon.end) - scalePosition(exon.start), 2)"
                :height="exonHeight"
                :fill="getExonColor(exon)"
                :stroke="zoomedExon?.number === exon.number ? '#FF6F00' : '#1565C0'"
                :stroke-width="zoomedExon?.number === exon.number ? 4 : 2"
                class="exon-rect"
                :class="{ 'exon-zoomed': zoomedExon?.number === exon.number }"
                @mouseenter="showExonTooltip($event, exon)"
                @mousemove="updateTooltipPosition($event)"
                @click="handleExonClick(exon)"
              />
              <!-- Exon label: hidden in region view to avoid clutter -->
              <text
                v-if="effectiveViewMode !== 'cnv'"
                :x="
                  scalePosition(exon.start) +
                  (scalePosition(exon.end) - scalePosition(exon.start)) / 2
                "
                :y="hnf1bTrackY - exonHeight / 2 - 8"
                text-anchor="middle"
                class="exon-label"
              >
                E{{ exon.number }}
              </text>
            </g>

            <!-- Gene Track (CNV mode only) -->
            <g v-if="effectiveViewMode === 'cnv'">
              <!-- Gene track title -->
              <text :x="margin.left" :y="centerY - 120" class="gene-track-label" font-weight="600">
                Genes in 17q12 Region:
              </text>

              <!-- Gene rectangles -->
              <g v-for="(gene, index) in chr17q12Genes" :key="`gene-${gene.symbol}`">
                <rect
                  :x="scalePosition(gene.start)"
                  :y="centerY - 60"
                  :width="Math.max(scalePosition(gene.end) - scalePosition(gene.start), 2)"
                  :height="20"
                  :fill="gene.color"
                  :stroke="gene.clinicalSignificance === 'critical' ? '#D32F2F' : '#424242'"
                  :stroke-width="gene.clinicalSignificance === 'critical' ? 3 : 1"
                  :opacity="0.8"
                  class="gene-rect"
                  @mouseenter="showGeneTooltip($event, gene)"
                  @mousemove="updateTooltipPosition($event)"
                />
                <!-- Gene label with connecting line - show ALL genes in 6 staggered rows (3 above, 3 below) -->
                <!-- Use collision-aware distribution to minimize overlap -->
                <g>
                  <!-- Connecting line from gene to label -->
                  <line
                    :x1="
                      scalePosition(gene.start) +
                      (scalePosition(gene.end) - scalePosition(gene.start)) / 2
                    "
                    :y1="getGeneLabelRow(index, gene) < 3 ? centerY - 60 : centerY - 40"
                    :x2="
                      scalePosition(gene.start) +
                      (scalePosition(gene.end) - scalePosition(gene.start)) / 2
                    "
                    :y2="getGeneLabelLineEndY(getGeneLabelRow(index, gene))"
                    stroke="#666"
                    stroke-width="1"
                    stroke-dasharray="2,2"
                    opacity="0.7"
                  />
                  <!-- Gene label -->
                  <text
                    :x="
                      scalePosition(gene.start) +
                      (scalePosition(gene.end) - scalePosition(gene.start)) / 2
                    "
                    :y="getGeneLabelYPosition(getGeneLabelRow(index, gene))"
                    text-anchor="middle"
                    class="gene-name-label"
                    font-size="10"
                    font-weight="600"
                    :fill="
                      gene.clinicalSignificance === 'critical' ||
                      gene.clinicalSignificance === 'high'
                        ? '#D32F2F'
                        : '#424242'
                    "
                    pointer-events="none"
                  >
                    {{ gene.symbol }}
                  </text>
                </g>
              </g>
            </g>

            <!-- CNV deletions (background bars) -->
            <g v-for="(cnv, index) in cnvVariants" :key="`cnv-${index}`">
              <!-- CNV deletion/duplication bar -->
              <rect
                v-if="cnv.start && cnv.end && getCNVDisplayCoords(cnv).width > 0"
                :x="getCNVDisplayCoords(cnv).x"
                :y="hnf1bTrackY + exonHeight / 2 + 10 + index * 20"
                :width="getCNVDisplayCoords(cnv).width"
                :height="15"
                :fill="getCNVColor(cnv)"
                :opacity="0.7"
                stroke="#424242"
                stroke-width="1"
                class="cnv-rect"
                @mouseenter="showVariantTooltip($event, cnv)"
                @mousemove="updateTooltipPosition($event)"
                @click="handleVariantClick(cnv)"
              />
            </g>

            <!-- Indel markers (small deletions/insertions < 50bp) -->
            <!-- Only shown in gene mode, not CNV mode -->
            <template v-if="effectiveViewMode !== 'cnv'">
              <g v-for="(indel, index) in indelVariants" :key="`indel-${index}`">
                <!-- Indel deletion bar (positioned below HNF1B track with larger gap) -->
                <rect
                  v-if="indel.start && indel.end"
                  :x="scalePosition(indel.start)"
                  :y="hnf1bTrackY + exonHeight / 2 + 30"
                  :width="Math.max(scalePosition(indel.end) - scalePosition(indel.start), 3)"
                  :height="25"
                  :fill="getVariantColor(indel)"
                  :stroke="'#424242'"
                  :stroke-width="1"
                  :opacity="0.9"
                  class="indel-rect"
                  @mouseenter="showVariantTooltip($event, indel)"
                  @mousemove="updateTooltipPosition($event)"
                  @click="handleVariantClick(indel)"
                />
                <!-- Connecting line from indel to affected exon region -->
                <line
                  v-if="indel.start && indel.end"
                  :x1="scalePosition(indel.start)"
                  :y1="hnf1bTrackY + exonHeight / 2"
                  :x2="scalePosition(indel.start)"
                  :y2="hnf1bTrackY + exonHeight / 2 + 30"
                  stroke="#424242"
                  stroke-width="1"
                  opacity="0.6"
                />
                <line
                  v-if="indel.start && indel.end"
                  :x1="scalePosition(indel.end)"
                  :y1="hnf1bTrackY + exonHeight / 2"
                  :x2="scalePosition(indel.end)"
                  :y2="hnf1bTrackY + exonHeight / 2 + 30"
                  stroke="#424242"
                  stroke-width="1"
                  opacity="0.6"
                />
                <!-- Indel label for current variant (positioned below the bar) -->
                <text
                  v-if="indel.isCurrentVariant"
                  :x="
                    scalePosition(indel.start) +
                    (scalePosition(indel.end) - scalePosition(indel.start)) / 2
                  "
                  :y="hnf1bTrackY + exonHeight / 2 + 65"
                  text-anchor="middle"
                  class="indel-label-text"
                  fill="#9C27B0"
                  font-size="13"
                  font-weight="bold"
                  pointer-events="none"
                >
                  {{ indel.simple_id || indel.variant_id }}
                </text>
                <!-- Star icon for current indel (next to label) -->
                <text
                  v-if="indel.isCurrentVariant"
                  :x="
                    scalePosition(indel.start) +
                    (scalePosition(indel.end) - scalePosition(indel.start)) / 2 -
                    35
                  "
                  :y="hnf1bTrackY + exonHeight / 2 + 65"
                  text-anchor="middle"
                  class="variant-star-icon"
                  fill="#9C27B0"
                  font-size="13"
                  font-weight="bold"
                  pointer-events="none"
                >
                  ★
                </text>
              </g>
            </template>

            <!-- SNV markers -->
            <!-- Only shown in gene mode, not CNV mode -->
            <template v-if="effectiveViewMode !== 'cnv'">
              <g v-for="(variant, index) in snvVariants" :key="`snv-${index}`">
                <!-- Connecting line (longer to avoid exon label overlap) -->
                <line
                  v-if="variant.position"
                  :x1="scalePosition(variant.position)"
                  :y1="hnf1bTrackY - exonHeight / 2"
                  :x2="scalePosition(variant.position)"
                  :y2="hnf1bTrackY - exonHeight / 2 - 50 - (index % 3) * 12"
                  :stroke="variant.isCurrentVariant ? '#9C27B0' : '#BDBDBD'"
                  :stroke-width="variant.isCurrentVariant ? 2 : 1"
                  stroke-dasharray="2,2"
                />
                <!-- Variant marker circle (removed purple border for non-current) -->
                <circle
                  v-if="variant.position"
                  :cx="scalePosition(variant.position)"
                  :cy="hnf1bTrackY - exonHeight / 2 - 50 - (index % 3) * 12"
                  :r="variant.isCurrentVariant ? 15 : 5"
                  :fill="getVariantColor(variant)"
                  :stroke="variant.isCurrentVariant ? '#9C27B0' : 'none'"
                  :stroke-width="variant.isCurrentVariant ? 5 : 0"
                  :opacity="variant.isCurrentVariant ? 1 : 0.7"
                  class="variant-circle"
                  :class="{ 'current-variant': variant.isCurrentVariant }"
                  @mouseenter="showVariantTooltip($event, variant)"
                  @mousemove="updateTooltipPosition($event)"
                  @click="handleVariantClick(variant)"
                />
                <!-- Star icon for current variant -->
                <text
                  v-if="variant.position && variant.isCurrentVariant"
                  :x="scalePosition(variant.position)"
                  :y="hnf1bTrackY - exonHeight / 2 - 50 - (index % 3) * 12 + 6"
                  text-anchor="middle"
                  class="variant-star-icon"
                  fill="white"
                  font-size="16"
                  font-weight="bold"
                  pointer-events="none"
                >
                  ★
                </text>
                <!-- Variant label for current variant -->
                <text
                  v-if="variant.position && variant.isCurrentVariant"
                  :x="scalePosition(variant.position)"
                  :y="hnf1bTrackY - exonHeight / 2 - 90"
                  text-anchor="middle"
                  class="variant-label-text"
                  fill="#9C27B0"
                  font-size="14"
                  font-weight="bold"
                  pointer-events="none"
                >
                  {{ variant.simple_id || variant.variant_id }}
                </text>
                <!-- Protein notation for current variant -->
                <text
                  v-if="variant.position && variant.isCurrentVariant && variant.protein"
                  :x="scalePosition(variant.position)"
                  :y="hnf1bTrackY - exonHeight / 2 - 75"
                  text-anchor="middle"
                  class="variant-protein-text"
                  fill="#757575"
                  font-size="11"
                  pointer-events="none"
                >
                  {{ extractPNotation(variant.protein) }}
                </text>
              </g>
            </template>

            <!-- Splice variant markers (diamonds) -->
            <!-- Only shown in gene mode, not CNV mode -->
            <template v-if="effectiveViewMode !== 'cnv'">
              <g v-for="(variant, index) in spliceVariants" :key="`splice-${index}`">
                <!-- Connecting line (same as SNVs but with different end position) -->
                <line
                  v-if="variant.position"
                  :x1="scalePosition(variant.position)"
                  :y1="hnf1bTrackY - exonHeight / 2"
                  :x2="scalePosition(variant.position)"
                  :y2="hnf1bTrackY - exonHeight / 2 - 50 - (index % 3) * 12"
                  :stroke="variant.isCurrentVariant ? '#9C27B0' : '#BDBDBD'"
                  :stroke-width="variant.isCurrentVariant ? 2 : 1"
                  stroke-dasharray="2,2"
                />
                <!-- Diamond marker (rotated square) -->
                <rect
                  v-if="variant.position"
                  :x="scalePosition(variant.position) - (variant.isCurrentVariant ? 10.5 : 3.5)"
                  :y="
                    hnf1bTrackY -
                    exonHeight / 2 -
                    50 -
                    (index % 3) * 12 -
                    (variant.isCurrentVariant ? 10.5 : 3.5)
                  "
                  :width="variant.isCurrentVariant ? 21 : 7"
                  :height="variant.isCurrentVariant ? 21 : 7"
                  :fill="getVariantColor(variant)"
                  :stroke="variant.isCurrentVariant ? '#9C27B0' : 'none'"
                  :stroke-width="variant.isCurrentVariant ? 3 : 0"
                  :opacity="variant.isCurrentVariant ? 1 : 0.7"
                  :transform="`rotate(45, ${scalePosition(variant.position)}, ${hnf1bTrackY - exonHeight / 2 - 50 - (index % 3) * 12})`"
                  class="variant-diamond"
                  :class="{ 'current-variant': variant.isCurrentVariant }"
                  @mouseenter="showVariantTooltip($event, variant)"
                  @mousemove="updateTooltipPosition($event)"
                  @click="handleVariantClick(variant)"
                />
                <!-- Star icon for current splice variant -->
                <text
                  v-if="variant.position && variant.isCurrentVariant"
                  :x="scalePosition(variant.position)"
                  :y="hnf1bTrackY - exonHeight / 2 - 50 - (index % 3) * 12 + 5"
                  text-anchor="middle"
                  class="variant-star-icon"
                  fill="white"
                  font-size="14"
                  font-weight="bold"
                  pointer-events="none"
                >
                  ★
                </text>
                <!-- Variant label for current splice variant -->
                <text
                  v-if="variant.position && variant.isCurrentVariant"
                  :x="scalePosition(variant.position)"
                  :y="hnf1bTrackY - exonHeight / 2 - 90"
                  text-anchor="middle"
                  class="variant-label-text"
                  fill="#9C27B0"
                  font-size="14"
                  font-weight="bold"
                  pointer-events="none"
                >
                  {{ variant.simple_id || variant.variant_id }}
                </text>
                <!-- Transcript notation for current splice variant -->
                <text
                  v-if="variant.position && variant.isCurrentVariant && variant.transcript"
                  :x="scalePosition(variant.position)"
                  :y="hnf1bTrackY - exonHeight / 2 - 75"
                  text-anchor="middle"
                  class="variant-protein-text"
                  fill="#757575"
                  font-size="11"
                  pointer-events="none"
                >
                  {{ extractCNotation(variant.transcript) }}
                </text>
              </g>
            </template>
          </g>
        </svg>
      </div>

      <!-- Zoom Controls -->
      <v-row class="mt-3">
        <v-col cols="12" class="text-center">
          <v-btn-group density="compact">
            <v-btn size="small" @click="zoomIn">
              <v-icon>mdi-magnify-plus</v-icon>
            </v-btn>
            <v-btn size="small" @click="zoomOut">
              <v-icon>mdi-magnify-minus</v-icon>
            </v-btn>
            <v-btn size="small" @click="resetZoom">
              <v-icon>mdi-magnify</v-icon>
              Reset
            </v-btn>
          </v-btn-group>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Floating Tooltip -->
    <div
      v-if="tooltipVisible && tooltipContent"
      :style="{
        position: 'fixed',
        left: tooltipX + 'px',
        top: tooltipY + 'px',
        zIndex: 9999,
      }"
      class="custom-tooltip"
    >
      <v-card max-width="350" elevation="8">
        <v-card-text class="pa-3">
          <div v-if="tooltipContent.type === 'exon'">
            <div class="text-h6 mb-2">Exon {{ tooltipContent.data.number }}</div>
            <div class="text-body-2">
              <strong>Position:</strong> chr17:{{ formatCoordinate(tooltipContent.data.start) }}-{{
                formatCoordinate(tooltipContent.data.end)
              }}
            </div>
            <div class="text-body-2"><strong>Size:</strong> {{ tooltipContent.data.size }} bp</div>
            <div v-if="tooltipContent.data.domain" class="text-body-2">
              <strong>Domain:</strong> {{ tooltipContent.data.domain }}
            </div>
            <div class="text-caption mt-2 text-grey">
              <v-icon size="small" left> mdi-magnify-plus-outline </v-icon>
              Click to zoom to this exon
            </div>
          </div>
          <div v-else-if="tooltipContent.type === 'variant'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.simple_id || tooltipContent.data.variant_id }}
            </div>
            <div v-if="tooltipContent.data.indelType" class="text-body-2 mb-1">
              <strong>Type:</strong> {{ tooltipContent.data.indelType }}
            </div>
            <div v-if="tooltipContent.data.transcript" class="text-body-2">
              {{ extractCNotation(tooltipContent.data.transcript) }}
            </div>
            <div v-if="tooltipContent.data.protein" class="text-body-2">
              {{ extractPNotation(tooltipContent.data.protein) }}
            </div>
            <div class="mt-2">
              <v-chip :color="getVariantColor(tooltipContent.data)" size="small">
                {{ tooltipContent.data.classificationVerdict || 'Unknown' }}
              </v-chip>
            </div>
            <div class="text-caption mt-2 text-grey">Click to view details</div>
          </div>
          <div v-else-if="tooltipContent.type === 'gene'">
            <div class="text-h6 mb-2">
              {{ tooltipContent.data.symbol }}
            </div>
            <div class="text-body-2 mb-1">
              <strong>{{ tooltipContent.data.name }}</strong>
            </div>
            <div class="text-body-2">
              chr17:{{ formatCoordinate(tooltipContent.data.start) }}-{{
                formatCoordinate(tooltipContent.data.end)
              }}
            </div>
            <div class="text-body-2">
              Size: {{ (tooltipContent.data.size / 1000).toFixed(1) }} kb
            </div>
            <div v-if="tooltipContent.data.function" class="text-body-2 mt-2">
              <strong>Function:</strong> {{ tooltipContent.data.function }}
            </div>
            <div v-if="tooltipContent.data.phenotype" class="text-body-2 mt-1">
              <strong>Phenotype:</strong> {{ tooltipContent.data.phenotype }}
            </div>
            <v-chip
              v-if="tooltipContent.data.clinicalSignificance !== 'unknown'"
              :color="tooltipContent.data.color"
              size="small"
              class="mt-2"
            >
              {{ tooltipContent.data.clinicalSignificance }} significance
            </v-chip>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </v-card>
</template>

<script>
import * as d3 from 'd3';
import { extractCNotation, extractPNotation } from '@/utils/hgvs';
import { getCNVDetails } from '@/utils/variants';
import { getReferenceGenomicRegion } from '@/api';

export default {
  name: 'HNF1BGeneVisualization',
  props: {
    variants: {
      type: Array,
      default: () => [],
    },
    currentVariantId: {
      type: String,
      default: null,
    },
    forceViewMode: {
      type: String,
      default: null,
      validator: (value) => value === null || ['gene', 'cnv'].includes(value),
    },
  },
  emits: ['variant-clicked'],
  data() {
    return {
      svgWidth: 1000,
      svgHeight: 480, // Increased to accommodate 6 rows of gene labels (3 above + 3 below)
      margin: { top: 130, right: 50, bottom: 130, left: 50 }, // Increased top and bottom margins for 6-layer gene labels
      exonHeight: 40,
      geneStart: 37680000, // chr17 coordinates (GRCh38) - adjusted to show actual variant positions
      geneEnd: 37750000, // 70kb range covering all HNF1B coding variants
      tooltipVisible: false,
      tooltipX: 0,
      tooltipY: 0,
      tooltipContent: null,
      zoomLevel: 1,
      zoomedExon: null, // Track which exon is zoomed in
      viewMode: 'gene', // 'gene' or 'cnv'
      // Loading state for API data
      loading: false,
      apiError: null,
      // Chr17q12 region data - fallback values
      chr17q12Region: {
        chromosome: '17',
        cytoBand: '17q12',
        start: 36000000,
        end: 39900000,
        size: 3900000,
        name: '17q12 extended region (chr17:36.0-39.9 Mb)',
        assembly: 'GRCh38/hg38',
      },
      chr17q12Genes: [], // Will be populated from API
      // D3 zoom properties
      d3Zoom: null, // D3 zoom behavior instance
      d3Transform: null, // Current D3 zoom transform
      exons: [
        // HNF1B coding exons (GRCh38 coordinates from UCSC NM_000458.4)
        // Note: Gene is on minus strand, so exon 1 is at higher genomic coordinates
        { number: 1, start: 37744540, end: 37745059, size: 519, domain: "5' UTR" },
        { number: 2, start: 37739439, end: 37739639, size: 200, domain: null },
        { number: 3, start: 37733556, end: 37733821, size: 265, domain: 'POU-S' },
        { number: 4, start: 37731594, end: 37731830, size: 236, domain: 'POU-H' },
        { number: 5, start: 37710502, end: 37710663, size: 161, domain: 'POU-H' },
        { number: 6, start: 37704916, end: 37705049, size: 133, domain: null },
        { number: 7, start: 37700982, end: 37701177, size: 195, domain: 'Transactivation' },
        { number: 8, start: 37699075, end: 37699194, size: 119, domain: 'Transactivation' },
        { number: 9, start: 37686430, end: 37687392, size: 962, domain: "3' UTR" },
      ],
    };
  },
  computed: {
    // Effective view mode: use forceViewMode if provided, otherwise use local viewMode
    effectiveViewMode() {
      return this.forceViewMode || this.viewMode;
    },
    // Show toggle button only when not forced to a specific mode
    showViewModeToggle() {
      return this.forceViewMode === null;
    },
    // Dynamic SVG height based on number of CNVs in CNV mode
    dynamicSvgHeight() {
      if (this.effectiveViewMode === 'cnv' && this.cnvVariants.length > 0) {
        // Base height + space for CNVs (20px per CNV)
        const cnvSpace = this.cnvVariants.length * 20 + 50;
        return Math.max(600, this.margin.top + this.margin.bottom + cnvSpace + 200);
      }
      return this.svgHeight;
    },
    centerY() {
      return (this.dynamicSvgHeight - this.margin.top - this.margin.bottom) / 2 + this.margin.top;
    },
    // HNF1B track Y position (shifted down in CNV mode to avoid overlap with gene labels)
    hnf1bTrackY() {
      // In CNV mode, shift down by 60px to leave space for gene labels below the 17q12 genes
      return this.effectiveViewMode === 'cnv' ? this.centerY + 60 : this.centerY;
    },
    visibleGeneStart() {
      if (this.zoomedExon) {
        // Add padding around exon (200bp on each side)
        return Math.max(this.zoomedExon.start - 200, this.geneStart);
      }
      // CNV mode: show full 17q12 region
      if (this.effectiveViewMode === 'cnv') {
        return this.chr17q12Region.start;
      }
      return this.geneStart;
    },
    visibleGeneEnd() {
      if (this.zoomedExon) {
        // Add padding around exon (200bp on each side)
        return Math.min(this.zoomedExon.end + 200, this.geneEnd);
      }
      // CNV mode: show full 17q12 region
      if (this.effectiveViewMode === 'cnv') {
        return this.chr17q12Region.end;
      }
      return this.geneEnd;
    },
    currentVariantCNVDetails() {
      // Parse CNV details directly from currentVariantId if it's a CNV
      // Format: var:HNF1B:17:36459258-37832869:DEL
      if (!this.currentVariantId) return null;

      const cnvMatch = this.currentVariantId.match(/(\d+|X|Y|MT?):(\d+)-(\d+):([A-Z]+)/);
      if (cnvMatch) {
        return {
          chromosome: cnvMatch[1],
          start: parseInt(cnvMatch[2]),
          end: parseInt(cnvMatch[3]),
          type: cnvMatch[4],
        };
      }
      return null;
    },
    hasExtendedCNV() {
      // Check if there are CNVs in the variants array that extend beyond HNF1B
      const hasCNVsInArray = this.cnvVariants.some(
        (cnv) => cnv.start < this.geneStart - 10000 || cnv.end > this.geneEnd + 10000
      );

      // Also check if current variant ID itself is an extended CNV
      if (this.currentVariantCNVDetails) {
        const { start, end } = this.currentVariantCNVDetails;
        return hasCNVsInArray || start < this.geneStart - 10000 || end > this.geneEnd + 10000;
      }

      return hasCNVsInArray;
    },
    variantsWithPositions() {
      // If currentVariantId is provided, show only that variant (used on variant detail page)
      // If no currentVariantId, show all variants (used on homepage)
      const filteredVariants = this.currentVariantId
        ? this.variants.filter((v) => v.variant_id === this.currentVariantId)
        : this.variants;

      return filteredVariants
        .map((v) => ({
          ...v,
          isCurrentVariant: v.variant_id === this.currentVariantId,
          position: this.extractVariantPosition(v),
          isCNV: this.isCNV(v),
          isIndel: this.isIndel(v),
          isSpliceVariant: this.isSpliceVariant(v),
        }))
        .filter((v) => v.position !== null);
    },
    snvVariants() {
      return this.variantsWithPositions.filter((v) => !v.isCNV && !v.isIndel && !v.isSpliceVariant);
    },
    spliceVariants() {
      return this.variantsWithPositions.filter((v) => v.isSpliceVariant);
    },
    indelVariants() {
      return this.variantsWithPositions
        .filter((v) => v.isIndel)
        .map((v) => {
          const details = this.getIndelDetails(v);
          return {
            ...v,
            start: details?.start ? parseInt(details.start) : null,
            end: details?.end ? parseInt(details.end) : null,
            indelType: details?.type,
          };
        })
        .filter((v) => v.start && v.end);
    },
    cnvVariants() {
      const cnvsFromArray = this.variantsWithPositions
        .filter((v) => v.isCNV)
        .map((v) => {
          const cnvDetails = this.getCNVDetails(v);
          return {
            ...v,
            start: cnvDetails?.start ? parseInt(cnvDetails.start) : null,
            end: cnvDetails?.end ? parseInt(cnvDetails.end) : null,
            cnvType: cnvDetails?.type,
            size: cnvDetails ? parseInt(cnvDetails.end) - parseInt(cnvDetails.start) : 0,
          };
        })
        .filter((v) => v.start && v.end)
        .sort((a, b) => b.size - a.size); // Sort by size descending (largest first)

      // If variants array is empty but current variant is a CNV, add it
      if (cnvsFromArray.length === 0 && this.currentVariantCNVDetails) {
        return [
          {
            variant_id: this.currentVariantId,
            isCurrentVariant: true,
            start: this.currentVariantCNVDetails.start,
            end: this.currentVariantCNVDetails.end,
            cnvType: this.currentVariantCNVDetails.type,
            classificationVerdict: 'PATHOGENIC', // Default for current variant
            size: this.currentVariantCNVDetails.end - this.currentVariantCNVDetails.start,
          },
        ];
      }

      return cnvsFromArray;
    },
    geneLabelRowAssignments() {
      // Collision-aware row assignment for gene labels
      // Returns a map of gene symbol -> row number (0-5)
      // Rows 0-2: Above gene track (top to bottom)
      // Rows 3-5: Below gene track (top to bottom)

      if (this.effectiveViewMode !== 'cnv') return {};

      const genes = this.chr17q12Genes;
      const assignments = {};

      // Track occupied regions for each row (array of {start, end} ranges in pixels)
      const rowOccupancy = [[], [], [], [], [], []]; // 6 rows: 3 above + 3 below

      // Character width estimation (approximate pixels per character for font-size: 10, font-weight: 600)
      const charWidth = 10;
      const labelPadding = 35;

      // Sort genes by their center position (left to right)
      const sortedGenes = [...genes].sort((a, b) => {
        const centerA = (a.start + a.end) / 2;
        const centerB = (b.start + b.end) / 2;
        return centerA - centerB;
      });

      // Assign each gene to the first available row
      sortedGenes.forEach((gene) => {
        const geneCenter = (gene.start + gene.end) / 2;
        const pixelX = this.scalePosition(geneCenter);
        const labelWidth = gene.symbol.length * charWidth + labelPadding;
        const labelStart = pixelX - labelWidth / 2;
        const labelEnd = pixelX + labelWidth / 2;

        // Try to find a row without collision
        let assignedRow = -1;
        for (let row = 0; row < 6; row++) {
          // Check if this position collides with any existing labels in this row
          const hasCollision = rowOccupancy[row].some((occupied) => {
            return labelEnd >= occupied.start && labelStart <= occupied.end;
          });

          if (!hasCollision) {
            assignedRow = row;
            break;
          }
        }

        // If all rows have collisions, find the row with the most space (least overlap)
        if (assignedRow === -1) {
          let minOverlap = Infinity;
          for (let row = 0; row < 6; row++) {
            let totalOverlap = 0;
            rowOccupancy[row].forEach((occupied) => {
              const overlapStart = Math.max(labelStart, occupied.start);
              const overlapEnd = Math.min(labelEnd, occupied.end);
              if (overlapStart < overlapEnd) {
                totalOverlap += overlapEnd - overlapStart;
              }
            });
            if (totalOverlap < minOverlap) {
              minOverlap = totalOverlap;
              assignedRow = row;
            }
          }
        }

        // Assign to this row and mark the region as occupied
        assignments[gene.symbol] = assignedRow;
        rowOccupancy[assignedRow].push({ start: labelStart, end: labelEnd });
      });

      return assignments;
    },
  },
  watch: {
    // Update SVG width when view mode changes (e.g., switching to region view)
    effectiveViewMode() {
      this.$nextTick(() => {
        this.updateSVGWidth();
      });
    },
  },
  async mounted() {
    this.updateSVGWidth();
    window.addEventListener('resize', this.updateSVGWidth);
    this.initializeD3Zoom();
    window.addEventListener('keydown', this.handleKeyboardShortcuts);

    // Fetch chr17q12 genes from API
    await this.fetchChr17q12Genes();
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.updateSVGWidth);
    window.removeEventListener('keydown', this.handleKeyboardShortcuts);
  },
  methods: {
    async fetchChr17q12Genes() {
      try {
        this.loading = true;
        this.apiError = null;

        window.logService.info('Fetching chr17q12 genes from API');

        // Fetch genes in the 17q12 region (36.0-39.9 Mb)
        const response = await getReferenceGenomicRegion('17:36000000-39900000', 'GRCh38');

        if (response.data && response.data.genes && response.data.genes.length > 0) {
          // Map API gene data to component format and filter for clinical relevance
          const MIN_GENE_SIZE = 10000; // 10kb minimum size

          this.chr17q12Genes = response.data.genes
            .map((gene) => ({
              symbol: gene.symbol,
              name: gene.name,
              start: gene.start,
              end: gene.end,
              size: gene.end - gene.start,
              strand: gene.strand,
              biotype: gene.extra_data?.biotype || 'protein_coding',
              transcriptId: gene.extra_data?.transcript_id || null,
              mim: gene.extra_data?.mim || null,
              function: gene.extra_data?.function || null,
              phenotype: gene.extra_data?.phenotype || null,
              clinicalSignificance: gene.extra_data?.clinical_significance || 'unknown',
              color: gene.extra_data?.color || '#90CAF9',
            }))
            .filter((gene) => {
              // Filter 1: Protein-coding genes only (exclude lncRNA, miRNA, etc.)
              const isProteinCoding = gene.biotype === 'protein_coding';

              // Filter 2: Has approved gene symbol (not ENSG* novel transcript)
              const hasApprovedSymbol = !gene.symbol.startsWith('ENSG');

              // Filter 3: Minimum size of 10kb to reduce clutter
              const meetsMinSize = gene.size >= MIN_GENE_SIZE;

              return isProteinCoding && hasApprovedSymbol && meetsMinSize;
            });

          window.logService.info('Successfully loaded chr17q12 genes from API (filtered)', {
            totalGenes: response.data.genes.length,
            filteredGenes: this.chr17q12Genes.length,
            filter: 'protein-coding, approved symbols, >10kb',
          });
        } else {
          window.logService.warn('No genes returned from API for 17q12 region');
        }
      } catch (error) {
        this.apiError = error.message;
        window.logService.warn('Failed to fetch chr17q12 genes from API, using empty array', {
          error: error.message,
        });
        // Keep empty array - component will still work but CNV mode won't show genes
      } finally {
        this.loading = false;
      }
    },
    updateSVGWidth() {
      if (this.$refs.svgContainer) {
        const containerWidth = this.$refs.svgContainer.clientWidth;
        // Use full container width for CNV view (no scrolling), minimum 800px for gene view
        const minWidth = this.effectiveViewMode === 'cnv' ? containerWidth : 800;
        this.svgWidth = Math.max(containerWidth, minWidth);
      }
    },
    scalePosition(genomicPosition) {
      // Use visible range when zoomed, full range otherwise
      const geneLength = this.visibleGeneEnd - this.visibleGeneStart;
      const svgLength = this.svgWidth - this.margin.left - this.margin.right;
      const relativePosition = (genomicPosition - this.visibleGeneStart) / geneLength;
      return this.margin.left + relativePosition * svgLength;
    },
    getGeneLabelRow(index, gene) {
      // Use cached row assignments calculated in computed property
      if (!this.geneLabelRowAssignments) return index % 6;
      return this.geneLabelRowAssignments[gene.symbol] || 0;
    },
    getGeneLabelYPosition(row) {
      // Calculate Y position for gene label based on row
      // Rows 0-2: Above gene track (top to bottom)
      // Rows 3-5: Below gene track (directly below gene boxes which end at centerY - 40)
      const rowSpacing = 15; // Vertical spacing between rows

      if (row < 3) {
        // Above gene track: row 0 is furthest up, row 2 is closest to gene
        return this.centerY - 70 - (2 - row) * rowSpacing;
      } else {
        // Below gene track: Start at centerY - 30 (10px below gene boxes which end at centerY - 40)
        // row 3 is closest to gene, row 5 is furthest down
        return this.centerY - 30 + (row - 3) * rowSpacing;
      }
    },
    getGeneLabelLineEndY(row) {
      // Calculate Y position for end of connecting line
      const rowSpacing = 15;

      if (row < 3) {
        // Above gene track: line goes up from gene
        return this.centerY - 65 - (2 - row) * rowSpacing;
      } else {
        // Below gene track: line goes down from gene bottom (centerY - 40) to label
        return this.centerY - 35 + (row - 3) * rowSpacing;
      }
    },
    extractVariantPosition(variant) {
      // For CNVs, return the midpoint
      if (this.isCNV(variant)) {
        const details = this.getCNVDetails(variant);
        if (details) {
          return (parseInt(details.start) + parseInt(details.end)) / 2;
        }
      }

      // Parse from HG38 coordinate
      if (variant.hg38) {
        // Format: "chr17-36098063-C-T" or "17:36459258-37832869:DEL"
        const snvMatch = variant.hg38.match(/chr\d+-(\d+)-/);
        if (snvMatch) return parseInt(snvMatch[1]);

        const cnvMatch = variant.hg38.match(/:(\d+)-(\d+):/);
        if (cnvMatch) return (parseInt(cnvMatch[1]) + parseInt(cnvMatch[2])) / 2;
      }

      return null;
    },
    isCNV(variant) {
      if (!variant || !variant.hg38) return false;
      // Check for range notation: 17:start-end:DEL/DUP
      const hasRangeNotation = /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
      if (!hasRangeNotation) return false;

      // Extract start and end positions
      const match = variant.hg38.match(/:(\d+)-(\d+):/);
      if (match) {
        const start = parseInt(match[1]);
        const end = parseInt(match[2]);
        const size = end - start;

        // Consider variants < 50bp as indels (small deletions/insertions)
        // These should be displayed differently from large CNVs (>= 50bp)
        return size >= 50;
      }

      return false;
    },
    isIndel(variant) {
      if (!variant || !variant.hg38) return false;

      // Check for range notation: 17:start-end:DEL/DUP
      const hasRangeNotation = /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
      if (hasRangeNotation) {
        // Extract start and end positions
        const match = variant.hg38.match(/:(\d+)-(\d+):/);
        if (match) {
          const start = parseInt(match[1]);
          const end = parseInt(match[2]);
          const size = end - start;

          // Indels are small variants < 50bp
          return size < 50;
        }
      }

      // Check for VCF-style indels: chr17-37710502-ATCG-A or chr17-37710502-A-ATCG
      // Where ref and alt have different lengths (not just substitution)
      const vcfMatch = variant.hg38.match(/chr(\d+|X|Y|MT?)-(\d+)-([A-Z]+)-([A-Z]+)/i);
      if (vcfMatch) {
        const ref = vcfMatch[3];
        const alt = vcfMatch[4];
        // If ref and alt have different lengths, it's an indel
        if (ref.length !== alt.length) {
          return true;
        }
      }

      return false;
    },
    isSpliceVariant(variant) {
      // Check if variant is a splice site variant
      // Splice variants have transcript notation with +/- positions and no protein notation
      if (!variant) return false;

      const hasTranscript = variant.transcript && variant.transcript !== '-';
      const noProtein = !variant.protein || variant.protein === '-';
      const isSpliceSite = hasTranscript && /[+-]\d+/.test(variant.transcript);

      return hasTranscript && noProtein && isSpliceSite;
    },
    getIndelDetails(variant) {
      if (!variant || !variant.hg38) return null;

      // First try range notation: 17:start-end:DEL/DUP
      const rangeMatch = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):([A-Z]+)/);
      if (rangeMatch) {
        return {
          chromosome: rangeMatch[1],
          start: rangeMatch[2],
          end: rangeMatch[3],
          type: rangeMatch[4],
        };
      }

      // Try VCF-style: chr17-37710502-ATCG-A or chr17-37710502-A-ATCG
      const vcfMatch = variant.hg38.match(/chr(\d+|X|Y|MT?)-(\d+)-([A-Z]+)-([A-Z]+)/i);
      if (vcfMatch) {
        const pos = parseInt(vcfMatch[2]);
        const ref = vcfMatch[3];
        const alt = vcfMatch[4];

        // Determine type and calculate end position
        let type = 'INDEL';
        let end = pos;

        if (ref.length > 1 && alt.length > 1 && ref.length !== alt.length) {
          // Complex indel: both ref and alt are multi-base and different lengths
          // This is a deletion-insertion event (indel with both del and ins)
          type = 'INDEL';
          end = pos + ref.length - 1;
        } else if (ref.length > alt.length) {
          // Pure deletion: reference is longer than alternate
          type = 'DEL';
          end = pos + ref.length - 1;
        } else if (alt.length > ref.length) {
          // Pure insertion: alternate is longer than reference
          type = 'INS';
          end = pos + ref.length; // Insertions don't extend the reference
        } else if (ref !== alt && ref.length === alt.length) {
          // Substitution: same length but different bases (not technically an indel)
          type = 'SUB';
          end = pos + ref.length - 1;
        }

        return {
          chromosome: vcfMatch[1],
          start: pos.toString(),
          end: end.toString(),
          type: type,
        };
      }

      return null;
    },
    getExonColor(exon) {
      if (exon.domain?.includes('POU')) return '#42A5F5'; // Blue
      if (exon.domain?.includes('Transactivation')) return '#66BB6A'; // Green
      if (exon.domain?.includes('UTR')) return '#BDBDBD'; // Grey
      return '#1E88E5'; // Default blue
    },
    getVariantColor(variant) {
      const classification = variant.classificationVerdict?.toUpperCase() || '';
      if (classification.includes('PATHOGENIC') && !classification.includes('LIKELY')) {
        return '#EF5350'; // red-lighten-3
      }
      if (
        classification.includes('LIKELY_PATHOGENIC') ||
        classification.includes('LIKELY PATHOGENIC')
      ) {
        return '#FF9800'; // orange-lighten-3
      }
      if (classification.includes('UNCERTAIN') || classification.includes('VUS')) {
        return '#FBC02D'; // yellow-darken-1
      }
      if (classification.includes('LIKELY_BENIGN')) {
        return '#9CCC65'; // light-green-lighten-3
      }
      if (classification.includes('BENIGN')) {
        return '#66BB6A'; // green-lighten-3
      }
      return '#BDBDBD'; // grey
    },
    getCNVColor(cnv) {
      if (cnv.cnvType === 'DEL') return '#EF5350'; // Red for deletion
      if (cnv.cnvType === 'DUP') return '#42A5F5'; // Blue for duplication
      return '#9E9E9E'; // Grey for unknown
    },
    getCNVDisplayCoords(cnv) {
      // Clamp CNV coordinates to VISIBLE region (not fixed gene boundaries)
      // In CNV mode, visible range is the full 17q12 region
      // In gene mode, visible range is just the HNF1B gene
      const clampedStart = Math.max(cnv.start, this.visibleGeneStart);
      const clampedEnd = Math.min(cnv.end, this.visibleGeneEnd);

      const x = this.scalePosition(clampedStart);
      const width = this.scalePosition(clampedEnd) - x;

      return {
        x: Math.max(x, this.margin.left), // Ensure x is within left margin
        width: Math.max(width, 0), // Ensure width is non-negative
      };
    },
    formatCoordinate(pos) {
      return parseInt(pos).toLocaleString();
    },
    // Utility functions imported from utils
    extractCNotation,
    extractPNotation,
    getCNVDetails,
    showExonTooltip(event, exon) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'exon', data: exon };
      this.tooltipVisible = true;
    },
    showVariantTooltip(event, variant) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'variant', data: variant };
      this.tooltipVisible = true;
    },
    showGeneTooltip(event, gene) {
      this.updateTooltipPosition(event);
      this.tooltipContent = { type: 'gene', data: gene };
      this.tooltipVisible = true;
    },
    updateTooltipPosition(event) {
      // Position tooltip, but prevent overflow on the right edge
      const tooltipWidth = 300; // Approximate tooltip width
      const tooltipHeight = 200; // Approximate tooltip height
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Default: position to the right and below cursor
      let x = event.clientX + 15;
      let y = event.clientY + 15;

      // If tooltip would overflow right edge, position to the left of cursor
      if (x + tooltipWidth > viewportWidth) {
        x = event.clientX - tooltipWidth - 15;
      }

      // If tooltip would overflow bottom edge, position above cursor
      if (y + tooltipHeight > viewportHeight) {
        y = event.clientY - tooltipHeight - 15;
      }

      this.tooltipX = Math.max(10, x); // Ensure at least 10px from left edge
      this.tooltipY = Math.max(10, y); // Ensure at least 10px from top edge
    },
    hideTooltip() {
      this.tooltipVisible = false;
      this.tooltipContent = null;
    },
    handleVariantClick(variant) {
      this.$emit('variant-clicked', variant);
    },
    handleExonClick(exon) {
      // Toggle zoom: if already zoomed to this exon, zoom out
      if (this.zoomedExon?.number === exon.number) {
        this.zoomedExon = null;
      } else {
        this.zoomedExon = exon;
      }
    },
    zoomIn() {
      if (this.d3Zoom && this.$refs.geneSvg) {
        const svg = d3.select(this.$refs.geneSvg);
        const centerX = this.svgWidth / 2;
        const centerY = this.dynamicSvgHeight / 2;

        // Get current transform
        const currentTransform = d3.zoomTransform(this.$refs.geneSvg);

        // Calculate new scale
        const newScale = Math.min(currentTransform.k * 1.3, 10);

        // Calculate new transform centered on the viewport center
        const transform = d3.zoomIdentity
          .translate(centerX, centerY)
          .scale(newScale)
          .translate(-centerX, -centerY);

        svg.transition().duration(300).call(this.d3Zoom.transform, transform);
      }
    },
    zoomOut() {
      if (this.d3Zoom && this.$refs.geneSvg) {
        const svg = d3.select(this.$refs.geneSvg);
        const centerX = this.svgWidth / 2;
        const centerY = this.dynamicSvgHeight / 2;

        // Get current transform
        const currentTransform = d3.zoomTransform(this.$refs.geneSvg);

        // Calculate new scale
        const newScale = Math.max(currentTransform.k / 1.3, 1);

        // Calculate new transform centered on the viewport center
        const transform = d3.zoomIdentity
          .translate(centerX, centerY)
          .scale(newScale)
          .translate(-centerX, -centerY);

        svg.transition().duration(300).call(this.d3Zoom.transform, transform);
      }
    },
    resetZoom() {
      this.zoomedExon = null; // Reset exon zoom
      if (this.d3Zoom && this.$refs.geneSvg) {
        const svg = d3.select(this.$refs.geneSvg);
        this.d3Zoom.transform(svg.transition().duration(500), d3.zoomIdentity);
      }
    },
    initializeD3Zoom() {
      if (!this.$refs.geneSvg) return;

      const svg = d3.select(this.$refs.geneSvg);
      const g = svg.select('#zoom-group');

      // Create zoom behavior with constraints
      this.d3Zoom = d3
        .zoom()
        .scaleExtent([1, 10]) // Min 1x, Max 10x zoom
        .on('zoom', (event) => {
          this.d3Transform = event.transform;
          g.attr('transform', event.transform);
          this.zoomLevel = event.transform.k; // Update zoomLevel for display
        });

      // Apply zoom behavior to SVG
      svg.call(this.d3Zoom);

      // Constrain panning to prevent scrolling off-canvas
      this.d3Zoom.translateExtent([
        [0, 0],
        [this.svgWidth, this.dynamicSvgHeight],
      ]);
    },
    handleKeyboardShortcuts(event) {
      // Only trigger if focused on body or SVG (not in input fields)
      const target = event.target;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      if (event.key === '+' || event.key === '=') {
        event.preventDefault();
        this.zoomIn();
      } else if (event.key === '-' || event.key === '_') {
        event.preventDefault();
        this.zoomOut();
      } else if (event.key === '0') {
        event.preventDefault();
        this.resetZoom();
      }
    },
    formatCNVSize() {
      if (!this.cnvVariants.length) return '';
      const cnv = this.cnvVariants[0];
      const size = cnv.end - cnv.start;
      if (size >= 1000000) {
        return `${(size / 1000000).toFixed(2)} Mb`;
      }
      return `${(size / 1000).toFixed(0)} kb`;
    },
    formatRegionSize() {
      const size = this.chr17q12Region.size;
      return `${(size / 1000000).toFixed(1)} Mb`;
    },
  },
};
</script>

<style scoped>
.gene-viz-card {
  margin-bottom: 16px;
}

.legend-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.svg-container {
  width: 100%;
  overflow-x: visible;
}

.gene-visualization {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #fafafa;
  display: block;
}

.chromosome-label {
  font-size: 14px;
  font-weight: 600;
  fill: #424242;
}

.coordinate-label {
  font-size: 11px;
  fill: #757575;
}

.exon-label {
  font-size: 10px;
  font-weight: 600;
  fill: #1565c0;
  pointer-events: none;
}

.exon-rect {
  cursor: pointer;
  transition: all 0.3s ease;
}

.exon-rect:hover {
  opacity: 0.8;
  filter: brightness(1.1);
}

.exon-rect.exon-zoomed {
  filter: drop-shadow(0 0 6px rgba(255, 111, 0, 0.8));
  animation: pulse-zoom 2s ease-in-out infinite;
}

@keyframes pulse-zoom {
  0%,
  100% {
    filter: drop-shadow(0 0 6px rgba(255, 111, 0, 0.8));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(255, 111, 0, 1));
  }
}

.zoom-indicator-label {
  font-size: 11px;
  font-weight: 600;
  fill: #ff6f00;
}

.variant-circle {
  cursor: pointer;
  transition: opacity 0.2s;
}

.variant-circle:hover {
  opacity: 0.9;
}

.current-variant {
  filter: drop-shadow(0 0 8px rgba(156, 39, 176, 0.6));
}

.cnv-rect {
  cursor: pointer;
  transition: opacity 0.2s;
}

.cnv-rect:hover {
  opacity: 0.9;
}

.indel-rect {
  cursor: pointer;
  transition: all 0.2s;
}

.indel-rect:hover {
  opacity: 0.9;
  filter: brightness(1.1);
}

.indel-label-text {
  pointer-events: none;
}

.custom-tooltip {
  pointer-events: none;
}

.gene-track-label {
  font-size: 12px;
  fill: #424242;
}

.gene-rect {
  cursor: help;
  transition: opacity 0.2s;
}

.gene-rect:hover {
  opacity: 1 !important;
  filter: brightness(1.1);
}

.gene-name-label {
  pointer-events: none;
}
</style>
