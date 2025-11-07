<!-- src/views/PagePublication.vue -->
<template>
  <v-container fluid>
    <!-- Breadcrumb Navigation -->
    <v-breadcrumbs :items="breadcrumbs" class="px-0">
      <template #divider>
        <v-icon>mdi-chevron-right</v-icon>
      </template>
    </v-breadcrumbs>

    <!-- Loading State -->
    <v-card v-if="loading" class="pa-6 text-center">
      <v-progress-circular indeterminate color="primary" size="48" />
      <p class="mt-4 text-grey">Loading publication data...</p>
    </v-card>

    <!-- Error State -->
    <v-alert v-else-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
    </v-alert>

    <!-- Publication Content -->
    <div v-else>
      <!-- Publication Metadata Card -->
      <v-card class="mb-4">
        <v-card-title class="text-h5 bg-grey-lighten-4">
          <v-icon left color="primary" size="large"> mdi-book-open-variant </v-icon>
          {{ publication.title || `Publication ${pmid}` }}
        </v-card-title>

        <!-- Authors and Journal -->
        <v-card-subtitle v-if="publication.authors || publication.journal" class="pt-3">
          <div v-if="publication.authors && publication.authors.length > 0">
            <v-icon size="small" class="mr-1"> mdi-account-multiple </v-icon>
            {{ formatAuthors(publication.authors) }}
          </div>
          <div v-if="publication.journal || publication.year" class="mt-1">
            <v-icon size="small" class="mr-1"> mdi-book </v-icon>
            {{ publication.journal }}{{ publication.year ? ` (${publication.year})` : '' }}
          </div>
        </v-card-subtitle>

        <v-card-text class="pa-4">
          <!-- Abstract (if available) -->
          <v-expansion-panels v-if="publication.abstract" class="mb-4">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon left size="small"> mdi-text-box-outline </v-icon>
                Abstract
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                {{ publication.abstract }}
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <v-list density="comfortable">
            <v-list-item>
              <v-list-item-title class="font-weight-bold"> PMID </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  :href="publicationUrl"
                  target="_blank"
                  color="primary"
                  size="small"
                  variant="flat"
                >
                  <v-icon left size="x-small"> mdi-open-in-new </v-icon>
                  {{ pmid }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="publication.doi">
              <v-list-item-title class="font-weight-bold"> DOI </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  :href="`https://doi.org/${publication.doi}`"
                  target="_blank"
                  color="secondary"
                  size="small"
                  variant="flat"
                >
                  <v-icon left size="x-small"> mdi-open-in-new </v-icon>
                  {{ publication.doi }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title class="font-weight-bold"> Individuals Cited </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip color="info" size="small" variant="flat">
                  {{ phenopacketsTotal }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="publication.first_added">
              <v-list-item-title class="font-weight-bold">
                First Added to Database
              </v-list-item-title>
              <v-list-item-subtitle>
                {{ formatDate(publication.first_added) }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>

      <!-- Phenopackets Citing This Publication -->
      <v-card>
        <v-card-title class="text-h6 bg-grey-lighten-4">
          <v-icon left color="primary"> mdi-account-multiple </v-icon>
          Individuals Cited in This Publication
          <v-chip class="ml-2" color="info" size="small">
            {{ filteredPhenopackets.length }}
          </v-chip>
        </v-card-title>
        <v-card-text class="pa-0">
          <v-data-table
            :headers="phenopacketHeaders"
            :items="filteredPhenopackets"
            :loading="phenopacketsLoading"
            density="compact"
            class="elevation-0"
          >
            <!-- Subject ID as link to phenopacket detail -->
            <template #item.subject_id="{ item }">
              <router-link :to="`/phenopackets/${item.id}`">
                {{ item.subject_id }}
              </router-link>
            </template>

            <!-- Sex with icon -->
            <template #item.sex="{ item }">
              <v-chip size="small" :color="getSexColor(item.sex)" variant="flat">
                {{ formatSex(item.sex) }}
              </v-chip>
            </template>

            <!-- Has variants indicator -->
            <template #item.has_variants="{ item }">
              <v-icon :color="item.has_variants ? 'success' : 'grey'" size="small">
                {{ item.has_variants ? 'mdi-check-circle' : 'mdi-close-circle' }}
              </v-icon>
            </template>

            <!-- Phenotype count -->
            <template #item.phenotype_count="{ item }">
              <v-chip size="small" color="info" variant="tonal">
                {{ item.phenotype_count }}
              </v-chip>
            </template>

            <template #no-data>
              <v-alert type="info" variant="tonal" class="ma-4">
                No phenopackets cite this publication.
              </v-alert>
            </template>
          </v-data-table>
        </v-card-text>
      </v-card>
    </div>
  </v-container>
</template>

<script>
import {
  getPublicationsAggregation,
  getPhenopacketsByPublication,
  getPublicationMetadata,
} from '@/api';

export default {
  name: 'PagePublication',
  data() {
    return {
      pmid: '',
      publication: {},
      phenopackets: [],
      phenopacketsTotal: 0,
      loading: true,
      phenopacketsLoading: true,
      error: null,
      phenopacketHeaders: [
        {
          title: 'Subject ID',
          value: 'subject_id',
          sortable: true,
        },
        {
          title: 'Sex',
          value: 'sex',
          sortable: true,
          width: '100px',
        },
        {
          title: 'Has Variants',
          value: 'has_variants',
          sortable: true,
          width: '120px',
          align: 'center',
        },
        {
          title: 'Phenotypes',
          value: 'phenotype_count',
          sortable: true,
          width: '120px',
          align: 'center',
        },
      ],
    };
  },
  computed: {
    breadcrumbs() {
      return [
        {
          title: 'Home',
          disabled: false,
          href: '/',
        },
        {
          title: 'Publications',
          disabled: false,
          href: '/publications',
        },
        {
          title: this.pmid || 'Loading...',
          disabled: true,
        },
      ];
    },
    publicationUrl() {
      return `https://pubmed.ncbi.nlm.nih.gov/${this.pmid}`;
    },
    filteredPhenopackets() {
      // Use server-filtered phenopackets directly (no client-side filtering needed)
      return this.phenopackets.map((item) => {
        // Extract useful data for the table
        const phenopacket = item.phenopacket || item;
        const subject = phenopacket.subject || {};
        const phenotypicFeatures = phenopacket.phenotypicFeatures || [];
        const interpretations = phenopacket.interpretations || [];

        return {
          id: item.phenopacket_id || phenopacket.id, // Use phenopacket_id for routing
          subject_id: subject.id || 'Unknown',
          sex: subject.sex || 'UNKNOWN_SEX',
          has_variants: interpretations.length > 0,
          phenotype_count: phenotypicFeatures.length,
        };
      });
    },
  },
  async created() {
    this.pmid = this.$route.params.publication_id;
    await this.loadPublicationData();
  },
  methods: {
    async loadPublicationData() {
      this.loading = true;
      this.phenopacketsLoading = true;
      this.error = null;

      try {
        // Try to fetch rich metadata from PubMed API (with database caching)
        try {
          const metadataResponse = await getPublicationMetadata(this.pmid);
          this.publication = {
            pmid: this.pmid,
            ...metadataResponse.data,
          };
        } catch (pubmedError) {
          // Fallback to aggregation endpoint if PubMed fetch fails
          window.logService.warn('PubMed metadata fetch failed, using fallback', {
            pmid: this.pmid,
            error: pubmedError.message,
            fallback: 'getPublicationsAggregation',
          });
          const response = await getPublicationsAggregation();
          const publications = response.data;
          this.publication = publications.find((pub) => pub.pmid === this.pmid);

          if (!this.publication) {
            this.error = `Publication with PMID ${this.pmid} not found in database.`;
            this.loading = false;
            this.phenopacketsLoading = false;
            return;
          }
        }

        this.loading = false;

        // Fetch phenopackets using server-side filtering (much faster!)
        const phenopacketsResponse = await getPhenopacketsByPublication(this.pmid, {
          skip: 0,
          limit: 500, // Server enforces max of 500
        });

        this.phenopackets = phenopacketsResponse.data.data;
        this.phenopacketsTotal = phenopacketsResponse.data.total;
        this.phenopacketsLoading = false;

        window.logService.info('Publication data loaded successfully', {
          pmid: this.pmid,
          phenopacketCount: this.phenopacketsTotal,
          hasMetadata: !!this.publication.title,
        });
      } catch (e) {
        window.logService.error('Failed to load publication data', {
          error: e.message,
          pmid: this.pmid,
          status: e.response?.status,
          detail: e.response?.data?.detail,
        });
        this.error = `Failed to load publication data: ${e.response?.data?.detail || e.message}`;
        this.loading = false;
        this.phenopacketsLoading = false;
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
    formatAuthors(authors) {
      if (!authors || authors.length === 0) return '';

      // Handle both array of strings and array of objects
      const authorNames = authors
        .map((author) => {
          if (typeof author === 'string') return author;
          return author.name || '';
        })
        .filter(Boolean);

      // Show first 3 authors, then "et al."
      if (authorNames.length <= 3) {
        return authorNames.join(', ');
      }
      return `${authorNames.slice(0, 3).join(', ')}, et al.`;
    },
    formatSex(sex) {
      const sexMap = {
        MALE: 'Male',
        FEMALE: 'Female',
        OTHER_SEX: 'Other',
        UNKNOWN_SEX: 'Unknown',
      };
      return sexMap[sex] || sex;
    },
    getSexColor(sex) {
      const colorMap = {
        MALE: 'primary',
        FEMALE: 'secondary',
        OTHER_SEX: 'info',
        UNKNOWN_SEX: 'grey',
      };
      return colorMap[sex] || 'grey';
    },
  },
};
</script>

<style scoped>
/* Add any custom styles if needed */
</style>
