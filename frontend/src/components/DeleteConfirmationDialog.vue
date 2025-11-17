<template>
  <v-dialog v-model="dialogVisible" max-width="600" persistent>
    <v-card>
      <v-card-title class="text-h5 bg-error text-white">
        <v-icon left class="mr-2">mdi-alert-circle</v-icon>
        Confirm Deletion
      </v-card-title>

      <v-card-text class="pt-6">
        <!-- Warning Message -->
        <v-alert type="warning" variant="tonal" class="mb-4">
          <v-alert-title>This action cannot be undone</v-alert-title>
          You are about to delete this phenopacket. This will remove it from the active database,
          though it will be preserved in the audit trail.
        </v-alert>

        <!-- Phenopacket Information -->
        <v-card variant="outlined" class="mb-4">
          <v-card-text>
            <div class="text-subtitle-2 text-grey-darken-1 mb-2">Phenopacket to be deleted:</div>
            <div class="text-body-1 font-weight-medium mb-1">
              <v-icon size="small" class="mr-1">mdi-identifier</v-icon>
              {{ phenopacketId }}
            </div>
            <div v-if="subjectId" class="text-body-2 text-grey-darken-2">
              <v-icon size="small" class="mr-1">mdi-account</v-icon>
              Subject: {{ subjectId }}
            </div>
          </v-card-text>
        </v-card>

        <!-- Deletion Reason Input -->
        <v-text-field
          v-model="deleteReason"
          label="Reason for deletion *"
          placeholder="e.g., Duplicate entry, Data error, Patient request"
          variant="outlined"
          color="error"
          :rules="[rules.required, rules.minLength]"
          hint="Required for audit trail. Please provide a clear explanation."
          persistent-hint
          autofocus
          @keyup.enter="handleConfirm"
        >
          <template #prepend-inner>
            <v-icon>mdi-text-box</v-icon>
          </template>
        </v-text-field>

        <!-- Example Reasons -->
        <div class="mt-2">
          <div class="text-caption text-grey-darken-1 mb-1">Common reasons:</div>
          <v-chip
            v-for="example in exampleReasons"
            :key="example"
            size="small"
            class="mr-1 mb-1"
            @click="deleteReason = example"
          >
            {{ example }}
          </v-chip>
        </div>
      </v-card-text>

      <v-divider />

      <v-card-actions class="px-6 py-4">
        <v-spacer />
        <v-btn color="grey" variant="text" @click="handleCancel"> Cancel </v-btn>
        <v-btn
          color="error"
          variant="flat"
          :disabled="!isValidReason"
          :loading="loading"
          @click="handleConfirm"
        >
          <v-icon left>mdi-delete</v-icon>
          Delete Phenopacket
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
  name: 'DeleteConfirmationDialog',

  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
    phenopacketId: {
      type: String,
      required: true,
    },
    subjectId: {
      type: String,
      default: null,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['update:modelValue', 'confirm', 'cancel'],

  data() {
    return {
      deleteReason: '',
      exampleReasons: [
        'Duplicate entry',
        'Data error',
        'Invalid data',
        'Patient request',
        'Testing data',
      ],
      rules: {
        required: (v) => !!v || 'Deletion reason is required',
        minLength: (v) => (v && v.length >= 5) || 'Reason must be at least 5 characters',
      },
    };
  },

  computed: {
    dialogVisible: {
      get() {
        return this.modelValue;
      },
      set(value) {
        this.$emit('update:modelValue', value);
      },
    },
    isValidReason() {
      return this.deleteReason && this.deleteReason.length >= 5;
    },
  },

  watch: {
    modelValue(newVal) {
      if (!newVal) {
        // Reset form when dialog closes
        this.deleteReason = '';
      }
    },
  },

  methods: {
    handleConfirm() {
      if (!this.isValidReason) return;

      window.logService.info('Delete confirmation received', {
        phenopacketId: this.phenopacketId,
        reasonLength: this.deleteReason.length,
      });

      this.$emit('confirm', this.deleteReason);
    },

    handleCancel() {
      window.logService.debug('Delete cancelled by user', {
        phenopacketId: this.phenopacketId,
      });

      this.deleteReason = '';
      this.$emit('cancel');
      this.$emit('update:modelValue', false);
    },
  },
};
</script>

<style scoped>
.bg-error {
  background-color: rgb(var(--v-theme-error)) !important;
}
</style>
