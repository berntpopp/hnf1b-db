<!-- src/views/PagePublication.vue -->
<template>
  <v-container fluid>
    <!-- Loading State -->
    <v-row v-if="loading" justify="center">
      <v-col cols="12" class="text-center">
        <v-progress-circular indeterminate color="primary" size="64" />
        <div class="mt-4">Loading publication...</div>
      </v-col>
    </v-row>

    <!-- Error State -->
    <v-row v-else-if="error" justify="center">
      <v-col cols="12" md="8">
        <v-alert type="error" variant="tonal" prominent>
          <v-alert-title>Error Loading Publication</v-alert-title>
          {{ error }}
        </v-alert>
        <v-btn class="mt-4" color="primary" @click="$router.push('/publications')">
          Back to Publications
        </v-btn>
      </v-col>
    </v-row>

    <!-- Main Content -->
    <div v-else-if="publication">
      <!-- Header with Publication Info -->
      <v-row>
        <v-col cols="12">
          <v-card flat class="mb-4">
            <v-card-title class="text-h4">
              <v-icon left color="primary" size="large"> mdi-book-open-variant </v-icon>
              {{ publication.title || 'Publication' }}
            </v-card-title>
            <v-card-subtitle class="text-h6 mt-2">
              <div v-if="publication.authors">
                {{ publication.authors }}
                <span v-if="publication.year" class="text-grey-darken-1"
                  >({{ publication.year }})</span
                >
              </div>
              <div class="mt-2">
                <v-chip
                  v-if="publicationId"
                  :href="`https://pubmed.ncbi.nlm.nih.gov/${publicationId}`"
                  color="orange-lighten-3"
                  size="small"
                  variant="flat"
                  target="_blank"
                  link
                  class="mr-2"
                >
                  <v-icon left size="small">mdi-book-open-variant</v-icon>
                  PMID: {{ publicationId }}
                  <v-icon right size="small">mdi-open-in-new</v-icon>
                </v-chip>
                <v-chip
                  v-if="publication.doi"
                  :href="`https://doi.org/${publication.doi}`"
                  color="blue-lighten-3"
                  size="small"
                  variant="flat"
                  target="_blank"
                  link
                >
                  <v-icon left size="small">mdi-link-variant</v-icon>
                  {{ publication.doi }}
                  <v-icon right size="small">mdi-open-in-new</v-icon>
                </v-chip>
              </div>
            </v-card-subtitle>
            <v-card-actions>
              <v-btn prepend-icon="mdi-arrow-left" @click="$router.push('/publications')">
                Back to Publications
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>

      <!-- Phenopackets Table -->
      <v-row>
        <v-col cols="12">
          <v-card>
            <v-card-title class="text-h5">
              Individuals from this Publication ({{ phenopackets.length }})
            </v-card-title>
            <v-data-table
              :headers="headers"
              :items="phenopackets"
              :loading="loading"
              :items-per-page="20"
              class="elevation-1"
              density="compact"
            >
              <!-- Phenopacket ID as clickable chip -->
              <template #item.id="{ item }">
                <v-chip
                  :to="`/phenopackets/${item.id}`"
                  color="blue-lighten-3"
                  size="small"
                  variant="flat"
                  link
                >
                  <v-icon left size="small">mdi-file-document</v-icon>
                  {{ item.id }}
                </v-chip>
              </template>

              <!-- Subject ID -->
              <template #item.subject_id="{ item }">
                {{ item.subject?.id || 'N/A' }}
              </template>

              <!-- Subject Sex with color coding -->
              <template #item.subject_sex="{ item }">
                <v-chip
                  v-if="item.subject?.sex"
                  :color="getSexColor(item.subject.sex)"
                  size="small"
                  variant="flat"
                >
                  {{ formatSex(item.subject.sex) }}
                </v-chip>
                <span v-else>-</span>
              </template>

              <!-- Phenotypic Features Count -->
              <template #item.features_count="{ item }">
                <v-chip color="purple-lighten-3" size="small" variant="flat">
                  {{ item.phenotypicFeatures?.length || 0 }}
                </v-chip>
              </template>

              <!-- Variants Count -->
              <template #item.variants_count="{ item }">
                <v-chip
                  v-if="item.interpretations && item.interpretations.length > 0"
                  color="green-lighten-3"
                  size="small"
                  variant="flat"
                >
                  {{ item.interpretations.length }}
                </v-chip>
                <span v-else>-</span>
              </template>

              <template #no-data>
                <v-alert type="info" variant="tonal">
                  No individuals found for this publication.
                </v-alert>
              </template>
            </v-data-table>
          </v-card>
        </v-col>
      </v-row>
    </div>
  </v-container>
</template>

<script>
import { getPhenopacketsByPublication } from '@/api';

export default {
  name: 'PagePublication',
  data() {
    return {
      publicationId: null,
      publication: null,
      phenopackets: [],
      loading: false,
      error: null,
      headers: [
        {
          title: 'Phenopacket ID',
          value: 'id',
          sortable: true,
          width: '200px',
        },
        {
          title: 'Subject ID',
          value: 'subject_id',
          sortable: true,
          width: '150px',
        },
        {
          title: 'Sex',
          value: 'subject_sex',
          sortable: true,
          width: '120px',
        },
        {
          title: 'Phenotypes',
          value: 'features_count',
          sortable: true,
          width: '120px',
          align: 'center',
        },
        {
          title: 'Variants',
          value: 'variants_count',
          sortable: true,
          width: '120px',
          align: 'center',
        },
      ],
    };
  },
  mounted() {
    this.fetchPublication();
  },
  methods: {
    async fetchPublication() {
      this.loading = true;
      this.error = null;

      // Get PMID from route params
      this.publicationId = this.$route.params.publication_id;

      window.logService.debug('Loading publication detail page', {
        publicationId: this.publicationId,
        route: this.$route.path,
      });

      try {
        // Fetch phenopackets from this publication
        const response = await getPhenopacketsByPublication(this.publicationId);
        // Backend returns {data: [{phenopacket_id, phenopacket}], total, skip, limit}
        // Extract the phenopacket objects from the wrapper
        this.phenopackets = (response.data.data || []).map((item) => item.phenopacket);

        window.logService.debug('Publication data received', {
          publicationId: this.publicationId,
          phenopacketCount: this.phenopackets.length,
        });

        // Extract publication metadata from first phenopacket (if available)
        if (this.phenopackets.length > 0) {
          const firstPhenopacket = this.phenopackets[0];
          const metaData = firstPhenopacket.metaData;

          // Find the publication reference in externalReferences
          if (metaData?.externalReferences) {
            const pubRef = metaData.externalReferences.find(
              (ref) =>
                ref.id === `PMID:${this.publicationId}` || ref.id === this.publicationId.toString()
            );
            if (pubRef) {
              this.publication = {
                title: pubRef.description || 'Title unavailable',
                doi: metaData.externalReferences
                  .find((ref) => ref.id.startsWith('DOI:'))
                  ?.id.replace('DOI:', ''),
                authors: null, // Will be enriched from PubMed API
                year: null, // Will be enriched from PubMed API
              };
            }
          }
        }

        // If no publication metadata found, create basic structure
        if (!this.publication) {
          this.publication = {
            title: `PMID: ${this.publicationId}`,
            authors: null,
            doi: null,
            year: null,
          };
        }

        // Enrich with PubMed metadata
        await this.enrichWithPubMedData();

        window.logService.info('Publication loaded successfully', {
          publicationId: this.publicationId,
          phenopacketCount: this.phenopackets.length,
        });
      } catch (error) {
        window.logService.error('Failed to fetch publication', {
          error: error.message,
          publicationId: this.publicationId,
          status: error.response?.status,
        });
        this.error =
          error.response?.status === 404
            ? `Publication '${this.publicationId}' not found.`
            : 'Failed to load publication. Please try again later.';
      } finally {
        this.loading = false;
      }
    },

    async enrichWithPubMedData() {
      try {
        // NCBI E-utilities API: fetch summary for this PMID
        const response = await fetch(
          `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=${this.publicationId}&retmode=json`
        );

        if (!response.ok) {
          window.logService.warn('Failed to fetch PubMed data', {
            status: response.status,
          });
          return;
        }

        const data = await response.json();
        const pubmedData = data.result?.[this.publicationId];

        if (pubmedData) {
          this.publication.title = pubmedData.title || this.publication.title;

          // Format authors: "FirstAuthor et al." or list first 3
          if (pubmedData.authors && pubmedData.authors.length > 0) {
            const authorNames = pubmedData.authors.map((a) => a.name);
            if (authorNames.length === 1) {
              this.publication.authors = authorNames[0];
            } else if (authorNames.length <= 3) {
              this.publication.authors = authorNames.join(', ');
            } else {
              this.publication.authors = `${authorNames[0]} et al.`;
            }
          }

          // Extract publication year from pubdate (format: "2019 Feb 21")
          if (pubmedData.pubdate) {
            const yearMatch = pubmedData.pubdate.match(/^\d{4}/);
            if (yearMatch) {
              this.publication.year = yearMatch[0];
            }
          }

          window.logService.info('Enriched publication with PubMed metadata', {
            publicationId: this.publicationId,
          });
        }
      } catch (error) {
        window.logService.error('Failed to enrich publication with PubMed data', {
          error: error.message,
        });
        // Don't fail the whole view if PubMed enrichment fails
      }
    },

    getSexColor(sex) {
      const colors = {
        MALE: 'blue',
        FEMALE: 'pink',
        OTHER_SEX: 'grey',
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
  },
};
</script>

<style scoped>
/* Add any custom styles here if needed */
</style>
