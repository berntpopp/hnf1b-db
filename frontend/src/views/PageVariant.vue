<!-- src/views/PageVariant.vue -->
<template>
  <div class="variant-container">
    <!-- HERO SECTION - Using PageHeader component -->
    <PageHeader
      title="Variant Details"
      icon="mdi-dna"
      icon-color="pink-darken-2"
      title-class="text-pink-darken-2"
      :breadcrumbs="breadcrumbs"
      variant="hero"
      show-back
      @back="$router.back()"
    >
      <template #prepend>
        <template v-if="!loading && variant.variant_id">
          <v-chip color="pink-lighten-4" size="small" variant="flat" class="font-weight-medium">
            {{ variant.simple_id || formatVariantId(variant.variant_id) }}
          </v-chip>
          <v-chip
            v-if="variant.classificationVerdict"
            :color="getPathogenicityColor(variant.classificationVerdict)"
            size="small"
            variant="flat"
          >
            <v-icon start size="small">
              {{ getPathogenicityIcon(variant.classificationVerdict) }}
            </v-icon>
            {{ formatClassification(variant.classificationVerdict) }}
          </v-chip>
          <v-chip
            v-if="getVariantType(variant)"
            color="purple-lighten-3"
            size="small"
            variant="flat"
          >
            {{ getVariantType(variant) }}
          </v-chip>
        </template>
        <v-skeleton-loader v-else type="chip" width="200" />
      </template>
    </PageHeader>

    <!-- Quick Stats Section (below PageHeader) -->
    <section class="stats-section py-4 px-4 mb-4">
      <v-container>
        <v-row justify="center">
          <v-col cols="12" xl="10">
            <!-- Quick Stats Row -->
            <v-row v-if="!loading">
              <!-- Individuals Count -->
              <v-col cols="6" sm="3">
                <v-card
                  class="py-3 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="purple" size="large" class="mb-1">mdi-account-multiple</v-icon>
                  <div class="text-h5 font-weight-bold text-purple mb-0">
                    {{ phenopacketsWithVariant.length }}
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Individuals
                  </div>
                </v-card>
              </v-col>

              <!-- Variant Size (for non-SNVs) -->
              <v-col v-if="getVariantSize(variant)" cols="6" sm="3">
                <v-card
                  class="py-3 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="blue" size="large" class="mb-1">mdi-ruler</v-icon>
                  <div class="text-h6 font-weight-bold text-blue mb-0">
                    {{ getVariantSize(variant) }}
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Size
                  </div>
                </v-card>
              </v-col>

              <!-- Gene -->
              <v-col cols="6" sm="3">
                <v-card
                  class="py-3 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="teal" size="large" class="mb-1">mdi-molecule</v-icon>
                  <div class="text-h6 font-weight-bold text-teal mb-0">
                    {{ variant.geneSymbol || 'HNF1B' }}
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Gene
                  </div>
                </v-card>
              </v-col>

              <!-- Molecular Consequence -->
              <v-col v-if="getMolecularConsequence(variant)" cols="6" sm="3">
                <v-card
                  class="py-3 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="amber-darken-2" size="large" class="mb-1">
                    mdi-lightning-bolt
                  </v-icon>
                  <div class="text-body-2 font-weight-bold text-amber-darken-2 mb-0">
                    {{ getMolecularConsequence(variant) }}
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Consequence
                  </div>
                </v-card>
              </v-col>
            </v-row>

            <!-- Loading skeleton for stats -->
            <v-row v-else>
              <v-col v-for="i in 4" :key="i" cols="6" sm="3">
                <v-skeleton-loader type="card" />
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- MAIN CONTENT -->
    <v-container class="pb-12">
      <v-row justify="center">
        <v-col cols="12" xl="10">
          <!-- VARIANT DETAILS CARD -->
          <v-card variant="outlined" class="border-opacity-12 mb-6" rounded="lg">
            <div class="d-flex align-center px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="pink-darken-2" class="mr-2">mdi-clipboard-text</v-icon>
              <span class="text-h6 font-weight-medium">Genomic Information</span>
              <v-spacer />
              <v-btn
                v-if="variant.hg38"
                icon="mdi-content-copy"
                size="small"
                variant="text"
                aria-label="Copy HG38 coordinates to clipboard"
                @click="copyToClipboard(variant.hg38, 'HG38 coordinates')"
              />
            </div>

            <v-card-text class="pa-4">
              <v-row>
                <!-- Left Column: Core Variant Info -->
                <v-col cols="12" md="6">
                  <v-list density="compact" class="bg-transparent">
                    <v-list-item v-if="variant.hg38">
                      <template #prepend>
                        <v-icon color="grey-darken-1" size="small">mdi-map-marker</v-icon>
                      </template>
                      <v-list-item-title class="text-caption text-medium-emphasis">
                        HG38 Coordinates
                      </v-list-item-title>
                      <v-list-item-subtitle class="text-body-2 font-weight-medium">
                        {{ variant.hg38 }}
                      </v-list-item-subtitle>
                    </v-list-item>

                    <!-- CNV-specific details -->
                    <template v-if="isCNV(variant) && getCNVDetails(variant)">
                      <v-list-item>
                        <template #prepend>
                          <v-icon color="grey-darken-1" size="small">mdi-chromosome</v-icon>
                        </template>
                        <v-list-item-title class="text-caption text-medium-emphasis">
                          Genomic Region
                        </v-list-item-title>
                        <v-list-item-subtitle class="text-body-2 font-weight-medium">
                          chr{{ getCNVDetails(variant).chromosome }}:{{
                            formatPosition(getCNVDetails(variant).start)
                          }}-{{ formatPosition(getCNVDetails(variant).end) }}
                        </v-list-item-subtitle>
                      </v-list-item>
                    </template>

                    <v-list-item v-if="variant.geneId">
                      <template #prepend>
                        <v-icon color="grey-darken-1" size="small">mdi-molecule</v-icon>
                      </template>
                      <v-list-item-title class="text-caption text-medium-emphasis">
                        Gene
                      </v-list-item-title>
                      <v-list-item-subtitle class="text-body-2 font-weight-medium">
                        <a
                          :href="`https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${variant.geneId}`"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-primary text-decoration-none"
                          :aria-label="`View ${variant.geneSymbol} on HGNC (opens in new tab)`"
                        >
                          {{ variant.geneSymbol }}
                          <v-icon size="x-small" class="ml-1" aria-hidden="true"
                            >mdi-open-in-new</v-icon
                          >
                        </a>
                        <span class="text-caption text-grey ml-1">({{ variant.geneId }})</span>
                      </v-list-item-subtitle>
                    </v-list-item>

                    <v-list-item v-if="variant.transcript">
                      <template #prepend>
                        <v-icon color="grey-darken-1" size="small">mdi-text-box</v-icon>
                      </template>
                      <v-list-item-title class="text-caption text-medium-emphasis">
                        Transcript (HGVS c.)
                      </v-list-item-title>
                      <v-list-item-subtitle class="text-body-2 font-weight-medium">
                        <a
                          v-if="extractTranscriptId(variant.transcript)"
                          :href="`https://www.ncbi.nlm.nih.gov/nuccore/${extractTranscriptId(variant.transcript)}`"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-primary text-decoration-none"
                          :aria-label="`View transcript ${extractTranscriptId(variant.transcript)} on NCBI (opens in new tab)`"
                        >
                          {{ extractTranscriptId(variant.transcript) }}
                          <v-icon size="x-small" class="ml-1" aria-hidden="true"
                            >mdi-open-in-new</v-icon
                          >
                        </a>
                        <span class="ml-1">{{ extractCNotation(variant.transcript) }}</span>
                      </v-list-item-subtitle>
                    </v-list-item>

                    <v-list-item v-if="variant.protein">
                      <template #prepend>
                        <v-icon color="grey-darken-1" size="small">mdi-protein</v-icon>
                      </template>
                      <v-list-item-title class="text-caption text-medium-emphasis">
                        Protein (HGVS p.)
                      </v-list-item-title>
                      <v-list-item-subtitle class="text-body-2 font-weight-medium">
                        <a
                          v-if="extractProteinId(variant.protein)"
                          :href="`https://www.ncbi.nlm.nih.gov/protein/${extractProteinId(variant.protein)}`"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-primary text-decoration-none"
                          :aria-label="`View protein ${extractProteinId(variant.protein)} on NCBI (opens in new tab)`"
                        >
                          {{ extractProteinId(variant.protein) }}
                          <v-icon size="x-small" class="ml-1" aria-hidden="true"
                            >mdi-open-in-new</v-icon
                          >
                        </a>
                        <span class="ml-1">{{ extractPNotation(variant.protein) }}</span>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>

                <!-- Right Column: External Resources -->
                <v-col cols="12" md="6">
                  <div
                    class="text-caption text-medium-emphasis mb-2 text-uppercase font-weight-bold"
                  >
                    External Resources
                  </div>
                  <div class="d-flex flex-wrap gap-2">
                    <!-- Variant databases -->
                    <v-chip
                      v-if="getClinVarLink(variant)"
                      :href="getClinVarLink(variant)"
                      target="_blank"
                      color="blue-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View on ClinVar (opens in new tab)"
                    >
                      ClinVar
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="getDbSNPLink(variant)"
                      :href="getDbSNPLink(variant)"
                      target="_blank"
                      color="blue-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View on dbSNP (opens in new tab)"
                    >
                      dbSNP
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="getClinGenLink(variant)"
                      :href="getClinGenLink(variant)"
                      target="_blank"
                      color="blue-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View on ClinGen (opens in new tab)"
                    >
                      ClinGen
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="getDecipherLink(variant)"
                      :href="getDecipherLink(variant)"
                      target="_blank"
                      color="green-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View on DECIPHER (opens in new tab)"
                    >
                      DECIPHER
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="getUCSCLink(variant)"
                      :href="getUCSCLink(variant)"
                      target="_blank"
                      color="green-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View on UCSC Genome Browser (opens in new tab)"
                    >
                      UCSC Browser
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>

                    <!-- Gene databases -->
                    <v-chip
                      v-if="variant.geneSymbol"
                      :href="`https://www.ncbi.nlm.nih.gov/gene/?term=${variant.geneSymbol}`"
                      target="_blank"
                      color="teal-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View gene on NCBI (opens in new tab)"
                    >
                      NCBI Gene
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="variant.geneSymbol"
                      :href="`https://www.omim.org/search?search=${variant.geneSymbol}`"
                      target="_blank"
                      color="teal-lighten-4"
                      size="small"
                      variant="flat"
                      link
                      aria-label="View gene on OMIM (opens in new tab)"
                    >
                      OMIM
                      <v-icon end size="x-small" aria-hidden="true">mdi-open-in-new</v-icon>
                    </v-chip>

                    <span v-if="!hasExternalLinks(variant)" class="text-grey text-body-2">
                      No external links available
                    </span>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- VISUALIZATIONS SECTION -->
          <v-card variant="outlined" class="border-opacity-12 mb-6" rounded="lg">
            <div class="d-flex align-center px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="primary" class="mr-2">mdi-chart-timeline-variant</v-icon>
              <span class="text-h6 font-weight-medium">Visualizations</span>
            </div>

            <v-tabs
              v-model="visualizationTab"
              bg-color="transparent"
              color="primary"
              align-tabs="start"
              class="px-2 pt-2"
              @update:model-value="handleTabChange"
            >
              <!-- Gene View tab (always shown) -->
              <v-tab value="gene" class="text-capitalize rounded-t-lg">
                <v-icon start>mdi-dna</v-icon>
                <span v-if="isCNV(variant)">Gene View (HNF1B)</span>
                <span v-else>Gene View</span>
              </v-tab>

              <!-- Protein View tab (only for SNVs/indels) -->
              <v-tab v-if="!isCNV(variant)" value="protein" class="text-capitalize rounded-t-lg">
                <v-icon start>mdi-protein</v-icon>
                Protein View
              </v-tab>

              <!-- 3D Structure tab (only for SNVs/indels) -->
              <v-tab
                v-if="!isCNV(variant)"
                value="structure3d"
                class="text-capitalize rounded-t-lg"
              >
                <v-icon start>mdi-cube-outline</v-icon>
                3D Structure
              </v-tab>

              <!-- Region View tab (only for CNVs) -->
              <v-tab v-if="isCNV(variant)" value="region" class="text-capitalize rounded-t-lg">
                <v-icon start>mdi-map-marker-radius</v-icon>
                17q12 Region (15 genes)
              </v-tab>
            </v-tabs>

            <v-divider />

            <v-window v-model="visualizationTab" class="pa-4 bg-white" style="min-height: 450px">
              <!-- Gene View -->
              <v-window-item value="gene">
                <HNF1BGeneVisualization
                  v-if="allVariants.length > 0"
                  :variants="allVariants"
                  :current-variant-id="$route.params.variant_id"
                  :force-view-mode="isCNV(variant) ? 'gene' : null"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                  <span class="mt-4 text-grey">Loading Gene Visualization...</span>
                </div>
              </v-window-item>

              <!-- Protein View -->
              <v-window-item value="protein">
                <HNF1BProteinVisualization
                  v-if="allVariants.length > 0"
                  :variants="allVariants"
                  :current-variant-id="$route.params.variant_id"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                </div>
              </v-window-item>

              <!-- 3D Structure View -->
              <v-window-item value="structure3d">
                <ProteinStructure3D
                  v-if="allVariants.length > 0"
                  :variants="allVariants"
                  :current-variant-id="$route.params.variant_id"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                </div>
              </v-window-item>

              <!-- Region View (CNVs only) -->
              <v-window-item value="region">
                <HNF1BGeneVisualization
                  v-if="allVariants.length > 0"
                  :variants="allVariants"
                  :current-variant-id="$route.params.variant_id"
                  :force-view-mode="'cnv'"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                </div>
              </v-window-item>
            </v-window>
          </v-card>

          <!-- AFFECTED INDIVIDUALS TABLE -->
          <v-card
            v-if="phenopacketsWithVariant.length > 0"
            variant="outlined"
            class="border-opacity-12"
            rounded="lg"
          >
            <div class="d-flex align-center px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="purple-darken-2" class="mr-2">mdi-account-multiple</v-icon>
              <span class="text-h6 font-weight-medium">
                Affected Individuals ({{ phenopacketsWithVariant.length }})
              </span>
            </div>

            <v-data-table
              :headers="headers"
              :items="phenopacketsWithVariant"
              density="comfortable"
              :items-per-page="10"
              class="elevation-0"
            >
              <!-- Subject ID as clickable chip with icon -->
              <template #item.subject_id="{ item }">
                <v-chip
                  :to="`/phenopackets/${item.phenopacket_id}`"
                  color="teal-lighten-3"
                  size="small"
                  variant="flat"
                  link
                >
                  <v-icon start size="small">mdi-card-account-details</v-icon>
                  {{ item.subject_id }}
                </v-chip>
              </template>

              <!-- Sex with icon as chip -->
              <template #item.subject_sex="{ item }">
                <v-chip :color="getSexChipColor(item.subject_sex)" size="small" variant="flat">
                  <v-icon start size="small">
                    {{ getSexIcon(item.subject_sex) }}
                  </v-icon>
                  {{ formatSex(item.subject_sex) }}
                </v-chip>
              </template>
            </v-data-table>
          </v-card>
        </v-col>
      </v-row>
    </v-container>

    <!-- Snackbar for copy notification -->
    <v-snackbar v-model="snackbar" :timeout="2000" color="success">
      {{ snackbarMessage }}
    </v-snackbar>
  </div>
</template>

<script>
import { ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { getVariants, getPhenopacketsByVariant } from '@/api';
import HNF1BGeneVisualization from '@/components/gene/HNF1BGeneVisualization.vue';
import HNF1BProteinVisualization from '@/components/gene/HNF1BProteinVisualization.vue';
import ProteinStructure3D from '@/components/gene/ProteinStructure3D.vue';
import PageHeader from '@/components/common/PageHeader.vue';
import {
  extractCNotation,
  extractPNotation,
  extractTranscriptId,
  extractProteinId,
} from '@/utils/hgvs';
import { getPathogenicityColor } from '@/utils/colors';
import { getVariantType, isCNV, getCNVDetails, getVariantSize } from '@/utils/variants';
import { getSexIcon, getSexChipColor, formatSex } from '@/utils/sex';
import {
  useVariantSeo,
  useVariantStructuredData,
  useBreadcrumbStructuredData,
} from '@/composables/useSeoMeta';

export default {
  name: 'PageVariant',
  components: {
    HNF1BGeneVisualization,
    HNF1BProteinVisualization,
    ProteinStructure3D,
    PageHeader,
  },
  setup() {
    const route = useRoute();

    // Reactive variant data for SEO
    const variantForSeo = ref(null);

    // Breadcrumbs for structured data
    const seoBreadcrumbs = computed(() => [
      { name: 'Home', url: '/' },
      { name: 'Variants', url: '/variants' },
      {
        name: variantForSeo.value?.simple_id || variantForSeo.value?.hgvs_c || 'Variant',
        url: `/variants/${encodeURIComponent(route.params.variant_id || '')}`,
      },
    ]);

    // Apply SEO meta tags - these update reactively when variantForSeo changes
    useVariantSeo(variantForSeo);
    useVariantStructuredData(variantForSeo);
    useBreadcrumbStructuredData(seoBreadcrumbs);

    // Expose the setter for the Options API part
    const updateSeoVariant = (variant) => {
      if (variant && variant.variant_id) {
        // Map variant data to SEO-friendly format
        variantForSeo.value = {
          variant_id: variant.variant_id,
          simple_id: variant.simple_id,
          hgvs_c: extractCNotation(variant.transcript),
          hgvs_p: extractPNotation(variant.protein),
          type: variant.variant_type,
          classification: variant.classificationVerdict?.toLowerCase(),
          consequence: variant.molecular_consequence,
          individual_count: 0, // Will be updated after phenopackets load
          cadd_score: variant.cadd_score,
          gnomad_af: variant.gnomad_af,
          rsid: variant.rsid,
        };
      }
    };

    const updateSeoIndividualCount = (count) => {
      if (variantForSeo.value) {
        variantForSeo.value = {
          ...variantForSeo.value,
          individual_count: count,
        };
      }
    };

    return {
      updateSeoVariant,
      updateSeoIndividualCount,
    };
  },
  data() {
    return {
      variant: {},
      phenopacketsWithVariant: [],
      allVariants: [],
      loading: true,
      snackbar: false,
      snackbarMessage: '',
      visualizationTab: 'gene',
      headers: [
        {
          title: 'Subject ID',
          value: 'subject_id',
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
  computed: {
    breadcrumbs() {
      return [
        { title: 'Home', to: '/' },
        { title: 'Variants', to: '/variants' },
        {
          title:
            this.variant.simple_id || this.formatVariantId(this.variant.variant_id) || 'Loading...',
          disabled: true,
        },
      ];
    },
  },
  watch: {
    '$route.params.variant_id': {
      handler() {
        this.loadVariantData();
      },
      immediate: false,
    },
  },
  created() {
    this.loadVariantData();
    this.loadAllVariants();
  },
  methods: {
    handleTabChange() {
      this.$nextTick(() => {
        window.dispatchEvent(new Event('resize'));
      });
    },
    formatVariantId(id) {
      if (!id) return '';
      // Shorten GA4GH IDs for display
      if (id.startsWith('ga4gh:VA.')) {
        return id.substring(0, 20) + '...';
      }
      return id;
    },
    formatClassification(classification) {
      if (!classification) return '';
      return classification
        .replace(/_/g, ' ')
        .toLowerCase()
        .replace(/\b\w/g, (c) => c.toUpperCase());
    },
    getPathogenicityIcon(classification) {
      const icons = {
        PATHOGENIC: 'mdi-alert-circle',
        LIKELY_PATHOGENIC: 'mdi-alert',
        UNCERTAIN_SIGNIFICANCE: 'mdi-help-circle',
        LIKELY_BENIGN: 'mdi-check-circle',
        BENIGN: 'mdi-check-circle',
      };
      return icons[classification] || 'mdi-help-circle';
    },
    async loadAllVariants() {
      try {
        const response = await getVariants({
          page: 1,
          pageSize: 500,
        });
        this.allVariants = response.data || [];
      } catch (error) {
        window.logService.error('Failed to load variants for visualization', {
          error: error.message,
          status: error.response?.status,
        });
        this.allVariants = [];
      }
    },
    navigateToVariant(variant) {
      if (variant && variant.variant_id) {
        window.logService.info('Navigating to variant from visualization', {
          fromVariantId: this.$route.params.variant_id,
          toVariantId: variant.variant_id,
          source: 'gene visualization',
        });
        this.$router.push(`/variants/${encodeURIComponent(variant.variant_id)}`);
      }
    },
    getVariantType(variant) {
      return getVariantType(variant, { specificCNVType: true });
    },
    isCNV,
    getCNVDetails,
    getVariantSize(variant) {
      return getVariantSize(variant, { formatted: true });
    },
    formatPosition(pos) {
      return parseInt(pos).toLocaleString();
    },
    async loadVariantData() {
      this.loading = true;
      const variantId = decodeURIComponent(this.$route.params.variant_id);

      window.logService.debug('Loading variant detail page', {
        variantId: variantId,
        route: this.$route.path,
      });

      try {
        const variantResponse = await getVariants({
          page: 1,
          pageSize: 500,
        });

        if (!variantResponse.data || variantResponse.data.length === 0) {
          this.$router.replace({ name: 'NotFound' });
          return;
        }

        this.variant = variantResponse.data.find((v) => v.variant_id === variantId);

        if (!this.variant) {
          window.logService.warn('Variant not found', {
            variantId: variantId,
            availableVariants: variantResponse.data.length,
          });
          this.$router.replace({ name: 'NotFound' });
          return;
        }

        const phenopacketsResponse = await getPhenopacketsByVariant(variantId);
        this.phenopacketsWithVariant = phenopacketsResponse.data.map((pp) => ({
          phenopacket_id: pp.phenopacket_id,
          subject_id: pp.phenopacket?.subject?.id || 'N/A',
          subject_sex: pp.phenopacket?.subject?.sex || 'UNKNOWN_SEX',
          created_at: new Date(pp.created_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
          }),
        }));

        // Update SEO meta tags with variant data for mutation discoverability
        this.updateSeoVariant(this.variant);
        this.updateSeoIndividualCount(this.phenopacketsWithVariant.length);

        window.logService.info('Variant detail loaded successfully', {
          variantId: this.variant.variant_id,
          variantType: this.getVariantType(this.variant),
          phenopacketCount: this.phenopacketsWithVariant.length,
        });

        this.loading = false;
      } catch (error) {
        window.logService.error('Failed to load variant detail data', {
          error: error.message,
          variantId: this.$route.params.variant_id,
          status: error.response?.status,
        });
        this.loading = false;
      }
    },
    extractCNotation,
    extractPNotation,
    extractTranscriptId,
    extractProteinId,
    getPathogenicityColor,
    getMolecularConsequence(variant) {
      if (!variant) return null;

      if (variant.molecular_consequence) {
        return variant.molecular_consequence;
      }

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

          if (sign === '+' && position >= 1 && position <= 6) return 'Splice Donor';
          if (sign === '-' && position >= 1 && position <= 3) return 'Splice Acceptor';
          return 'Intronic Variant';
        }

        return 'Coding Sequence Variant';
      }

      if (variant.variant_type === 'deletion') return 'Copy Number Loss';
      if (variant.variant_type === 'duplication') return 'Copy Number Gain';

      return null;
    },
    hasExternalLinks(variant) {
      return (
        this.getClinVarLink(variant) ||
        this.getDbSNPLink(variant) ||
        this.getClinGenLink(variant) ||
        this.getDecipherLink(variant) ||
        this.getUCSCLink(variant) ||
        variant.geneSymbol
      );
    },
    copyToClipboard(text, label) {
      window.logService.debug('Clipboard copy initiated', {
        label: label,
        textLength: text?.length || 0,
      });

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard
          .writeText(text)
          .then(() => {
            window.logService.debug('Clipboard copy succeeded', { label: label });
            this.snackbarMessage = `${label} copied to clipboard!`;
            this.snackbar = true;
          })
          .catch((err) => {
            window.logService.warn('Clipboard copy failed', {
              error: err.message,
              label: label,
            });
            this.snackbarMessage = 'Failed to copy to clipboard';
            this.snackbar = true;
          });
      } else {
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
          window.logService.warn('Fallback clipboard copy failed', {
            error: err.message,
            label: label,
          });
          this.snackbarMessage = 'Failed to copy to clipboard';
          this.snackbar = true;
        }
        document.body.removeChild(textarea);
      }
    },
    getClinVarLink(variant) {
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

      if (
        (variant.variant_type === 'deletion' || variant.variant_type === 'duplication') &&
        variant.geneSymbol
      ) {
        return `https://search.clinicalgenome.org/kb/genes/${variant.geneSymbol}`;
      }

      return null;
    },
    getDecipherLink(variant) {
      if (
        !variant ||
        (variant.variant_type !== 'deletion' && variant.variant_type !== 'duplication') ||
        !variant.hg38
      ) {
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
      if (
        !variant ||
        (variant.variant_type !== 'deletion' && variant.variant_type !== 'duplication') ||
        !variant.hg38
      ) {
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
    getSexIcon,
    getSexChipColor,
    formatSex,
  },
};
</script>

<style scoped>
.variant-container {
  min-height: 100vh;
  background-color: #fafafa;
}

/* Override PageHeader hero background for pink variant page */
.variant-container :deep(.page-header--hero) {
  background: linear-gradient(135deg, #fce4ec 0%, #f8bbd9 50%, #f5f7fa 100%);
}

.stats-section {
  background: linear-gradient(180deg, #f8bbd9 0%, #f5f7fa 50%);
}

.border-bottom {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.border-opacity-12 {
  border-color: rgba(0, 0, 0, 0.12) !important;
}

.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}
</style>
