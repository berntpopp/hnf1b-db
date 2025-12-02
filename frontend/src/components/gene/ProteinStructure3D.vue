<!-- 3D Protein Structure Viewer using NGL.js -->
<!-- Supports two modes: single variant (detail page) or all variants with panel (homepage) -->
<template>
  <v-card class="protein-3d-card">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left color="secondary"> mdi-cube-outline </v-icon>
      HNF1B 3D Structure (PDB: 2H8R)
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-btn
            icon
            size="x-small"
            variant="text"
            v-bind="props"
            href="https://www.rcsb.org/structure/2H8R"
            target="_blank"
            class="ml-1"
          >
            <v-icon size="small"> mdi-open-in-new </v-icon>
          </v-btn>
        </template>
        <span>View in RCSB PDB</span>
      </v-tooltip>
      <v-spacer />
      <!-- Show current variant info if available (single variant mode) -->
      <v-chip
        v-if="!showAllVariants && currentVariant && currentVariantInStructure"
        size="small"
        :color="getVariantChipColor(currentVariant)"
      >
        {{ getVariantLabel(currentVariant) }}
      </v-chip>
      <!-- Show variant count (all variants mode) -->
      <v-chip v-if="showAllVariants && variantsInStructure.length > 0" size="small" color="primary">
        {{ variantsInStructure.length }} variants in structure
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Info Alert about structure coverage -->
      <v-alert type="info" density="compact" variant="tonal" class="mb-3">
        <v-icon size="small" class="mr-1"> mdi-information </v-icon>
        <strong>Structure coverage:</strong> Residues 90-308 (DNA-binding domain, gap at 187-230).
        Variants outside this region cannot be visualized in 3D.
      </v-alert>

      <!-- Loading state -->
      <div v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48" />
        <div class="mt-2 text-grey">Loading 3D structure...</div>
      </div>

      <!-- Error state -->
      <v-alert v-else-if="error" type="error" density="compact" class="mb-3">
        <v-icon size="small" class="mr-1"> mdi-alert </v-icon>
        {{ error }}
      </v-alert>

      <!-- Main Content: 3D Viewport + Optional Variant Panel -->
      <v-row v-show="!loading && !error" no-gutters>
        <!-- 3D Viewport Column -->
        <v-col :cols="showAllVariants ? 8 : 12">
          <div ref="nglContainer" class="ngl-viewport" />
        </v-col>

        <!-- Variant List Panel (only in showAllVariants mode) -->
        <v-col v-if="showAllVariants" cols="4">
          <div class="variant-panel">
            <div class="variant-panel-header">
              <span class="text-subtitle-2">Variants in Structure</span>
              <v-chip size="x-small" color="primary" class="ml-2">
                {{ filteredAndSortedVariants.length }}
                <template v-if="filteredAndSortedVariants.length !== variantsInStructure.length">
                  / {{ variantsInStructure.length }}
                </template>
              </v-chip>
            </div>

            <!-- Filter and Sort Controls -->
            <div class="variant-panel-controls">
              <!-- Sort Control -->
              <v-select
                v-model="sortBy"
                :items="sortOptions"
                label="Sort by"
                density="compact"
                hide-details
                variant="outlined"
                class="sort-select"
              />

              <!-- Pathogenicity Filter -->
              <v-select
                v-model="filterPathogenicity"
                :items="pathogenicityOptions"
                label="Pathogenicity"
                density="compact"
                hide-details
                variant="outlined"
                clearable
                class="filter-select"
              />

              <!-- Distance Filter -->
              <v-select
                v-model="filterDistance"
                :items="distanceOptions"
                label="DNA Distance"
                density="compact"
                hide-details
                variant="outlined"
                clearable
                class="filter-select"
              />
            </div>

            <v-list density="compact" class="variant-list">
              <v-list-item
                v-for="variant in filteredAndSortedVariants"
                :key="variant.variant_id"
                :class="{
                  'variant-item-active': selectedVariantId === variant.variant_id,
                  'variant-item-hover': hoveredVariantId === variant.variant_id,
                }"
                @click="selectVariant(variant)"
                @mouseenter="hoverVariant(variant)"
                @mouseleave="unhoverVariant()"
              >
                <template #prepend>
                  <v-avatar :color="getVariantChipColor(variant)" size="28">
                    <span class="text-white text-caption">{{ extractAAPosition(variant) }}</span>
                  </v-avatar>
                </template>
                <v-list-item-title class="text-body-2">
                  {{ getVariantLabel(variant) }}
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption d-flex align-center">
                  <span>{{ variant.classificationVerdict || 'Unknown' }}</span>
                  <v-chip
                    v-if="getVariantDistanceCategory(variant)"
                    size="x-small"
                    :color="getDistanceChipColor(getVariantDistanceCategory(variant))"
                    class="ml-2"
                  >
                    {{ getVariantDistanceFormatted(variant) }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
            <div v-if="filteredAndSortedVariants.length === 0" class="text-center py-4 text-grey">
              <v-icon size="large" color="grey-lighten-1">mdi-alert-circle-outline</v-icon>
              <div class="text-caption mt-1">
                {{
                  variantsInStructure.length === 0
                    ? 'No variants in structure range'
                    : 'No variants match filters'
                }}
              </div>
              <v-btn
                v-if="variantsInStructure.length > 0 && (filterPathogenicity || filterDistance)"
                size="x-small"
                variant="text"
                color="primary"
                class="mt-2"
                @click="clearFilters"
              >
                Clear Filters
              </v-btn>
            </div>
          </div>
        </v-col>
      </v-row>

      <!-- Controls Row -->
      <v-row v-if="!loading && !error" class="mt-3">
        <!-- Representation Controls -->
        <v-col cols="12" sm="6" md="5">
          <v-btn-toggle v-model="representation" mandatory density="compact" color="primary">
            <v-btn value="cartoon" size="small">
              <v-icon left size="small"> mdi-waves </v-icon>
              Cartoon
            </v-btn>
            <v-btn value="surface" size="small">
              <v-icon left size="small"> mdi-circle </v-icon>
              Surface
            </v-btn>
            <v-btn value="ball+stick" size="small">
              <v-icon left size="small"> mdi-atom </v-icon>
              Ball+Stick
            </v-btn>
          </v-btn-toggle>
        </v-col>

        <!-- DNA Toggle -->
        <v-col cols="6" sm="3" md="2">
          <v-switch
            v-model="showDNA"
            label="Show DNA"
            density="compact"
            hide-details
            color="primary"
          />
        </v-col>

        <!-- Domain Coloring Toggle -->
        <v-col cols="6" sm="3" md="2">
          <v-switch
            v-model="colorByDomain"
            label="Domain Colors"
            density="compact"
            hide-details
            color="secondary"
          />
        </v-col>

        <!-- Action Buttons -->
        <v-col cols="12" sm="3" md="4" class="text-right">
          <v-btn size="small" variant="outlined" class="mr-2" @click="resetView">
            <v-icon left size="small"> mdi-refresh </v-icon>
            Reset View
          </v-btn>
          <v-btn
            v-if="activeVariantInStructure && activeVariantDistanceInfo"
            size="small"
            variant="outlined"
            :color="showDistanceLine ? 'primary' : 'default'"
            @click="toggleDistanceLine"
          >
            <v-icon left size="small"> mdi-ruler </v-icon>
            {{ activeVariantDistanceInfo.distanceFormatted }} &Aring;
          </v-btn>
        </v-col>
      </v-row>

      <!-- Active Variant Distance Info -->
      <v-alert
        v-if="!loading && !error && activeVariantInStructure && activeVariantDistanceInfo"
        :type="getDistanceAlertType(activeVariantDistanceInfo.category)"
        density="compact"
        variant="tonal"
        class="mt-3"
      >
        <v-icon size="small" class="mr-1"> mdi-ruler </v-icon>
        <strong>Distance to DNA:</strong>
        {{ activeVariantDistanceInfo.distanceFormatted }} &Aring; ({{
          getDistanceCategoryLabel(activeVariantDistanceInfo.category)
        }})
        <span class="text-caption ml-2">
          Closest DNA atom: {{ activeVariantDistanceInfo.closestDNAAtom?.label }}
        </span>
      </v-alert>

      <!-- Legend Row -->
      <v-row v-if="!loading && !error" class="mt-2">
        <v-col cols="12">
          <div class="legend-container">
            <span class="text-caption text-grey mr-2">Pathogenicity:</span>
            <v-chip size="x-small" color="red-lighten-1" class="mr-1"> Pathogenic </v-chip>
            <v-chip size="x-small" color="orange-lighten-1" class="mr-1">
              Likely Pathogenic
            </v-chip>
            <v-chip size="x-small" color="yellow-darken-1" class="mr-1"> VUS </v-chip>
            <v-chip size="x-small" color="light-green-lighten-1" class="mr-1">
              Likely Benign
            </v-chip>
            <v-chip size="x-small" color="grey-lighten-1"> Unknown </v-chip>
          </div>
          <!-- Domain Legend (shown when domain coloring is enabled) -->
          <div v-if="colorByDomain" class="legend-container mt-2">
            <span class="text-caption text-grey mr-2">Domains:</span>
            <v-chip size="x-small" style="background-color: #ab47bc; color: white" class="mr-1">
              POU-S (90-173)
            </v-chip>
            <v-chip size="x-small" style="background-color: #26a69a; color: white" class="mr-1">
              POU-H (232-305)
            </v-chip>
            <v-chip size="x-small" style="background-color: #9e9e9e" class="mr-1"> Linker </v-chip>
            <span class="text-caption text-grey-darken-1 ml-2"> (Gap: 187-230 not resolved) </span>
          </div>
        </v-col>
      </v-row>

      <!-- Current variant not in structure warning (single variant mode) -->
      <v-alert
        v-if="!showAllVariants && currentVariant && !currentVariantInStructure"
        type="warning"
        density="compact"
        variant="tonal"
        class="mt-3"
      >
        <v-icon size="small" class="mr-1"> mdi-map-marker-off </v-icon>
        <strong>Current variant not in structure:</strong>
        {{ currentVariant.protein || currentVariant.transcript }} is outside the PDB structure range
        (residues 90-308, gap at 187-230).
      </v-alert>

      <!-- Selected variant info (all variants mode) -->
      <v-alert
        v-if="showAllVariants && selectedVariant"
        :type="selectedVariantInStructure ? 'info' : 'warning'"
        density="compact"
        variant="tonal"
        class="mt-3"
      >
        <v-icon size="small" class="mr-1">
          {{ selectedVariantInStructure ? 'mdi-cursor-default-click' : 'mdi-map-marker-off' }}
        </v-icon>
        <strong>Selected:</strong> {{ getVariantLabel(selectedVariant) }}
        <v-chip size="x-small" :color="getVariantChipColor(selectedVariant)" class="ml-2">
          {{ selectedVariant.classificationVerdict || 'Unknown' }}
        </v-chip>
        <v-btn
          v-if="selectedVariant"
          size="x-small"
          variant="outlined"
          color="primary"
          class="ml-3"
          @click="emitVariantClicked(selectedVariant)"
        >
          <v-icon size="x-small" left>mdi-open-in-new</v-icon>
          View Details
        </v-btn>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script>
import * as NGL from 'ngl';
import { markRaw } from 'vue';
import { extractPNotation } from '@/utils/hgvs';
import {
  DNADistanceCalculator,
  STRUCTURE_START,
  STRUCTURE_END,
} from '@/utils/dnaDistanceCalculator';
import {
  getPathogenicityColor,
  getPathogenicityScore,
  getPathogenicityHexColor,
} from '@/utils/colors';
import { extractAAPosition as extractAAPositionUtil } from '@/utils/proteinDomains';

// Store NGL objects outside Vue's reactivity system
// This prevents Vue 3 Proxy conflicts with Three.js internal properties
let nglStage = null;
let nglStructureComponent = null;
let nglVariantRepresentation = null;
let nglVariantBallStickRepresentation = null;
let nglLabelRepresentation = null;
let nglDistanceShape = null;
let distanceCalculator = null;

export default {
  name: 'ProteinStructure3D',
  props: {
    variants: {
      type: Array,
      default: () => [],
    },
    currentVariantId: {
      type: String,
      default: null,
    },
    showAllVariants: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['variant-clicked'],
  data() {
    return {
      loading: true,
      error: null,
      representation: 'cartoon',
      structureLoaded: false,
      showDNA: true,
      showDistanceLine: false,
      colorByDomain: false,
      currentVariantDistanceInfo: null,
      // HNF1B protein domains (from UniProt P35680)
      // Note: PDB 2H8R only covers residues 90-308 (with gap 187-230)
      proteinDomains: [
        {
          name: 'Dimerization',
          shortName: 'Dim',
          start: 1,
          end: 31,
          color: 0xffb74d, // Orange - not visible in structure (before res 90)
        },
        {
          name: 'POU-Specific',
          shortName: 'POU-S',
          start: 88,
          end: 173,
          color: 0xab47bc, // Purple - partially visible (90-173)
        },
        {
          name: 'POU-Homeodomain',
          shortName: 'POU-H',
          start: 232,
          end: 305,
          color: 0x26a69a, // Teal - fully visible
        },
        {
          name: 'Transactivation',
          shortName: 'TAD',
          start: 314,
          end: 557,
          color: 0x81c784, // Green - not visible in structure (after res 308)
        },
      ],
      // Color for linker regions (between domains)
      linkerColor: 0x9e9e9e, // Grey
      // For showAllVariants mode
      selectedVariantId: null,
      hoveredVariantId: null,
      // Sorting and filtering
      sortBy: 'position',
      filterPathogenicity: null,
      filterDistance: null,
      // Cache for variant distances
      variantDistanceCache: {},
      // Options for selects
      sortOptions: [
        { title: 'Position', value: 'position' },
        { title: 'Distance to DNA', value: 'distance' },
        { title: 'Pathogenicity', value: 'pathogenicity' },
      ],
      pathogenicityOptions: [
        { title: 'Pathogenic', value: 'PATHOGENIC' },
        { title: 'Likely Pathogenic', value: 'LIKELY_PATHOGENIC' },
        { title: 'VUS', value: 'VUS' },
        { title: 'Likely Benign', value: 'LIKELY_BENIGN' },
        { title: 'Benign', value: 'BENIGN' },
      ],
      distanceOptions: [
        { title: 'Close (<5 Å)', value: 'close' },
        { title: 'Medium (5-10 Å)', value: 'medium' },
        { title: 'Far (>10 Å)', value: 'far' },
      ],
    };
  },
  computed: {
    // Single variant mode computed properties
    currentVariant() {
      if (!this.currentVariantId) return null;
      return this.variants.find((v) => v.variant_id === this.currentVariantId);
    },
    currentVariantAAPosition() {
      if (!this.currentVariant) return null;
      return this.extractAAPosition(this.currentVariant);
    },
    currentVariantInStructure() {
      return (
        this.currentVariantAAPosition && this.isPositionInStructure(this.currentVariantAAPosition)
      );
    },
    // All variants mode computed properties
    variantsInStructure() {
      return this.variants.filter((v) => {
        const pos = this.extractAAPosition(v);
        return pos && this.isPositionInStructure(pos);
      });
    },
    selectedVariant() {
      if (!this.selectedVariantId) return null;
      return this.variants.find((v) => v.variant_id === this.selectedVariantId);
    },
    selectedVariantAAPosition() {
      if (!this.selectedVariant) return null;
      return this.extractAAPosition(this.selectedVariant);
    },
    selectedVariantInStructure() {
      return (
        this.selectedVariantAAPosition && this.isPositionInStructure(this.selectedVariantAAPosition)
      );
    },
    // Unified computed properties for active variant (works for both modes)
    activeVariant() {
      if (this.showAllVariants) {
        return this.selectedVariant;
      }
      return this.currentVariant;
    },
    activeVariantAAPosition() {
      if (!this.activeVariant) return null;
      return this.extractAAPosition(this.activeVariant);
    },
    activeVariantInStructure() {
      return (
        this.activeVariantAAPosition && this.isPositionInStructure(this.activeVariantAAPosition)
      );
    },
    activeVariantDistanceInfo() {
      return this.currentVariantDistanceInfo;
    },
    // Filtered and sorted variants for display in panel
    filteredAndSortedVariants() {
      let variants = [...this.variantsInStructure];

      // Apply pathogenicity filter
      if (this.filterPathogenicity) {
        variants = variants.filter((v) => {
          const classification = (v.classificationVerdict || '').toUpperCase();
          if (this.filterPathogenicity === 'VUS') {
            return classification.includes('UNCERTAIN') || classification.includes('VUS');
          }
          return classification.includes(this.filterPathogenicity);
        });
      }

      // Apply distance filter
      if (this.filterDistance) {
        variants = variants.filter((v) => {
          const category = this.getVariantDistanceCategory(v);
          return category === this.filterDistance;
        });
      }

      // Apply sorting
      variants.sort((a, b) => {
        if (this.sortBy === 'position') {
          return (this.extractAAPosition(a) || 0) - (this.extractAAPosition(b) || 0);
        }
        if (this.sortBy === 'distance') {
          const distA = this.getVariantDistanceValue(a);
          const distB = this.getVariantDistanceValue(b);
          return distA - distB;
        }
        if (this.sortBy === 'pathogenicity') {
          return this.getPathogenicityScoreValue(b) - this.getPathogenicityScoreValue(a);
        }
        return 0;
      });

      return variants;
    },
  },
  watch: {
    representation() {
      this.updateRepresentation();
    },
    showDNA() {
      this.updateRepresentation();
    },
    colorByDomain() {
      this.updateRepresentation();
    },
    currentVariantId() {
      if (!this.showAllVariants) {
        this.highlightActiveVariant();
        this.calculateActiveVariantDistance();
      }
    },
    selectedVariantId() {
      if (this.showAllVariants) {
        this.highlightActiveVariant();
        this.calculateActiveVariantDistance();
      }
    },
    showAllVariants: {
      handler() {
        this.updateRepresentation();
        // In showAllVariants mode, we don't auto-highlight anything
        // User selects from the panel to highlight
        if (!this.showAllVariants) {
          this.highlightActiveVariant();
        }
      },
      immediate: false,
    },
  },
  mounted() {
    this.initializeNGL();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.handleResize);
    if (nglStage) {
      nglStage.dispose();
      nglStage = null;
      nglStructureComponent = null;
      nglVariantRepresentation = null;
      nglLabelRepresentation = null;
      nglDistanceShape = null;
      distanceCalculator = null;
    }
  },
  methods: {
    async initializeNGL() {
      try {
        this.loading = true;
        this.error = null;

        // Wait for container to be rendered
        await this.$nextTick();

        if (!this.$refs.nglContainer) {
          throw new Error('NGL container not found');
        }

        // Initialize NGL Stage
        nglStage = markRaw(
          new NGL.Stage(this.$refs.nglContainer, {
            backgroundColor: 'white',
            quality: 'medium',
            impostor: true,
            workerDefault: true,
          })
        );

        // Load PDB structure 2H8R (HNF1B DNA-binding domain)
        window.logService.info('Loading PDB structure 2H8R');
        nglStructureComponent = markRaw(
          await nglStage.loadFile('https://www.ebi.ac.uk/pdbe/entry-files/2h8r.cif', {
            defaultRepresentation: false,
            ext: 'cif',
          })
        );

        this.structureLoaded = true;

        // Initialize distance calculator
        distanceCalculator = new DNADistanceCalculator();
        distanceCalculator.initialize(nglStructureComponent);

        // Add initial representation
        this.updateRepresentation();

        // Highlight active variant if in single variant mode
        // In showAllVariants mode, user selects from the panel
        if (!this.showAllVariants) {
          this.highlightActiveVariant();
          this.calculateActiveVariantDistance();
        }

        // Pre-calculate distances for all variants (for filtering/sorting)
        if (this.showAllVariants) {
          this.calculateAllVariantDistances();
        }

        // Handle resize after a short delay
        setTimeout(() => {
          if (nglStage) {
            nglStage.handleResize();
            nglStage.autoView();
          }
        }, 100);

        window.logService.info('3D structure loaded successfully', { pdb: '2H8R' });
      } catch (err) {
        window.logService.error('Failed to load 3D structure', { error: err.message });
        this.error = `Failed to load 3D structure: ${err.message}`;
      } finally {
        this.loading = false;
      }
    },

    updateRepresentation() {
      if (!nglStructureComponent) return;

      // Remove existing representations
      nglStructureComponent.removeAllRepresentations();
      nglVariantRepresentation = null;
      nglLabelRepresentation = null;
      this.removeDistanceLine();

      // Determine coloring approach
      if (this.colorByDomain) {
        // Add domain-colored representations
        this.addDomainColoredRepresentations();
      } else {
        // Add protein representation with chain coloring
        const proteinParams = {
          sele: 'protein',
          color: 'chainid',
        };

        if (this.representation === 'cartoon') {
          nglStructureComponent.addRepresentation('cartoon', {
            ...proteinParams,
            aspectRatio: 5,
            smoothSheet: true,
          });
        } else if (this.representation === 'surface') {
          nglStructureComponent.addRepresentation('surface', {
            ...proteinParams,
            opacity: 0.7,
            surfaceType: 'ms',
          });
        } else if (this.representation === 'ball+stick') {
          nglStructureComponent.addRepresentation('ball+stick', {
            ...proteinParams,
            multipleBond: 'symmetric',
          });
        }
      }

      // Add DNA representation if enabled
      if (this.showDNA) {
        nglStructureComponent.addRepresentation('cartoon', {
          sele: 'nucleic',
          color: 0x1976d2,
          aspectRatio: 2.0,
          radiusScale: 1.5,
        });

        nglStructureComponent.addRepresentation('base', {
          sele: 'nucleic',
          color: 'resname',
          colorScale: ['#A5D6A7', '#EF9A9A', '#90CAF9', '#FFCC80'],
        });
      }

      // Re-highlight active variant
      this.highlightActiveVariant();
    },

    addDomainColoredRepresentations() {
      // PDB 2H8R covers residues 90-308 (with gap at 187-230)
      // Define residue ranges for each domain visible in the structure
      const domainRanges = [
        // POU-Specific Domain (POU-S): residues 88-173 - visible as 90-173
        { sele: 'protein and 90-173', color: 0xab47bc, name: 'POU-S' },
        // Linker region: 174-186 (between POU-S and gap)
        { sele: 'protein and 174-186', color: this.linkerColor, name: 'Linker1' },
        // Note: Gap 187-230 is not resolved in structure
        // Linker region: 231 (between gap and POU-H)
        { sele: 'protein and 231', color: this.linkerColor, name: 'Linker2' },
        // POU-Homeodomain (POU-H): residues 232-305
        { sele: 'protein and 232-305', color: 0x26a69a, name: 'POU-H' },
        // After POU-H: 306-308 (small tail visible in structure)
        { sele: 'protein and 306-308', color: this.linkerColor, name: 'C-tail' },
      ];

      // Common parameters based on representation type
      const getRepParams = (sele, color) => {
        const base = { sele, color };
        if (this.representation === 'cartoon') {
          return { ...base, aspectRatio: 5, smoothSheet: true };
        } else if (this.representation === 'surface') {
          return { ...base, opacity: 0.7, surfaceType: 'ms' };
        } else if (this.representation === 'ball+stick') {
          return { ...base, multipleBond: 'symmetric' };
        }
        return base;
      };

      // Add representation for each domain/region
      domainRanges.forEach((range) => {
        const params = getRepParams(range.sele, range.color);
        nglStructureComponent.addRepresentation(this.representation, params);
      });

      window.logService.debug('Domain coloring applied', {
        domains: domainRanges.map((d) => d.name),
      });
    },

    highlightActiveVariant() {
      if (!nglStructureComponent || !nglStage) return;

      // Remove existing variant representations
      if (nglVariantRepresentation) {
        nglStructureComponent.removeRepresentation(nglVariantRepresentation);
        nglVariantRepresentation = null;
      }
      if (nglVariantBallStickRepresentation) {
        nglStructureComponent.removeRepresentation(nglVariantBallStickRepresentation);
        nglVariantBallStickRepresentation = null;
      }
      if (nglLabelRepresentation) {
        nglStructureComponent.removeRepresentation(nglLabelRepresentation);
        nglLabelRepresentation = null;
      }

      // If no active variant or not in structure, just show the structure
      if (!this.activeVariant || !this.activeVariantInStructure) {
        return;
      }

      const pdbPosition = this.activeVariantAAPosition;
      const color = this.getVariantColor(this.activeVariant);
      const selection = `${pdbPosition}`;

      // Add ball+stick representation first (underneath)
      nglVariantBallStickRepresentation = nglStructureComponent.addRepresentation('ball+stick', {
        sele: selection,
        colorScheme: 'element',
        aspectRatio: 1.5,
        bondScale: 0.3,
        bondSpacing: 1.0,
      });

      // Add semi-transparent spacefill representation on top
      nglVariantRepresentation = nglStructureComponent.addRepresentation('spacefill', {
        sele: selection,
        color: color,
        opacity: 0.4,
        scale: 1.2,
      });

      // Add label using format string for better reliability
      const variantLabel = this.getVariantLabel(this.activeVariant);
      nglLabelRepresentation = nglStructureComponent.addRepresentation('label', {
        sele: `${pdbPosition} and .CA`,
        labelType: 'format',
        labelFormat: variantLabel,
        labelGrouping: 'residue',
        color: 0x000000,
        fontFamily: 'sans-serif',
        fontWeight: 'bold',
        fontSize: 16,
        xOffset: 0,
        yOffset: 3,
        zOffset: 0,
        fixedSize: true,
        attachment: 'middle-center',
        showBackground: true,
        backgroundColor: 0xffffff,
        backgroundOpacity: 0.9,
        backgroundMargin: 4,
        borderColor: 0x000000,
        borderWidth: 1,
      });

      // Focus on the variant
      nglStructureComponent.autoView(`${pdbPosition}`, 1000);
    },

    calculateActiveVariantDistance() {
      if (!distanceCalculator || !this.structureLoaded) {
        this.currentVariantDistanceInfo = null;
        return;
      }

      if (!this.activeVariantInStructure) {
        this.currentVariantDistanceInfo = null;
        return;
      }

      const distanceInfo = distanceCalculator.calculateResidueToHelixDistance(
        this.activeVariantAAPosition,
        true
      );

      this.currentVariantDistanceInfo = distanceInfo;

      // Reset distance line when variant changes
      this.showDistanceLine = false;
      this.removeDistanceLine();
    },

    // Variant selection methods for showAllVariants mode
    selectVariant(variant) {
      this.selectedVariantId = variant.variant_id;
    },

    hoverVariant(variant) {
      this.hoveredVariantId = variant.variant_id;
    },

    unhoverVariant() {
      this.hoveredVariantId = null;
    },

    emitVariantClicked(variant) {
      this.$emit('variant-clicked', variant);
    },

    toggleDistanceLine() {
      if (this.showDistanceLine) {
        this.removeDistanceLine();
        this.showDistanceLine = false;
      } else {
        this.addDistanceLine();
        this.showDistanceLine = true;
      }
    },

    addDistanceLine() {
      if (!nglStage || !this.currentVariantDistanceInfo) return;

      const lineCoords = distanceCalculator.getDistanceLineCoordinates(
        this.activeVariantAAPosition,
        true
      );
      if (!lineCoords) return;

      // Create distance line using shape
      const shape = new NGL.Shape('distance-line');

      // Convert hex color string to RGB array
      const colorHex = lineCoords.color.replace('#', '');
      const r = parseInt(colorHex.substring(0, 2), 16) / 255;
      const g = parseInt(colorHex.substring(2, 4), 16) / 255;
      const b = parseInt(colorHex.substring(4, 6), 16) / 255;

      // Add cylinder for the line
      shape.addCylinder(
        [lineCoords.start.x, lineCoords.start.y, lineCoords.start.z],
        [lineCoords.end.x, lineCoords.end.y, lineCoords.end.z],
        [r, g, b],
        0.15
      );

      // Add label at midpoint
      const midX = (lineCoords.start.x + lineCoords.end.x) / 2;
      const midY = (lineCoords.start.y + lineCoords.end.y) / 2;
      const midZ = (lineCoords.start.z + lineCoords.end.z) / 2;

      shape.addText([midX, midY + 1, midZ], [0, 0, 0], 2, `${lineCoords.distanceFormatted} Å`);

      nglDistanceShape = nglStage.addComponentFromObject(shape);
      nglDistanceShape.addRepresentation('buffer');
    },

    removeDistanceLine() {
      if (nglDistanceShape && nglStage) {
        nglStage.removeComponent(nglDistanceShape);
        nglDistanceShape = null;
      }
    },

    resetView() {
      if (nglStage) {
        nglStage.autoView(1000);
      }
    },

    handleResize() {
      if (nglStage) {
        nglStage.handleResize();
      }
    },

    extractAAPosition(variant) {
      return extractAAPositionUtil(variant);
    },

    isPositionInStructure(aaPosition) {
      return aaPosition >= STRUCTURE_START && aaPosition <= STRUCTURE_END;
    },

    getVariantColor(variant) {
      // Convert hex color string to NGL-compatible hex number
      const hexString = getPathogenicityHexColor(variant.classificationVerdict);
      return parseInt(hexString.replace('#', ''), 16);
    },

    getVariantChipColor(variant) {
      return getPathogenicityColor(variant.classificationVerdict);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    getDistanceAlertType(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },

    getDistanceCategoryLabel(category) {
      if (category === 'close') return 'Close to DNA - likely functional impact';
      if (category === 'medium') return 'Medium distance';
      return 'Far from DNA';
    },

    // Helper methods for filtering and sorting
    getVariantDistanceCategory(variant) {
      const info = this.calculateVariantDistance(variant);
      return info ? info.category : null;
    },

    getVariantDistanceValue(variant) {
      const info = this.calculateVariantDistance(variant);
      return info ? info.distance : Infinity;
    },

    getVariantDistanceFormatted(variant) {
      const info = this.calculateVariantDistance(variant);
      return info ? `${info.distanceFormatted} Å` : null;
    },

    calculateVariantDistance(variant) {
      // Use cached value if available
      if (this.variantDistanceCache[variant.variant_id]) {
        return this.variantDistanceCache[variant.variant_id];
      }

      // Calculate distance using the distance calculator
      if (!distanceCalculator || !nglStructureComponent) return null;

      const position = this.extractAAPosition(variant);
      if (!position || !this.isPositionInStructure(position)) return null;

      // Use position directly - dnaDistanceCalculator uses auth_seq_id which matches UniProt numbering
      const info = distanceCalculator.calculateResidueToHelixDistance(position);

      if (info) {
        this.variantDistanceCache[variant.variant_id] = info;
      }

      return info;
    },

    getPathogenicityScoreValue(variant) {
      return getPathogenicityScore(variant.classificationVerdict);
    },

    getDistanceChipColor(category) {
      if (category === 'close') return 'error';
      if (category === 'medium') return 'warning';
      return 'success';
    },

    clearFilters() {
      this.filterPathogenicity = null;
      this.filterDistance = null;
    },

    // Calculate distances for all variants when structure loads
    calculateAllVariantDistances() {
      if (!distanceCalculator || !nglStructureComponent) return;

      this.variantsInStructure.forEach((variant) => {
        this.calculateVariantDistance(variant);
      });
    },
  },
};
</script>

<style scoped>
.protein-3d-card {
  margin-bottom: 16px;
}

.ngl-viewport {
  width: 100%;
  height: 500px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: white;
}

.legend-container {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

/* Variant panel styles */
.variant-panel {
  height: 500px;
  border: 1px solid #e0e0e0;
  border-left: none;
  border-radius: 0 4px 4px 0;
  background-color: #fafafa;
  display: flex;
  flex-direction: column;
}

.variant-panel-header {
  padding: 12px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
}

.variant-panel-controls {
  padding: 8px 12px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sort-select,
.filter-select {
  font-size: 12px;
}

.variant-list {
  flex: 1;
  overflow-y: auto;
  background-color: transparent;
}

.variant-item-active {
  background-color: #e3f2fd !important;
  border-left: 3px solid #1976d2;
}

.variant-item-hover {
  background-color: #f5f5f5;
}
</style>
