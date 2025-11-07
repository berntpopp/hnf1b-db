<!-- src/views/Phenopackets.vue -->
<template>
  <v-container>
    <v-data-table-server
      v-model:options="options"
      :headers="headers"
      :items="phenopackets"
      :loading="loading"
      :items-length="totalItems"
      :custom-sort="customSort"
      hide-default-footer
      class="elevation-1 clickable-rows"
      density="compact"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <template #top>
        <v-toolbar flat>
          <v-toolbar-title>Phenopackets</v-toolbar-title>
          <v-spacer />
          <div class="d-flex align-center">
            <!-- Rows per page label and dropdown -->
            <span class="mr-2">Rows per page:</span>
            <v-select
              v-model="options.itemsPerPage"
              :items="itemsPerPageOptions"
              dense
              hide-details
              solo
              style="max-width: 120px"
            />
            <!-- Display the current items range -->
            <span class="mx-2">{{ rangeText }}</span>
            <!-- Pagination navigation buttons -->
            <v-btn icon :disabled="currentPage === 1" @click="goToFirstPage">
              <v-icon>mdi-page-first</v-icon>
            </v-btn>
            <v-btn icon :disabled="currentPage === 1" @click="goToPreviousPage">
              <v-icon>mdi-chevron-left</v-icon>
            </v-btn>
            <v-btn icon :disabled="currentPage >= totalPages" @click="goToNextPage">
              <v-icon>mdi-chevron-right</v-icon>
            </v-btn>
            <v-btn icon :disabled="currentPage >= totalPages" @click="goToLastPage">
              <v-icon>mdi-page-last</v-icon>
            </v-btn>
          </div>
        </v-toolbar>
      </template>

      <!-- Render Phenopacket ID as a chip -->
      <template #item.phenopacket_id="{ item }">
        <v-chip color="lime-lighten-2" class="ma-2" small variant="flat">
          {{ item.phenopacket_id }}
          <v-icon right> mdi-file-document </v-icon>
        </v-chip>
      </template>

      <!-- Render subject ID -->
      <template #item.subject_id="{ item }">
        <span>{{ item.subject_id || 'N/A' }}</span>
      </template>

      <!-- Render sex with icon -->
      <template #item.sex="{ item }">
        <v-icon small :color="getSexColor(item.sex)" class="mr-1">
          {{ getSexIcon(item.sex) }}
        </v-icon>
        {{ formatSex(item.sex) }}
      </template>

      <!-- Render primary disease -->
      <template #item.primary_disease="{ item }">
        <v-tooltip v-if="item.primary_disease" location="top">
          <template #activator="{ props }">
            <span
              v-bind="props"
              class="text-truncate"
              style="max-width: 200px; display: inline-block"
            >
              {{ item.primary_disease }}
            </span>
          </template>
          <span>{{ item.primary_disease }}</span>
        </v-tooltip>
        <span v-else>N/A</span>
      </template>

      <!-- Render features count with badge -->
      <template #item.features_count="{ item }">
        <v-chip :color="item.features_count > 0 ? 'green' : 'grey'" small variant="flat">
          {{ item.features_count }}
        </v-chip>
      </template>

      <!-- Render variants count with badge -->
      <template #item.variants_count="{ item }">
        <v-chip :color="item.variants_count > 0 ? 'blue' : 'grey'" small variant="flat">
          {{ item.variants_count }}
        </v-chip>
      </template>

      <template #no-data> No phenopackets found. </template>
    </v-data-table-server>
  </v-container>
</template>

<script>
import { getPhenopackets } from '@/api';
import {
  buildSortParameter,
  buildPaginationParameters,
  extractPaginationMeta,
} from '@/utils/pagination';

export default {
  name: 'Phenopackets',
  data() {
    return {
      phenopackets: [],
      loading: false,
      totalItems: 0,
      currentPage: 1,
      headers: [
        {
          title: 'Phenopacket ID',
          value: 'phenopacket_id',
          sortable: true,
          width: '180px',
        },
        {
          title: 'Subject ID',
          value: 'subject_id',
          sortable: true,
          width: '150px',
        },
        {
          title: 'Sex',
          value: 'sex',
          sortable: true,
          width: '120px',
        },
        {
          title: 'Primary Disease',
          value: 'primary_disease',
          sortable: false,
          width: '220px',
        },
        {
          title: 'Features',
          value: 'features_count',
          sortable: false,
          width: '100px',
          align: 'center',
        },
        {
          title: 'Variants',
          value: 'variants_count',
          sortable: false,
          width: '100px',
          align: 'center',
        },
      ],
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [],
      },
      itemsPerPageOptions: [10, 20, 50, 100],
    };
  },
  computed: {
    totalPages() {
      return Math.ceil(this.totalItems / this.options.itemsPerPage);
    },
    pageStart() {
      return (this.currentPage - 1) * this.options.itemsPerPage + 1;
    },
    pageEnd() {
      return Math.min(this.currentPage * this.options.itemsPerPage, this.totalItems);
    },
    rangeText() {
      return this.totalItems === 0
        ? '0 of 0'
        : `${this.pageStart}-${this.pageEnd} of ${this.totalItems}`;
    },
  },
  watch: {
    options: {
      handler() {
        this.fetchPhenopackets();
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    async fetchPhenopackets() {
      this.loading = true;
      window.logService.debug('Starting phenopackets fetch', {
        currentPage: this.currentPage,
        itemsPerPage: this.options.itemsPerPage,
        sortBy: this.options.sortBy,
      });

      try {
        const { itemsPerPage, sortBy } = this.options;

        // Map frontend column keys to backend sort fields
        const sortFieldMap = {
          phenopacket_id: 'created_at', // Default to created_at for phenopacket_id
          subject_id: 'subject_id',
          sex: 'subject_sex',
        };

        // Build sort and pagination parameters using utility functions
        const sortParam = buildSortParameter(sortBy, sortFieldMap);
        const paginationParams = buildPaginationParameters(this.currentPage, itemsPerPage);

        // Fetch phenopackets using JSON:API parameters
        const response = await getPhenopackets({
          ...paginationParams,
          ...(sortParam && { sort: sortParam }),
        });

        // Extract JSON:API response structure
        const jsonApiData = response.data || {};
        const phenopacketDocuments = jsonApiData.data || [];
        const paginationMeta = extractPaginationMeta(response);

        window.logService.debug('JSON:API response received', {
          dataCount: phenopacketDocuments.length,
          pagination: paginationMeta,
          hasLinks: !!jsonApiData.links,
        });

        // Transform response data (phenopackets are already GA4GH format)
        this.phenopackets = phenopacketDocuments.map((pp) => this.transformPhenopacket(pp));

        window.logService.debug('Phenopackets data transformation complete', {
          rawDataCount: phenopacketDocuments.length,
          transformedCount: this.phenopackets.length,
          sampleStructure: this.phenopackets.length > 0 ? Object.keys(this.phenopackets[0]) : [],
        });

        // Update pagination metadata from JSON:API response
        this.totalItems = paginationMeta.totalRecords;

        window.logService.info('Phenopackets fetched successfully', {
          count: phenopacketDocuments.length,
          ...paginationMeta,
        });
      } catch (error) {
        window.logService.error('Failed to fetch phenopackets', {
          error: error.message,
          status: error.response?.status,
          pagination: { page: this.currentPage, itemsPerPage: this.options.itemsPerPage },
        });
        this.phenopackets = [];
        this.totalItems = 0;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Transform phenopacket JSONB to flat table row.
     * Extracts nested fields for display.
     * Input is now GA4GH Phenopacket v2 directly (from JSON:API data array)
     */
    transformPhenopacket(phenopacket) {
      const subject = phenopacket.subject || {};
      const diseases = phenopacket.diseases || [];
      const features = phenopacket.phenotypicFeatures || [];
      const interpretations = phenopacket.interpretations || [];

      // Count variants from interpretations
      let variantsCount = 0;
      interpretations.forEach((interp) => {
        const genomicInterps = interp.diagnosis?.genomicInterpretations || [];
        variantsCount += genomicInterps.length;
      });

      return {
        phenopacket_id: phenopacket.id,
        subject_id: subject.id || 'N/A',
        sex: subject.sex || 'UNKNOWN_SEX',
        primary_disease: diseases[0]?.term?.label || null,
        features_count: features.length,
        variants_count: variantsCount,
      };
    },

    onOptionsUpdate(newOptions) {
      this.options = { ...newOptions };
    },

    // Disable client-side sorting
    customSort(items) {
      return items;
    },

    goToFirstPage() {
      window.logService.debug('Pagination: navigating to first page', {
        fromPage: this.currentPage,
        toPage: 1,
      });
      this.currentPage = 1;
      this.fetchPhenopackets();
    },

    goToPreviousPage() {
      if (this.currentPage > 1) {
        window.logService.debug('Pagination: navigating to previous page', {
          fromPage: this.currentPage,
          toPage: this.currentPage - 1,
        });
        this.currentPage--;
        this.fetchPhenopackets();
      }
    },

    goToNextPage() {
      if (this.currentPage < this.totalPages) {
        window.logService.debug('Pagination: navigating to next page', {
          fromPage: this.currentPage,
          toPage: this.currentPage + 1,
        });
        this.currentPage++;
        this.fetchPhenopackets();
      }
    },

    goToLastPage() {
      window.logService.debug('Pagination: navigating to last page', {
        fromPage: this.currentPage,
        toPage: this.totalPages,
      });
      this.currentPage = this.totalPages;
      this.fetchPhenopackets();
    },

    getSexIcon(sex) {
      const icons = {
        MALE: 'mdi-gender-male',
        FEMALE: 'mdi-gender-female',
        OTHER_SEX: 'mdi-gender-non-binary',
        UNKNOWN_SEX: 'mdi-help-circle',
      };
      return icons[sex] || 'mdi-help-circle';
    },

    getSexColor(sex) {
      const colors = {
        MALE: 'blue',
        FEMALE: 'pink',
        OTHER_SEX: 'purple',
        UNKNOWN_SEX: 'grey',
      };
      return colors[sex] || 'grey';
    },

    formatSex(sex) {
      const labels = {
        MALE: 'Male',
        FEMALE: 'Female',
        OTHER_SEX: 'Other',
        UNKNOWN_SEX: 'Unknown',
      };
      return labels[sex] || sex;
    },

    handleRowClick(event, { item }) {
      // Navigate to phenopacket detail page
      window.logService.info('Navigating to phenopacket detail', {
        phenopacketId: item.phenopacket_id,
        subjectId: item.subject_id,
      });
      this.$router.push(`/phenopackets/${item.phenopacket_id}`);
    },
  },
};
</script>

<style scoped>
.font-weight-bold {
  font-weight: bold;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Make table rows clickable with hover effect */
.clickable-rows :deep(tbody tr) {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.clickable-rows :deep(tbody tr:hover) {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
