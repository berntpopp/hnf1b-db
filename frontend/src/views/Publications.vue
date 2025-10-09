<!-- src/views/Publications.vue -->
<template>
  <v-container>
    <v-data-table
      :headers="headers"
      :items="publications"
      :loading="loading"
      :sort-by="sortBy"
      class="elevation-1"
      density="compact"
    >
      <template #top>
        <v-toolbar flat>
          <v-toolbar-title>Publications</v-toolbar-title>
          <v-spacer />
        </v-toolbar>
      </template>

      <!-- Render PMID as clickable PubMed link -->
      <template #item.pmid="{ item }">
        <a
          v-if="item.pmid"
          :href="'https://pubmed.ncbi.nlm.nih.gov/' + item.pmid"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ item.pmid }}
        </a>
        <span v-else>-</span>
      </template>

      <!-- Render DOI as clickable link -->
      <template #item.doi="{ item }">
        <a
          v-if="item.doi"
          :href="'https://doi.org/' + item.doi"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ item.doi }}
        </a>
        <span v-else>-</span>
      </template>

      <!-- Render phenopacket count as clickable chip -->
      <template #item.phenopacket_count="{ item }">
        <v-chip
          color="primary"
          size="small"
          :to="{ path: '/phenopackets', query: { pmid: item.pmid } }"
        >
          {{ item.phenopacket_count }}
        </v-chip>
      </template>

      <!-- Format date -->
      <template #item.first_added="{ item }">
        {{ formatDate(item.first_added) }}
      </template>

      <template #no-data>
        <v-alert
          type="info"
          variant="tonal"
        >
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
      loading: false,
      sortBy: [{ key: 'phenopacket_count', order: 'desc' }],
      headers: [
        {
          title: 'PMID',
          value: 'pmid',
          sortable: true,
          width: '150px',
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
  mounted() {
    this.fetchPublications();
  },
  methods: {
    async fetchPublications() {
      this.loading = true;
      try {
        const response = await getPublicationsAggregation();
        this.publications = response.data;
      } catch (error) {
        console.error('Error fetching publications:', error);
      } finally {
        this.loading = false;
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
  },
};
</script>

<style scoped>
/* Add view-specific styles if needed */
</style>
