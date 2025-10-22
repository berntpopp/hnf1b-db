<!-- src/views/PagePublication.vue -->
<template>
  <v-container fluid>
    <!-- Breadcrumb Navigation -->
    <v-breadcrumbs
      :items="breadcrumbs"
      class="px-0"
    >
      <template #divider>
        <v-icon>mdi-chevron-right</v-icon>
      </template>
    </v-breadcrumbs>

    <!-- Loading State -->
    <v-card
      v-if="loading"
      class="pa-6 text-center"
    >
      <v-progress-circular
        indeterminate
        color="primary"
        size="48"
      />
      <p class="mt-4 text-grey">
        Loading publication data...
      </p>
    </v-card>

    <!-- Error State -->
    <v-alert
      v-else-if="error"
      type="error"
      variant="tonal"
      class="mb-4"
    >
      {{ error }}
    </v-alert>

    <!-- Publication Content -->
    <div v-else>
      <!-- Publication Metadata Card -->
      <v-card class="mb-4">
        <v-card-title class="text-h5 bg-grey-lighten-4">
          <v-icon
            left
            color="primary"
            size="large"
          >
            mdi-book-open-variant
          </v-icon>
          Publication {{ pmid }}
        </v-card-title>
        <v-card-text class="pa-4">
          <v-list density="comfortable">
            <v-list-item>
              <v-list-item-title class="font-weight-bold">
                PMID
              </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  :href="publicationUrl"
                  target="_blank"
                  color="primary"
                  size="small"
                  variant="flat"
                >
                  <v-icon
                    left
                    size="x-small"
                  >
                    mdi-open-in-new
                  </v-icon>
                  {{ pmid }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="publication.doi">
              <v-list-item-title class="font-weight-bold">
                DOI
              </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  :href="`https://doi.org/${publication.doi}`"
                  target="_blank"
                  color="secondary"
                  size="small"
                  variant="flat"
                >
                  <v-icon
                    left
                    size="x-small"
                  >
                    mdi-open-in-new
                  </v-icon>
                  {{ publication.doi }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title class="font-weight-bold">
                Individuals Cited
              </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  color="info"
                  size="small"
                  variant="flat"
                >
                  {{ publication.phenopacket_count || 0 }}
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
          <v-icon
            left
            color="primary"
          >
            mdi-account-multiple
          </v-icon>
          Individuals Cited in This Publication
          <v-chip
            class="ml-2"
            color="info"
            size="small"
          >
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
              <v-chip
                size="small"
                :color="getSexColor(item.sex)"
                variant="flat"
              >
                {{ formatSex(item.sex) }}
              </v-chip>
            </template>

            <!-- Has variants indicator -->
            <template #item.has_variants="{ item }">
              <v-icon
                :color="item.has_variants ? 'success' : 'grey'"
                size="small"
              >
                {{ item.has_variants ? 'mdi-check-circle' : 'mdi-close-circle' }}
              </v-icon>
            </template>

            <!-- Phenotype count -->
            <template #item.phenotype_count="{ item }">
              <v-chip
                size="small"
                color="info"
                variant="tonal"
              >
                {{ item.phenotype_count }}
              </v-chip>
            </template>

            <template #no-data>
              <v-alert
                type="info"
                variant="tonal"
                class="ma-4"
              >
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
import { getPublicationsAggregation, getPhenopackets } from '@/api';

export default {
  name: 'PagePublication',
  data() {
    return {
      pmid: '',
      publication: {},
      allPhenopackets: [],
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
      if (!this.allPhenopackets.length) return [];

      // Filter phenopackets that have this PMID in their externalReferences
      // Note: API returns wrapper with nested phenopacket document at phenopacket.phenopacket
      return this.allPhenopackets
        .filter((item) => {
          // Access the nested phenopacket document
          const phenopacket = item.phenopacket || item;
          const externalRefs = phenopacket.metaData?.externalReferences || [];
          return externalRefs.some((ref) => ref.id === `PMID:${this.pmid}`);
        })
        .map((item) => {
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
        // Fetch publication metadata from aggregation endpoint
        const response = await getPublicationsAggregation();
        const publications = response.data;

        // Find the publication matching this PMID
        this.publication = publications.find((pub) => pub.pmid === this.pmid);

        if (!this.publication) {
          this.error = `Publication with PMID ${this.pmid} not found in database.`;
          this.loading = false;
          this.phenopacketsLoading = false;
          return;
        }

        this.loading = false;

        // Fetch all phenopackets (we'll filter client-side for now)
        // TODO: Once backend /by-publication/{pmid} endpoint is implemented, use that instead
        const phenopacketsResponse = await getPhenopackets({
          skip: 0,
          limit: 1000, // Fetch all phenopackets
        });

        this.allPhenopackets = phenopacketsResponse.data;
        this.phenopacketsLoading = false;
      } catch (e) {
        console.error('Error loading publication data:', e);
        this.error = `Failed to load publication data: ${e.message}`;
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
