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
                    :items="sexOptions"
                    label="Sex *"
                    :rules="[rules.required]"
                    required
                  />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Phenotypic Features Section -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="bg-green-lighten-5">
              <v-icon left>mdi-dna</v-icon>
              Phenotypic Features
            </v-card-title>
            <v-card-text>
              <div
                v-for="(feature, index) in phenopacket.phenotypicFeatures"
                :key="index"
                class="mb-3"
              >
                <v-row>
                  <v-col cols="12" md="10">
                    <v-autocomplete
                      v-model="feature.type.id"
                      v-model:search-input="hpoSearchQuery"
                      :items="hpoTerms"
                      :loading="hpoLoading"
                      item-title="title"
                      item-value="id"
                      label="HPO Term *"
                      placeholder="Start typing to search (e.g., renal cyst)"
                      :rules="[rules.required]"
                      clearable
                      @update:search="searchHPO"
                      @update:model-value="(val) => updateHPOLabel(index, val)"
                    >
                      <template #item="{ props, item }">
                        <v-list-item v-bind="props">
                          <v-list-item-title>{{ item.raw.label }}</v-list-item-title>
                          <v-list-item-subtitle>{{ item.raw.id }}</v-list-item-subtitle>
                        </v-list-item>
                      </template>
                    </v-autocomplete>
                  </v-col>
                  <v-col cols="12" md="2">
                    <v-btn
                      color="error"
                      icon="mdi-delete"
                      variant="text"
                      @click="removeFeature(index)"
                    />
                  </v-col>
                </v-row>
              </div>
              <v-btn color="primary" prepend-icon="mdi-plus" @click="addFeature">
                Add Phenotypic Feature
              </v-btn>
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
import { useHPOAutocomplete } from '@/composables/useHPOAutocomplete';

export default {
  name: 'PhenopacketCreateEdit',
  setup() {
    const { terms: hpoTerms, loading: hpoLoading, search: searchHPO } = useHPOAutocomplete();
    return { hpoTerms, hpoLoading, searchHPO };
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
      hpoSearchQuery: '',
      sexOptions: [
        { title: 'Male', value: 'MALE' },
        { title: 'Female', value: 'FEMALE' },
        { title: 'Other', value: 'OTHER_SEX' },
        { title: 'Unknown', value: 'UNKNOWN_SEX' },
      ],
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

    addFeature() {
      this.phenopacket.phenotypicFeatures.push({
        type: {
          id: '',
          label: '',
        },
      });
    },

    removeFeature(index) {
      this.phenopacket.phenotypicFeatures.splice(index, 1);
    },

    updateHPOLabel(index, hpoId) {
      if (!hpoId) return;
      const term = this.hpoTerms.find((t) => t.id === hpoId);
      if (term) {
        this.phenopacket.phenotypicFeatures[index].type.label = term.label;
      }
    },

    async handleSubmit() {
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
