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

      <!-- Render Variant ID as a clickable chip linking to its detail page -->
      <template #item.variant_id="{ item }">
        <v-chip
          color="pink-lighten-4"
          class="ma-2"
          small
          link
          variant="flat"
          :to="'/variants/' + item.variant_id"
        >
          {{ item.variant_id }}
          <v-icon right>
            mdi-dna
          </v-icon>
        </v-chip>
      </template>

      <!-- Custom slot for Classification Verdict column -->
      <template #item.classificationVerdict="{ item }">
        {{
          item.classifications && item.classifications.length
            ? item.classifications[0].verdict
            : 'N/A'
        }}
      </template>

      <!-- Custom slot for Individual Count column -->
      <template #item.individualCount="{ item }">
        {{ item.individual_ids ? item.individual_ids.length : 'N/A' }}
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
          value: 'variant_id',
          sortable: true,
          maxWidth: '150px',
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
          maxWidth: '100px',
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
          maxWidth: '150px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Classification Verdict',
          value: 'classificationVerdict',
          sortable: true,
          maxWidth: '100px',
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
          maxWidth: '100px',
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
</style>
