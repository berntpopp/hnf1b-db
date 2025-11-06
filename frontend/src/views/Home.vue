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
import { ref, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import SearchCard from '@/components/SearchCard.vue';
import HNF1BGeneVisualization from '@/components/gene/HNF1BGeneVisualization.vue';
import HNF1BProteinVisualization from '@/components/gene/HNF1BProteinVisualization.vue';
import { getSummaryStats, getVariants } from '@/api/index.js';
import { API_CONFIG } from '@/config/app';

/**
 * Home view component.
 *
 * This component fetches summary statistics and includes the search functionality.
 * It initializes stat values to 0 and animates them when the actual data is received.
 *
 * @component
 */
export default {
  name: 'Home',
  components: {
    SearchCard,
    HNF1BGeneVisualization,
    HNF1BProteinVisualization,
  },
  setup() {
    const router = useRouter();

    // Holds the stats to be displayed, with default values of 0.
    const displayStats = ref({
      individuals: 0,
      variants: 0,
      total_reports: 0,
      publications: 0,
    });

    // Holds all variants for the gene visualization
    const allVariants = ref([]);

    // Separate variants by type for different visualization cards
    const snvVariants = ref([]);
    const cnvVariants = ref([]);

    // Track which variant types have been loaded (for lazy loading)
    const snvVariantsLoaded = ref(false);
    const cnvVariantsLoaded = ref(false);

    // Active tab state (default to protein view)
    const activeTab = ref('protein');

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
        animateCount('individuals', data.total_phenopackets || 0);
        animateCount('variants', data.distinct_variants || 0);
        animateCount('total_reports', data.distinct_hpo_terms || 0);
        animateCount('publications', data.distinct_publications || 0);
      } catch (error) {
        console.error('Error fetching summary stats:', error);
      }
    };

    /**
     * Check if a variant is a CNV that extends beyond HNF1B gene boundaries.
     * Only large structural variants that span beyond HNF1B should be in CNV track.
     *
     * @param {Object} variant - Variant object with hg38 field
     * @returns {boolean} True if variant is a large CNV extending beyond HNF1B
     */
    const isCNV = (variant) => {
      if (!variant || !variant.hg38) return false;

      // HNF1B gene boundaries (GRCh38)
      const HNF1B_START = 37686430;
      const HNF1B_END = 37745059;

      // Check for range notation: 17:start-end:DEL/DUP
      const match = variant.hg38.match(/:(\d+)-(\d+):/);
      if (match) {
        const start = parseInt(match[1]);
        const end = parseInt(match[2]);
        const size = end - start;

        // Only consider it a "CNV track variant" if:
        // 1. Size >= 50bp (structural variant)
        // 2. Extends beyond HNF1B gene boundaries
        const extendsBeyondHNF1B = start < HNF1B_START || end > HNF1B_END;
        return size >= 50 && extendsBeyondHNF1B;
      }
      return false;
    };

    /**
     * Fetch SNV variants for protein and gene visualizations.
     * Only fetches if not already loaded (lazy loading).
     *
     * @async
     * @function fetchSNVVariants
     * @returns {Promise<void>}
     */
    const fetchSNVVariants = async () => {
      if (snvVariantsLoaded.value) return; // Already loaded

      try {
        // Fetch all variants to filter SNVs
        // ⚠️ WARNING: Assumes total variants < MAX_VARIANTS_FOR_PRIORITY_SORT
        // See @/config/app.js for details
        const response = await getVariants({
          page: 1,
          page_size: API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT,
        });
        allVariants.value = response.data || [];

        // Filter SNVs: Point mutations, splice variants, and small variants (not large CNVs)
        snvVariants.value = allVariants.value.filter((v) => !isCNV(v));
        snvVariantsLoaded.value = true;
      } catch (error) {
        console.error('Error fetching SNV variants:', error);
      }
    };

    /**
     * Fetch CNV variants for 17q12 region visualization.
     * Only fetches if not already loaded (lazy loading).
     *
     * @async
     * @function fetchCNVVariants
     * @returns {Promise<void>}
     */
    const fetchCNVVariants = async () => {
      if (cnvVariantsLoaded.value) return; // Already loaded

      try {
        // Use cached allVariants if available, otherwise fetch
        // ⚠️ WARNING: Assumes total variants < MAX_VARIANTS_FOR_PRIORITY_SORT
        // See @/config/app.js for details
        if (allVariants.value.length === 0) {
          const response = await getVariants({
            page: 1,
            page_size: API_CONFIG.MAX_VARIANTS_FOR_PRIORITY_SORT,
          });
          allVariants.value = response.data || [];
        }

        // Filter CNVs: Large structural variants >= 50bp that extend beyond HNF1B
        cnvVariants.value = allVariants.value.filter((v) => isCNV(v));
        cnvVariantsLoaded.value = true;
      } catch (error) {
        console.error('Error fetching CNV variants:', error);
      }
    };

    /**
     * Handle tab change - lazy load variants when tab is clicked.
     * Triggers a resize event after DOM updates to ensure SVG visualizations render correctly.
     *
     * @param {string} tab - The active tab value ('protein', 'gene', or 'region')
     */
    const handleTabChange = (tab) => {
      if (tab === 'protein' || tab === 'gene') {
        fetchSNVVariants(); // Protein and gene views use SNVs
      } else if (tab === 'region') {
        fetchCNVVariants(); // Region view uses CNVs
      }

      // Trigger resize event after DOM updates to fix SVG width calculation
      nextTick(() => {
        window.dispatchEvent(new Event('resize'));
      });
    };

    /**
     * Navigate to a variant detail page when clicked in the visualization.
     *
     * @param {Object} variant - The variant object that was clicked
     */
    const navigateToVariant = (variant) => {
      // Use Vue Router for SPA navigation (no page reload)
      router.push(`/variants/${variant.variant_id}`);
    };

    onMounted(() => {
      // Load statistics immediately (lightweight)
      fetchStats();

      // Load protein view variants immediately (default tab)
      fetchSNVVariants();
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
