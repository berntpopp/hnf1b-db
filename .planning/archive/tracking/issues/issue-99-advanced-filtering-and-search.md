# Issue #92: feat(frontend): add advanced filtering and search to variant view

## Summary

Add filter sidebar and search bar to variant view to quickly find relevant variants.

**Current:** All 200+ variants shown, pagination only
**Target:** Filters (type, pathogenicity, consequence, domain) + full-text search

## Implementation

### 1. Create Filter Sidebar

**File:** `frontend/src/components/variant/VariantFilterSidebar.vue` (NEW)

```vue
<template>
  <v-navigation-drawer v-model="isOpen" location="right" width="400">
    <v-toolbar color="primary" dark>
      <v-toolbar-title>Filter Variants</v-toolbar-title>
      <v-btn icon @click="isOpen = false"><v-icon>mdi-close</v-icon></v-btn>
    </v-toolbar>

    <v-container>
      <!-- Variant Type -->
      <v-card class="mb-4">
        <v-card-title>Variant Type</v-card-title>
        <v-card-text>
          <v-checkbox v-model="filters.types" label="SNV" value="SNV" />
          <v-checkbox v-model="filters.types" label="CNV Deletion" value="CNV_DEL" />
          <v-checkbox v-model="filters.types" label="CNV Duplication" value="CNV_DUP" />
        </v-card-text>
      </v-card>

      <!-- Pathogenicity -->
      <v-card class="mb-4">
        <v-card-title>Pathogenicity</v-card-title>
        <v-card-text>
          <v-chip-group v-model="filters.pathogenicity" multiple column>
            <v-chip value="Pathogenic" color="error" filter>Pathogenic</v-chip>
            <v-chip value="Likely pathogenic" color="warning" filter>Likely pathogenic</v-chip>
            <v-chip value="VUS" color="info" filter>VUS</v-chip>
            <v-chip value="Benign" color="success" filter>Benign</v-chip>
          </v-chip-group>
        </v-card-text>
      </v-card>

      <!-- Consequence -->
      <v-card class="mb-4">
        <v-card-title>Molecular Consequence</v-card-title>
        <v-card-text>
          <v-select
            v-model="filters.consequences"
            :items="['Frameshift', 'Nonsense', 'Missense', 'Splice site', 'Synonymous']"
            multiple
            chips
          />
        </v-card-text>
      </v-card>

      <!-- Domain -->
      <v-card class="mb-4">
        <v-card-title>Functional Domain</v-card-title>
        <v-card-text>
          <v-select
            v-model="filters.domains"
            :items="['Dimerization (1-80)', 'POU-specific (81-215)', 'POU-homeodomain (216-280)', 'Transactivation (281-557)']"
            multiple
            chips
          />
        </v-card-text>
      </v-card>
    </v-container>

    <v-card-actions class="pa-4">
      <v-btn block color="primary" @click="applyFilters">Apply Filters</v-btn>
      <v-btn block variant="outlined" @click="resetFilters">Reset</v-btn>
    </v-card-actions>
  </v-navigation-drawer>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['apply-filters'])

const filters = ref({
  types: [],
  pathogenicity: [],
  consequences: [],
  domains: []
})

function applyFilters() {
  emit('apply-filters', filters.value)
}

function resetFilters() {
  filters.value = { types: [], pathogenicity: [], consequences: [], domains: [] }
  applyFilters()
