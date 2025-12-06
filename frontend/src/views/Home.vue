<!-- src/views/Home.vue -->
<template>
  <div class="home-container">
    <!-- HERO SECTION -->
    <section class="hero-section py-6 px-4 mb-4">
      <v-container>
        <v-row justify="center" align="center">
          <v-col cols="12" md="10" lg="8" class="text-center">
            <h1 class="text-h3 font-weight-bold text-teal-darken-2 mb-2">HNF1B-db</h1>
            <p
              class="text-subtitle-1 text-medium-emphasis mb-6"
              style="max-width: 800px; margin: 0 auto"
            >
              A curated database of HNF1B gene variants and associated phenotypes, integrating
              clinical reports and genomic data.
            </p>

            <!-- Search Bar Integrated in Hero -->
            <div class="d-flex justify-center mb-6">
              <SearchCard />
            </div>
          </v-col>
        </v-row>

        <!-- STATS GRID (Stable Layout) -->
        <v-row justify="center" class="mt-2">
          <v-col cols="12" md="10">
            <v-row>
              <!-- Individuals -->
              <v-col cols="6" md="3">
                <v-card
                  class="py-4 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="teal" size="large" class="mb-2">mdi-account-group</v-icon>
                  <div class="text-h4 font-weight-bold text-teal mb-0">
                    <span v-if="!loadingStats">{{ displayStats.individuals }}</span>
                    <v-skeleton-loader v-else type="text" width="60" class="mx-auto" />
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Individuals
                  </div>
                </v-card>
              </v-col>

              <!-- Variants -->
              <v-col cols="6" md="3">
                <v-card
                  class="py-4 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="pink" size="large" class="mb-2">mdi-dna</v-icon>
                  <div class="text-h4 font-weight-bold text-pink mb-0">
                    <span v-if="!loadingStats">{{ displayStats.variants }}</span>
                    <v-skeleton-loader v-else type="text" width="60" class="mx-auto" />
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Unique Variants
                  </div>
                </v-card>
              </v-col>

              <!-- Phenotypes -->
              <v-col cols="6" md="3">
                <v-card
                  class="py-4 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="amber-darken-2" size="large" class="mb-2">mdi-medical-bag</v-icon>
                  <div class="text-h4 font-weight-bold text-amber-darken-2 mb-0">
                    <span v-if="!loadingStats">{{ displayStats.total_reports }}</span>
                    <v-skeleton-loader v-else type="text" width="60" class="mx-auto" />
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Phenotypes
                  </div>
                </v-card>
              </v-col>

              <!-- Publications -->
              <v-col cols="6" md="3">
                <v-card
                  class="py-4 px-2 text-center h-100"
                  variant="elevated"
                  elevation="2"
                  rounded="lg"
                >
                  <v-icon color="cyan-darken-1" size="large" class="mb-2"
                    >mdi-file-document-multiple</v-icon
                  >
                  <div class="text-h4 font-weight-bold text-cyan-darken-1 mb-0">
                    <span v-if="!loadingStats">{{ displayStats.publications }}</span>
                    <v-skeleton-loader v-else type="text" width="60" class="mx-auto" />
                  </div>
                  <div class="text-caption text-uppercase font-weight-bold text-medium-emphasis">
                    Publications
                  </div>
                </v-card>
              </v-col>
            </v-row>
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- VISUALIZATIONS SECTION -->
    <v-container class="pb-12">
      <v-row justify="center">
        <v-col cols="12" xl="10">
          <v-card variant="outlined" class="border-opacity-12" rounded="lg">
            <div class="d-flex align-center px-4 py-2 bg-grey-lighten-4 border-bottom">
              <v-icon color="primary" class="mr-2">mdi-chart-timeline-variant</v-icon>
              <span class="text-h6 font-weight-medium">Variant Visualizations</span>
            </div>

            <v-tabs
              v-model="activeTab"
              bg-color="transparent"
              color="primary"
              align-tabs="start"
              class="px-2 pt-2"
              @update:model-value="handleTabChange"
            >
              <v-tab value="protein" class="text-capitalize rounded-t-lg">Protein View</v-tab>
              <v-tab value="gene" class="text-capitalize rounded-t-lg">Gene View</v-tab>
              <v-tab value="structure3d" class="text-capitalize rounded-t-lg">3D Structure</v-tab>
              <v-tab value="region" class="text-capitalize rounded-t-lg">17q12 Region</v-tab>
            </v-tabs>

            <v-divider />

            <v-window v-model="activeTab" class="pa-4 bg-white" style="min-height: 500px">
              <!-- Protein View Tab (Default) -->
              <v-window-item value="protein">
                <HNF1BProteinVisualization
                  v-if="snvVariantsLoaded"
                  :variants="snvVariants"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                  <span class="mt-4 text-grey">Loading Protein Visualization...</span>
                </div>
              </v-window-item>

              <!-- Gene View Tab -->
              <v-window-item value="gene">
                <HNF1BGeneVisualization
                  v-if="snvVariantsLoaded"
                  :variants="snvVariants"
                  force-view-mode="gene"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                </div>
              </v-window-item>

              <!-- 3D Structure View Tab -->
              <v-window-item value="structure3d">
                <ProteinStructure3D
                  v-if="snvVariantsLoaded"
                  :variants="snvVariants"
                  :show-all-variants="true"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                </div>
              </v-window-item>

              <!-- CNV Region View Tab -->
              <v-window-item value="region">
                <HNF1BGeneVisualization
                  v-if="cnvVariantsLoaded"
                  :variants="cnvVariants"
                  force-view-mode="cnv"
                  @variant-clicked="navigateToVariant"
                />
                <div v-else class="d-flex flex-column align-center justify-center pa-12">
                  <v-progress-circular indeterminate color="primary" size="64" />
                  <span class="mt-4 text-grey">Loading CNV Data...</span>
                </div>
              </v-window-item>
            </v-window>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick, defineAsyncComponent, h } from 'vue';
import { useRouter } from 'vue-router';
import SearchCard from '@/components/SearchCard.vue';
import { useVariantStore } from '@/stores/variantStore';
import { getSummaryStats } from '@/api/index.js';

/**
 * Loading placeholder component using render function (no runtime compiler needed).
 */
const LoadingPlaceholder = {
  render: () => h('div', { style: 'height: 400px' }),
};

/**
 * Lazy-loaded heavy visualization components.
 * Uses render functions instead of template strings to avoid runtime compilation.
 */
const HNF1BGeneVisualization = defineAsyncComponent({
  loader: () => import('@/components/gene/HNF1BGeneVisualization.vue'),
  loadingComponent: LoadingPlaceholder,
  delay: 200,
});

const HNF1BProteinVisualization = defineAsyncComponent({
  loader: () => import('@/components/gene/HNF1BProteinVisualization.vue'),
  loadingComponent: LoadingPlaceholder,
  delay: 200,
});

const ProteinStructure3D = defineAsyncComponent({
  loader: () => import('@/components/gene/ProteinStructure3D.vue'),
  loadingComponent: LoadingPlaceholder,
  delay: 200,
});

export default {
  name: 'Home',
  components: {
    SearchCard,
    HNF1BGeneVisualization,
    HNF1BProteinVisualization,
    ProteinStructure3D,
  },
  setup() {
    const router = useRouter();
    const variantStore = useVariantStore();

    // Stats
    const displayStats = ref({
      individuals: 0,
      variants: 0,
      total_reports: 0,
      publications: 0,
    });
    const loadingStats = ref(true);

    // Active tab
    const activeTab = ref('protein');

    // ==================== COMPUTED FROM STORE ====================

    const snvVariants = computed(() => variantStore.snvVariants);
    const cnvVariants = computed(() => variantStore.cnvVariants);
    const snvVariantsLoaded = computed(() => variantStore.hasPathogenic);
    const cnvVariantsLoaded = computed(() => variantStore.cnvVariants.length > 0);

    // ==================== STATS ANIMATION ====================

    function animateCount(prop, targetValue, duration = 1500) {
      const startTime = performance.now();
      const startValue = 0;

      const animate = () => {
        const now = performance.now();
        const progress = Math.min((now - startTime) / duration, 1);

        // Easing function (easeOutExpo)
        const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);

        displayStats.value[prop] = Math.floor(startValue + (targetValue - startValue) * ease);

        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          displayStats.value[prop] = targetValue;
        }
      };
      requestAnimationFrame(animate);
    }

    const fetchStats = async () => {
      loadingStats.value = true;
      try {
        const response = await getSummaryStats();
        const data = response.data || {};

        window.logService.info('Summary statistics loaded', data);

        // Start animation
        loadingStats.value = false;
        animateCount('individuals', data.total_phenopackets || 0);
        animateCount('variants', data.distinct_variants || 0);
        animateCount('total_reports', data.distinct_hpo_terms || 0);
        animateCount('publications', data.distinct_publications || 0);
      } catch (error) {
        window.logService.error('Failed to fetch summary statistics', {
          error: error.message,
        });
        loadingStats.value = false; // Show 0s or errors
      }
    };

    // ==================== TAB HANDLING ====================

    const handleTabChange = (tab) => {
      // Trigger resize event after DOM updates to fix SVG width calculation
      nextTick(() => {
        window.dispatchEvent(new Event('resize'));
      });
      // Track event
      window.logService.debug('Visualization tab changed', { toTab: tab });
    };

    // ==================== NAVIGATION ====================

    const navigateToVariant = (variant) => {
      router.push(`/variants/${variant.variant_id}`);
    };

    // ==================== LIFECYCLE ====================

    onMounted(async () => {
      fetchStats();
      await variantStore.fetchProgressively();
    });

    return {
      displayStats,
      loadingStats,
      snvVariants,
      cnvVariants,
      snvVariantsLoaded,
      cnvVariantsLoaded,
      activeTab,
      handleTabChange,
      navigateToVariant,
    };
  },
};
</script>

<style scoped>
.hero-section {
  background: linear-gradient(135deg, #f5f7fa 0%, #e0f2f1 100%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.border-bottom {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.border-opacity-12 {
  border-color: rgba(0, 0, 0, 0.12) !important;
}
</style>
