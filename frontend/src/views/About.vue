<!-- src/views/About.vue -->
<template>
  <v-container class="py-8">
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <!-- Page Header -->
        <div class="text-center mb-8">
          <v-avatar color="teal" size="80" class="mb-4">
            <v-icon size="48" color="white">mdi-information-outline</v-icon>
          </v-avatar>
          <h1 class="text-h3 font-weight-bold text-grey-darken-3 mb-2">About HNF1B Database</h1>
          <p class="text-h6 text-grey-darken-1">
            A curated resource for HNF1B-related clinical and genetic data
          </p>
        </div>

        <!-- Background Section -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-teal-lighten-5">
            <v-icon left color="teal">mdi-book-open-variant</v-icon>
            Background
          </v-card-title>
          <v-card-text class="text-body-1 pa-6">
            <p class="mb-4">
              Pathogenic variants in <strong>HNF1B</strong> (Hepatocyte Nuclear Factor 1-Beta) are
              associated with a variety of inherited kidney diseases including:
            </p>
            <v-list density="compact" class="mb-4">
              <v-list-item>
                <template #prepend>
                  <v-icon color="teal" size="small">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>
                  <strong>RCAD</strong> - Renal Cysts and Diabetes Syndrome
                </v-list-item-title>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="teal" size="small">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>
                  <strong>CAKUT</strong> - Congenital Anomalies of Kidney and Urinary Tract
                </v-list-item-title>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="teal" size="small">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>
                  <strong>ADTKD</strong> - Autosomal Dominant Tubulointerstitial Kidney Disease
                </v-list-item-title>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="teal" size="small">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>
                  <strong>MODY5</strong> - Maturity-Onset Diabetes of the Young, type 5
                </v-list-item-title>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="teal" size="small">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>
                  <strong>17q12 Deletion Syndrome</strong>
                </v-list-item-title>
              </v-list-item>
            </v-list>
            <p>
              Variable extrarenal manifestations have also been linked to HNF1B defects, including
              genital tract abnormalities, gout, pancreatic insufficiency, electrolyte
              abnormalities, liver disease, and neuropsychological disorders.
            </p>
          </v-card-text>
        </v-card>

        <!-- Mission Section -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-blue-lighten-5">
            <v-icon left color="blue">mdi-target</v-icon>
            Mission
          </v-card-title>
          <v-card-text class="text-body-1 pa-6">
            <p class="mb-4">
              Although high-throughput sequencing has greatly advanced diagnostic variant detection,
              there is a lack of specific databases gathering both genotypic and phenotypic
              information to establish valid genotype-phenotype correlations.
            </p>
            <p>
              By introducing the <strong>HNF1B Database</strong>, we aim to gather published and
              unpublished cases for identification of reliable variant-disease associations,
              ultimately improving clinical management and genetic counseling.
            </p>
          </v-card-text>
        </v-card>

        <!-- Methods Section -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-purple-lighten-5">
            <v-icon left color="purple">mdi-flask</v-icon>
            Methodology
          </v-card-title>
          <v-card-text class="pa-6">
            <v-row>
              <v-col cols="12" md="6">
                <div class="d-flex align-start mb-4">
                  <v-avatar color="purple-lighten-4" size="40" class="mr-3">
                    <v-icon color="purple-darken-2">mdi-file-document-multiple</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">Systematic Literature Review</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Comprehensive review of all published cases with HNF1B-associated disease from
                      1997 onwards.
                    </p>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="d-flex align-start mb-4">
                  <v-avatar color="purple-lighten-4" size="40" class="mr-3">
                    <v-icon color="purple-darken-2">mdi-account-group</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">Unpublished Cohorts</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Integration of locally recruited cohorts with comprehensive clinical and
                      genetic data.
                    </p>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="d-flex align-start">
                  <v-avatar color="purple-lighten-4" size="40" class="mr-3">
                    <v-icon color="purple-darken-2">mdi-medical-bag</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">HPO Ontology</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Phenotypes annotated using Human Phenotype Ontology (HPO) terms for
                      standardized clinical characterization.
                    </p>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="d-flex align-start">
                  <v-avatar color="purple-lighten-4" size="40" class="mr-3">
                    <v-icon color="purple-darken-2">mdi-dna</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">Variant Harmonization</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Variants harmonized to HGVS nomenclature (NM_000458.4) with ACMG/AMP
                      classification.
                    </p>
                  </div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Data Standards Section -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-green-lighten-5">
            <v-icon left color="green">mdi-database-check</v-icon>
            Data Standards
          </v-card-title>
          <v-card-text class="pa-6">
            <v-row>
              <v-col cols="12" md="6">
                <div class="d-flex align-start mb-4">
                  <v-avatar color="green-lighten-4" size="40" class="mr-3">
                    <v-icon color="green-darken-2">mdi-card-account-details</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">GA4GH Phenopackets v2</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      All clinical data stored using the international standard for phenotypic data
                      exchange.
                    </p>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="d-flex align-start mb-4">
                  <v-avatar color="green-lighten-4" size="40" class="mr-3">
                    <v-icon color="green-darken-2">mdi-dna</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">VRS 2.0 Compliant</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Variant representations follow the GA4GH Variation Representation
                      Specification.
                    </p>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="d-flex align-start">
                  <v-avatar color="green-lighten-4" size="40" class="mr-3">
                    <v-icon color="green-darken-2">mdi-api</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">Open REST API</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Programmatic access via JSON:API v1.1 compliant endpoints.
                    </p>
                  </div>
                </div>
              </v-col>
              <v-col cols="12" md="6">
                <div class="d-flex align-start">
                  <v-avatar color="green-lighten-4" size="40" class="mr-3">
                    <v-icon color="green-darken-2">mdi-code-braces</v-icon>
                  </v-avatar>
                  <div>
                    <h4 class="text-subtitle-1 font-weight-bold">Open Source</h4>
                    <p class="text-body-2 text-grey-darken-1">
                      Built with Vue.js 3, FastAPI, and PostgreSQL. Source code available on GitHub.
                    </p>
                  </div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- How to Cite Section -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-amber-lighten-5">
            <v-icon left color="amber-darken-2">mdi-format-quote-close</v-icon>
            How to Cite
          </v-card-title>
          <v-card-text class="pa-6">
            <p class="text-body-1 mb-4">
              If you use data from the HNF1B Database in your research, please cite:
            </p>
            <v-sheet color="grey-lighten-4" rounded class="pa-4 mb-4">
              <p class="text-body-2 mb-2"><strong>APA 7th Edition:</strong></p>
              <p class="text-body-2 font-italic mb-0">
                HNF1B Database. (2025).
                <em>HNF1B Database: Clinical phenotype and variant registry</em>.
                <a href="https://hnf1b.org" target="_blank">https://hnf1b.org</a>
              </p>
            </v-sheet>
            <v-sheet color="grey-lighten-4" rounded class="pa-4">
              <p class="text-body-2 mb-2"><strong>BibTeX:</strong></p>
              <pre
                class="text-body-2"
                style="white-space: pre-wrap; font-family: monospace; margin: 0"
                >{{ bibtexCitation }}</pre
              >
            </v-sheet>
          </v-card-text>
        </v-card>

        <!-- Contact & Contributing Section -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-orange-lighten-5">
            <v-icon left color="orange">mdi-account-group</v-icon>
            Contributing
          </v-card-title>
          <v-card-text class="pa-6">
            <p class="text-body-1 mb-4">
              We welcome contributions from the clinical and research community. If you have:
            </p>
            <v-list density="compact">
              <v-list-item>
                <template #prepend>
                  <v-icon color="orange" size="small">mdi-plus-circle</v-icon>
                </template>
                <v-list-item-title>New cases with HNF1B variants</v-list-item-title>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="orange" size="small">mdi-pencil</v-icon>
                </template>
                <v-list-item-title>Corrections or updates to existing data</v-list-item-title>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="orange" size="small">mdi-file-document</v-icon>
                </template>
                <v-list-item-title>Published literature not yet included</v-list-item-title>
              </v-list-item>
            </v-list>
            <v-divider class="my-4" />
            <p class="text-body-2 text-grey-darken-1">
              Please contact us via
              <a href="https://github.com/berntpopp/hnf1b-db/issues" target="_blank">
                GitHub Issues
              </a>
              or submit a pull request.
            </p>
          </v-card-text>
        </v-card>

        <!-- License Section -->
        <v-card elevation="2">
          <v-card-title class="bg-grey-lighten-4">
            <v-icon left color="grey-darken-2">mdi-license</v-icon>
            License
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="d-flex align-center">
              <v-img
                src="https://licensebuttons.net/l/by/4.0/88x31.png"
                alt="CC BY 4.0"
                max-width="88"
                class="mr-4"
              />
              <div>
                <p class="text-body-1 mb-2">
                  This work is licensed under a
                  <a
                    href="https://creativecommons.org/licenses/by/4.0/"
                    target="_blank"
                    rel="noopener"
                  >
                    Creative Commons Attribution 4.0 International License </a
                  >.
                </p>
                <p class="text-body-2 text-grey-darken-1 mb-0">
                  You are free to share and adapt the data with proper attribution.
                </p>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { computed } from 'vue';

// Computed property for current date in YYYY-MM-DD format
const currentDate = computed(() => {
  return new Date().toISOString().split('T')[0];
});

// BibTeX citation with proper escaping (double braces for corporate author)
const bibtexCitation = computed(() => {
  return `@misc{hnf1b_database_2025,
  author = {{HNF1B Database}},
  title = {HNF1B Database: Clinical Phenotype and Variant Registry},
  year = {2025},
  url = {https://hnf1b.org},
  note = {Accessed: ${currentDate.value}}
}`;
});
</script>
