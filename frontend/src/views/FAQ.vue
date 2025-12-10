<!-- src/views/FAQ.vue -->
<template>
  <v-container class="py-8">
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <!-- Page Header -->
        <div class="text-center mb-8">
          <v-avatar color="blue" size="80" class="mb-4">
            <v-icon size="48" color="white">mdi-frequently-asked-questions</v-icon>
          </v-avatar>
          <h1 class="text-h3 font-weight-bold text-grey-darken-3 mb-2">
            Frequently Asked Questions
          </h1>
          <p class="text-h6 text-grey-darken-1">
            Common questions about HNF1B-related disease and our database
          </p>
        </div>

        <!-- FAQ Expansion Panels -->
        <v-expansion-panels variant="accordion" class="mb-6">
          <!-- About HNF1B Disease -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="teal" class="mr-3">mdi-help-circle</v-icon>
              What is HNF1B-related disease?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">
                HNF1B-related disease refers to a spectrum of conditions caused by pathogenic
                variants in the <strong>HNF1B</strong> gene (Hepatocyte Nuclear Factor 1-Beta), also
                known as TCF2 (Transcription Factor 2). HNF1B is a transcription factor crucial for
                the development and function of the kidney, liver, intestine, and pancreatic beta
                cells.
              </p>
              <p class="mb-3">Associated conditions include:</p>
              <ul class="mb-3">
                <li>
                  <strong>RCAD</strong> (Renal Cysts and Diabetes Syndrome) - the most common
                  presentation
                </li>
                <li><strong>MODY5</strong> (Maturity-Onset Diabetes of the Young, type 5)</li>
                <li>
                  <strong>17q12 Deletion Syndrome</strong> - often includes neurodevelopmental
                  features
                </li>
                <li>
                  <strong>ADTKD</strong> (Autosomal Dominant Tubulointerstitial Kidney Disease)
                </li>
                <li><strong>CAKUT</strong> (Congenital Anomalies of Kidney and Urinary Tract)</li>
              </ul>
              <p>
                The condition follows autosomal dominant inheritance, though approximately 50% of
                cases occur de novo (new mutations not inherited from parents).
              </p>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Phenotypic Variability -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="teal" class="mr-3">mdi-help-circle</v-icon>
              What symptoms are associated with HNF1B variants?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">
                HNF1B-related disease shows remarkable phenotypic variability. Common manifestations
                include:
              </p>
              <v-row>
                <v-col cols="12" md="6">
                  <h4 class="text-subtitle-2 font-weight-bold mb-2">Renal Features</h4>
                  <ul class="mb-3">
                    <li>Renal cysts (most common)</li>
                    <li>Renal hypoplasia/dysplasia</li>
                    <li>Chronic kidney disease</li>
                    <li>Hyperuricemia/Gout</li>
                    <li>Hypomagnesemia</li>
                  </ul>
                </v-col>
                <v-col cols="12" md="6">
                  <h4 class="text-subtitle-2 font-weight-bold mb-2">Extrarenal Features</h4>
                  <ul class="mb-3">
                    <li>Diabetes mellitus (MODY5)</li>
                    <li>Pancreatic hypoplasia</li>
                    <li>Genital tract abnormalities</li>
                    <li>Liver abnormalities</li>
                    <li>Neurodevelopmental delay (especially in 17q12 deletions)</li>
                  </ul>
                </v-col>
              </v-row>
              <v-alert type="info" density="compact" variant="tonal" class="mt-2">
                Genotype-phenotype correlations suggest that variant type (CNV vs. missense vs.
                truncating) influences which features predominate.
              </v-alert>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Variant Types -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="teal" class="mr-3">mdi-help-circle</v-icon>
              What types of HNF1B variants are there?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">HNF1B variants fall into several categories:</p>
              <v-list density="compact">
                <v-list-item>
                  <template #prepend>
                    <v-chip color="error" size="small" class="mr-2">CNV</v-chip>
                  </template>
                  <v-list-item-title class="font-weight-bold">
                    17q12 Deletion/Duplication
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    Large ~1.4Mb deletions affecting HNF1B and neighboring genes. Most common
                    variant type (~45% of cases).
                  </v-list-item-subtitle>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-chip color="warning" size="small" class="mr-2">SNV</v-chip>
                  </template>
                  <v-list-item-title class="font-weight-bold">Missense Variants</v-list-item-title>
                  <v-list-item-subtitle>
                    Single amino acid changes. May have dominant-negative effects on protein
                    function.
                  </v-list-item-subtitle>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-chip color="purple" size="small" class="mr-2">SNV</v-chip>
                  </template>
                  <v-list-item-title class="font-weight-bold"
                    >Truncating Variants</v-list-item-title
                  >
                  <v-list-item-subtitle>
                    Frameshift, nonsense, or splice site variants causing premature protein
                    termination.
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- About Database -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="blue" class="mr-3">mdi-help-circle</v-icon>
              What data does this database contain?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">The HNF1B Database currently contains:</p>
              <v-row class="mb-4">
                <v-col cols="6" md="3">
                  <v-card color="teal-lighten-5" flat class="pa-3 text-center">
                    <div class="text-h4 font-weight-bold text-teal">864</div>
                    <div class="text-caption">Individuals</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card color="pink-lighten-5" flat class="pa-3 text-center">
                    <div class="text-h4 font-weight-bold text-pink">198</div>
                    <div class="text-caption">Unique Variants</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card color="blue-lighten-5" flat class="pa-3 text-center">
                    <div class="text-h4 font-weight-bold text-blue">141</div>
                    <div class="text-caption">Publications</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card color="purple-lighten-5" flat class="pa-3 text-center">
                    <div class="text-h4 font-weight-bold text-purple">36</div>
                    <div class="text-caption">HPO Phenotypes</div>
                  </v-card>
                </v-col>
              </v-row>
              <p>
                Data sources include a systematic literature review (1997-2021) and unpublished
                cohorts from collaborating centers.
              </p>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Data Standards -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="blue" class="mr-3">mdi-help-circle</v-icon>
              What data standards does the database use?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">
                We use internationally recognized standards to ensure data interoperability:
              </p>
              <v-list density="compact">
                <v-list-item>
                  <template #prepend>
                    <v-icon color="green">mdi-check</v-icon>
                  </template>
                  <v-list-item-title>
                    <strong>GA4GH Phenopackets v2</strong> - Clinical data schema
                  </v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="green">mdi-check</v-icon>
                  </template>
                  <v-list-item-title>
                    <strong>HPO</strong> - Human Phenotype Ontology for phenotype annotation
                  </v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="green">mdi-check</v-icon>
                  </template>
                  <v-list-item-title>
                    <strong>HGVS</strong> - Variant nomenclature (NM_000458.4)
                  </v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="green">mdi-check</v-icon>
                  </template>
                  <v-list-item-title>
                    <strong>VRS 2.0</strong> - GA4GH Variation Representation Specification
                  </v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="green">mdi-check</v-icon>
                  </template>
                  <v-list-item-title>
                    <strong>ACMG/AMP</strong> - Variant classification guidelines
                  </v-list-item-title>
                </v-list-item>
              </v-list>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- API Access -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="blue" class="mr-3">mdi-help-circle</v-icon>
              Can I access the data programmatically?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">
                Yes! The database provides a RESTful API compliant with JSON:API v1.1 specification.
                You can:
              </p>
              <ul class="mb-3">
                <li>Retrieve phenopackets with pagination</li>
                <li>Search by clinical and genetic parameters</li>
                <li>Access aggregation endpoints for statistical summaries</li>
                <li>Query variant annotations via Ensembl VEP integration</li>
              </ul>
              <v-btn
                color="primary"
                variant="outlined"
                href="/api/v2/docs"
                target="_blank"
                size="small"
              >
                <v-icon left>mdi-api</v-icon>
                View API Documentation
              </v-btn>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Pathogenicity -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="orange" class="mr-3">mdi-help-circle</v-icon>
              How is variant pathogenicity determined?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">
                Variant pathogenicity is assessed according to
                <strong>ACMG/AMP criteria</strong> via InterVar, with subsequent manual curation by
                expert physicians. Variants are classified as:
              </p>
              <v-chip-group>
                <v-chip color="error" variant="flat" size="small">Pathogenic (P)</v-chip>
                <v-chip color="orange" variant="flat" size="small">Likely Pathogenic (LP)</v-chip>
                <v-chip color="grey" variant="flat" size="small">VUS</v-chip>
                <v-chip color="info" variant="flat" size="small">Likely Benign (LB)</v-chip>
                <v-chip color="success" variant="flat" size="small">Benign (B)</v-chip>
              </v-chip-group>
              <p class="mt-3">
                Additional annotations include CADD scores, gnomAD population frequencies, and
                computational predictions from dbNSFP.
              </p>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Submit Data -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="green" class="mr-3">mdi-help-circle</v-icon>
              How can I submit data to the database?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">
                We welcome contributions from clinicians and researchers. To submit data:
              </p>
              <ol class="mb-3">
                <li>
                  <strong>Contact us</strong> via
                  <a href="https://github.com/berntpopp/hnf1b-db/issues" target="_blank">
                    GitHub Issues
                  </a>
                </li>
                <li>
                  <strong>Curator access</strong> can be granted for direct data entry through our
                  web interface
                </li>
                <li><strong>Bulk submissions</strong> are possible via phenopacket JSON format</li>
              </ol>
              <v-alert type="info" density="compact" variant="tonal">
                All data is reviewed by expert physicians before inclusion in the public database.
              </v-alert>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Citation -->
          <v-expansion-panel>
            <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
              <v-icon color="amber" class="mr-3">mdi-help-circle</v-icon>
              How should I cite this database?
            </v-expansion-panel-title>
            <v-expansion-panel-text class="text-body-1 pa-4">
              <p class="mb-3">Please cite (APA 7th Edition format):</p>
              <v-sheet color="grey-lighten-4" rounded class="pa-4">
                <p class="text-body-2 font-italic mb-0">
                  HNF1B Database. (2025).
                  <em>HNF1B Database: Clinical phenotype and variant registry</em>.
                  <a href="https://hnf1b.org" target="_blank">https://hnf1b.org</a>
                </p>
              </v-sheet>
              <p class="text-body-2 text-grey-darken-1 mt-3">
                For detailed citation formats including BibTeX, see the
                <router-link to="/about">About page</router-link>.
              </p>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

        <!-- Contact Section -->
        <v-card elevation="2">
          <v-card-title class="bg-grey-lighten-4">
            <v-icon left color="grey-darken-2">mdi-email</v-icon>
            Still have questions?
          </v-card-title>
          <v-card-text class="pa-6 text-center">
            <p class="text-body-1 mb-4">
              If you couldn't find the answer you're looking for, please reach out:
            </p>
            <v-btn
              color="primary"
              href="https://github.com/berntpopp/hnf1b-db/issues"
              target="_blank"
            >
              <v-icon left>mdi-github</v-icon>
              Open an Issue on GitHub
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
// No additional script needed for static FAQ page
</script>
