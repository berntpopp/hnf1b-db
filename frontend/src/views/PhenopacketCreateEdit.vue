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
            label="Phenopacket ID *"
            :readonly="isEditing"
            :rules="[rules.required]"
            :hint="
              isEditing
                ? 'Cannot change ID when editing'
                : 'Enter a unique identifier (e.g., CASE001, HNF1B-P001)'
            "
            persistent-hint
            required
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

          <!-- Publications/Citations -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="bg-orange-lighten-5">
              <v-icon left>mdi-book-open-variant</v-icon>
              Publications
            </v-card-title>
            <v-card-text>
              <div v-for="(pub, index) in phenopacket.publications" :key="index" class="mb-3">
                <v-row>
                  <v-col cols="12" md="10">
                    <v-text-field
                      v-model="pub.pmid"
                      label="PubMed ID (PMID)"
                      hint="Enter numeric PMID (e.g., 12345678)"
                      persistent-hint
                    />
                  </v-col>
                  <v-col cols="12" md="2" class="d-flex align-center">
                    <v-btn
                      color="error"
                      icon="mdi-delete"
                      variant="text"
                      @click="removePublication(index)"
                    />
                  </v-col>
                </v-row>
              </div>
              <v-btn color="primary" prepend-icon="mdi-plus" @click="addPublication">
                Add Publication
              </v-btn>
            </v-card-text>
          </v-card>

          <!-- Variant Information -->
          <VariantAnnotationForm
            v-model="phenopacket.interpretations"
            :subject-id="phenopacket.subject?.id || ''"
          />

          <!-- Phenotypic Features Section -->
          <PhenotypicFeaturesSection
            v-model="phenopacket.phenotypicFeatures"
            :form-submitted="formSubmitted"
          />

          <!-- Change Reason (Edit Mode Only) -->
          <v-card v-if="isEditing" variant="outlined" class="mb-4">
            <v-card-title class="bg-yellow-lighten-4">
              <v-icon left>mdi-pencil-box-outline</v-icon>
              Reason for Change
            </v-card-title>
            <v-card-text>
              <v-alert type="info" variant="tonal" density="compact" class="mb-3">
                All changes are tracked in the audit trail. Please provide a clear explanation for
                this update.
              </v-alert>
              <v-textarea
                v-model="changeReason"
                label="Change Reason *"
                placeholder="e.g., Adding new phenotype data, Correcting variant information, Updated diagnosis"
                variant="outlined"
                rows="3"
                :rules="[rules.required, rules.minLength]"
                hint="Required for audit trail. Minimum 5 characters."
                persistent-hint
                required
              >
                <template #prepend-inner>
                  <v-icon>mdi-text-box</v-icon>
                </template>
              </v-textarea>
            </v-card-text>
          </v-card>

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
        interpretations: [],
        publications: [],
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
      revision: null, // For optimistic locking
      changeReason: '', // For audit trail
      rules: {
        required: (value) => !!value || 'Required field',
        minLength: (value) => (value && value.length >= 5) || 'Must be at least 5 characters',
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
      // Leave ID empty for user to specify (required field will enforce entry)
      this.phenopacket.id = '';
    }
  },
  methods: {
    async loadPhenopacket() {
      this.loading = true;
      this.error = null;

      try {
        const response = await getPhenopacket(this.$route.params.phenopacket_id);

        // Backend returns the GA4GH phenopacket object directly
        this.phenopacket = response.data;

        // Initialize revision to 1 (optimistic locking disabled for now)
        this.revision = 1;

        window.logService.info('Phenopacket loaded for editing', {
          phenopacketId: this.phenopacket.id,
          revision: this.revision,
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

    addPublication() {
      this.phenopacket.publications.push({
        pmid: '',
      });
    },

    removePublication(index) {
      this.phenopacket.publications.splice(index, 1);
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

      // Validate change reason for edits
      if (this.isEditing && (!this.changeReason || this.changeReason.length < 5)) {
        this.error = 'Change reason is required for updates (minimum 5 characters)';
        return;
      }

      this.saving = true;
      this.error = null;

      try {
        let result;

        if (this.isEditing) {
          // Update existing phenopacket with optimistic locking and audit trail
          result = await updatePhenopacket(this.phenopacket.id, {
            phenopacket: this.phenopacket,
            revision: this.revision,
            change_reason: this.changeReason,
          });

          window.logService.info('Phenopacket updated successfully', {
            phenopacketId: result.data.phenopacket_id,
            revision: this.revision,
            changeReasonLength: this.changeReason.length,
          });
        } else {
          // Create new phenopacket
          result = await createPhenopacket({
            phenopacket: this.phenopacket,
          });

          window.logService.info('Phenopacket created successfully', {
            phenopacketId: result.data.phenopacket_id,
          });
        }

        // Navigate to detail page using phenopacket_id (not database id)
        this.$router.push(`/phenopackets/${result.data.phenopacket_id}`);
      } catch (err) {
        // Handle concurrent edit conflicts (409 Conflict)
        if (err.response?.status === 409) {
          this.error =
            'This phenopacket was modified by another user. Please refresh the page to see the latest version and try again.';
          window.logService.warn('Concurrent edit detected', {
            phenopacketId: this.phenopacket.id,
            revision: this.revision,
            status: err.response?.status,
          });
        } else {
          this.error = 'Failed to save phenopacket: ' + (err.response?.data?.detail || err.message);
          window.logService.error('Failed to save phenopacket', {
            error: err.message,
            status: err.response?.status,
          });
        }
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
