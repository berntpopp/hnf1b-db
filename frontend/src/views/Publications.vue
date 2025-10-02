<!-- src/views/Publications.vue -->
<template>
  <v-container>
    <v-data-table-server
      v-model:options="options"
      :headers="headers"
      :items="publications"
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
          <v-toolbar-title>Publications</v-toolbar-title>
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

      <!-- Render Publication ID as a clickable chip with icon -->
      <template #item.publication_id="{ item }">
        <v-chip
          color="cyan-accent-2"
          class="ma-2"
          small
          link
          variant="flat"
          :to="'/publications/' + item.publication_id"
        >
          {{ item.publication_id }}
          <v-icon right>
            mdi-book-open-blank-variant
          </v-icon>
        </v-chip>
      </template>

      <!-- Render PMID as a clickable link -->
      <template #item.pmid="{ item }">
        <a
          v-if="item.pmid"
          :href="'https://pubmed.ncbi.nlm.nih.gov/' + item.pmid"
          target="_blank"
        >
          {{ item.pmid }}
        </a>
        <span v-else>-</span>
      </template>

      <!-- Render DOI as a clickable link -->
      <template #item.doi="{ item }">
        <a
          v-if="item.doi && item.doi !== 'nan'"
          :href="'https://doi.org/' + item.doi"
          target="_blank"
        >
          {{ item.doi }}
        </a>
        <span v-else>-</span>
      </template>

      <!-- Show title or fallback text -->
      <template #item.title="{ item }">
        <span v-if="item.title && item.title.trim()">{{ item.title }}</span>
        <span
          v-else
          class="text-grey"
        >No title available</span>
      </template>

      <!-- Show publication type with better formatting -->
      <template #item.publication_type="{ item }">
        <v-chip
          v-if="item.publication_type"
          small
          :color="getPublicationTypeColor(item.publication_type)"
        >
          {{ formatPublicationType(item.publication_type) }}
        </v-chip>
      </template>

      <template #no-data>
        No publications found.
      </template>
    </v-data-table-server>
  </v-container>
</template>

<script>
import { getPublications } from '@/api';

export default {
  name: 'Publications',
  data() {
    return {
      publications: [],
      loading: false,
      totalItems: 0,
      totalPages: 0,
      headers: [
        {
          title: 'Publication ID',
          value: 'publication_id',
          sortable: true,
          width: '100px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Publication Type',
          value: 'publication_type',
          sortable: true,
          maxWidth: '100px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'PMID',
          value: 'pmid',
          sortable: true,
          maxWidth: '100px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'DOI',
          value: 'doi',
          sortable: true,
          maxWidth: '150px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Title',
          value: 'title',
          sortable: true,
          maxWidth: '250px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Publication Date',
          value: 'publication_date',
          sortable: true,
          maxWidth: '130px',
          cellClass: 'truncate',
          headerProps: {
            class: 'font-weight-bold',
          },
          nowrap: true,
        },
        {
          title: 'Journal',
          value: 'journal',
          sortable: true,
          maxWidth: '150px',
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
        this.fetchPublications();
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    async fetchPublications() {
      this.loading = true;
      try {
        const { page, itemsPerPage, sortBy } = this.options;
        let sortParam = '';
        if (Array.isArray(sortBy) && sortBy.length > 0) {
          // Expect sortBy[0] in the form: { key: 'fieldName', order: 'asc' } or { key: 'fieldName', order: 'desc' }
          const { key, order } = sortBy[0];
          sortParam = (order === 'desc' ? '-' : '') + key;
        }
        const response = await getPublications({
          page,
          page_size: itemsPerPage,
          sort: sortParam,
        });
        // Unpack the JSON:API response.
        this.publications = response.data;
        this.totalItems = response.meta.total || 0;
        this.totalPages = response.meta.total_pages || 0;
      } catch (error) {
        console.error('Error fetching publications:', error);
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
    // Get color for publication type chip
    getPublicationTypeColor(type) {
      const colors = {
        case_report: 'blue',
        research: 'green',
        case_series: 'purple',
        screening_multiple: 'orange',
        review: 'teal',
        review_and_cases: 'indigo',
      };
      return colors[type] || 'grey';
    },
    // Format publication type for display
    formatPublicationType(type) {
      return type
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
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
