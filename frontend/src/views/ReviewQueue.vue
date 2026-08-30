<template>
  <v-container fluid class="py-6">
    <section aria-labelledby="review-queue-title" :aria-busy="queue.loading.value">
      <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
        <div>
          <h1 id="review-queue-title" class="text-h5 mb-1">Review Queue</h1>
          <p class="text-body-2 text-medium-emphasis mb-0">
            Records ready for curator review and publication.
          </p>
        </div>
        <v-chip color="teal" variant="tonal" aria-live="polite">
          {{ queue.meta.value.total.toLocaleString() }} records
        </v-chip>
      </div>

      <v-tabs
        :model-value="queue.tab.value"
        color="primary"
        class="mb-4"
        @update:model-value="queue.setTab"
      >
        <v-tab value="needs-review">Needs review</v-tab>
        <v-tab value="changes-requested">Changes requested</v-tab>
        <v-tab value="approved">Approved</v-tab>
        <v-tab value="my-drafts">My drafts</v-tab>
      </v-tabs>

      <v-alert v-if="queue.error.value" type="error" variant="tonal" class="mb-4" role="alert">
        Unable to load the review queue: {{ queue.error.value.message || 'Unknown error' }}
        <template #append>
          <v-btn data-testid="retry-review-queue" variant="text" @click="queue.retry">Retry</v-btn>
        </template>
      </v-alert>

      <AppDataTable
        server-side
        :headers="headers"
        :items="queue.items.value"
        :items-length="queue.meta.value.total"
        :loading="queue.loading.value"
        :items-per-page="queue.pageSize.value"
        :page="queue.page.value"
        :sort-by="sortBy"
        hide-default-footer
        @update:options="onOptionsUpdate"
      >
        <template #toolbar>
          <AppTableToolbar
            v-model:search-query="searchModel"
            :loading="queue.loading.value"
            :result-count="queue.meta.value.total"
            result-label="records"
            search-placeholder="Search case ID or subject"
            @clear-search="clearSearch"
          >
            <template #actions>
              <v-select
                :model-value="queue.eligibility.value"
                :items="eligibilityOptions"
                label="Eligibility"
                density="compact"
                hide-details
                style="max-width: 210px"
                @update:model-value="setFilter('eligibility', $event)"
              />
              <v-select
                :model-value="queue.issues.value"
                :items="issueOptions"
                label="Issues"
                density="compact"
                hide-details
                style="max-width: 160px"
                @update:model-value="setFilter('issues', $event)"
              />
              <v-btn v-if="queue.hasFilters.value" variant="text" @click="queue.clearFilters">
                Clear filters
              </v-btn>
            </template>
          </AppTableToolbar>
        </template>

        <template #item.phenopacket_id="{ item }">
          <span class="font-weight-medium">{{ item.phenopacket_id }}</span>
        </template>

        <template #item.effective_state="{ item }">
          <StateBadge :state="item.effective_state" />
        </template>

        <template #item.owner="{ item }">
          {{ item.owner?.display_name || item.owner?.username || 'Unassigned' }}
        </template>

        <template #item.submitted_at="{ item }">
          {{ formatDate(item.submitted_at) }}
        </template>

        <template #item.open_issue_count="{ item }">
          <span :aria-label="`${item.open_issue_count} open issues`">
            {{ issueLabel(item.open_issue_count) }}
          </span>
        </template>

        <template #item.eligibility="{ item }">
          {{ eligibilityLabel(item) }}
        </template>

        <template #item.actions="{ item }">
          <v-btn
            class="review-link"
            color="primary"
            size="small"
            variant="tonal"
            :to="reviewLocation(item)"
          >
            Review
          </v-btn>
        </template>

        <template #bottom>
          <AppPagination
            :current-count="queue.items.value.length"
            :current-page="queue.page.value"
            :page-size="queue.pageSize.value"
            :total-pages="queue.meta.value.total_pages"
            :total-records="queue.meta.value.total"
            :items-per-page-options="pageSizeOptions"
            @go-to-page="goToPage"
            @update:page-size="setPageSize"
          />
        </template>

        <template #no-data>
          <div class="py-6 text-center text-body-2 text-medium-emphasis">
            <template v-if="queue.hasFilters.value">
              No records match the active filters.
              <v-btn variant="text" size="small" @click="queue.clearFilters">Clear filters</v-btn>
            </template>
            <template v-else>No records are currently awaiting review.</template>
          </div>
        </template>
      </AppDataTable>
    </section>
  </v-container>
</template>

<script setup>
import { computed } from 'vue';

import AppDataTable from '@/components/common/AppDataTable.vue';
import AppPagination from '@/components/common/AppPagination.vue';
import AppTableToolbar from '@/components/common/AppTableToolbar.vue';
import StateBadge from '@/components/state/StateBadge.vue';
import { useReviewQueue } from '@/composables/useReviewQueue';
import { buildSortParameter } from '@/utils/pagination';

const queue = useReviewQueue();

const headers = [
  { title: 'Case', value: 'phenopacket_id', sortable: true },
  { title: 'Subject', value: 'subject_label', sortable: true },
  { title: 'State', value: 'effective_state', sortable: true },
  { title: 'Owner', value: 'owner', sortable: false },
  { title: 'Submitted', value: 'submitted_at', sortable: true },
  { title: 'Changes', value: 'active_cycle_change_count', sortable: true, align: 'center' },
  { title: 'Open issues', value: 'open_issue_count', sortable: true, align: 'center' },
  { title: 'Eligibility', value: 'eligibility', sortable: false },
  { title: 'Actions', value: 'actions', sortable: false, align: 'end' },
];
const eligibilityOptions = [
  { title: 'All records', value: 'all' },
  { title: 'Reviewable by me', value: 'reviewable_by_me' },
];
const issueOptions = [
  { title: 'All issues', value: 'all' },
  { title: 'Open issues', value: 'open' },
  { title: 'No open issues', value: 'none' },
];
const pageSizeOptions = [10, 25, 50, 100];
const sortFieldMap = {
  phenopacket_id: 'phenopacket_id',
  subject_label: 'subject_label',
  effective_state: 'effective_state',
  submitted_at: 'submitted_at',
  active_cycle_change_count: 'change_count',
  open_issue_count: 'open_issue_count',
};

const searchModel = computed({
  get: () => queue.search.value,
  set: (value) => {
    queue.search.value = value || '';
  },
});
const sortBy = computed(() => {
  const value = queue.sort.value;
  if (!value) return [];
  const descending = value.startsWith('-');
  const field = descending ? value.slice(1) : value;
  const key = Object.entries(sortFieldMap).find(([, backendField]) => backendField === field)?.[0];
  return key ? [{ key, order: descending ? 'desc' : 'asc' }] : [];
});

function onOptionsUpdate(options) {
  const nextSort = buildSortParameter(options.sortBy, sortFieldMap) || null;
  if (queue.sort.value !== nextSort) queue.sort.value = nextSort;
  if (queue.page.value !== options.page) queue.page.value = options.page;
  if (queue.pageSize.value !== options.itemsPerPage) queue.pageSize.value = options.itemsPerPage;
}

function setFilter(name, value) {
  queue[name].value = value;
}

function clearSearch() {
  queue.search.value = '';
}

function setPageSize(pageSize) {
  queue.pageSize.value = pageSize;
  queue.page.value = 1;
}

function goToPage(page) {
  if (page >= 1 && page <= queue.meta.value.total_pages) queue.page.value = page;
}

function issueLabel(count) {
  return `${count || 0} open issue${count === 1 ? '' : 's'}`;
}

function eligibilityLabel(item) {
  const decisions = item.capabilities || [];
  return decisions.some(
    (capability) => ['approve', 'request_changes'].includes(capability.action) && capability.allowed
  )
    ? 'Reviewable by you'
    : 'Not reviewable by you';
}

function formatDate(value) {
  if (!value) return 'Not submitted';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}

function reviewLocation(item) {
  return {
    name: 'PhenopacketReview',
    params: { phenopacket_id: item.phenopacket_id },
    query: { return_to: `${window.location.pathname}${window.location.search}` },
  };
}
</script>

<style scoped></style>
