<!-- src/views/PhenopacketCreateEdit.vue -->
<template>
  <v-container>
    <v-card>
      <h1 class="v-card-title text-h4">
        <v-icon left color="primary" size="large">
          {{ isEditing ? 'mdi-pencil' : 'mdi-plus' }}
        </v-icon>
        {{ isEditing ? 'Edit Phenopacket' : 'Create New Phenopacket' }}
      </h1>

      <v-card-text>
        <!-- Error State -->
        <v-alert v-if="error" type="error" variant="tonal" prominent class="mb-4">
          <v-alert-title>Error</v-alert-title>
          {{ error }}
        </v-alert>

        <!-- Loading State (Edit Mode) -->
        <div v-if="loading && isEditing">
          <v-skeleton-loader type="article, article" class="mb-4" />
          <div class="text-center mt-4">
            <v-progress-circular indeterminate color="primary" size="48" />
            <div class="mt-3 text-medium-emphasis">Loading phenopacket data...</div>
          </div>
        </div>

        <!-- Form -->
        <v-form v-else-if="!error" ref="form" @submit.prevent="handleSubmit">
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

          <v-row>
            <!-- Curation sections -->
            <v-col cols="12" md="8">
              <CurationSection
                id="case"
                ref="caseSection"
                title="Case"
                :filled="caseCompleteness.filled"
                :total="caseCompleteness.total"
              >
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

                <div class="text-subtitle-2 text-medium-emphasis mt-4 mb-2">Publications</div>
                <div v-for="(pub, index) in publications" :key="index" class="mb-3">
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
              </CurationSection>

              <CurationSection
                id="variant"
                ref="variantSection"
                title="Variant"
                :filled="variantCompleteness.filled"
                :total="variantCompleteness.total"
              >
                <VariantAnnotationForm
                  v-model="phenopacket.interpretations"
                  :subject-id="phenopacket.subject?.id || ''"
                />
              </CurationSection>

              <CurationSection
                id="classification"
                ref="classificationSection"
                title="Classification"
                :filled="classificationCompleteness.filled"
                :total="classificationCompleteness.total"
              >
                <p class="text-medium-emphasis mb-0">
                  Nothing here yet — classification fields land in a later task.
                </p>
              </CurationSection>

              <CurationSection
                id="phenotypes"
                ref="phenotypesSection"
                title="Phenotypes"
                :filled="phenotypesCompleteness.filled"
                :total="phenotypesCompleteness.total"
              >
                <PhenotypicFeaturesSection
                  v-model="phenopacket.phenotypicFeatures"
                  :form-submitted="formSubmitted"
                />
              </CurationSection>

              <CurationSection
                id="age"
                ref="ageSection"
                title="Age & Onset"
                :filled="ageCompleteness.filled"
                :total="ageCompleteness.total"
              >
                <p class="text-medium-emphasis mb-0">
                  Nothing here yet — age & onset fields land in a later task.
                </p>
              </CurationSection>

              <CurationSection
                id="provenance"
                ref="provenanceSection"
                title="Provenance & Notes"
                :filled="provenanceCompleteness.filled"
                :total="provenanceCompleteness.total"
              >
                <p class="text-medium-emphasis mb-0">
                  Nothing here yet — provenance & notes fields land in a later task.
                </p>
              </CurationSection>

              <!-- Change Reason (Edit Mode Only) -->
              <v-card v-if="isEditing" variant="outlined" class="mb-4">
                <v-card-title class="text-subtitle-1 font-weight-medium">
                  <v-icon left>mdi-pencil-box-outline</v-icon>
                  Reason for Change
                </v-card-title>
                <v-card-text>
                  <v-alert type="info" variant="tonal" density="compact" class="mb-3">
                    All changes are tracked in the audit trail. Please provide a clear explanation
                    for this update.
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
                <template v-if="error.includes('Concurrent edit')">
                  <v-btn
                    color="white"
                    variant="outlined"
                    class="mt-2"
                    prepend-icon="mdi-refresh"
                    @click="loadPhenopacket"
                  >
                    Reload Latest Version
                  </v-btn>
                </template>
              </v-alert>

              <!-- Actions -->
              <v-card-actions>
                <v-btn color="primary" type="submit" :loading="saving" size="large">
                  <v-icon left>mdi-content-save</v-icon>
                  {{ isEditing ? 'Update' : 'Create' }} Phenopacket
                </v-btn>
                <v-btn size="large" @click="$router.push('/phenopackets')"> Cancel </v-btn>
              </v-card-actions>
            </v-col>

            <!-- Sticky completeness rail -->
            <v-col cols="12" md="4">
              <CompletenessRail
                :phenopacket="phenopacket"
                :phenotypes-completeness="phenotypesCompleteness"
                @navigate="onRailNavigate"
              />
            </v-col>
          </v-row>
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
import CurationSection from '@/components/curation/CurationSection.vue';
import CompletenessRail from '@/components/curation/CompletenessRail.vue';
import { computeSectionCompleteness } from '@/utils/curationFields';

export default {
  name: 'PhenopacketCreateEdit',
  components: {
    PhenotypicFeaturesSection,
    VariantAnnotationForm,
    CurationSection,
    CompletenessRail,
  },
  // Vue Router 4-style in-component guard (works with the Options API used
  // throughout this file). Prompts on navigate-away only when the live form
  // state has actually diverged from what was loaded/initialized, and never
  // on the save flow's own post-success redirect (see `justSaved`).
  beforeRouteLeave(to, from, next) {
    if (this.justSaved || !this.hasUnsavedChanges()) {
      next();
      return;
    }
    const leave = window.confirm('You have unsaved changes. Leave without saving?');
    next(leave);
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
      // Editor-only state. Deliberately NOT on `phenopacket`: `publications` is
      // not a Phenopackets v2 field, and buildSubmissionPhenopacket spreads that
      // object wholesale. PMIDs are promoted to metaData.externalReferences on save.
      publications: [],
      loading: true, // Start with loading true to prevent form flash
      saving: false,
      error: null,
      formSubmitted: false,
      revision: null, // For optimistic locking
      changeReason: '', // For audit trail
      // Saved record state for toast message selection
      savedRecordState: null,
      // Unsaved-changes guard (curation console Task 3, design spec §5): a
      // JSON snapshot of {phenopacket, publications} taken right after the
      // form finishes loading/initializing. beforeRouteLeave diffs the live
      // state against this to decide whether to prompt.
      initialSnapshot: null,
      // Set true immediately before the post-save navigation so
      // beforeRouteLeave doesn't prompt on the save flow's own redirect.
      justSaved: false,
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
    // Per-section completeness for the sections whose fields live in the
    // shared CURATION_FIELDS registry (curationFields.js). All report 0/0
    // until Tasks 4-8 register fields against these section ids -- that is
    // correct, not a bug: the registry is the single source of truth, so
    // these badges (and the CompletenessRail row below) update automatically
    // once later tasks push entries in, with no further changes here.
    caseCompleteness() {
      return computeSectionCompleteness(this.phenopacket, 'case');
    },
    variantCompleteness() {
      return computeSectionCompleteness(this.phenopacket, 'variant');
    },
    classificationCompleteness() {
      return computeSectionCompleteness(this.phenopacket, 'classification');
    },
    ageCompleteness() {
      return computeSectionCompleteness(this.phenopacket, 'age');
    },
    provenanceCompleteness() {
      return computeSectionCompleteness(this.phenopacket, 'provenance');
    },
    // Phenotypes is deliberately NOT in CURATION_FIELDS (its completeness is
    // dynamic per-case -- see curationFields.js). This is a naive stand-in
    // (present/total feature count) until Task 7 wires the real tri-state
    // count; kept intentionally simple since Task 7 replaces it wholesale.
    // TODO(Task 7): replace with the real present/excluded/unknown count.
    phenotypesCompleteness() {
      const features = this.phenopacket.phenotypicFeatures || [];
      return { filled: features.length, total: features.length };
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
      // Create mode - hide loader and show empty form
      this.loading = false;
      // Leave ID empty for user to specify (required field will enforce entry)
      this.phenopacket.id = '';
    }

    // Snapshot the settled initial state for the unsaved-changes guard. Taken
    // after both branches above so it reflects the actually-loaded record in
    // edit mode, not the placeholder pre-load shape.
    this.captureSnapshot();
  },
  methods: {
    captureSnapshot() {
      this.initialSnapshot = JSON.stringify({
        phenopacket: this.phenopacket,
        publications: this.publications,
      });
    },
    hasUnsavedChanges() {
      if (this.initialSnapshot === null) return false;
      const current = JSON.stringify({
        phenopacket: this.phenopacket,
        publications: this.publications,
      });
      return current !== this.initialSnapshot;
    },
    async loadPhenopacket() {
      this.loading = true;
      this.error = null;

      try {
        const response = await getPhenopacket(this.$route.params.phenopacket_id);

        // Backend returns full phenopacket response with metadata
        this.phenopacket = response.data.phenopacket;

        // Enable optimistic locking by capturing current revision
        this.revision = response.data.revision;

        // Capture state for toast message selection (Wave 7/D.1 §9.2)
        this.savedRecordState = response.data.state ?? null;

        // Load existing publications into the same state the template and
        // submit path use so edits stay round-trippable.
        this.publications = (this.phenopacket.metaData?.externalReferences || [])
          .filter((ref) => ref.id?.startsWith('PMID:'))
          .map((ref) => ({
            pmid: ref.id.replace('PMID:', ''),
          }));

        window.logService.info('Phenopacket loaded for editing', {
          phenopacketId: this.phenopacket.id,
          revision: this.revision,
          publicationsLoaded: this.publications.length,
        });

        // Re-baseline the unsaved-changes snapshot here too: this method is
        // also called directly from the "Reload Latest Version" button after
        // a 409 conflict, which replaces `phenopacket` wholesale without a
        // remount. Without this, reloading would itself look like an
        // unsaved change relative to the stale mount-time snapshot.
        this.captureSnapshot();
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
      this.publications.push({ pmid: '' });
    },

    removePublication(index) {
      this.publications.splice(index, 1);
    },

    buildSubmissionPhenopacket() {
      // `publications` is destructured out and discarded: it is not a Phenopackets
      // v2 field, and records saved before this fix may carry it in the loaded
      // document. `this.publications` (component state) is the source of truth.
      const { publications: _legacyPublications, ...phenopacket } = this.phenopacket;

      const existingReferences = phenopacket.metaData?.externalReferences || [];
      const nonPmidExternalReferences = existingReferences.filter(
        (ref) => !ref.id?.startsWith('PMID:')
      );
      const pmidExternalReferences = this.publications
        .map((pub) => `${pub.pmid || ''}`.trim())
        .filter(Boolean)
        .map((pmid) => ({ id: `PMID:${pmid}` }));

      return {
        ...phenopacket,
        metaData: {
          ...(phenopacket.metaData || {}),
          externalReferences: [...nonPmidExternalReferences, ...pmidExternalReferences],
        },
      };
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
        const phenopacketPayload = this.buildSubmissionPhenopacket();

        if (this.isEditing) {
          // Update existing phenopacket with optimistic locking and audit trail
          result = await updatePhenopacket(this.phenopacket.id, {
            phenopacket: phenopacketPayload,
            revision: this.revision,
            change_reason: this.changeReason,
          });

          window.logService.info('Phenopacket updated successfully', {
            phenopacketId: result.data.phenopacket_id,
            revision: this.revision,
            changeReasonLength: this.changeReason.length,
          });

          // Wave 7/D.1 §9.2: context-sensitive toast after PUT.
          // Pass the message via router state so it survives navigation and is
          // displayed on the detail page (this view unmounts on push, so a
          // local snackbar would never be visible).
          const recordState = this.savedRecordState;
          const toastMsg =
            recordState === 'published'
              ? 'Draft saved — submit for review when ready.'
              : 'Draft updated.';
          window.logService.info('Navigating to detail with save toast', { recordState, toastMsg });
          // Mark as saved BEFORE navigating so beforeRouteLeave's diff check
          // doesn't prompt "unsaved changes" on this success redirect.
          this.justSaved = true;
          // Navigate to detail page using phenopacket_id (not database id)
          this.$router.push({
            path: `/phenopackets/${result.data.phenopacket_id}`,
            state: { toast: toastMsg },
          });
          return;
        } else {
          // Create new phenopacket
          result = await createPhenopacket({
            phenopacket: phenopacketPayload,
          });

          window.logService.info('Phenopacket created successfully', {
            phenopacketId: result.data.phenopacket_id,
          });
        }

        // Mark as saved BEFORE navigating -- see the comment on the isEditing
        // branch's push above.
        this.justSaved = true;
        // Navigate to detail page using phenopacket_id (not database id)
        this.$router.push(`/phenopackets/${result.data.phenopacket_id}`);
      } catch (err) {
        // Handle concurrent edit conflicts (409 Conflict).
        // Wave 7 D.1 envelope: {code: "revision_mismatch", message: "..."}
        if (err.response?.status === 409) {
          const errorDetail = err.response?.data?.detail;
          // New shape (Wave 7 D.1): {code, message}
          const errorCode = errorDetail?.code;
          const errorMessage = errorDetail?.message;

          if (errorCode === 'revision_mismatch' && errorMessage) {
            this.error = `Concurrent edit detected: ${errorMessage}. Click "Reload" to get the latest version.`;
          } else {
            this.error =
              'This phenopacket was modified by another user. Click "Reload" to see the latest version and try again.';
          }

          window.logService.warn('Concurrent edit detected', {
            phenopacketId: this.phenopacket.id,
            revision: this.revision,
            errorCode,
            errorMessage,
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

    // CompletenessRail owns none of the CurationSection refs (it only knows
    // section ids), so it emits @navigate and this view -- which does hold
    // the refs -- force-expands the target section. Scrolling is handled by
    // CompletenessRail itself via useAccessibleScroll.
    onRailNavigate(sectionId) {
      const sectionRefs = {
        case: this.$refs.caseSection,
        variant: this.$refs.variantSection,
        classification: this.$refs.classificationSection,
        phenotypes: this.$refs.phenotypesSection,
        age: this.$refs.ageSection,
        provenance: this.$refs.provenanceSection,
      };
      const section = sectionRefs[sectionId];
      if (section && typeof section.expand === 'function') {
        section.expand();
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
