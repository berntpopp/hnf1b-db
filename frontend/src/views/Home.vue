<!-- src/views/Home.vue -->
<template>
  <v-container fill-height>
    <v-row
      align="center"
      justify="center"
    >
      <v-col
        cols="12"
        md="8"
      >
        <v-card
          class="pa-4"
          variant="flat"
        >
          <!-- Title -->
          <v-card-title class="text-h3 text-center">
            Welcome to HNF1B-db
          </v-card-title>

          <!-- Subtitle -->
          <v-card-subtitle class="text-center">
            This is a curated database of HNF1B gene variants and associated phenotypes. It
            currently contains:
          </v-card-subtitle>

          <v-card-text class="text-center">
            <!-- Stats row: defaults start at 0 and then animate upward -->
            <p>
              <v-chip
                color="light-green-lighten-3"
                class="ma-1"
                variant="flat"
              >
                {{ displayStats.individuals }} individuals
                <v-icon right>
                  mdi-account
                </v-icon>
              </v-chip>
              with
              <v-chip
                color="pink-lighten-3"
                class="ma-1"
                variant="flat"
              >
                {{ displayStats.variants }} distinct variants
                <v-icon right>
                  mdi-dna
                </v-icon>
              </v-chip>
              from
              <v-chip
                color="amber-lighten-3"
                class="ma-1"
                variant="flat"
              >
                {{ displayStats.total_reports }} reports
                <v-icon right>
                  mdi-file-document-outline
                </v-icon>
              </v-chip>
              in
              <v-chip
                color="cyan-lighten-3"
                class="ma-1"
                variant="flat"
              >
                {{ displayStats.publications }} publications
                <v-icon right>
                  mdi-book-open-blank-variant
                </v-icon>
              </v-chip>
            </p>

            <!-- Centered Search card below the stats -->
            <div class="searchcard-flex">
              <SearchCard />
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { ref, onMounted } from 'vue';
import SearchCard from '@/components/SearchCard.vue';
import { getSummary } from '@/api/index.js';

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
  },
  setup() {
    // Holds the stats to be displayed, with default values of 0.
    const displayStats = ref({
      individuals: 0,
      variants: 0,
      total_reports: 0,
      publications: 0,
    });

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
        // Fetch summary stats from /api/aggregations/summary
        const response = await getSummary();
        const data = response.data || {};
        // Animate each statistic from 0 to its target value.
        animateCount('individuals', data.individuals || 0);
        animateCount('variants', data.variants || 0);
        animateCount('total_reports', data.total_reports || 0);
        animateCount('publications', data.publications || 0);
      } catch (error) {
        console.error('Error fetching summary stats:', error);
      }
    };

    onMounted(fetchStats);

    return { displayStats };
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
