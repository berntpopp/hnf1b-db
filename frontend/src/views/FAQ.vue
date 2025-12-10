<!-- src/views/FAQ.vue -->
<!--
  FAQ page rendered from JSON configuration.

  Features:
  - Content loaded from /config/faqContent.json
  - Dynamic expansion panels based on JSON categories and questions
  - Supports multiple answer types (text, lists, stats, alerts, etc.)
  - Markdown-like syntax support for inline formatting
-->
<template>
  <v-container class="py-8">
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <!-- Loading State -->
        <div v-if="loading" class="text-center py-12">
          <v-progress-circular indeterminate color="blue" size="64" />
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
            <v-avatar color="blue" size="80" class="mb-4">
              <v-icon size="48" color="white">{{ content.meta.icon }}</v-icon>
            </v-avatar>
            <h1 class="text-h3 font-weight-bold text-grey-darken-3 mb-2">
              {{ content.meta.title }}
            </h1>
            <p class="text-h6 text-grey-darken-1">
              {{ content.meta.subtitle }}
            </p>
          </div>

          <!-- FAQ Expansion Panels -->
          <v-expansion-panels variant="accordion" class="mb-6">
            <template v-for="category in content.categories" :key="category.id">
              <v-expansion-panel v-for="q in category.questions" :key="q.id">
                <v-expansion-panel-title class="text-subtitle-1 font-weight-medium">
                  <v-icon :color="category.color" class="mr-3">mdi-help-circle</v-icon>
                  {{ q.question }}
                </v-expansion-panel-title>
                <v-expansion-panel-text class="text-body-1 pa-4">
                  <!-- Render answer content blocks -->
                  <template v-for="(block, idx) in q.answer.content" :key="idx">
                    <!-- Paragraph -->
                    <p
                      v-if="block.type === 'paragraph'"
                      class="mb-3"
                      v-html="renderMarkdown(block.text)"
                    />

                    <!-- Unordered List -->
                    <ul v-else-if="block.type === 'list'" class="mb-3">
                      <li
                        v-for="(item, itemIdx) in block.items"
                        :key="itemIdx"
                        v-html="renderMarkdown(item)"
                      />
                    </ul>

                    <!-- Numbered List -->
                    <ol v-else-if="block.type === 'numberedList'" class="mb-3">
                      <li
                        v-for="(item, itemIdx) in block.items"
                        :key="itemIdx"
                        v-html="renderMarkdown(item.text)"
                      />
                    </ol>

                    <!-- Two-column layout -->
                    <v-row v-else-if="block.type === 'columns'" class="mb-3">
                      <v-col v-for="(col, colIdx) in block.columns" :key="colIdx" cols="12" md="6">
                        <h4 class="text-subtitle-2 font-weight-bold mb-2">{{ col.title }}</h4>
                        <ul>
                          <li v-for="(item, itemIdx) in col.items" :key="itemIdx">
                            {{ item }}
                          </li>
                        </ul>
                      </v-col>
                    </v-row>

                    <!-- Alert -->
                    <v-alert
                      v-else-if="block.type === 'alert'"
                      :type="block.alertType"
                      density="compact"
                      variant="tonal"
                      class="mt-2"
                    >
                      {{ block.text }}
                    </v-alert>

                    <!-- Variant List -->
                    <v-list v-else-if="block.type === 'variantList'" density="compact">
                      <v-list-item
                        v-for="(variant, variantIdx) in block.variants"
                        :key="variantIdx"
                      >
                        <template #prepend>
                          <v-chip :color="variant.chipColor" size="small" class="mr-2">
                            {{ variant.chip }}
                          </v-chip>
                        </template>
                        <v-list-item-title class="font-weight-bold">
                          {{ variant.title }}
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          {{ variant.description }}
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>

                    <!-- Stats Cards -->
                    <v-row v-else-if="block.type === 'stats'" class="mb-4">
                      <v-col v-for="(stat, statIdx) in block.stats" :key="statIdx" cols="6" md="3">
                        <v-card :color="`${stat.color}-lighten-5`" flat class="pa-3 text-center">
                          <div :class="`text-h4 font-weight-bold text-${stat.color}`">
                            {{ stat.value }}
                          </div>
                          <div class="text-caption">{{ stat.label }}</div>
                        </v-card>
                      </v-col>
                    </v-row>

                    <!-- Checklist -->
                    <v-list v-else-if="block.type === 'checklist'" density="compact">
                      <v-list-item v-for="(item, itemIdx) in block.items" :key="itemIdx">
                        <template #prepend>
                          <v-icon color="green">mdi-check</v-icon>
                        </template>
                        <v-list-item-title>
                          <span v-html="renderMarkdown(item.text)" />
                        </v-list-item-title>
                      </v-list-item>
                    </v-list>

                    <!-- Chips -->
                    <v-chip-group v-else-if="block.type === 'chips'" class="mb-3">
                      <v-chip
                        v-for="(chip, chipIdx) in block.chips"
                        :key="chipIdx"
                        :color="chip.color"
                        variant="flat"
                        size="small"
                      >
                        {{ chip.label }}
                      </v-chip>
                    </v-chip-group>

                    <!-- Button -->
                    <v-btn
                      v-else-if="block.type === 'button'"
                      color="primary"
                      variant="outlined"
                      :href="block.url"
                      :target="block.external ? '_blank' : undefined"
                      size="small"
                    >
                      <v-icon left>{{ block.icon }}</v-icon>
                      {{ block.text }}
                    </v-btn>

                    <!-- Citation -->
                    <v-sheet
                      v-else-if="block.type === 'citation'"
                      color="grey-lighten-4"
                      rounded
                      class="pa-4"
                    >
                      <p class="text-body-2 font-italic mb-0" v-html="renderMarkdown(block.text)" />
                    </v-sheet>
                  </template>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </template>
          </v-expansion-panels>

          <!-- Contact Section -->
          <v-card v-if="content.contact" elevation="2">
            <v-card-title class="bg-grey-lighten-4">
              <v-icon left color="grey-darken-2">mdi-email</v-icon>
              {{ content.contact.title }}
            </v-card-title>
            <v-card-text class="pa-6 text-center">
              <p class="text-body-1 mb-4">{{ content.contact.text }}</p>
              <v-btn color="primary" :href="content.contact.button.url" target="_blank">
                <v-icon left>{{ content.contact.button.icon }}</v-icon>
                {{ content.contact.button.text }}
              </v-btn>
            </v-card-text>
          </v-card>
        </template>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';

// Reactive state
const content = ref(null);
const loading = ref(true);
const error = ref(null);

// Methods
const loadContent = async () => {
  loading.value = true;
  error.value = null;

  try {
    const response = await fetch('/config/faqContent.json');
    if (!response.ok) {
      throw new Error(`Failed to load content: ${response.status}`);
    }
    content.value = await response.json();
    window.logService.info('FAQ page content loaded', {
      categoriesCount: content.value.categories?.length,
      questionsCount: content.value.categories?.reduce((sum, cat) => sum + cat.questions.length, 0),
    });
  } catch (err) {
    window.logService.error('Failed to load FAQ content', {
      error: err.message,
    });
    error.value = 'Failed to load page content. Please try again later.';
  } finally {
    loading.value = false;
  }
};

// Render markdown-like syntax (bold, italic, links)
const renderMarkdown = (text) => {
  if (!text) return '';
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
};

// Lifecycle
onMounted(() => {
  loadContent();
});
</script>
