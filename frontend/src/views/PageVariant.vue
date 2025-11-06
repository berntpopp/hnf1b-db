<!-- src/views/PageVariant.vue -->
<template>
  <v-container fluid>
    <v-row justify="center">
      <v-col cols="12">
        <v-sheet outlined>
          <!-- Loading overlay -->
          <v-overlay
            :model-value="loading"
            contained
            class="align-center justify-center"
          >
            <v-progress-circular
              indeterminate
              color="primary"
            />
          </v-overlay>

          <!-- Variant Details Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="pink darken-2"
              >
                mdi-dna
              </v-icon>
              Variant Details
              <v-chip
                color="pink lighten-4"
                class="ma-2"
              >
                {{ variant.simple_id || variant.variant_id }}
              </v-chip>
            </v-card-title>
            <v-card-text class="text-body-1">
              <v-row>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div><strong>Type:</strong> {{ getVariantType(variant) }}</div>

                  <!-- Variant size (for all types except SNVs) -->
                  <div v-if="getVariantSize(variant)">
                    <strong>Size:</strong> {{ getVariantSize(variant) }}
                  </div>

                  <!-- CNV-specific details -->
                  <div v-if="isCNV(variant) && getCNVDetails(variant)">
                    <div><strong>Chromosome:</strong> chr{{ getCNVDetails(variant).chromosome }}</div>
                    <div><strong>Start Position:</strong> {{ formatPosition(getCNVDetails(variant).start) }}</div>
                    <div><strong>End Position:</strong> {{ formatPosition(getCNVDetails(variant).end) }}</div>
                  </div>

                  <div>
                    <strong>HG38:</strong> {{ variant.hg38 }}
                    <v-btn
                      icon="mdi-content-copy"
                      size="x-small"
                      variant="text"
                      class="ml-1"
                      @click="copyToClipboard(variant.hg38, 'HG38 coordinates')"
                    />
                  </div>
                  <div v-if="variant.geneId">
                    <strong>Gene:</strong>
                    <a
                      :href="`https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${variant.geneId}`"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="gene-link"
                    >
                      {{ variant.geneSymbol }}
                    </a>
                    <span class="text-caption text-grey">({{ variant.geneId }})</span>
                  </div>
                  <div v-if="variant.transcript">
                    <strong>Transcript:</strong>
                    <a
                      v-if="extractTranscriptId(variant.transcript)"
                      :href="`https://www.ncbi.nlm.nih.gov/nuccore/${extractTranscriptId(variant.transcript)}`"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="transcript-link"
                    >
                      {{ extractTranscriptId(variant.transcript) }}
                    </a>
                    {{ extractCNotation(variant.transcript) }}
                  </div>
                  <div v-if="variant.protein">
                    <strong>Protein:</strong>
                    <a
                      v-if="extractProteinId(variant.protein)"
                      :href="`https://www.ncbi.nlm.nih.gov/protein/${extractProteinId(variant.protein)}`"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="protein-link"
                    >
                      {{ extractProteinId(variant.protein) }}
                    </a>
                    {{ extractPNotation(variant.protein) }}
                  </div>
                </v-col>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div v-if="variant.classificationVerdict">
                    <strong>Classification:</strong>
                    <v-chip
                      :color="getPathogenicityColor(variant.classificationVerdict)"
                      class="ml-2"
                      size="small"
                      variant="flat"
                    >
                      {{ variant.classificationVerdict }}
                    </v-chip>
                  </div>
                  <div v-if="getMolecularConsequence(variant)">
                    <strong>Molecular Consequence:</strong>
                    <v-chip
                      color="purple-lighten-3"
                      class="ml-2"
                      size="small"
                      variant="flat"
                    >
                      {{ getMolecularConsequence(variant) }}
                    </v-chip>
                  </div>
                  <div>
                    <strong>Individuals Count:</strong>
                    {{ variant.individualCount || phenopacketsWithVariant.length }}
                  </div>
                  <div v-if="hasExternalLinks(variant)">
                    <strong>External Resources:</strong>
                    <div class="external-links-container">
                      <!-- Variant-specific databases -->
                      <a
                        v-if="getClinVarLink(variant)"
                        :href="getClinVarLink(variant)"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link"
                      >
                        ClinVar
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>
                      <a
                        v-if="getDbSNPLink(variant)"
                        :href="getDbSNPLink(variant)"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link"
                      >
                        dbSNP
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>
                      <a
                        v-if="getClinGenLink(variant)"
                        :href="getClinGenLink(variant)"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link"
                      >
                        ClinGen
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>
                      <a
                        v-if="getDecipherLink(variant)"
                        :href="getDecipherLink(variant)"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link"
                      >
                        DECIPHER
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>
                      <a
                        v-if="getUCSCLink(variant)"
                        :href="getUCSCLink(variant)"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link"
                      >
                        UCSC Browser
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>

                      <!-- Gene databases (divider) -->
                      <span
                        v-if="variant.geneSymbol"
                        class="external-link-divider"
                      >|</span>

                      <!-- General gene databases -->
                      <a
                        v-if="variant.geneSymbol"
                        :href="`https://www.ncbi.nlm.nih.gov/gene/?term=${variant.geneSymbol}`"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link external-link-gene"
                      >
                        NCBI Gene
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>
                      <a
                        v-if="variant.geneSymbol"
                        :href="`https://www.omim.org/search?search=${variant.geneSymbol}`"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="external-link external-link-gene"
                      >
                        OMIM
                        <v-icon
                          size="x-small"
                          class="ml-1"
                        >
                          mdi-open-in-new
                        </v-icon>
                      </a>
                    </div>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Snackbar for copy notification -->
          <v-snackbar
            v-model="snackbar"
            :timeout="2000"
            color="success"
          >
            {{ snackbarMessage }}
          </v-snackbar>

          <!-- Gene/Protein Visualizations -->
          <!-- Use wider layout (98%) for region view, standard (90%) otherwise -->
          <div
            :style="{ width: (visualizationTab === 'region' ? '98%' : '90%'), margin: 'auto' }"
            class="mb-4"
          >
            <v-card>
              <!-- Conditional tabs based on variant type -->
              <v-tabs
                v-model="visualizationTab"
                bg-color="grey-lighten-4"
              >
                <!-- Gene View tab (always shown) -->
                <v-tab value="gene">
                  <v-icon left>
                    mdi-dna
                  </v-icon>
                  <span v-if="isCNV(variant)">Gene View (HNF1B only)</span>
                  <span v-else>Gene View</span>
                </v-tab>

                <!-- Protein View tab (only for SNVs/indels) -->
                <v-tab
                  v-if="!isCNV(variant)"
                  value="protein"
                >
                  <v-icon left>
                    mdi-protein
                  </v-icon>
                  Protein View
                </v-tab>

                <!-- Region View tab (only for CNVs) -->
                <v-tab
                  v-if="isCNV(variant)"
                  value="region"
                >
                  <v-icon left>
                    mdi-map-marker-radius
                  </v-icon>
                  Region View (17q12 - 15 genes)
                </v-tab>
              </v-tabs>

              <v-window v-model="visualizationTab">
                <!-- Gene View: Shows HNF1B gene structure -->
                <v-window-item value="gene">
                  <HNF1BGeneVisualization
                    :variants="allVariants"
                    :current-variant-id="$route.params.variant_id"
                    :force-view-mode="isCNV(variant) ? 'gene' : null"
                    @variant-clicked="navigateToVariant"
                  />
                </v-window-item>

                <!-- Protein View: Only for SNVs/indels -->
                <v-window-item value="protein">
                  <HNF1BProteinVisualization
                    :variants="allVariants"
                    :current-variant-id="$route.params.variant_id"
                    @variant-clicked="navigateToVariant"
                  />
                </v-window-item>

                <!-- Region View: Only for CNVs - shows 17q12 region with 15 genes -->
                <v-window-item value="region">
                  <HNF1BGeneVisualization
                    :variants="allVariants"
                    :current-variant-id="$route.params.variant_id"
                    :force-view-mode="'cnv'"
                    @variant-clicked="navigateToVariant"
                  />
                </v-window-item>
              </v-window>
            </v-card>
          </div>

          <!-- Affected Individuals Table -->
          <v-card
            v-if="phenopacketsWithVariant.length > 0"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="purple darken-2"
              >
                mdi-account-multiple
              </v-icon>
              Affected Individuals ({{ phenopacketsWithVariant.length }})
            </v-card-title>
            <v-card-text>
              <v-data-table
                :headers="headers"
                :items="phenopacketsWithVariant"
                density="compact"
                :items-per-page="10"
                class="elevation-0"
              >
                <!-- Phenopacket ID as clickable chip -->
                <template #item.phenopacket_id="{ item }">
                  <v-chip
                    :to="`/phenopackets/${item.phenopacket_id}`"
                    color="lime-lighten-2"
                    size="small"
                    link
                  >
                    {{ item.phenopacket_id }}
                    <v-icon
                      right
                      size="small"
                    >
                      mdi-open-in-new
                    </v-icon>
                  </v-chip>
                </template>

                <!-- Sex with icon -->
                <template #item.subject_sex="{ item }">
                  <div class="d-flex align-center">
                    <v-icon
                      :color="getSexColor(item.subject_sex)"
                      size="small"
                      class="mr-1"
                    >
                      {{ getSexIcon(item.subject_sex) }}
                    </v-icon>
                    {{ formatSex(item.subject_sex) }}
                  </div>
                </template>
              </v-data-table>
            </v-card-text>
          </v-card>
        </v-sheet>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { getVariants, getPhenopacketsByVariant } from '@/api';
import HNF1BGeneVisualization from '@/components/gene/HNF1BGeneVisualization.vue';
import HNF1BProteinVisualization from '@/components/gene/HNF1BProteinVisualization.vue';

export default {
  name: 'PageVariant',
  components: {
    HNF1BGeneVisualization,
    HNF1BProteinVisualization,
  },
  data() {
    return {
      variant: {},
      phenopacketsWithVariant: [],
      allVariants: [], // All variants for visualization context
      loading: false,
      snackbar: false,
      snackbarMessage: '',
      visualizationTab: 'gene', // Default to gene view
      headers: [
        {
          title: 'Phenopacket ID',
          value: 'phenopacket_id',
          sortable: true,
        },
        {
          title: 'Sex',
          value: 'subject_sex',
          sortable: true,
          width: '120px',
        },
        {
          title: 'Added',
          value: 'created_at',
          sortable: true,
          width: '150px',
        },
      ],
    };
  },
  watch: {
    '$route.params.variant_id': {
      handler() {
        this.loadVariantData();
      },
      immediate: false,
    },
    visualizationTab() {
      // When tab changes, trigger a resize event after DOM updates
      // This ensures SVG width is recalculated correctly for the newly visible tab
      this.$nextTick(() => {
        window.dispatchEvent(new Event('resize'));
      });
    },
  },
  created() {
    this.loadVariantData();
    this.loadAllVariants();
  },
  methods: {
    async loadAllVariants() {
      // Load all variants for visualization context
      try {
        const response = await getVariants({
          page: 1,
          page_size: 1000, // Get all variants
        });
        this.allVariants = response.data || [];
      } catch (error) {
        console.error('Error loading variants for visualization:', error);
        // Don't block page load if this fails
        this.allVariants = [];
      }
    },
    navigateToVariant(variant) {
      // Navigate to another variant's detail page
      if (variant && variant.variant_id) {
        this.$router.push(`/variants/${variant.variant_id}`);
      }
    },
    getVariantType(variant) {
      // Detect actual variant type - detail view shows specific type (deletion/duplication)
      // while list view shows "CNV" for large structural variants
      if (!variant) return 'Unknown';

      // For CNVs, check the HG38 format to determine deletion vs duplication
      if (variant.hg38) {
        const cnvMatch = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):([A-Z]+)/);
        if (cnvMatch) {
          const svType = cnvMatch[4]; // DEL, DUP, etc.
          if (svType === 'DEL') return 'deletion';
          if (svType === 'DUP') return 'duplication';
          return svType.toLowerCase();
        }
      }

      // For small variants, detect type from c. notation
      const cNotation = this.extractCNotation(variant.transcript);

      if (cNotation) {
        // Check for deletions
        if (/del/.test(cNotation) && !/dup/.test(cNotation)) {
          return 'deletion';
        }
        // Check for duplications
        if (/dup/.test(cNotation)) {
          return 'duplication';
        }
        // Check for insertions
        if (/ins/.test(cNotation)) {
          return 'insertion';
        }
        // Check for delins (deletion-insertion)
        if (/delins/.test(cNotation)) {
          return 'indel';
        }
        // Check for substitutions (true SNVs: single position with >)
        if (/>\w$/.test(cNotation) && !/[+-]/.test(cNotation) && !/_/.test(cNotation)) {
          return 'SNV';
        }
      }

      // Fall back to stored variant_type
      return variant.variant_type || 'Unknown';
    },
    isCNV(variant) {
      // Check if this variant is a CNV (has genomic coordinates)
      if (!variant || !variant.hg38) return false;
      return /(\d+|X|Y|MT?):(\d+)-(\d+):/.test(variant.hg38);
    },
    getCNVDetails(variant) {
      // Extract CNV details from HG38 format: "17:36459258-37832869:DEL"
      if (!variant || !variant.hg38) return null;
      const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):([A-Z]+)/);
      if (match) {
        return {
          chromosome: match[1],
          start: match[2],
          end: match[3],
          type: match[4],
        };
      }
      return null;
    },
    getCNVSize(variant) {
      // Calculate CNV size in human-readable format
      const details = this.getCNVDetails(variant);
      if (!details) return null;

      const start = parseInt(details.start);
      const end = parseInt(details.end);
      const sizeInBp = end - start;

      // Format size based on magnitude
      if (sizeInBp >= 1000000) {
        return `${(sizeInBp / 1000000).toFixed(2)} Mb`;
      } else if (sizeInBp >= 1000) {
        return `${(sizeInBp / 1000).toFixed(2)} kb`;
      } else {
        return `${sizeInBp.toLocaleString()} bp`;
      }
    },
    formatPosition(pos) {
      // Add thousand separators: 36459258 → 36,459,258
      return parseInt(pos).toLocaleString();
    },
    async loadVariantData() {
      this.loading = true;
      const variantId = this.$route.params.variant_id;

      try {
        const variantResponse = await getVariants({
          page: 1,
          page_size: 1000,
        });

        if (!variantResponse.data || variantResponse.data.length === 0) {
          this.$router.push('/PageNotFound');
          return;
        }

        this.variant = variantResponse.data.find((v) => v.variant_id === variantId);

        if (!this.variant) {
          console.error(`Variant with ID ${variantId} not found`);
          this.$router.push('/PageNotFound');
          return;
        }

        const phenopacketsResponse = await getPhenopacketsByVariant(variantId);
        this.phenopacketsWithVariant = phenopacketsResponse.data.map(pp => ({
          phenopacket_id: pp.phenopacket_id,
          subject_sex: pp.phenopacket?.subject?.sex || 'UNKNOWN_SEX',
          created_at: new Date(pp.created_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
          }),
        }));

        this.loading = false;
      } catch (error) {
        console.error('Error loading variant data:', error);
        this.loading = false;
      }
    },
    extractCNotation(transcript) {
      if (!transcript) return '-';
      const match = transcript.match(/:(.+)$/);
      return match && match[1] ? match[1] : transcript;
    },
    extractPNotation(protein) {
      if (!protein) return '-';
      const match = protein.match(/:(.+)$/);
      return match && match[1] ? match[1] : protein;
    },
    extractTranscriptId(transcript) {
      if (!transcript) return null;
      const match = transcript.match(/^(NM_[\d.]+):/);
      return match && match[1] ? match[1] : null;
    },
    extractProteinId(protein) {
      if (!protein) return null;
      const match = protein.match(/^(NP_[\d.]+):/);
      return match && match[1] ? match[1] : null;
    },
    getPathogenicityColor(pathogenicity) {
      const upperPath = pathogenicity ? pathogenicity.toUpperCase() : '';
      if (upperPath.includes('PATHOGENIC') && !upperPath.includes('LIKELY')) {
        return 'red-lighten-3';
      }
      if (upperPath.includes('LIKELY_PATHOGENIC') || upperPath.includes('LIKELY PATHOGENIC')) {
        return 'orange-lighten-3';
      }
      if (upperPath.includes('UNCERTAIN') || upperPath.includes('VUS')) {
        return 'yellow-darken-1';
      }
      if (upperPath.includes('LIKELY_BENIGN') || upperPath.includes('LIKELY BENIGN')) {
        return 'light-green-lighten-3';
      }
      if (upperPath.includes('BENIGN')) {
        return 'green-lighten-3';
      }
      return 'grey-lighten-2';
    },
    getMolecularConsequence(variant) {
      // Backend now correctly computes molecular_consequence
      // Just return it directly instead of recomputing
      if (!variant) return null;

      // Use the computed consequence from backend if available
      if (variant.molecular_consequence) {
        return variant.molecular_consequence;
      }

      // Fallback to client-side computation (for backwards compatibility)
      // IMPORTANT: Check protein/transcript BEFORE variant_type
      if (variant.protein) {
        const pNotation = this.extractPNotation(variant.protein);
        if (!pNotation) return 'Coding Sequence Variant';

        if (pNotation.includes('fs')) return 'Frameshift';
        if (pNotation.includes('Ter') || pNotation.includes('*')) return 'Nonsense';
        if (pNotation.match(/p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}/)) return 'Missense';
        if (pNotation.includes('del') && !pNotation.includes('fs')) return 'In-frame Deletion';
        if (pNotation.includes('ins') && !pNotation.includes('fs')) return 'In-frame Insertion';
        if (pNotation.includes('=')) return 'Synonymous';

        return 'Coding Sequence Variant';
      }

      if (variant.transcript) {
        const cNotation = this.extractCNotation(variant.transcript);
        if (!cNotation) return null;

        const spliceMatch = cNotation.match(/([+-])(\d+)/);
        if (spliceMatch) {
          const sign = spliceMatch[1];
          const position = parseInt(spliceMatch[2], 10);

          // Canonical splice site boundaries (HGVS/Sequence Ontology conventions):
          // Splice Donor (5' site): +1 to +6 positions after exon end
          //   - Conserved GT dinucleotide at +1/+2 (SO:0000164)
          //   - Extended donor motif spans +1 to +6
          // Splice Acceptor (3' site): -1 to -3 positions before exon start
          //   - Conserved AG dinucleotide at -2/-1 (SO:0000162)
          //   - Branch point region at -3
          // References:
          //   - Sequence Ontology: http://www.sequenceontology.org/
          //   - HGVS nomenclature: https://varnomen.hgvs.org/
          if (sign === '+' && position >= 1 && position <= 6) return 'Splice Donor';
          if (sign === '-' && position >= 1 && position <= 3) return 'Splice Acceptor';
          return 'Intronic Variant';
        }

        return 'Coding Sequence Variant';
      }

      // Check variant type last (only for CNVs without protein/transcript data)
      if (variant.variant_type === 'deletion') return 'Copy Number Loss';
      if (variant.variant_type === 'duplication') return 'Copy Number Gain';

      return null;
    },
    hasExternalLinks(variant) {
      return this.getClinVarLink(variant) ||
             this.getDbSNPLink(variant) ||
             this.getClinGenLink(variant) ||
             this.getDecipherLink(variant) ||
             this.getUCSCLink(variant) ||
             variant.geneSymbol; // Always show if we have gene symbol (for NCBI Gene & OMIM)
    },
    copyToClipboard(text, label) {
      // Copy to clipboard using modern Clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          this.snackbarMessage = `${label} copied to clipboard!`;
          this.snackbar = true;
        }).catch((err) => {
          console.error('Failed to copy:', err);
          this.snackbarMessage = 'Failed to copy to clipboard';
          this.snackbar = true;
        });
      } else {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
          document.execCommand('copy');
          this.snackbarMessage = `${label} copied to clipboard!`;
          this.snackbar = true;
        } catch (err) {
          console.error('Failed to copy:', err);
          this.snackbarMessage = 'Failed to copy to clipboard';
          this.snackbar = true;
        }
        document.body.removeChild(textarea);
      }
    },
    getClinVarLink(variant) {
      // ClinVar search works for all variant types with HGVS notation (not just SNVs)
      if (!variant || !variant.transcript || !variant.geneSymbol) {
        return null;
      }
      const cNotation = this.extractCNotation(variant.transcript);
      if (cNotation) {
        const searchTerm = encodeURIComponent(`${variant.geneSymbol}[gene] AND ${cNotation}`);
        return `https://www.ncbi.nlm.nih.gov/clinvar/?term=${searchTerm}`;
      }
      return null;
    },
    getVariantSize(variant) {
      if (!variant || !variant.hg38) return null;

      // SNVs don't need size display
      if (variant.variant_type === 'SNV') return null;

      // Parse VCF format: chr17-37739638-TG-T or 17:12345-67890:DEL
      // For small variants: chr-pos-REF-ALT
      const smallVariantMatch = variant.hg38.match(/chr\d+-\d+-([A-Z]+)-([A-Z]+)/i);
      if (smallVariantMatch) {
        const ref = smallVariantMatch[1];
        const alt = smallVariantMatch[2];
        const refLen = ref.length;
        const altLen = alt.length;

        if (variant.variant_type === 'deletion') {
          const deleted = refLen - altLen;
          const deletedBases = ref.slice(1); // Skip first base (anchor)
          return `${deleted}bp deletion (${deletedBases} deleted)`;
        } else if (variant.variant_type === 'insertion') {
          const inserted = altLen - refLen;
          const insertedBases = alt.slice(1); // Skip first base (anchor)
          return `${inserted}bp insertion (${insertedBases} inserted)`;
        } else if (variant.variant_type === 'indel') {
          const deleted = refLen - 1; // Subtract anchor base
          const inserted = altLen - 1; // Subtract anchor base
          const deletedBases = ref.slice(1);
          const insertedBases = alt.slice(1);
          return `${deleted}bp deleted, ${inserted}bp inserted (${deletedBases}→${insertedBases})`;
        }
      }

      // For large CNVs: 17:12345-67890:DEL
      const cnvMatch = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
      if (cnvMatch && (variant.variant_type === 'deletion' || variant.variant_type === 'duplication')) {
        const start = parseInt(cnvMatch[2]);
        const end = parseInt(cnvMatch[3]);
        const size = end - start;

        if (size >= 1000000) {
          return `${(size / 1000000).toFixed(2)}Mb`;
        } else if (size >= 1000) {
          return `${(size / 1000).toFixed(1)}kb`;
        } else {
          return `${size}bp`;
        }
      }

      return null;
    },
    getDbSNPLink(variant) {
      if (!variant || variant.variant_type !== 'SNV' || !variant.hg38) return null;
      const match = variant.hg38.match(/chr(\d+|X|Y|MT?)-(\d+)/);
      if (match) {
        const chromosome = match[1];
        const position = match[2];
        return `https://www.ncbi.nlm.nih.gov/snp/?term=${chromosome}[CHR]+AND+${position}[POS]`;
      }
      return null;
    },
    getClinGenLink(variant) {
      if (!variant) return null;

      if (variant.variant_type === 'SNV' && variant.transcript && variant.geneSymbol) {
        const cNotation = this.extractCNotation(variant.transcript);
        if (cNotation) {
          const searchTerm = encodeURIComponent(`${variant.geneSymbol} ${cNotation}`);
          return `https://reg.clinicalgenome.org/redmine/projects/registry/genboree_registry/by_caid?caid=${searchTerm}`;
        }
      }

      if ((variant.variant_type === 'deletion' || variant.variant_type === 'duplication') && variant.geneSymbol) {
        return `https://search.clinicalgenome.org/kb/genes/${variant.geneSymbol}`;
      }

      return null;
    },
    getDecipherLink(variant) {
      if (!variant || (variant.variant_type !== 'deletion' && variant.variant_type !== 'duplication') || !variant.hg38) {
        return null;
      }
      const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
      if (match) {
        const chr = match[1];
        const start = match[2];
        const end = match[3];
        return `https://www.deciphergenomics.org/browser#q/${chr}:${start}-${end}`;
      }
      return null;
    },
    getUCSCLink(variant) {
      if (!variant || (variant.variant_type !== 'deletion' && variant.variant_type !== 'duplication') || !variant.hg38) {
        return null;
      }
      const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
      if (match) {
        const chr = match[1];
        const start = match[2];
        const end = match[3];
        return `https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr${chr}:${start}-${end}`;
      }
      return null;
    },
    getSexIcon(sex) {
      const sexIcons = {
        MALE: 'mdi-gender-male',
        FEMALE: 'mdi-gender-female',
        OTHER_SEX: 'mdi-gender-transgender',
        UNKNOWN_SEX: 'mdi-help-circle',
      };
      return sexIcons[sex] || 'mdi-help-circle';
    },
    getSexColor(sex) {
      const sexColors = {
        MALE: 'blue',
        FEMALE: 'pink',
        OTHER_SEX: 'purple',
        UNKNOWN_SEX: 'grey',
      };
      return sexColors[sex] || 'grey';
    },
    formatSex(sex) {
      const sexLabels = {
        MALE: 'Male',
        FEMALE: 'Female',
        OTHER_SEX: 'Other',
        UNKNOWN_SEX: 'Unknown',
      };
      return sexLabels[sex] || 'Unknown';
    },
  },
};
</script>

<style scoped>
/* Link styling for transcript and protein references */
.transcript-link,
.protein-link {
  color: #1976d2;
  text-decoration: none;
  margin-right: 4px;
}

.transcript-link:hover,
.protein-link:hover {
  text-decoration: underline;
}

/* External links container */
.external-links-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
}

.external-link {
  display: inline-flex;
  align-items: center;
  color: #1976d2;
  text-decoration: none;
  font-weight: 500;
  padding: 4px 8px;
  border: 1px solid #1976d2;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.external-link:hover {
  background-color: #1976d2;
  color: white;
  text-decoration: none;
}

/* Gene link styling */
.gene-link {
  color: #1976d2;
  text-decoration: none;
  font-weight: 500;
  margin-left: 4px;
  margin-right: 4px;
}

.gene-link:hover {
  text-decoration: underline;
}

/* External links divider */
.external-link-divider {
  margin: 0 8px;
  color: #999;
  font-weight: 300;
}

/* Gene-specific external links (lighter style) */
.external-link-gene {
  border-color: #64b5f6;
  color: #64b5f6;
}

.external-link-gene:hover {
  background-color: #64b5f6;
  color: white;
}
</style>
