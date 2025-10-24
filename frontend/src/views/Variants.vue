<!-- src/views/Variants.vue -->
<template>
  <v-container>
    <v-data-table-server
      v-model:options="options"
      :headers="headers"
      :items="variants"
      :loading="loading"
      :items-length="totalPages"
      :custom-sort="customSort"
      hide-default-footer
      class="elevation-1"
      density="compact"
      @update:options="onOptionsUpdate"
      @click:row="handleRowClick"
    >
      <template #top>
        <v-toolbar flat>
          <v-toolbar-title>Variants</v-toolbar-title>
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
            <v-btn
              icon
              :disabled="options.page === 1"
              @click="goToFirstPage"
            >
              <v-icon>mdi-page-first</v-icon>
            </v-btn>
            <v-btn
              icon
              :disabled="options.page === 1"
              @click="goToPreviousPage"
            >
              <v-icon>mdi-chevron-left</v-icon>
            </v-btn>
            <v-btn
              icon
              :disabled="options.page === totalPages"
              @click="goToNextPage"
            >
              <v-icon>mdi-chevron-right</v-icon>
            </v-btn>
            <v-btn
              icon
              :disabled="options.page === totalPages"
              @click="goToLastPage"
            >
              <v-icon>mdi-page-last</v-icon>
            </v-btn>
          </div>
        </v-toolbar>
      </template>

      <!-- Render simple_id as a clickable chip -->
      <template #item.simple_id="{ item }">
        <v-chip
          color="pink-lighten-3"
          class="ma-1"
          size="small"
          variant="flat"
        >
          {{ item.simple_id }}
          <v-icon right>
            mdi-dna
          </v-icon>
        </v-chip>
      </template>

      <!-- Render transcript with only c. notation (strip NM_ prefix) -->
      <template #item.transcript="{ item }">
        {{ extractCNotation(item.transcript) }}
      </template>

      <!-- Render protein with only p. notation (strip NP_ prefix) -->
      <template #item.protein="{ item }">
        {{ extractPNotation(item.protein) }}
      </template>

      <!-- Render variant type with color coding -->
      <template #item.variant_type="{ item }">
        <v-chip
          :color="getVariantTypeColor(item.variant_type)"
          class="ma-1"
          size="small"
          variant="flat"
        >
          {{ item.variant_type }}
        </v-chip>
      </template>

      <!-- Render classification with color coding -->
      <template #item.classificationVerdict="{ item }">
        <v-chip
          v-if="item.classificationVerdict"
          :color="getPathogenicityColor(item.classificationVerdict)"
          class="ma-1"
          size="small"
          variant="flat"
        >
          {{ item.classificationVerdict }}
        </v-chip>
        <span v-else>-</span>
      </template>

      <!-- Render individual count as a badge -->
      <template #item.individualCount="{ item }">
        <v-chip
          color="light-green-lighten-3"
          class="ma-1"
          size="small"
          variant="flat"
        >
          {{ item.individualCount || 0 }}
        </v-chip>
      </template>

      <template #no-data>
        No variants found.
      </template>
    </v-data-table-server>
  </v-container>
</template>

<script>
import { getVariants } from '@/api';

export default {
  name: 'Variants',
  data() {
    return {
      variants: [],
      loading: false,
      totalItems: 0,
      totalPages: 0,
      headers: [
        {
          title: 'Variant ID',
          value: 'simple_id',
          sortable: true,
          maxWidth: '100px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Transcript (c.)',
          value: 'transcript',
          sortable: true,
          maxWidth: '200px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Protein (p.)',
          value: 'protein',
          sortable: true,
          maxWidth: '200px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Variant Type',
          value: 'variant_type',
          sortable: true,
          maxWidth: '120px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'HG38',
          value: 'hg38',
          sortable: true,
          maxWidth: '250px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Classification',
          value: 'classificationVerdict',
          sortable: true,
          maxWidth: '150px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Individual Count',
          value: 'individualCount',
          sortable: false,
          maxWidth: '120px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
      ],
      // Options for server-side pagination and sorting.
      options: {
        page: 1,
        itemsPerPage: 10,
        sortBy: [],
      },
      itemsPerPageOptions: [10, 20, 50, 100],
    };
  },
  computed: {
    // Calculate the starting item index for the current page.
    pageStart() {
      return (this.options.page - 1) * this.options.itemsPerPage + 1;
    },
    // Calculate the ending item index for the current page.
    pageEnd() {
      return Math.min(this.options.page * this.options.itemsPerPage, this.totalItems);
    },
    // Create the range text (e.g., "1-10 of 160").
    rangeText() {
      return this.totalItems === 0
        ? '0 of 0'
        : `${this.pageStart}-${this.pageEnd} of ${this.totalItems}`;
    },
  },
  watch: {
    // Fetch data on initialization and whenever pagination or sorting options change.
    options: {
      handler() {
        this.fetchVariants();
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    async fetchVariants() {
      this.loading = true;
      try {
        const { page, itemsPerPage, sortBy } = this.options;
        let sortParam = '';
        if (Array.isArray(sortBy) && sortBy.length > 0) {
          // Expect sortBy[0] in the form: { key: 'fieldName', order: 'asc' } or { key: 'fieldName', order: 'desc' }
          const { key, order } = sortBy[0];
          sortParam = (order === 'desc' ? '-' : '') + key;
        }
        const response = await getVariants({
          page,
          page_size: itemsPerPage,
          sort: sortParam,
        });
        // Unpack the JSON:API response.
        this.variants = response.data;
        this.totalItems = response.meta.total || 0;
        this.totalPages = response.meta.total_pages || 0;
      } catch (error) {
        console.error('Error fetching variants:', error);
      } finally {
        this.loading = false;
      }
    },
    onOptionsUpdate(newOptions) {
      this.options = { ...newOptions };
    },
    // Disable client-side sorting.
    customSort(items) {
      return items;
    },
    goToFirstPage() {
      this.options.page = 1;
    },
    goToPreviousPage() {
      if (this.options.page > 1) {
        this.options.page--;
      }
    },
    goToNextPage() {
      if (this.options.page < this.totalPages) {
        this.options.page++;
      }
    },
    goToLastPage() {
      this.options.page = this.totalPages;
    },
    handleRowClick(event, row) {
      // Navigate to variant detail page using variant_id
      if (row.item && row.item.variant_id) {
        this.$router.push(`/variants/${row.item.variant_id}`);
      }
    },
    getVariantTypeColor(variantType) {
      const colorMap = {
        deletion: 'red-lighten-3',
        duplication: 'blue-lighten-3',
        SNV: 'purple-lighten-3',
        insertion: 'green-lighten-3',
        inversion: 'orange-lighten-3',
        CNV: 'amber-lighten-3',
      };
      return colorMap[variantType] || 'grey-lighten-2';
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
  },
};
</script>

<style scoped>
/* Ensure header cells are bold */
.font-weight-bold {
  font-weight: bold;
}

/* Truncate long text in table cells */
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Make table rows look clickable */
:deep(tbody tr) {
  cursor: pointer;
}

:deep(tbody tr:hover) {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
