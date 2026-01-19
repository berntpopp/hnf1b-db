<!-- NGL.js 3D Structure Viewer Component -->
<!-- Handles NGL Stage initialization, structure loading, and rendering -->
<template>
  <div ref="nglContainer" class="ngl-viewport" />
</template>

<script>
import * as NGL from 'ngl';
import { markRaw } from 'vue';
import {
  DNADistanceCalculator,
  STRUCTURE_START,
  STRUCTURE_END,
} from '@/utils/dnaDistanceCalculator';
import { getPathogenicityHexColor } from '@/utils/colors';
import { extractPNotation } from '@/utils/hgvs';
import './styles.css';

// CRITICAL: Store NGL objects outside Vue's reactivity system
// This prevents Vue 3 Proxy conflicts with Three.js internal properties
let nglStage = null;
let nglStructureComponent = null;
let nglVariantRepresentation = null;
let nglVariantBallStickRepresentation = null;
let nglLabelRepresentation = null;
let nglDistanceShape = null;
let distanceCalculator = null;

// HNF1B protein domains for domain coloring
// PDB 2H8R covers residues 90-308 (with gap at 187-230)
const DOMAIN_RANGES = [
  // POU-Specific Domain (POU-S): residues 88-173 - visible as 90-173
  { sele: 'protein and 90-173', color: 0xab47bc, name: 'POU-S' },
  // Linker region: 174-186 (between POU-S and gap)
  { sele: 'protein and 174-186', color: 0x9e9e9e, name: 'Linker1' },
  // Note: Gap 187-230 is not resolved in structure
  // Linker region: 231 (between gap and POU-H)
  { sele: 'protein and 231', color: 0x9e9e9e, name: 'Linker2' },
  // POU-Homeodomain (POU-H): residues 232-305
  { sele: 'protein and 232-305', color: 0x26a69a, name: 'POU-H' },
  // After POU-H: 306-308 (small tail visible in structure)
  { sele: 'protein and 306-308', color: 0x9e9e9e, name: 'C-tail' },
];

export default {
  name: 'StructureViewer',
  props: {
    /** Representation type: 'cartoon', 'surface', or 'ball+stick' */
    representation: {
      type: String,
      default: 'cartoon',
      validator: (value) => ['cartoon', 'surface', 'ball+stick'].includes(value),
    },
    /** Whether to show DNA in the visualization */
    showDna: {
      type: Boolean,
      default: true,
    },
    /** Whether to color protein by domain */
    colorByDomain: {
      type: Boolean,
      default: false,
    },
    /** Currently active variant object to highlight */
    activeVariant: {
      type: Object,
      default: null,
    },
    /** Amino acid position of the active variant */
    activeVariantPosition: {
      type: Number,
      default: null,
    },
    /** Distance info for drawing distance line */
    distanceInfo: {
      type: Object,
      default: null,
    },
    /** Whether to show the distance line */
    showDistanceLine: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['structure-ready', 'calculator-created'],
  data() {
    return {
      loading: true,
      error: null,
      structureLoaded: false,
    };
  },
  computed: {
    activeVariantInStructure() {
      return (
        this.activeVariantPosition !== null &&
        this.activeVariantPosition >= STRUCTURE_START &&
        this.activeVariantPosition <= STRUCTURE_END
      );
    },
  },
  watch: {
    representation() {
      this.updateRepresentation();
    },
    showDna() {
      this.updateRepresentation();
    },
    colorByDomain() {
      this.updateRepresentation();
    },
    activeVariant() {
      this.highlightActiveVariant();
    },
    activeVariantPosition() {
      this.highlightActiveVariant();
    },
    showDistanceLine(newVal) {
      if (newVal) {
        this.addDistanceLine();
      } else {
        this.removeDistanceLine();
      }
    },
    distanceInfo() {
      // Re-draw distance line if showing and info changed
      if (this.showDistanceLine) {
        this.removeDistanceLine();
        this.addDistanceLine();
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
      nglVariantBallStickRepresentation = null;
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

        // Clean up any existing stage first to prevent Timer warnings
        // This can happen when component remounts (e.g., tab switching)
        if (nglStage) {
          nglStage.dispose();
          nglStage = null;
          nglStructureComponent = null;
          nglVariantRepresentation = null;
          nglVariantBallStickRepresentation = null;
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

        // Initialize distance calculator
        distanceCalculator = new DNADistanceCalculator();
        distanceCalculator.initialize(nglStructureComponent);

        // Emit calculator reference to parent
        this.$emit('calculator-created', distanceCalculator);

        // Add initial representation
        this.updateRepresentation();

        // Highlight active variant if provided
        this.highlightActiveVariant();

        // Handle resize after a short delay
        setTimeout(() => {
          if (nglStage) {
            nglStage.handleResize();
            nglStage.autoView();
          }
        }, 100);

        // Emit structure ready event
        this.$emit('structure-ready');

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
      nglVariantBallStickRepresentation = null;
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
      if (this.showDna) {
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

      // Re-draw distance line if showing
      if (this.showDistanceLine) {
        this.addDistanceLine();
      }
    },

    addDomainColoredRepresentations() {
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
      DOMAIN_RANGES.forEach((range) => {
        const params = getRepParams(range.sele, range.color);
        nglStructureComponent.addRepresentation(this.representation, params);
      });

      window.logService.debug('Domain coloring applied', {
        domains: DOMAIN_RANGES.map((d) => d.name),
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

      const pdbPosition = this.activeVariantPosition;
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

    addDistanceLine() {
      if (!nglStage || !this.distanceInfo || !distanceCalculator) return;

      const lineCoords = distanceCalculator.getDistanceLineCoordinates(
        this.activeVariantPosition,
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

      shape.addText([midX, midY + 1, midZ], [0, 0, 0], 2, `${lineCoords.distanceFormatted} A`);

      nglDistanceShape = nglStage.addComponentFromObject(shape);
      nglDistanceShape.addRepresentation('buffer');
    },

    removeDistanceLine() {
      if (nglDistanceShape && nglStage) {
        nglStage.removeComponent(nglDistanceShape);
        nglDistanceShape = null;
      }
    },

    /**
     * Reset the view to show full structure.
     * Exposed via ref for parent component access.
     */
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

    getVariantColor(variant) {
      // Convert hex color string to NGL-compatible hex number
      const hexString = getPathogenicityHexColor(variant.classificationVerdict);
      return parseInt(hexString.replace('#', ''), 16);
    },

    getVariantLabel(variant) {
      const pNotation = extractPNotation(variant.protein);
      return pNotation || variant.simple_id || variant.variant_id;
    },

    /**
     * Get the distance calculator instance.
     * Exposed for parent component access.
     */
    getDistanceCalculator() {
      return distanceCalculator;
    },

    /**
     * Get the NGL stage instance.
     * Exposed for parent component access if needed.
     */
    getNglStage() {
      return nglStage;
    },
  },
};
</script>
