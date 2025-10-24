<!-- src/views/PageVariant.vue -->
<template>
  <v-container fluid>
    <v-row justify="center">
      <v-col cols="12">
        <v-sheet outlined>
          <!-- Loading overlay -->
          <v-overlay
            :absolute="absolute"
            :opacity="opacity"
            :value="loading"
            :color="color"
          >
            <v-progress-circular
              indeterminate
              color="primary"
            />
          </v-overlay>

          <!-- Variant Basic Details Card -->
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
                {{ variant.variant_id }}
              </v-chip>
            </v-card-title>
            <v-card-text class="text-body-1">
              <v-row>
                <v-col
                  cols="12"
                  sm="6"
                >
                  <div><strong>Type:</strong> {{ variant.variant_type }}</div>
                  <div><strong>HG38:</strong> {{ variant.hg38 }}</div>
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
                    </div>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Classification Details Card -->
          <v-card
            v-if="variant.classifications && variant.classifications.length"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="deep-purple"
              >
                mdi-clipboard-check-outline
              </v-icon>
              Classification
            </v-card-title>
            <v-card-text>
              <v-list dense>
                <v-list-item
                  v-for="(cl, index) in variant.classifications"
                  :key="index"
                >
                  <v-list-item-title>
                    <div class="d-flex align-center">
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-check-circle-outline
                      </v-icon>
                      <span class="font-weight-bold">Verdict:</span>
                      <span class="ml-1">{{ cl.verdict }}</span>
                    </div>
                    <div class="d-flex align-center">
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-calendar-clock
                      </v-icon>
                      <span class="font-weight-bold">Date:</span>
                      <span class="ml-1">{{ cl.classification_date }}</span>
                    </div>
                    <div class="d-flex align-center">
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-format-list-bulleted
                      </v-icon>
                      <span class="font-weight-bold">Criteria:</span>
                      <span class="ml-1">{{ cl.criteria }}</span>
                    </div>
                    <div
                      v-if="cl.comment"
                      class="d-flex align-center"
                    >
                      <v-icon
                        color="deep-purple"
                        class="mr-1"
                      >
                        mdi-comment-alert-outline
                      </v-icon>
                      <span class="font-weight-bold">Comment:</span>
                      <span class="ml-1">{{ cl.comment }}</span>
                    </div>
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>

          <!-- Annotations Card (Collapsible) -->
          <v-card
            v-if="variant.annotations && variant.annotations.length"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="teal"
              >
                mdi-note-text-outline
              </v-icon>
              Annotations
            </v-card-title>
            <v-card-text>
              <v-expansion-panels accordion>
                <v-expansion-panel
                  v-for="(ann, index) in variant.annotations"
                  :key="index"
                >
                  <v-expansion-panel-title>
                    <v-icon
                      start
                      color="teal"
                    >
                      mdi-file-document-outline
                    </v-icon>
                    <span class="font-weight-bold">{{ ann.transcript }}</span>
                    <small class="text-grey-darken-1 ml-2">({{ ann.annotation_date }})</small>
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-list dense>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="teal"
                              class="mr-1"
                            >
                              mdi-code-tags
                            </v-icon>
                            <span class="font-weight-bold">cDNA:</span>
                            <span class="ml-1">{{ ann.c_dot || 'N/A' }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>
                          <div class="d-flex align-center">
                            <v-icon
                              color="teal"
                              class="mr-1"
                            >
                              mdi-cube-outline
                            </v-icon>
                            <span class="font-weight-bold">Protein:</span>
                            <span class="ml-1">{{ ann.p_dot || 'N/A' }}</span>
                          </div>
                        </v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-card-text>
          </v-card>

          <!-- Reported Data Card -->
          <v-card
            v-if="variant.reported && variant.reported.length"
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="orange"
              >
                mdi-alert-circle-outline
              </v-icon>
              Reported Variants
            </v-card-title>
            <v-card-text>
              <v-list dense>
                <v-list-item
                  v-for="(rep, idx) in variant.reported"
                  :key="idx"
                >
                  <template #prepend>
                    <v-icon color="orange">
                      mdi-file-document-outline
                    </v-icon>
                  </template>
                  <v-list-item-title class="d-flex align-center">
                    <span class="font-weight-bold">Reported:</span>
                    <span class="ml-1">{{ rep.variant_reported }}</span>
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    <div class="d-flex align-center">
                      <v-icon
                        color="orange"
                        class="mr-1"
                      >
                        mdi-book-open-page-variant
                      </v-icon>
                      <span class="font-weight-bold">Publication:</span>
                      <span class="ml-1">{{ rep.publication_ref }}</span>
                    </div>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-card-text>
          </v-card>

          <!-- Protein Linear Plot Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="indigo"
              >
                mdi-chart-line
              </v-icon>
              Protein Linear Plot
            </v-card-title>
            <v-card-text>
              <ProteinLinearPlot
                :show_controls="false"
                :variant_filter="'equals(variant_id,' + variant.variant_id + ')'"
              />
            </v-card-text>
          </v-card>

          <!-- Individuals Carrying This Variant Card -->
          <v-card
            outlined
            class="mb-4"
            :style="{ width: '90%', margin: 'auto' }"
            tile
          >
            <v-card-title class="text-h6">
              <v-icon
                left
                color="primary"
              >
                mdi-account-multiple-outline
              </v-icon>
              Individuals Carrying This Variant ({{ phenopacketsWithVariant.length }})
            </v-card-title>
            <v-card-text>
              <v-data-table
                :headers="phenopacketHeaders"
                :items="phenopacketsWithVariant"
                :items-per-page="10"
                density="compact"
                class="elevation-1"
                @click:row="handlePhenopacketRowClick"
              >
                <template #item.phenopacket_id="{ item }">
                  <v-chip
                    color="blue-lighten-3"
                    size="small"
                    class="ma-1"
                  >
                    {{ item.phenopacket_id }}
                  </v-chip>
                </template>

                <template #item.subject_sex="{ item }">
                  <v-chip
                    :color="getSexColor(item.subject_sex)"
                    size="small"
                    class="ma-1"
                  >
                    {{ item.subject_sex }}
                  </v-chip>
                </template>

                <template #no-data>
                  <v-alert
                    type="info"
                    variant="tonal"
                  >
                    No phenopackets found with this variant.
                  </v-alert>
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
import ProteinLinearPlot from '@/components/analyses/ProteinLinearPlot.vue';
import colorAndSymbolsMixin from '@/assets/js/mixins/colorAndSymbolsMixin.js';
import { getVariants, getPhenopacketsByVariant } from '@/api';

export default {
  name: 'PageVariant',
  components: {
    ProteinLinearPlot,
  },
  mixins: [colorAndSymbolsMixin],

  data() {
    return {
      variant: {},
      absolute: true,
      opacity: 1,
      color: '#FFFFFF',
      loading: true,
      phenopacketsWithVariant: [],
      phenopacketHeaders: [
        {
          title: 'Phenopacket ID',
          value: 'phenopacket_id',
          sortable: true,
        },
        {
          title: 'Sex',
          value: 'subject_sex',
          sortable: true,
        },
        {
          title: 'Created',
          value: 'created_at',
          sortable: true,
        },
      ],
      icons: {
        mdiDna: 'mdi-dna',
        mdiNewspaperVariant: 'mdi-newspaper-variant',
      },
    };
  },
  created() {
    this.loadVariantData();
  },
  watch: {
    '$route.params.variant_id': {
      handler() {
        this.loadVariantData();
      },
      immediate: false,
    },
  },
  methods: {
    async loadVariantData() {
      this.loading = true;
      const variantId = this.$route.params.variant_id;

      try {
        // Fetch all variants to find the one with matching ID
        // Note: We fetch a large page size since there's no single variant endpoint
        const variantResponse = await getVariants({
          page: 1,
          page_size: 1000,
        });

        if (!variantResponse.data || variantResponse.data.length === 0) {
          this.$router.push('/PageNotFound');
          return;
        }

        // Find the variant with matching ID
        this.variant = variantResponse.data.find((v) => v.variant_id === variantId);

        if (!this.variant) {
          console.error(`Variant with ID ${variantId} not found`);
          this.$router.push('/PageNotFound');
          return;
        }

        // Fetch phenopackets containing this variant
        const phenopacketsResponse = await getPhenopacketsByVariant(variantId);

        // Transform phenopacket data for table display
        this.phenopacketsWithVariant = phenopacketsResponse.data.map((pp) => ({
          phenopacket_id: pp.phenopacket_id,
          subject_sex: pp.phenopacket?.subject?.sex || 'UNKNOWN_SEX',
          created_at: new Date(pp.created_at).toLocaleDateString(),
        }));
      } catch (e) {
        console.error('Error loading variant data:', e);
      }

      this.loading = false;
    },
    handlePhenopacketRowClick(event, row) {
      // Navigate to phenopacket detail page
      if (row.item && row.item.phenopacket_id) {
        this.$router.push(`/phenopackets/${row.item.phenopacket_id}`);
      }
    },
    getSexColor(sex) {
      const colorMap = {
        MALE: 'blue-lighten-3',
        FEMALE: 'pink-lighten-3',
        UNKNOWN_SEX: 'grey-lighten-2',
        OTHER_SEX: 'purple-lighten-3',
      };
      return colorMap[sex] || 'grey-lighten-2';
    },
    extractCNotation(transcript) {
      // Extract only the c. notation from HGVS format (e.g., "NM_000458.4:c.544+1G>T" -> "c.544+1G>T")
      if (!transcript) return '-';

      // Match the c. notation part (everything after the colon)
      const match = transcript.match(/:(.+)$/);
      if (match && match[1]) {
        return match[1];
      }

      // If no colon found, return the original value
      return transcript;
    },
    extractPNotation(protein) {
      // Extract only the p. notation from HGVS format (e.g., "NP_000449.3:p.Arg177Ter" -> "p.Arg177Ter")
      if (!protein) return '-';

      // Match the p. notation part (everything after the colon)
      const match = protein.match(/:(.+)$/);
      if (match && match[1]) {
        return match[1];
      }

      // If no colon found, return the original value
      return protein;
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
        return 'yellow-lighten-3';
      }
      if (upperPath.includes('LIKELY_BENIGN') || upperPath.includes('LIKELY BENIGN')) {
        return 'light-green-lighten-3';
      }
      if (upperPath.includes('BENIGN')) {
        return 'green-lighten-3';
      }
      return 'grey-lighten-2';
    },
    extractTranscriptId(transcript) {
      // Extract the NM_ reference from HGVS format (e.g., "NM_000458.4:c.544+1G>T" -> "NM_000458.4")
      if (!transcript) return null;

      // Match the NM_ part (everything before the colon)
      const match = transcript.match(/^(NM_[\d.]+):/);
      if (match && match[1]) {
        return match[1];
      }

      return null;
    },
    extractProteinId(protein) {
      // Extract the NP_ reference from HGVS format (e.g., "NP_000449.3:p.Arg177Ter" -> "NP_000449.3")
      if (!protein) return null;

      // Match the NP_ part (everything before the colon)
      const match = protein.match(/^(NP_[\d.]+):/);
      if (match && match[1]) {
        return match[1];
      }

      return null;
    },
    getClinVarLink(variant) {
      // Generate ClinVar search URL based on variant information
      // ClinVar search works best with gene + HGVS notation for SNVs
      // Skip ClinVar for CNVs as coordinate search doesn't work well
      if (!variant) return null;

      // Only for SNVs with transcript notation
      if (variant.variant_type === 'SNV' && variant.transcript && variant.geneSymbol) {
        const cNotation = this.extractCNotation(variant.transcript);
        if (cNotation) {
          // ClinVar search format: gene[gene] AND c.notation
          const searchTerm = encodeURIComponent(`${variant.geneSymbol}[gene] AND ${cNotation}`);
          return `https://www.ncbi.nlm.nih.gov/clinvar/?term=${searchTerm}`;
        }
      }

      return null;
    },
    getDbSNPLink(variant) {
      // Generate dbSNP search URL
      // dbSNP works best with chromosome position for SNVs
      if (!variant) return null;

      // Only for SNVs with HG38 coordinates
      if (variant.variant_type === 'SNV' && variant.hg38) {
        // Parse chr17-37739455-G-A format to get chromosome and position
        const match = variant.hg38.match(/chr(\d+|X|Y|MT?)-(\d+)/);
        if (match) {
          const chromosome = match[1];
          const position = match[2];
          // dbSNP search by chromosome:position
          return `https://www.ncbi.nlm.nih.gov/snp/?term=${chromosome}[CHR]+AND+${position}[POS]`;
        }
      }

      return null;
    },
    getClinGenLink(variant) {
      // Generate ClinGen search URL
      // ClinGen works well with gene + variant notation
      if (!variant) return null;

      // For SNVs with transcript notation
      if (variant.variant_type === 'SNV' && variant.transcript && variant.geneSymbol) {
        const cNotation = this.extractCNotation(variant.transcript);
        if (cNotation) {
          // ClinGen search format: gene + c. notation
          const searchTerm = encodeURIComponent(`${variant.geneSymbol} ${cNotation}`);
          return `https://reg.clinicalgenome.org/redmine/projects/registry/genboree_registry/by_caid?caid=${searchTerm}`;
        }
      }

      // For CNVs, use ClinGen dosage sensitivity map
      if ((variant.variant_type === 'deletion' || variant.variant_type === 'duplication') && variant.geneSymbol) {
        // Search by gene in dosage sensitivity map
        return `https://search.clinicalgenome.org/kb/genes/${variant.geneSymbol}`;
      }

      return null;
    },
    getDecipherLink(variant) {
      // Generate DECIPHER database link for CNVs
      // DECIPHER is excellent for CNV interpretation
      if (!variant) return null;

      // Only for CNVs with HG38 coordinates
      if ((variant.variant_type === 'deletion' || variant.variant_type === 'duplication') && variant.hg38) {
        // Parse 17:36459258-37832869:DEL format
        const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
        if (match) {
          const chr = match[1];
          const start = match[2];
          const end = match[3];
          // DECIPHER browser format
          return `https://www.deciphergenomics.org/browser#q/${chr}:${start}-${end}`;
        }
      }

      return null;
    },
    getUCSCLink(variant) {
      // Generate UCSC Genome Browser link for visualizing CNVs
      if (!variant) return null;

      // Only for CNVs with HG38 coordinates
      if ((variant.variant_type === 'deletion' || variant.variant_type === 'duplication') && variant.hg38) {
        // Parse 17:36459258-37832869:DEL format
        const match = variant.hg38.match(/(\d+|X|Y|MT?):(\d+)-(\d+):/);
        if (match) {
          const chr = match[1];
          const start = match[2];
          const end = match[3];
          // UCSC browser format (hg38 assembly)
          return `https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr${chr}:${start}-${end}`;
        }
      }

      return null;
    },
    hasExternalLinks(variant) {
      // Check if variant has any external links available
      return this.getClinVarLink(variant) || this.getDbSNPLink(variant) || this.getClinGenLink(variant) || this.getDecipherLink(variant) || this.getUCSCLink(variant);
    },
    getMolecularConsequence(variant) {
      // Infer molecular consequence from protein notation
      // This is a simplified inference - ideally would come from VEP or ClinVar API
      if (!variant) return null;

      // For CNVs
      if (variant.variant_type === 'deletion') {
        return 'Copy Number Loss';
      }
      if (variant.variant_type === 'duplication') {
        return 'Copy Number Gain';
      }

      // For SNVs, infer from protein notation
      if (variant.protein) {
        const pNotation = this.extractPNotation(variant.protein);
        if (!pNotation) return 'Coding Sequence Variant';

        // Frameshift (check before Nonsense since frameshifts often end with Ter)
        if (pNotation.includes('fs')) {
          return 'Frameshift';
        }

        // Nonsense (stop gain)
        if (pNotation.includes('Ter') || pNotation.includes('*')) {
          return 'Nonsense';
        }

        // Missense (amino acid substitution)
        if (pNotation.match(/p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}/)) {
          return 'Missense';
        }

        // Deletion/insertion
        if (pNotation.includes('del') && !pNotation.includes('fs')) {
          return 'In-frame Deletion';
        }
        if (pNotation.includes('ins') && !pNotation.includes('fs')) {
          return 'In-frame Insertion';
        }

        // Synonymous (no change)
        if (pNotation.includes('=')) {
          return 'Synonymous';
        }

        return 'Coding Sequence Variant';
      }

      // For variants with c. notation but no p. notation
      if (variant.transcript) {
        const cNotation = this.extractCNotation(variant.transcript);
        if (!cNotation) return null;

        // Splice site variants - distinguish between donor and acceptor
        const spliceMatch = cNotation.match(/([+-])(\d+)/);
        if (spliceMatch) {
          const sign = spliceMatch[1];
          const position = parseInt(spliceMatch[2], 10);

          // Donor site: +1 to +6 (GT dinucleotide at +1/+2, extended donor at +3 to +6)
          if (sign === '+' && position >= 1 && position <= 6) {
            return 'Splice Donor';
          }

          // Acceptor site: -1 to -3 (AG dinucleotide at -2/-1, extended acceptor at -3)
          if (sign === '-' && position >= 1 && position <= 3) {
            return 'Splice Acceptor';
          }

          // Other intronic positions
          return 'Intronic Variant';
        }

        return 'Coding Sequence Variant';
      }

      return null;
    },
  },
};
</script>

<style scoped>
.chip-container {
  display: flex;
  flex-wrap: wrap;
}
.phenotype-chip {
  font-size: 0.7rem;
  margin: 1px !important;
}

/* Link styling for transcript, protein, and external resources */
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
</style>
