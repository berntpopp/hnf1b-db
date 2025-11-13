<!-- src/views/Publications.vue -->
<template>
  <v-container>
    <v-data-table
      :headers="headers"
      :items="filteredPublications"
      :loading="loading"
      :sort-by="sortBy"
      class="elevation-1"
      density="compact"
    >
      <template #top>
        <v-toolbar flat>
          <v-toolbar-title>Publications</v-toolbar-title>
          <v-spacer />
          <!-- Search Field -->
          <v-text-field
            v-model="searchQuery"
            label="Search"
            placeholder="PMID, DOI, Title, or Author"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
            density="compact"
            style="max-width: 350px"
            class="mr-4"
            @click:clear="clearSearch"
          />
        </v-toolbar>
      </template>

      <!-- Render PMID as clickable chip with external link -->
      <template #item.pmid="{ item }">
        <v-chip
          v-if="item.pmid"
          :href="`https://pubmed.ncbi.nlm.nih.gov/${item.pmid}`"
          color="orange-lighten-3"
          size="small"
          variant="flat"
          target="_blank"
          link
        >
          <v-icon left size="small">mdi-book-open-variant</v-icon>
          PMID: {{ item.pmid }}
          <v-icon right size="small">mdi-open-in-new</v-icon>
        </v-chip>
        <span v-else>-</span>
      </template>

      <!-- Render DOI as clickable chip -->
      <template #item.doi="{ item }">
        <v-chip
          v-if="item.doi"
          :href="'https://doi.org/' + item.doi"
          color="blue-lighten-3"
          size="small"
          variant="flat"
          target="_blank"
          link
        >
          <v-icon left size="small">mdi-link-variant</v-icon>
          {{ item.doi }}
          <v-icon right size="small">mdi-open-in-new</v-icon>
        </v-chip>
        <span v-else>-</span>
      </template>

      <!-- Render phenopacket count as clickable chip -->
      <template #item.phenopacket_count="{ item }">
        <v-chip
          color="green-lighten-3"
          size="small"
          variant="flat"
          :to="`/publications/${item.pmid}`"
          link
        >
          <v-icon left size="small">mdi-account-multiple</v-icon>
          {{ item.phenopacket_count }}
        </v-chip>
      </template>

      <!-- Format date -->
      <template #item.first_added="{ item }">
        {{ formatDate(item.first_added) }}
      </template>

      <template #no-data>
        <v-alert type="info" variant="tonal">
          No publications found. Publications are extracted from phenopacket metadata.
        </v-alert>
      </template>
    </v-data-table>
  </v-container>
</template>

<script>
import { getPublicationsAggregation } from '@/api';

export default {
  name: 'Publications',
  data() {
    return {
      publications: [],
      searchQuery: '', // Search query for filtering
      loading: false,
      sortBy: [{ key: 'phenopacket_count', order: 'desc' }],
      headers: [
        {
          title: 'PMID',
          value: 'pmid',
          sortable: true,
          width: '180px',
        },
        {
          title: 'Title',
          value: 'title',
          sortable: true,
          width: '350px',
        },
        {
          title: 'Authors',
          value: 'authors',
          sortable: true,
          width: '200px',
        },
        {
          title: 'DOI',
          value: 'doi',
          sortable: true,
          width: '250px',
        },
        {
          title: 'Individuals',
          value: 'phenopacket_count',
          sortable: true,
          width: '120px',
          align: 'center',
        },
        {
          title: 'First Added',
          value: 'first_added',
          sortable: true,
          width: '150px',
        },
      ],
    };
  },
  computed: {
    filteredPublications() {
      if (!this.searchQuery || this.searchQuery.trim() === '') {
        return this.publications;
      }

      const query = this.searchQuery.toLowerCase().trim();
      return this.publications.filter((pub) => {
        return (
          pub.pmid?.toLowerCase().includes(query) ||
          pub.doi?.toLowerCase().includes(query) ||
          pub.title?.toLowerCase().includes(query) ||
          pub.authors?.toLowerCase().includes(query)
        );
      });
    },
  },
  mounted() {
    this.fetchPublications();
  },
  methods: {
    async fetchPublications() {
      this.loading = true;
      try {
        const response = await getPublicationsAggregation();
        this.publications = response.data;

        // Fetch titles and authors from PubMed API for each publication
        await this.enrichWithPubMedData();
      } catch (error) {
        window.logService.error('Failed to fetch publications aggregation', {
          error: error.message,
          status: error.response?.status,
        });
      } finally {
        this.loading = false;
      }
    },

    async enrichWithPubMedData() {
      // Fetch publication metadata from PubMed API in parallel
      const pmids = this.publications.map((pub) => pub.pmid).filter(Boolean);
      if (pmids.length === 0) return;

      try {
        // NCBI E-utilities API: fetch summaries for all PMIDs
        const response = await fetch(
          `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=${pmids.join(',')}&retmode=json`
        );

        if (!response.ok) {
          window.logService.warn('Failed to fetch PubMed data', {
            status: response.status,
          });
          return;
        }

        const data = await response.json();
        const results = data.result;

        // Update publications with title and authors
        this.publications.forEach((pub) => {
          if (!pub.pmid || !results[pub.pmid]) {
            pub.title = 'Title unavailable';
            pub.authors = '-';
            return;
          }

          const pubmedData = results[pub.pmid];
          pub.title = pubmedData.title || 'Title unavailable';

          // Format authors: "FirstAuthor et al." or list first 3
          if (pubmedData.authors && pubmedData.authors.length > 0) {
            const authorNames = pubmedData.authors.map((a) => a.name);
            if (authorNames.length === 1) {
              pub.authors = authorNames[0];
            } else if (authorNames.length <= 3) {
              pub.authors = authorNames.join(', ');
            } else {
              pub.authors = `${authorNames[0]} et al.`;
            }
          } else {
            pub.authors = '-';
          }
        });

        window.logService.info('Enriched publications with PubMed metadata', {
          count: pmids.length,
        });
      } catch (error) {
        window.logService.error('Failed to enrich publications with PubMed data', {
          error: error.message,
        });
        // Don't fail the whole view if PubMed enrichment fails
        this.publications.forEach((pub) => {
          if (!pub.title) pub.title = 'Title unavailable';
          if (!pub.authors) pub.authors = '-';
        });
      }
    },
    formatDate(dateString) {
      if (!dateString) return '-';
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    },
    clearSearch() {
      this.searchQuery = '';
      window.logService.info('Cleared publications search filter');
    },
  },
};
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
