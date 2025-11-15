<!-- src/views/PhenopacketCreateEdit.vue -->
<template>
  <v-container>
    <v-card>
      <v-card-title class="text-h4">
        <v-icon left color="primary" size="large">
          {{ isEditing ? 'mdi-pencil' : 'mdi-plus' }}
        </v-icon>
        {{ isEditing ? 'Edit Phenopacket' : 'Create New Phenopacket' }}
      </v-card-title>

      <v-card-text>
        <!-- Loading State -->
        <v-row v-if="loading && isEditing" justify="center">
          <v-col cols="12" class="text-center">
            <v-progress-circular indeterminate color="primary" size="64" />
            <div class="mt-4">Loading phenopacket...</div>
          </v-col>
        </v-row>

        <!-- Form -->
        <v-form v-else ref="form" @submit.prevent="handleSubmit">
          <!-- Phenopacket ID (read-only for edit) -->
          <v-text-field
            v-model="phenopacket.id"
            label="Phenopacket ID"
            :readonly="isEditing"
            :hint="isEditing ? 'Cannot change ID when editing' : 'Auto-generated if empty'"
            persistent-hint
            class="mb-4"
          />

          <!-- Subject Section -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="bg-blue-lighten-5">
              <v-icon left>mdi-account</v-icon>
              Subject Information
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="phenopacket.subject.id"
                    label="Subject ID *"
                    :rules="[rules.required]"
                    required
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-select
                    v-model="phenopacket.subject.sex"
                    :items="vocabularies.sex.value"
                    item-title="label"
                    item-value="value"
                    label="Sex *"
                    :loading="vocabularies.loading.value"
                    :disabled="vocabularies.loading.value"
                    :rules="[rules.required]"
                    required
                  />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Phenotypic Features Section -->
          <PhenotypicFeaturesSection
            v-model="phenopacket.phenotypicFeatures"
            :form-submitted="formSubmitted"
          />

          <!-- Variant Information -->
          <VariantAnnotationForm v-model="phenopacket.variants" />

          <!-- Error Display -->
          <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
            {{ error }}
          </v-alert>

          <!-- Actions -->
          <v-card-actions>
            <v-btn color="primary" type="submit" :loading="saving" size="large">
              <v-icon left>mdi-content-save</v-icon>
              {{ isEditing ? 'Update' : 'Create' }} Phenopacket
            </v-btn>
            <v-btn size="large" @click="$router.push('/phenopackets')"> Cancel </v-btn>
          </v-card-actions>
        </v-form>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script>
import { getPhenopacket, createPhenopacket, updatePhenopacket } from '@/api';
import { usePhenopacketVocabularies } from '@/composables/usePhenopacketVocabularies';
import PhenotypicFeaturesSection from '@/components/PhenotypicFeaturesSection.vue';
import VariantAnnotationForm from '@/components/VariantAnnotationForm.vue';

export default {
  name: 'PhenopacketCreateEdit',
  components: {
    PhenotypicFeaturesSection,
    VariantAnnotationForm,
  },
  setup() {
    const vocabularies = usePhenopacketVocabularies();
    return { vocabularies };
  },
  data() {
    return {
      phenopacket: {
        id: '',
        subject: {
          id: '',
          sex: 'UNKNOWN_SEX',
        },
        phenotypicFeatures: [],
        variants: [],
        interpretations: [],
        metaData: {
          created: new Date().toISOString(),
          createdBy: 'HNF1B-DB Curation Interface',
          resources: [
            {
              id: 'hp',
              name: 'human phenotype ontology',
              url: 'http://purl.obolibrary.org/obo/hp.owl',
              version: '2024-01-16',
              namespacePrefix: 'HP',
              iriPrefix: 'http://purl.obolibrary.org/obo/HP_',
            },
          ],
        },
      },
      loading: false,
      saving: false,
      error: null,
      formSubmitted: false,
      rules: {
        required: (value) => !!value || 'Required field',
      },
    };
  },
  computed: {
    isEditing() {
      return !!this.$route.params.phenopacket_id;
    },
  },
  async mounted() {
    // Load controlled vocabularies from API
    try {
      await this.vocabularies.loadAll();
      window.logService.info('Loaded phenopacket vocabularies for form');
    } catch (err) {
      window.logService.error('Failed to load vocabularies', { error: err.message });
      this.error = 'Failed to load form vocabularies. Please refresh the page.';
    }

    if (this.isEditing) {
      await this.loadPhenopacket();
    } else {
      // Generate ID for new phenopacket
      this.phenopacket.id = `phenopacket-${Date.now()}`;
    }
  },
  methods: {
    async loadPhenopacket() {
      this.loading = true;
      this.error = null;

      try {
        const response = await getPhenopacket(this.$route.params.phenopacket_id);
        this.phenopacket = response.data;

        window.logService.info('Phenopacket loaded for editing', {
          phenopacketId: this.phenopacket.id,
        });
      } catch (err) {
        this.error = 'Failed to load phenopacket: ' + err.message;
        window.logService.error('Failed to load phenopacket for editing', {
          error: err.message,
        });
      } finally {
        this.loading = false;
      }
    },

    async handleSubmit() {
      this.formSubmitted = true;
      // Validate form
      const { valid } = await this.$refs.form.validate();
      if (!valid) {
        this.error = 'Please fix validation errors';
        return;
      }

      // Ensure at least one phenotypic feature
      if (this.phenopacket.phenotypicFeatures.length === 0) {
        this.error = 'At least one phenotypic feature is required';
        return;
      }

      this.saving = true;
      this.error = null;

      try {
        const apiCall = this.isEditing ? updatePhenopacket : createPhenopacket;
        const result = await apiCall(this.phenopacket.id, this.phenopacket);

        window.logService.info('Phenopacket saved successfully', {
          phenopacketId: result.data.id,
          mode: this.isEditing ? 'update' : 'create',
        });

        // Navigate to detail page
        this.$router.push(`/phenopackets/${result.data.id}`);
      } catch (err) {
        this.error = 'Failed to save phenopacket: ' + err.message;
        window.logService.error('Failed to save phenopacket', {
          error: err.message,
        });
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style scoped>
.v-card-title {
  font-weight: 600;
}
</style>
