<!-- src/views/About.vue -->
<!--
  About page rendered from JSON configuration.

  Features:
  - Content loaded from /config/aboutContent.json
  - Flexible section rendering based on JSON structure
  - Supports markdown-like syntax for bold text
  - Dynamic citation generation with current date
-->
<template>
  <v-container class="py-8">
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <!-- Loading State -->
        <div v-if="loading" class="text-center py-12">
          <v-progress-circular indeterminate color="teal" size="64" />
          <p class="mt-4 text-grey-darken-1">Loading content...</p>
        </div>

        <!-- Error State -->
        <v-alert v-else-if="error" type="error" variant="tonal" class="mb-6">
          {{ error }}
        </v-alert>

        <!-- Content Loaded -->
        <template v-else-if="content">
          <!-- Page Header -->
          <div class="text-center mb-8">
            <v-avatar color="teal" size="80" class="mb-4">
              <v-icon size="48" color="white">{{ content.meta.icon }}</v-icon>
            </v-avatar>
            <h1 class="text-h3 font-weight-bold text-grey-darken-3 mb-2">
              {{ content.meta.title }}
            </h1>
            <p class="text-h6 text-grey-darken-1">
              {{ content.meta.subtitle }}
            </p>
          </div>

          <!-- Dynamic Sections -->
          <template v-for="section in content.sections" :key="section.id">
            <!-- Background Section -->
            <v-card v-if="section.id === 'background'" class="mb-6" elevation="2">
              <v-card-title :class="`bg-${section.color}-lighten-5`">
                <v-icon left :color="section.color">{{ section.icon }}</v-icon>
                {{ section.title }}
              </v-card-title>
              <v-card-text class="text-body-1 pa-6">
                <p class="mb-4" v-html="renderMarkdown(section.content.intro)" />
                <v-list density="compact" class="mb-4">
                  <v-list-item
                    v-for="condition in section.content.conditions"
                    :key="condition.acronym"
                  >
                    <template #prepend>
                      <v-icon :color="section.color" size="small">mdi-check-circle</v-icon>
                    </template>
                    <v-list-item-title>
                      <strong>{{ condition.acronym }}</strong> - {{ condition.name }}
                    </v-list-item-title>
                  </v-list-item>
                </v-list>
                <p>{{ section.content.outro }}</p>
              </v-card-text>
            </v-card>

            <!-- Mission Section -->
            <v-card v-else-if="section.id === 'mission'" class="mb-6" elevation="2">
              <v-card-title :class="`bg-${section.color}-lighten-5`">
                <v-icon left :color="section.color">{{ section.icon }}</v-icon>
                {{ section.title }}
              </v-card-title>
              <v-card-text class="text-body-1 pa-6">
                <p
                  v-for="(para, idx) in section.content.paragraphs"
                  :key="idx"
                  :class="{ 'mb-4': idx < section.content.paragraphs.length - 1 }"
                  v-html="renderMarkdown(para)"
                />
              </v-card-text>
            </v-card>

            <!-- Features Section (Methodology, Data Standards) -->
            <v-card v-else-if="section.content.features" class="mb-6" elevation="2">
              <v-card-title :class="`bg-${section.color}-lighten-5`">
                <v-icon left :color="section.color">{{ section.icon }}</v-icon>
                {{ section.title }}
              </v-card-title>
              <v-card-text class="pa-6">
                <v-row>
                  <v-col
                    v-for="(feature, idx) in section.content.features"
                    :key="idx"
                    cols="12"
                    md="6"
                  >
                    <div
                      class="d-flex align-start"
                      :class="{ 'mb-4': idx < section.content.features.length - 2 }"
                    >
                      <v-avatar :color="`${section.color}-lighten-4`" size="40" class="mr-3">
                        <v-icon :color="`${section.color}-darken-2`">{{ feature.icon }}</v-icon>
                      </v-avatar>
                      <div>
                        <h4 class="text-subtitle-1 font-weight-bold">{{ feature.title }}</h4>
                        <p class="text-body-2 text-grey-darken-1">
                          {{ feature.description }}
                        </p>
                      </div>
                    </div>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>

            <!-- Citation Section -->
            <v-card v-else-if="section.id === 'citation'" class="mb-6" elevation="2">
              <v-card-title :class="`bg-${section.color}-lighten-5`">
                <v-icon left :color="`${section.color}-darken-2`">{{ section.icon }}</v-icon>
                {{ section.title }}
              </v-card-title>
              <v-card-text class="pa-6">
                <p class="text-body-1 mb-4">{{ section.content.intro }}</p>
                <v-sheet color="grey-lighten-4" rounded class="pa-4 mb-4">
                  <p class="text-body-2 mb-2">
                    <strong>{{ section.content.formats.apa.label }}:</strong>
                  </p>
                  <p
                    class="text-body-2 font-italic mb-0"
                    v-html="formatCitation(section.content.formats.apa.template)"
                  />
                </v-sheet>
                <v-sheet color="grey-lighten-4" rounded class="pa-4">
                  <p class="text-body-2 mb-2">
                    <strong>{{ section.content.formats.bibtex.label }}:</strong>
                  </p>
                  <pre
                    class="text-body-2"
                    style="white-space: pre-wrap; font-family: monospace; margin: 0"
                    >{{ formatBibtex(section.content.formats.bibtex.template) }}</pre
                  >
                </v-sheet>
              </v-card-text>
            </v-card>

            <!-- Contributing Section -->
            <v-card v-else-if="section.id === 'contributing'" class="mb-6" elevation="2">
              <v-card-title :class="`bg-${section.color}-lighten-5`">
                <v-icon left :color="section.color">{{ section.icon }}</v-icon>
                {{ section.title }}
              </v-card-title>
              <v-card-text class="pa-6">
                <p class="text-body-1 mb-4">{{ section.content.intro }}</p>
                <v-list density="compact">
                  <v-list-item v-for="(item, idx) in section.content.items" :key="idx">
                    <template #prepend>
                      <v-icon :color="section.color" size="small">{{ item.icon }}</v-icon>
                    </template>
                    <v-list-item-title>{{ item.text }}</v-list-item-title>
                  </v-list-item>
                </v-list>
                <v-divider class="my-4" />
                <p class="text-body-2 text-grey-darken-1">
                  {{ section.content.contact.text }}
                  <a :href="section.content.contact.linkUrl" target="_blank">
                    {{ section.content.contact.linkText }}
                  </a>
                  or submit a pull request.
                </p>
              </v-card-text>
            </v-card>

            <!-- License Section -->
            <v-card v-else-if="section.id === 'license'" elevation="2">
              <v-card-title class="bg-grey-lighten-4">
                <v-icon left color="grey-darken-2">{{ section.icon }}</v-icon>
                {{ section.title }}
              </v-card-title>
              <v-card-text class="pa-6">
                <div class="d-flex align-center">
                  <v-img
                    :src="section.content.badgeUrl"
                    :alt="section.content.type"
                    max-width="88"
                    class="mr-4"
                  />
                  <div>
                    <p class="text-body-1 mb-2">
                      This work is licensed under a
                      <a :href="section.content.url" target="_blank" rel="noopener">
                        {{ section.content.name }} </a
                      >.
                    </p>
                    <p class="text-body-2 text-grey-darken-1 mb-0">
                      {{ section.content.description }}
                    </p>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </template>
        </template>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';

// Reactive state
const content = ref(null);
const loading = ref(true);
const error = ref(null);

// Current date for citation
const currentDate = computed(() => {
  return new Date().toISOString().split('T')[0];
});

const currentYear = computed(() => {
  return new Date().getFullYear();
});

// Methods
const loadContent = async () => {
  loading.value = true;
  error.value = null;

  try {
    const response = await fetch('/config/aboutContent.json');
    if (!response.ok) {
      throw new Error(`Failed to load content: ${response.status}`);
    }
    content.value = await response.json();
    window.logService.info('About page content loaded', {
      sectionsCount: content.value.sections?.length,
    });
  } catch (err) {
    window.logService.error('Failed to load about content', {
      error: err.message,
    });
    error.value = 'Failed to load page content. Please try again later.';
  } finally {
    loading.value = false;
  }
};

// Render markdown-like syntax (bold only)
const renderMarkdown = (text) => {
  if (!text) return '';
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
};

// Format citation with current year
const formatCitation = (template) => {
  if (!template) return '';
  return template.replace('{year}', currentYear.value).replace(/\*(.+?)\*/g, '<em>$1</em>');
};

// Format BibTeX with current date and year
const formatBibtex = (template) => {
  if (!template) return '';
  return template.replace(/{year}/g, currentYear.value).replace('{date}', currentDate.value);
};

// Lifecycle
onMounted(() => {
  loadContent();
});
</script>
