<!-- The single NGL.js owner: holds the canvas + ALL imperative NGL logic. -->
<!-- NGL handles live in module-level vars (kept out of Vue reactivity via markRaw). -->
<template>
  <div>
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

    <!-- NGL viewport (always present so the ref exists for initialization). -->
    <div v-show="!loading && !error" ref="nglContainer" class="ngl-viewport" />
  </div>
</template>

<script>
import * as NGL from 'ngl';
import { markRaw } from 'vue';
import {
  DNADistanceCalculator,
  STRUCTURE_START,
  STRUCTURE_END,
} from '@/utils/dnaDistanceCalculator';
import { getVariantColorByMode } from '@/utils/variantFilters';
import { extractPNotation } from '@/utils/hgvs';
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

// Color for linker regions (between domains)
const LINKER_COLOR = 0x9e9e9e; // Grey

export default {
  name: 'StructureViewer',
  props: {
    activeVariant: {
      type: Object,
      default: null,
    },
    activeVariantAAPosition: {
      type: Number,
      default: null,
    },
    activeVariantInStructure: {
      type: Boolean,
      default: false,
    },
    representation: {
      type: String,
      default: 'cartoon',
    },
    showDNA: {
      type: Boolean,
      default: true,
    },
    colorByDomain: {
      type: Boolean,
      default: false,
    },
    showDistanceLine: {
      type: Boolean,
      default: false,
    },
    variants: {
      type: Array,
      default: () => [],
    },
    showAllVariants: {
      type: Boolean,
      default: false,
    },
    coloringMode: {
      type: String,
      default: 'classification',
    },
  },
  emits: [
    'loading',
    'loaded',
    'error',
    'distance-info',
    'distances-calculated',
    'reset-distance-line',
  ],
  data() {
    return {
      loading: true,
      error: null,
      structureLoaded: false,
    };
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
    coloringMode() {
      // Recolour the highlighted variant when the colour-by mode changes.
      this.highlightActiveVariant();
    },
    activeVariant() {
      this.highlightActiveVariant();
      this.calculateActiveVariantDistance();
    },
    showDistanceLine(value) {
      if (value) {
        this.addDistanceLine();
      } else {
        this.removeDistanceLine();
      }
    },
    showAllVariants() {
      this.updateRepresentation();
      if (!this.showAllVariants) {
        this.highlightActiveVariant();
      }
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
    setLoading(value) {
      this.loading = value;
      this.$emit('loading', value);
    },

    setError(value) {
      this.error = value;
      this.$emit('error', value);
    },

    async initializeNGL() {
      try {
        this.setLoading(true);
        this.setError(null);

        // Wait for container to be rendered
        await this.$nextTick();

        if (!this.$refs.nglContainer) {
          throw new Error('NGL container not found');
        }

        // Clean up any existing stage first to prevent Timer warnings
        // This can happen when component remounts (e.g., tab switching)
        if (nglStage) {
          nglStage.dispose();
          nglStage = null;
          nglStructureComponent = null;
          nglVariantRepresentation = null;
          nglLabelRepresentation = null;
          nglDistanceShape = null;
          distanceCalculator = null;
        }

        // Initialize NGL Stage
        // Temporarily suppress Three.js useLegacyLights deprecation warning
        // This is a known issue in NGL library (v2.4.0) that hasn't been fixed upstream
        const originalWarn = console.warn;
        console.warn = (...args) => {
          if (args[0]?.includes?.('useLegacyLights')) return;
          originalWarn.apply(console, args);
        };

        nglStage = markRaw(
          new NGL.Stage(this.$refs.nglContainer, {
            backgroundColor: 'white',
            quality: 'medium',
            impostor: true,
            workerDefault: true,
          })
        );

        // Restore original console.warn
        console.warn = originalWarn;

        // Load PDB structure 2H8R (HNF1B DNA-binding domain)
        // Served locally to reduce network dependency and improve load times
        window.logService.info('Loading PDB structure 2H8R');
        nglStructureComponent = markRaw(
          await nglStage.loadFile('/2h8r.cif', {
            defaultRepresentation: false,
            ext: 'cif',
          })
        );

        this.structureLoaded = true;
        this.$emit('loaded');

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
        this.setError(`Failed to load 3D structure: ${err.message}`);
      } finally {
        this.setLoading(false);
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
        { sele: 'protein and 174-186', color: LINKER_COLOR, name: 'Linker1' },
        // Note: Gap 187-230 is not resolved in structure
        // Linker region: 231 (between gap and POU-H)
        { sele: 'protein and 231', color: LINKER_COLOR, name: 'Linker2' },
        // POU-Homeodomain (POU-H): residues 232-305
        { sele: 'protein and 232-305', color: 0x26a69a, name: 'POU-H' },
        // After POU-H: 306-308 (small tail visible in structure)
        { sele: 'protein and 306-308', color: LINKER_COLOR, name: 'C-tail' },
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
        this.$emit('distance-info', null);
        return;
      }

      if (!this.activeVariantInStructure) {
        this.$emit('distance-info', null);
        return;
      }

      const distanceInfo = distanceCalculator.calculateResidueToHelixDistance(
        this.activeVariantAAPosition,
        true
      );

      this.$emit('distance-info', distanceInfo);

      // Reset distance line when variant changes
      this.$emit('reset-distance-line');
      this.removeDistanceLine();
    },

    toggleDistanceLine() {
      if (this.showDistanceLine) {
        this.removeDistanceLine();
      } else {
        this.addDistanceLine();
      }
    },

    addDistanceLine() {
      if (!nglStage || !distanceCalculator) return;

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
      // Mode-aware hex (classification ⇄ consequence), converted to an
      // NGL-compatible hex number.
      const hexString = getVariantColorByMode(variant, { coloringMode: this.coloringMode });
      return parseInt(hexString.replace('#', ''), 16);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    calculateVariantDistance(variant) {
      // Calculate distance using the distance calculator
      if (!distanceCalculator || !nglStructureComponent) return null;

      const position = this.extractAAPosition(variant);
      if (!position || !this.isPositionInStructure(position)) return null;

      // Use position directly - dnaDistanceCalculator uses auth_seq_id which matches UniProt numbering
      return distanceCalculator.calculateResidueToHelixDistance(position);
    },

    // Calculate distances for all variants when structure loads, emitting a cache up.
    calculateAllVariantDistances() {
      if (!distanceCalculator || !nglStructureComponent) return;

      const cache = {};
      this.variants.forEach((variant) => {
        const position = this.extractAAPosition(variant);
        if (!position || !this.isPositionInStructure(position)) return;
        const info = this.calculateVariantDistance(variant);
        if (info) {
          cache[variant.variant_id] = info;
        }
      });

      this.$emit('distances-calculated', cache);
    },
  },
};
</script>

<style scoped>
.ngl-viewport {
  width: 100%;
  height: 500px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: white;
}
</style>
