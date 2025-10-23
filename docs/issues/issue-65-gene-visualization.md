# Issue #65: feat(frontend): add HNF1B gene visualization with variant mapping

## Overview

Add an interactive SVG visualization of the HNF1B gene structure to the variant detail page, showing exon/intron architecture with variants mapped to their genomic positions.

**Current:** Variant detail page shows metadata only (text/table format)
**Target:** Visual gene diagram with variants positioned on gene structure

## Why This Matters

Visual representation helps clinicians and researchers quickly understand:

- **Variant location:** Where in the gene does this variant occur?
- **Hotspots:** Are multiple variants clustered in specific exons?
- **Domain context:** Does the variant affect a specific functional domain?
- **Comparison:** How do different variants relate spatially?

### Current User Experience (Without Visualization)

```
User views variant: c.1654-2A>T
Information shown:
- Transcript: NM_000458.4:c.1654-2A>T
- Type: SNV
- Effect: Splice acceptor variant

Questions user has:
❓ Which exon is affected?
❓ Is this in a conserved region?
❓ Are there other variants nearby?

User must: Cross-reference with genome browser (UCSC/Ensembl)
⏱️ Time: 5-10 minutes
```

### Target User Experience (With Visualization)

```
User views variant: c.1654-2A>T
Sees:
- Gene diagram showing all 9 exons
- Red marker on exon 6 splice site
- Other variants also visible as colored markers
- Hover shows: "Exon 6 splice acceptor, c.1654-2A>T"

Questions answered visually:
✅ Exon 6 is affected
✅ Splice site location clear
✅ Can see nearby variants

⏱️ Time: Instant visual understanding
```

## HNF1B Gene Structure

### Gene Architecture
```
Gene: HNF1B (TCF2)
Chromosome: 17q12
Coordinates (GRCh38): chr17:36,096,264-36,164,048 (67.8 kb)
Exons: 9 exons
Transcript: NM_000458.4
Protein: 557 amino acids
```

### Exon Structure
```
Exon 1:  chr17:36,162,719-36,164,048 (1,330 bp) - 5' UTR + coding
Exon 2:  chr17:36,128,663-36,128,841 (179 bp)
Exon 3:  chr17:36,127,274-36,127,418 (145 bp)
Exon 4:  chr17:36,118,768-36,119,002 (235 bp) - DNA-binding domain (POU-H)
Exon 5:  chr17:36,113,941-36,114,065 (125 bp) - DNA-binding domain (POU-H)
Exon 6:  chr17:36,108,318-36,108,415 (98 bp)
Exon 7:  chr17:36,104,951-36,105,082 (132 bp)
Exon 8:  chr17:36,103,228-36,103,398 (171 bp)
Exon 9:  chr17:36,096,264-36,096,699 (436 bp) - 3' UTR

Total coding sequence: ~1,671 bp (557 amino acids)
```

### Functional Domains
```
1. Dimerization domain (N-terminal)
2. POU-specific domain (POU-S) - Exons 3-4
3. POU-homeodomain (POU-H) - Exons 4-5
4. Transactivation domain (C-terminal) - Exons 7-9
```

## Required Changes

### 1. Gene Visualization Component

**File:** `frontend/src/components/gene/HNF1BGeneVisualization.vue` (NEW)

```vue
<template>
  <v-card class="mb-4">
    <v-card-title class="text-h6 bg-grey-lighten-4">
      <v-icon left color="primary">mdi-dna</v-icon>
      HNF1B Gene Structure (NM_000458.4)
    </v-card-title>

    <v-card-text>
      <!-- Legend -->
      <v-row class="mb-4">
        <v-col cols="12">
          <v-chip-group>
            <v-chip size="small" color="blue">
              <v-icon left size="small">mdi-square</v-icon>
              Exon
            </v-chip>
            <v-chip size="small" color="grey">
              <v-icon left size="small">mdi-minus</v-icon>
              Intron
            </v-chip>
            <v-chip size="small" color="red">
              <v-icon left size="small">mdi-circle</v-icon>
              Pathogenic
            </v-chip>
            <v-chip size="small" color="orange">
              <v-icon left size="small">mdi-circle</v-icon>
              Likely Pathogenic
            </v-chip>
            <v-chip size="small" color="yellow">
              <v-icon left size="small">mdi-circle</v-icon>
              VUS
            </v-chip>
            <v-chip size="small" color="purple">
              <v-icon left size="small">mdi-star</v-icon>
              Current Variant
            </v-chip>
          </v-chip-group>
        </v-col>
      </v-row>

      <!-- SVG Visualization -->
      <svg
        ref="geneSvg"
        :width="svgWidth"
        :height="svgHeight"
        class="gene-visualization"
      >
        <!-- Chromosome label -->
        <text
          :x="margin.left"
          :y="margin.top - 10"
          class="chromosome-label"
        >
          Chromosome 17q12
        </text>

        <!-- Gene coordinates -->
        <text
          :x="margin.left"
          :y="margin.top + svgHeight - margin.bottom - margin.top + 30"
          class="coordinate-label"
        >
          {{ formatCoordinate(geneStart) }}
        </text>
        <text
          :x="svgWidth - margin.right"
          :y="margin.top + svgHeight - margin.bottom - margin.top + 30"
          text-anchor="end"
          class="coordinate-label"
        >
          {{ formatCoordinate(geneEnd) }}
        </text>

        <!-- Intron line (backbone) -->
        <line
          :x1="margin.left"
          :y1="centerY"
          :x2="svgWidth - margin.right"
          :y2="centerY"
          stroke="#9E9E9E"
          stroke-width="2"
        />

        <!-- Exons -->
        <g
          v-for="(exon, index) in exons"
          :key="`exon-${index}`"
        >
          <rect
            :x="scalePosition(exon.start)"
            :y="centerY - exonHeight / 2"
            :width="scalePosition(exon.end) - scalePosition(exon.start)"
            :height="exonHeight"
            :fill="getExonColor(exon)"
            stroke="#1976D2"
            stroke-width="1"
            @mouseenter="showExonTooltip($event, exon)"
            @mouseleave="hideTooltip"
          />
          <text
            :x="scalePosition(exon.start) + (scalePosition(exon.end) - scalePosition(exon.start)) / 2"
            :y="centerY - exonHeight / 2 - 5"
            text-anchor="middle"
            class="exon-label"
          >
            {{ exon.number }}
          </text>
        </g>

        <!-- Variants -->
        <g
          v-for="(variant, index) in variantsToDisplay"
          :key="`variant-${index}`"
        >
          <!-- Variant marker -->
          <circle
            v-if="variant.position"
            :cx="scalePosition(variant.position)"
            :cy="centerY + (index % 2 === 0 ? -30 : 30)"
            :r="variant.isCurrentVariant ? 8 : 5"
            :fill="getVariantColor(variant)"
            :stroke="variant.isCurrentVariant ? '#9C27B0' : 'none'"
            :stroke-width="variant.isCurrentVariant ? 3 : 0"
            @mouseenter="showVariantTooltip($event, variant)"
            @mouseleave="hideTooltip"
            style="cursor: pointer"
            @click="$emit('variant-clicked', variant)"
          />
          <!-- Line connecting variant to gene -->
          <line
            v-if="variant.position"
            :x1="scalePosition(variant.position)"
            :y1="centerY"
            :x2="scalePosition(variant.position)"
            :y2="centerY + (index % 2 === 0 ? -30 : 30)"
            stroke="#BDBDBD"
            stroke-width="1"
            stroke-dasharray="2,2"
          />
        </g>
      </svg>

      <!-- Tooltip -->
      <v-menu
        v-model="tooltipVisible"
        :position-x="tooltipX"
        :position-y="tooltipY"
        absolute
        offset-y
      >
        <v-card v-if="tooltipContent" max-width="300">
          <v-card-text>
            <div v-if="tooltipContent.type === 'exon'">
              <strong>Exon {{ tooltipContent.data.number }}</strong>
              <div>Position: {{ formatCoordinate(tooltipContent.data.start) }} - {{ formatCoordinate(tooltipContent.data.end) }}</div>
              <div>Size: {{ tooltipContent.data.size }} bp</div>
              <div v-if="tooltipContent.data.domain">Domain: {{ tooltipContent.data.domain }}</div>
            </div>
            <div v-else-if="tooltipContent.type === 'variant'">
              <strong>{{ tooltipContent.data.label }}</strong>
              <div>{{ tooltipContent.data.hgvs_c }}</div>
              <div v-if="tooltipContent.data.hgvs_p">{{ tooltipContent.data.hgvs_p }}</div>
              <div>
                <v-chip :color="getVariantColor(tooltipContent.data)" size="small">
                  {{ tooltipContent.data.classification }}
                </v-chip>
              </div>
              <div class="text-caption mt-1">
                Click to view details
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-menu>

      <!-- Zoom Controls -->
      <v-row class="mt-2">
        <v-col cols="12" class="text-center">
          <v-btn-group>
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
  </v-card>
</template>

<script>
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
  },
  data() {
    return {
      svgWidth: 1000,
      svgHeight: 200,
      margin: { top: 40, right: 50, bottom: 50, left: 50 },
      exonHeight: 40,
      geneStart: 36096264, // chr17 coordinates (GRCh38)
      geneEnd: 36164048,
      tooltipVisible: false,
      tooltipX: 0,
      tooltipY: 0,
      tooltipContent: null,
      zoomLevel: 1,
      exons: [
        { number: 1, start: 36162719, end: 36164048, size: 1330, domain: '5\' UTR' },
        { number: 2, start: 36128663, end: 36128841, size: 179, domain: null },
        { number: 3, start: 36127274, end: 36127418, size: 145, domain: 'POU-S' },
        { number: 4, start: 36118768, end: 36119002, size: 235, domain: 'POU-H' },
        { number: 5, start: 36113941, end: 36114065, size: 125, domain: 'POU-H' },
        { number: 6, start: 36108318, end: 36108415, size: 98, domain: null },
        { number: 7, start: 36104951, end: 36105082, size: 132, domain: 'Transactivation' },
        { number: 8, start: 36103228, end: 36103398, size: 171, domain: 'Transactivation' },
        { number: 9, start: 36096264, end: 36096699, size: 436, domain: '3\' UTR' },
      ],
    };
  },
  computed: {
    centerY() {
      return (this.svgHeight - this.margin.top - this.margin.bottom) / 2 + this.margin.top;
    },
    variantsToDisplay() {
      return this.variants.map((v) => ({
        ...v,
        isCurrentVariant: v.id === this.currentVariantId,
        position: this.extractVariantPosition(v),
      }));
    },
  },
  methods: {
    scalePosition(genomicPosition) {
      const geneLength = this.geneEnd - this.geneStart;
      const svgLength = this.svgWidth - this.margin.left - this.margin.right;
      const relativePosition = (genomicPosition - this.geneStart) / geneLength;
      return this.margin.left + relativePosition * svgLength * this.zoomLevel;
    },
    extractVariantPosition(variant) {
      // Extract genomic position from variant data
      if (variant.vcf?.pos) {
        return variant.vcf.pos;
      }
      // Parse from HGVS if available
      if (variant.hgvs_g) {
        const match = variant.hgvs_g.match(/chr17[:-](\d+)/);
        if (match) return parseInt(match[1]);
      }
      return null;
    },
    getExonColor(exon) {
      // Color by functional domain
      if (exon.domain?.includes('POU')) return '#2196F3'; // Blue
      if (exon.domain?.includes('Transactivation')) return '#4CAF50'; // Green
      if (exon.domain?.includes('UTR')) return '#9E9E9E'; // Grey
      return '#1976D2'; // Default blue
    },
    getVariantColor(variant) {
      const colorMap = {
        PATHOGENIC: '#F44336',
        LIKELY_PATHOGENIC: '#FF9800',
        UNCERTAIN_SIGNIFICANCE: '#FFEB3B',
        LIKELY_BENIGN: '#8BC34A',
        BENIGN: '#4CAF50',
      };
      return colorMap[variant.classification] || '#9E9E9E';
    },
    formatCoordinate(pos) {
      return pos.toLocaleString();
    },
    showExonTooltip(event, exon) {
      this.tooltipX = event.clientX;
      this.tooltipY = event.clientY;
      this.tooltipContent = { type: 'exon', data: exon };
      this.tooltipVisible = true;
    },
    showVariantTooltip(event, variant) {
      this.tooltipX = event.clientX;
      this.tooltipY = event.clientY;
      this.tooltipContent = { type: 'variant', data: variant };
      this.tooltipVisible = true;
    },
    hideTooltip() {
      this.tooltipVisible = false;
    },
    zoomIn() {
      this.zoomLevel *= 1.2;
    },
    zoomOut() {
      this.zoomLevel /= 1.2;
    },
    resetZoom() {
      this.zoomLevel = 1;
    },
  },
};
</script>

<style scoped>
.gene-visualization {
  border: 1px solid #E0E0E0;
  border-radius: 4px;
  background-color: #FAFAFA;
}

.chromosome-label {
  font-size: 14px;
  font-weight: 600;
  fill: #424242;
}

.coordinate-label {
  font-size: 12px;
  fill: #757575;
}

.exon-label {
  font-size: 11px;
  font-weight: 600;
  fill: #FFFFFF;
}
</style>
```

### 2. Integration into Variant Detail Page

**File:** `frontend/src/views/PageVariant.vue` (modify)

```vue
<template>
  <v-container fluid>
    <!-- Breadcrumb Navigation -->
    <v-breadcrumbs :items="breadcrumbs" />

    <!-- Variant Metadata Card -->
    <v-card class="mb-4">
      <!-- ... existing variant details ... -->
    </v-card>

    <!-- Gene Visualization -->
    <HNF1BGeneVisualization
      :variants="allVariants"
      :current-variant-id="variantId"
      @variant-clicked="navigateToVariant"
    />

    <!-- Individuals with This Variant -->
    <v-card>
      <!-- ... existing individuals table ... -->
    </v-card>
  </v-container>
</template>

<script>
import HNF1BGeneVisualization from '@/components/gene/HNF1BGeneVisualization.vue';

export default {
  name: 'PageVariant',
  components: {
    HNF1BGeneVisualization,
  },
  data() {
    return {
      variantId: '',
      variant: {},
      allVariants: [], // All variants for gene visualization
      individuals: [],
    };
  },
  async created() {
    this.variantId = this.$route.params.variant_id;
    await this.loadVariantData();
    await this.loadAllVariants(); // For gene viz
  },
  methods: {
    async loadVariantData() {
      // ... existing code ...
    },
    async loadAllVariants() {
      try {
        const response = await this.$api.getVariants({ gene: 'HNF1B', limit: 1000 });
        this.allVariants = response.data.data;
      } catch (error) {
        console.error('Error loading variants for visualization:', error);
      }
    },
    navigateToVariant(variant) {
      this.$router.push(`/variants/${variant.id}`);
    },
  },
};
</script>
```

## Alternative: Use ProtVista Library

Instead of custom SVG, could use EMBL-EBI's ProtVista:

**Pros:**
- Professional gene visualization library
- Well-tested and maintained
- Handles protein domains automatically

**Cons:**
- Additional dependency (~100KB)
- May require protein-level coordinates conversion
- Less customizable for project-specific needs

**Recommendation:** Start with custom SVG for full control, consider ProtVista in future if needed.

## Implementation Checklist

### Phase 1: Basic Gene Structure (4 hours)
- [ ] Create HNF1BGeneVisualization.vue component
- [ ] Define HNF1B exon coordinates
- [ ] Render gene backbone (intron line)
- [ ] Render exons as rectangles
- [ ] Add exon labels
- [ ] Add chromosome/coordinate labels
- [ ] Add basic styling

### Phase 2: Variant Mapping (2 hours)
- [ ] Extract variant genomic positions
- [ ] Map variants to gene coordinates
- [ ] Render variant markers (circles)
- [ ] Color-code by pathogenicity
- [ ] Highlight current variant
- [ ] Add connecting lines to gene

### Phase 3: Interactivity (2 hours)
- [ ] Add exon hover tooltips
- [ ] Add variant hover tooltips
- [ ] Add click handler for variants
- [ ] Add zoom controls
- [ ] Test responsiveness

### Phase 4: Integration & Testing (2 hours)
- [ ] Integrate into PageVariant.vue
- [ ] Fetch all variants for visualization
- [ ] Test with different variant types
- [ ] Test with CNVs (span multiple exons)
- [ ] Test with 100+ variants
- [ ] Verify performance

## Acceptance Criteria

- [ ] Gene structure displays all 9 exons
- [ ] Exons correctly positioned by genomic coordinates
- [ ] Introns shown as connecting lines
- [ ] Variants displayed as colored circles
- [ ] Current variant highlighted distinctly
- [ ] Variant colors match pathogenicity (P=red, LP=orange, VUS=yellow)
- [ ] Exon hover shows number, position, size, domain
- [ ] Variant hover shows HGVS, classification
- [ ] Clicking variant navigates to detail page
- [ ] Zoom controls work (in/out/reset)
- [ ] Legend explains colors and symbols
- [ ] Responsive design (works on mobile)
- [ ] Performance: renders < 100ms for 100 variants

## Dependencies

- Issue #35 (Variant detail page) - ✅ Required
- Issue #34 (Variants list) - ✅ Required (for fetching all variants)

## Performance Impact

**Rendering Performance:**
- SVG rendering: ~50ms for gene + 100 variants
- Zoom/pan: ~10ms (transforms only)
- Hover tooltips: Instant

**Memory:**
- SVG DOM elements: ~1KB per variant
- 100 variants = ~100KB memory

## Files Modified/Created

### New Files (1 file, ~400 lines)
- `frontend/src/components/gene/HNF1BGeneVisualization.vue`

### Modified Files (1 file, ~20 lines)
- `frontend/src/views/PageVariant.vue` (add visualization component)

## Timeline

**Estimated:** 10 hours (1.5 days)

## Priority

**P3 (Low)** - Enhancement, not critical for MVP

## Labels

`frontend`, `visualization`, `variants`, `enhancement`, `p3`

## Future Enhancements

- [ ] Show protein domains more prominently
- [ ] Add transcript selector (if multiple isoforms)
- [ ] Show conservation scores as heatmap
- [ ] Export visualization as SVG/PNG
- [ ] Add variant clustering analysis
- [ ] Show variant frequency data
- [ ] Integrate with gnomAD population data

## References

- HNF1B gene: HGNC:5024
- Transcript: NM_000458.4
- Protein: NP_000449.3
- UCSC Genome Browser: https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr17%3A36096264-36164048
- Ensembl: https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000108753

## Notes

- Gene coordinates based on GRCh38/hg38
- Visualization uses linear scale (not log scale)
- CNVs displayed differently (may span multiple exons)
- Zoom is client-side only (no server interaction)
- Component is reusable for other genes with coordinate changes
