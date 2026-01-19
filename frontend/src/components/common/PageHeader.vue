<template>
  <header class="page-header" :class="headerClasses">
    <v-container :fluid="fluid">
      <!-- Breadcrumbs (if provided) -->
      <nav v-if="breadcrumbs?.length" aria-label="Breadcrumb">
        <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0 mb-2" />
      </nav>

      <!-- Title Row -->
      <div class="d-flex align-center flex-wrap gap-3">
        <!-- Back button (optional) -->
        <v-btn
          v-if="showBack"
          icon="mdi-arrow-left"
          variant="text"
          size="small"
          aria-label="Go back"
          @click="$emit('back')"
        />

        <!-- Icon (optional) -->
        <v-icon v-if="icon" :color="iconColor" size="large" aria-hidden="true">
          {{ icon }}
        </v-icon>

        <!-- Title + Subtitle -->
        <div class="flex-grow-1">
          <h1 class="text-h5 font-weight-bold" :class="titleClass">
            {{ title }}
          </h1>
          <p v-if="subtitle" class="text-body-2 text-medium-emphasis mb-0">
            {{ subtitle }}
          </p>
        </div>

        <!-- Prepend slot (for badges/chips next to title) -->
        <slot name="prepend" />

        <!-- Actions slot -->
        <div v-if="$slots.actions" class="d-flex align-center gap-2">
          <slot name="actions" />
        </div>
      </div>
    </v-container>
  </header>
</template>

<script>
/**
 * PageHeader component for consistent page headers across views.
 *
 * Provides semantic HTML structure with <header> and <h1> elements,
 * accessibility support, and flexible variants for different page types.
 *
 * @example
 * <PageHeader
 *   title="Phenopacket Details"
 *   subtitle="View individual clinical data"
 *   icon="mdi-account-details"
 *   variant="hero"
 *   :breadcrumbs="[{ title: 'Home', to: '/' }, { title: 'Details', disabled: true }]"
 *   show-back
 *   @back="goBack"
 * >
 *   <template #actions>
 *     <v-btn>Download</v-btn>
 *   </template>
 * </PageHeader>
 */
export default {
  name: 'PageHeader',
  props: {
    /**
     * Page title (required).
     * Rendered as an <h1> element for accessibility and SEO.
     */
    title: {
      type: String,
      required: true,
    },
    /**
     * Optional subtitle displayed below the title.
     */
    subtitle: {
      type: String,
      default: '',
    },
    /**
     * Material Design icon name (e.g., 'mdi-account-details').
     */
    icon: {
      type: String,
      default: '',
    },
    /**
     * Vuetify color for the icon.
     */
    iconColor: {
      type: String,
      default: 'teal-darken-2',
    },
    /**
     * Breadcrumb items array for v-breadcrumbs.
     * Each item should have { title, to?, disabled? }.
     */
    breadcrumbs: {
      type: Array,
      default: () => [],
    },
    /**
     * Show back navigation button.
     */
    showBack: {
      type: Boolean,
      default: false,
    },
    /**
     * Header variant style.
     * - 'default': Standard page header
     * - 'hero': Larger padding with gradient background (for detail pages)
     * - 'compact': Minimal padding
     */
    variant: {
      type: String,
      default: 'default',
      validator: (v) => ['default', 'hero', 'compact'].includes(v),
    },
    /**
     * Use fluid container (full width).
     */
    fluid: {
      type: Boolean,
      default: true,
    },
    /**
     * CSS class for title text styling.
     */
    titleClass: {
      type: String,
      default: 'text-teal-darken-2',
    },
  },
  emits: ['back'],
  computed: {
    /**
     * Dynamic CSS classes based on variant prop.
     */
    headerClasses() {
      return {
        'page-header--hero': this.variant === 'hero',
        'page-header--compact': this.variant === 'compact',
      };
    },
  },
};
</script>

<style scoped>
.page-header {
  padding: 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.page-header--hero {
  padding: 24px 0;
  background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 50%, #f5f7fa 100%);
}

.page-header--compact {
  padding: 8px 0;
}

.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}
</style>
