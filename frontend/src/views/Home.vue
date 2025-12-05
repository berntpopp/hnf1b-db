<!-- src/views/Home.vue -->
<template>
  <v-container fill-height>
    <v-row align="center" justify="center">
      <v-col cols="12" md="11" lg="10" xl="10">
        <v-card class="pa-4" variant="flat">
          <!-- Title -->
          <v-card-title class="text-h3 text-center"> Welcome to HNF1B-db </v-card-title>

          <!-- Subtitle -->
          <v-card-subtitle class="text-center">
            This is a curated database of HNF1B gene variants and associated phenotypes. It
            currently contains:
          </v-card-subtitle>

          <v-card-text class="text-center">
            <!-- Stats row: defaults start at 0 and then animate upward -->
            <p>
              <v-chip color="light-green-lighten-3" class="ma-1" variant="flat">
                {{ displayStats.individuals }} individuals
                <v-icon right> mdi-account </v-icon>
              </v-chip>
              with
              <v-chip color="pink-lighten-3" class="ma-1" variant="flat">
                {{ displayStats.variants }} genetic variants
                <v-icon right> mdi-dna </v-icon>
              </v-chip>
              with
              <v-chip color="amber-lighten-3" class="ma-1" variant="flat">
                {{ displayStats.total_reports }} phenotypes
                <v-icon right> mdi-medical-bag </v-icon>
              </v-chip>
              from
              <v-chip color="cyan-lighten-3" class="ma-1" variant="flat">
                {{ displayStats.publications }} publications
                <v-icon right> mdi-book-open-blank-variant </v-icon>
              </v-chip>
            </p>

            <!-- Centered Search card below the stats -->
            <div class="searchcard-flex">
              <SearchCard />
            </div>
          </v-card-text>
        </v-card>

        <!-- Variant Visualizations with Tabs -->
        <v-card class="mt-4" variant="flat">
          <v-card-title class="text-h5"> HNF1B Variant Visualizations </v-card-title>
          <v-tabs
            v-model="activeTab"
            bg-color="transparent"
            color="primary"
            @update:model-value="handleTabChange"
          >
            <v-tab value="protein">
              <v-icon start> mdi-protein </v-icon>
              Protein View
            </v-tab>
            <v-tab value="gene">
              <v-icon start> mdi-dna </v-icon>
              Gene View
            </v-tab>
            <v-tab value="structure3d">
              <v-icon start> mdi-cube-outline </v-icon>
              3D Structure
            </v-tab>
            <v-tab value="region">
              <v-icon start> mdi-map-marker-radius </v-icon>
              17q12 Region
            </v-tab>
          </v-tabs>

          <v-window v-model="activeTab">
            <!-- Protein View Tab (Default) -->
            <v-window-item value="protein">
              <v-card-text>
                <HNF1BProteinVisualization
                  v-if="snvVariantsLoaded"
                  :variants="snvVariants"
                  @variant-clicked="navigateToVariant"
                />
                <v-skeleton-loader v-else type="image" height="400" />
              </v-card-text>
            </v-window-item>

            <!-- Gene View Tab -->
            <v-window-item value="gene">
              <v-card-text>
                <HNF1BGeneVisualization
                  v-if="snvVariantsLoaded"
                  :variants="snvVariants"
                  force-view-mode="gene"
                  @variant-clicked="navigateToVariant"
                />
                <v-skeleton-loader v-else type="image" height="400" />
              </v-card-text>
            </v-window-item>

            <!-- 3D Structure View Tab -->
            <v-window-item value="structure3d">
              <v-card-text>
                <ProteinStructure3D
                  v-if="snvVariantsLoaded"
                  :variants="snvVariants"
                  :show-all-variants="true"
                  @variant-clicked="navigateToVariant"
                />
                <v-skeleton-loader v-else type="image" height="400" />
              </v-card-text>
            </v-window-item>

            <!-- CNV Region View Tab -->
            <v-window-item value="region">
              <v-card-text>
                <HNF1BGeneVisualization
                  v-if="cnvVariantsLoaded"
                  :variants="cnvVariants"
                  force-view-mode="cnv"
                  @variant-clicked="navigateToVariant"
                />
                <v-skeleton-loader v-else type="image" height="400" />
              </v-card-text>
            </v-window-item>
          </v-window>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { ref, computed, onMounted, nextTick, defineAsyncComponent } from 'vue';
import { useRouter } from 'vue-router';
import SearchCard from '@/components/SearchCard.vue';
import { useVariantStore } from '@/stores/variantStore';
import { getSummaryStats } from '@/api/index.js';

/**
 * Lazy-loaded heavy visualization components.
 * Uses defineAsyncComponent to defer loading D3/NGL bundles until needed.
 * This reduces initial bundle size and improves first paint time.
 */
const HNF1BGeneVisualization = defineAsyncComponent({
  loader: () => import('@/components/gene/HNF1BGeneVisualization.vue'),
  loadingComponent: {
    template: '<v-skeleton-loader type="image" height="400" />',
  },
  delay: 200,
});

const HNF1BProteinVisualization = defineAsyncComponent({
  loader: () => import('@/components/gene/HNF1BProteinVisualization.vue'),
  loadingComponent: {
    template: '<v-skeleton-loader type="image" height="400" />',
  },
  delay: 200,
});

const ProteinStructure3D = defineAsyncComponent({
  loader: () => import('@/components/gene/ProteinStructure3D.vue'),
  loadingComponent: {
    template: '<v-skeleton-loader type="image" height="400" />',
  },
  delay: 200,
});

/**
 * Home view component.
 *
 * This component fetches summary statistics and includes the search functionality.
 * Uses Pinia variantStore for progressive variant loading by clinical relevance:
 * 1. PATHOGENIC variants first (fast first paint)
 * 2. LIKELY_PATHOGENIC second
 * 3. VUS + BENIGN in parallel
 *
 * @component
 * @see stores/variantStore.js
 * @see plan/01-active/home-page-loading-optimization.md
 */
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

    // Holds the stats to be displayed, with default values of 0.
    const displayStats = ref({
      individuals: 0,
      variants: 0,
      total_reports: 0,
      publications: 0,
    });

    // Active tab state (default to protein view)
    const activeTab = ref('protein');

    // ==================== COMPUTED FROM STORE ====================

    /**
     * SNV variants from store (reactive).
     * Updates automatically as progressive loading brings in more data.
     */
    const snvVariants = computed(() => variantStore.snvVariants);

    /**
     * CNV variants from store (reactive).
     */
    const cnvVariants = computed(() => variantStore.cnvVariants);

    /**
     * Whether SNV data is ready for display.
     * Uses hasPathogenic for fast first paint - shows visualization
     * as soon as PATHOGENIC variants load, even before complete data.
     */
    const snvVariantsLoaded = computed(() => variantStore.hasPathogenic);

    /**
     * Whether CNV data is ready for display.
     * CNVs are extracted from all variants, so we need at least partial data.
     */
    const cnvVariantsLoaded = computed(() => variantStore.cnvVariants.length > 0);

    // ==================== STATS ANIMATION ====================

    /**
     * Animate a count from 0 to the target value.
     *
     * @param {string} prop The property name to animate.
     * @param {number} targetValue The final value to reach.
     * @param {number} duration Duration of the animation in ms.
     */
    function animateCount(prop, targetValue, duration = 500) {
      const startTime = performance.now();
      const animate = () => {
        const now = performance.now();
        const progress = Math.min((now - startTime) / duration, 1);
        displayStats.value[prop] = Math.floor(progress * targetValue);
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          displayStats.value[prop] = targetValue;
        }
      };
      requestAnimationFrame(animate);
    }

    /**
     * Fetch summary statistics from the backend API and animate each stat.
     *
     * @async
     * @function fetchStats
     * @returns {Promise<void>}
     */
    const fetchStats = async () => {
      try {
        // Fetch summary stats from /api/v2/phenopackets/aggregate/summary
        const response = await getSummaryStats();
        const data = response.data || {};
        // Animate each statistic from 0 to its target value.
        // Map API response fields to display fields:
        // - total_phenopackets -> individuals
        // - distinct_variants -> variants (UNIQUE variants, not total variant interpretations)
        // - distinct_hpo_terms -> total_reports (repurposed for HPO count)
        // - distinct_publications -> publications
        window.logService.info('Summary statistics loaded', {
          individuals: data.total_phenopackets || 0,
          variants: data.distinct_variants || 0,
          hpoTerms: data.distinct_hpo_terms || 0,
          publications: data.distinct_publications || 0,
        });

        animateCount('individuals', data.total_phenopackets || 0);
        animateCount('variants', data.distinct_variants || 0);
        animateCount('total_reports', data.distinct_hpo_terms || 0);
        animateCount('publications', data.distinct_publications || 0);
      } catch (error) {
        window.logService.error('Failed to fetch summary statistics', {
          error: error.message,
          status: error.response?.status,
        });
      }
    };

    // ==================== TAB HANDLING ====================

    /**
     * Handle tab change - triggers resize for SVG visualizations.
     * The variantStore handles progressive loading automatically.
     *
     * @param {string} tab - The active tab value ('protein', 'gene', 'structure3d', or 'region')
     */
    const handleTabChange = (tab) => {
      window.logService.debug('Visualization tab changed', {
        toTab: tab,
        loadingState: variantStore.loadingState,
        snvCount: snvVariants.value.length,
        cnvCount: cnvVariants.value.length,
      });

      // Trigger resize event after DOM updates to fix SVG width calculation
      nextTick(() => {
        window.dispatchEvent(new Event('resize'));
      });
    };

    // ==================== NAVIGATION ====================

    /**
     * Navigate to a variant detail page when clicked in the visualization.
     *
     * @param {Object} variant - The variant object that was clicked
     */
    const navigateToVariant = (variant) => {
      // Use Vue Router for SPA navigation (no page reload)
      router.push(`/variants/${variant.variant_id}`);
    };

    // ==================== LIFECYCLE ====================

    onMounted(async () => {
      // Load statistics immediately (lightweight, 164 bytes)
      fetchStats();

      // Start progressive variant loading
      // This loads PATHOGENIC first for fast first paint (~100ms),
      // then continues loading LIKELY_PATHOGENIC, VUS, and BENIGN
      await variantStore.fetchProgressively();
    });

    return {
      displayStats,
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
/* Center the search card using flexbox */
.searchcard-flex {
  display: flex;
  justify-content: center;
}
</style>
