<!-- src/components/curation/BulkImportWorkbenchDialog.vue -->
<template>
  <div class="bulk-import-workbench-container">
    <v-btn
      color="primary"
      variant="outlined"
      prepend-icon="mdi-file-upload-outline"
      data-testid="bulk-import-workbench-btn"
      @click="isOpen = true"
    >
      Bulk Import Workbench
    </v-btn>

    <v-dialog
      v-model="isOpen"
      max-width="960"
      scrollable
      data-testid="bulk-import-workbench-dialog"
    >
      <v-card>
        <v-toolbar color="surface" density="compact" class="border-b px-4">
          <v-icon icon="mdi-file-upload-outline" class="mr-2" color="primary" />
          <v-toolbar-title class="text-subtitle-1 font-weight-bold">
            Bulk Import Dry-Run & Validation Workbench
          </v-toolbar-title>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="isOpen = false" />
        </v-toolbar>

        <v-card-text class="pa-4">
          <div class="mb-4">
            <div class="text-body-2 text-medium-emphasis mb-2">
              Paste a JSON array of Phenopackets v2 records (or a
              <code>{"phenopackets": [...]}</code> wrapper) to validate and dry-run import.
            </div>
            <v-textarea
              v-model="jsonInput"
              label="Phenopackets JSON Payload"
              :placeholder="placeholderText"
              rows="6"
              variant="outlined"
              density="comfortable"
              data-testid="batch-json-input"
            />
          </div>

          <!-- Error Alert -->
          <v-alert
            v-if="parseError || apiError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            {{ parseError || apiError }}
          </v-alert>

          <!-- Success Alert -->
          <v-alert
            v-if="successMessage"
            type="success"
            variant="tonal"
            density="compact"
            class="mb-4"
          >
            {{ successMessage }}
          </v-alert>

          <!-- Report preview -->
          <div v-if="report" class="mt-4" data-testid="batch-report-table">
            <div class="d-flex align-center justify-space-between mb-3">
              <h3 class="text-subtitle-1 font-weight-bold">
                Dry-Run Validation Report
              </h3>
              <div class="d-flex ga-2">
                <v-chip size="small" variant="outlined">
                  Total: {{ report.total_rows }}
                </v-chip>
                <v-chip size="small" color="success" variant="flat">
                  Valid: {{ report.valid_rows }}
                </v-chip>
                <v-chip
                  size="small"
                  :color="report.invalid_rows > 0 ? 'error' : 'default'"
                  variant="flat"
                >
                  Invalid: {{ report.invalid_rows }}
                </v-chip>
              </div>
            </div>

            <v-table density="compact" class="border rounded">
              <thead>
                <tr>
                  <th class="text-left">#</th>
                  <th class="text-left">Phenopacket ID</th>
                  <th class="text-left">Subject ID</th>
                  <th class="text-left">Status</th>
                  <th class="text-left">Validation Notes / Errors</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in report.results" :key="row.row_index">
                  <td>{{ row.row_index + 1 }}</td>
                  <td class="font-mono font-weight-medium">
                    {{ row.phenopacket_id || '-' }}
                  </td>
                  <td class="font-mono">{{ row.subject_id || '-' }}</td>
                  <td>
                    <v-chip
                      size="x-small"
                      :color="row.valid ? 'success' : 'error'"
                      variant="flat"
                      class="text-uppercase font-weight-bold"
                    >
                      {{ row.valid ? 'Valid' : 'Invalid' }}
                    </v-chip>
                  </td>
                  <td>
                    <div v-if="row.valid && !row.errors.length" class="text-caption text-success">
                      Ready to import
                    </div>
                    <ul v-else class="text-caption text-error pl-3">
                      <li v-for="(err, eIdx) in row.errors" :key="eIdx">
                        {{ err }}
                      </li>
                    </ul>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>

        <v-card-actions class="pa-4 border-t bg-surface d-flex justify-space-between">
          <v-btn
            color="primary"
            variant="tonal"
            :loading="validating"
            data-testid="run-dry-run-btn"
            @click="runDryRun"
          >
            Run Dry-Run Preview
          </v-btn>

          <v-btn
            color="success"
            variant="flat"
            :disabled="!canCommit"
            :loading="committing"
            data-testid="commit-batch-btn"
            @click="commitBatch"
          >
            Commit Approved Rows as Drafts ({{ report?.valid_rows || 0 }})
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { apiClient } from '@/api';

const emit = defineEmits(['import-complete']);

const isOpen = ref(false);
const placeholderText =
  '[ { "id": "SAMPLE-01", "subject": { "id": "SUBJ-01", "sex": "MALE" } } ]';
const jsonInput = ref('');
const validating = ref(false);
const committing = ref(false);
const parseError = ref(null);
const apiError = ref(null);
const successMessage = ref(null);
const report = ref(null);

const canCommit = computed(() => {
  return report.value && report.value.valid_rows > 0 && !committing.value;
});

function validatePayload() {
  parseError.value = null;
  apiError.value = null;
  successMessage.value = null;

  if (!jsonInput.value.trim()) {
    parseError.value = 'Please paste a JSON array of phenopackets.';
    return null;
  }

  try {
    const parsed = JSON.parse(jsonInput.value.trim());
    const phenopackets = Array.isArray(parsed) ? parsed : parsed.phenopackets;
    if (!Array.isArray(phenopackets) || phenopackets.length === 0) {
      parseError.value =
        'Payload must be a non-empty array or an object with a "phenopackets" array.';
      return null;
    }
    return phenopackets;
  } catch (err) {
    parseError.value = `Malformed JSON: ${err.message}`;
    return null;
  }
}

async function runDryRun() {
  const phenopackets = validatePayload();
  if (!phenopackets) return;

  validating.value = true;
  apiError.value = null;
  report.value = null;

  try {
    const response = await apiClient.post(
      '/phenopackets/import-batch',
      { phenopackets },
      { params: { dry_run: true } }
    );
    report.value = response.data;
  } catch (err) {
    apiError.value =
      err.response?.data?.detail || err.message || 'Dry-run execution failed';
    if (window.logService?.error) {
      window.logService.error('Bulk import dry-run failed', { error: err });
    }
  } finally {
    validating.value = false;
  }
}

async function commitBatch() {
  const phenopackets = validatePayload();
  if (!phenopackets) return;

  committing.value = true;
  apiError.value = null;
  successMessage.value = null;

  try {
    const response = await apiClient.post(
      '/phenopackets/import-batch',
      { phenopackets },
      { params: { dry_run: false } }
    );
    report.value = response.data;
    const committed = response.data?.committed_rows || 0;
    successMessage.value = `Successfully committed ${committed} phenopacket${
      committed === 1 ? '' : 's'
    } as drafts.`;
    emit('import-complete', response.data);
  } catch (err) {
    apiError.value =
      err.response?.data?.detail || err.message || 'Batch commit failed';
    if (window.logService?.error) {
      window.logService.error('Bulk import commit failed', { error: err });
    }
  } finally {
    committing.value = false;
  }
}
</script>

<style scoped>
.font-mono {
  font-family: monospace;
}
</style>
