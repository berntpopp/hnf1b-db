<!-- src/components/common/AppPagination.vue -->
<!--
  Reusable pagination controls for offset-based pagination.

  Features:
  - Items per page selector
  - Range text with total count: "1-20 of 864"
  - First/Previous/Next/Last navigation buttons
  - Clickable page number buttons (1, 2, 3 ... n) on >= sm
  - Compact two-row, 44px-touch-target layout on mobile (< sm)
  - JSON:API v1.1 compliant offset-based server-side pagination
-->
<template>
  <div
    class="app-pagination d-flex align-center px-4 py-2"
    :class="
      mobile
        ? 'app-pagination--mobile flex-column flex-wrap justify-center ga-1'
        : 'justify-end flex-wrap'
    "
  >
    <!-- Meta: items-per-page selector + range text -->
    <div
      class="pg-meta d-flex align-center"
      :class="mobile ? 'order-2 justify-space-between w-100 mt-1' : ''"
    >
      <div class="d-flex align-center" :class="mobile ? '' : 'mr-4'">
        <span class="text-caption text-medium-emphasis mr-2">Items per page:</span>
        <v-select
          :model-value="pageSize"
          :items="itemsPerPageOptions"
          density="compact"
          hide-details
          variant="plain"
          class="items-per-page-select"
          aria-label="Items per page"
          @update:model-value="$emit('update:pageSize', $event)"
        />
      </div>

      <!-- Range text -->
      <span class="text-caption font-weight-medium" :class="mobile ? '' : 'mx-4'">
        {{ rangeText }}
      </span>
    </div>

    <!-- Navigation buttons -->
    <nav aria-label="Pagination Navigation" :class="mobile ? 'order-1' : ''">
      <ul class="d-flex align-center justify-center pa-0 ma-0" style="list-style: none; gap: 2px">
        <!-- First page button -->
        <li>
          <v-btn
            icon
            variant="text"
            :size="mobile ? 'large' : 'small'"
            class="pg-icon-btn"
            :disabled="currentPage <= 1"
            aria-label="First page"
            @click="$emit('go-to-page', 1)"
          >
            <v-icon :size="mobile ? 'default' : 'small'">mdi-page-first</v-icon>
          </v-btn>
        </li>

        <!-- Previous page button -->
        <li>
          <v-btn
            icon
            variant="text"
            :size="mobile ? 'large' : 'small'"
            class="pg-icon-btn"
            :disabled="currentPage <= 1"
            aria-label="Previous page"
            @click="$emit('go-to-page', currentPage - 1)"
          >
            <v-icon :size="mobile ? 'default' : 'small'">mdi-chevron-left</v-icon>
          </v-btn>
        </li>

        <!-- Mobile: compact "Page X of Y" label (replaces numbered buttons) -->
        <li v-if="mobile" class="pg-page-label-wrap">
          <span class="pg-page-label text-body-2 font-weight-medium px-2">
            Page {{ currentPage }} of {{ safeTotalPages }}
          </span>
        </li>

        <!-- Desktop: numbered page buttons (smart pagination with ellipsis) -->
        <template v-else-if="totalPages > 0">
          <!-- First page (always visible if not in range) -->
          <li v-if="displayedPages[0] > 1">
            <v-btn
              size="small"
              :variant="currentPage === 1 ? 'flat' : 'text'"
              :color="currentPage === 1 ? 'primary' : 'default'"
              class="page-btn"
              min-width="32"
              @click="$emit('go-to-page', 1)"
            >
              1
            </v-btn>
          </li>

          <!-- Left ellipsis -->
          <li v-if="displayedPages[0] > 2" class="ellipsis">
            <span class="text-caption text-medium-emphasis px-1">...</span>
          </li>

          <!-- Middle page numbers -->
          <li v-for="page in displayedPages" :key="page">
            <v-btn
              size="small"
              :variant="currentPage === page ? 'flat' : 'text'"
              :color="currentPage === page ? 'primary' : 'default'"
              class="page-btn"
              min-width="32"
              @click="$emit('go-to-page', page)"
            >
              {{ page }}
            </v-btn>
          </li>

          <!-- Right ellipsis -->
          <li v-if="displayedPages[displayedPages.length - 1] < totalPages - 1" class="ellipsis">
            <span class="text-caption text-medium-emphasis px-1">...</span>
          </li>

          <!-- Last page (always visible if not in range) -->
          <li v-if="displayedPages[displayedPages.length - 1] < totalPages">
            <v-btn
              size="small"
              :variant="currentPage === totalPages ? 'flat' : 'text'"
              :color="currentPage === totalPages ? 'primary' : 'default'"
              class="page-btn"
              min-width="32"
              @click="$emit('go-to-page', totalPages)"
            >
              {{ totalPages }}
            </v-btn>
          </li>
        </template>

        <!-- Next page button -->
        <li>
          <v-btn
            icon
            variant="text"
            :size="mobile ? 'large' : 'small'"
            class="pg-icon-btn"
            :disabled="currentPage >= totalPages"
            aria-label="Next page"
            @click="$emit('go-to-page', currentPage + 1)"
          >
            <v-icon :size="mobile ? 'default' : 'small'">mdi-chevron-right</v-icon>
          </v-btn>
        </li>

        <!-- Last page button -->
        <li>
          <v-btn
            icon
            variant="text"
            :size="mobile ? 'large' : 'small'"
            class="pg-icon-btn"
            :disabled="currentPage >= totalPages"
            aria-label="Last page"
            @click="$emit('go-to-page', totalPages)"
          >
            <v-icon :size="mobile ? 'default' : 'small'">mdi-page-last</v-icon>
          </v-btn>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useDisplay } from 'vuetify';
import { calculateRangeText } from '@/utils/pagination';

const { smAndDown } = useDisplay();
const mobile = smAndDown;

const props = defineProps({
  /**
   * Number of items currently displayed on page
   */
  currentCount: {
    type: Number,
    required: true,
  },
  /**
   * Current page number (1-indexed)
   */
  currentPage: {
    type: Number,
    default: 1,
  },
  /**
   * Items per page
   */
  pageSize: {
    type: Number,
    default: 10,
  },
  /**
   * Total number of pages
   */
  totalPages: {
    type: Number,
    default: 0,
  },
  /**
   * Total count of items
   */
  totalRecords: {
    type: Number,
    default: 0,
  },
  /**
   * Available page size options
   */
  itemsPerPageOptions: {
    type: Array,
    default: () => [10, 20, 50, 100],
  },
  /**
   * Maximum number of page buttons to display (excluding first/last)
   */
  maxVisiblePages: {
    type: Number,
    default: 5,
  },
});

defineEmits(['update:pageSize', 'go-to-page']);

// At least 1 so the mobile "Page X of Y" label never reads "of 0".
const safeTotalPages = computed(() => Math.max(props.totalPages, 1));

// Calculate which page numbers to display (smart pagination with ellipsis)
const displayedPages = computed(() => {
  const total = props.totalPages;
  const current = props.currentPage;
  const maxVisible = props.maxVisiblePages;

  if (total <= maxVisible + 2) {
    // Show all pages if they fit
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages = [];
  const halfVisible = Math.floor(maxVisible / 2);

  let start = Math.max(2, current - halfVisible);
  let end = Math.min(total - 1, current + halfVisible);

  // Adjust if at the beginning
  if (current <= halfVisible + 1) {
    end = Math.min(total - 1, maxVisible);
    start = 2;
  }

  // Adjust if at the end
  if (current >= total - halfVisible) {
    start = Math.max(2, total - maxVisible + 1);
    end = total - 1;
  }

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  return pages;
});

const rangeText = computed(() => {
  return calculateRangeText(
    props.currentCount,
    props.currentPage,
    props.pageSize,
    props.totalRecords
  );
});
</script>

<style scoped>
.app-pagination {
  min-height: 52px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.02);
}

.items-per-page-select {
  max-width: 70px;
}

.items-per-page-select :deep(.v-field__input) {
  padding-top: 4px;
  padding-bottom: 4px;
  min-height: 28px;
}

.items-per-page-select :deep(.v-select__selection-text) {
  font-size: 0.875rem;
}

.page-btn {
  font-size: 0.8125rem;
  font-weight: 500;
  min-width: 32px !important;
  height: 28px;
  padding: 0 6px;
}

.ellipsis {
  display: flex;
  align-items: center;
  height: 28px;
}

/* Mobile: ensure all nav controls meet the 44px touch-target minimum */
.app-pagination--mobile .pg-icon-btn {
  min-width: 48px;
  min-height: 48px;
}

.app-pagination--mobile .pg-page-label-wrap {
  flex-shrink: 0;
}

.app-pagination--mobile .pg-page-label {
  white-space: nowrap;
  font-size: 0.875rem;
}

.app-pagination--mobile {
  /* Two stacked rows need a touch more vertical room */
  min-height: 88px;
}

/* 44px touch target for the items-per-page select on mobile */
.app-pagination--mobile .items-per-page-select :deep(.v-field__input) {
  min-height: 44px;
}
</style>
