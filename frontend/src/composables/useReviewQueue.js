import { computed, onScopeDispose, ref, watch } from 'vue';

import { getReviewQueue } from '@/api/domain/reviews';
import { useTableUrlState } from '@/composables/useTableUrlState';

const TAB_FILTERS = {
  'needs-review': { state: 'in_review' },
  'changes-requested': { state: 'changes_requested' },
  approved: { state: 'approved' },
  'my-drafts': { state: 'draft', owner: 'mine' },
};

const EMPTY_META = {
  page_number: 1,
  page_size: 25,
  total: 0,
  total_pages: 0,
  state_counts: {},
};

function requestParams({ page, pageSize, sort, search, tab, eligibility, issues }) {
  const tabFilters = TAB_FILTERS[tab] || TAB_FILTERS['needs-review'];
  const q = search.trim();

  return {
    pageNumber: page,
    pageSize,
    ...tabFilters,
    ...(sort ? { sort } : {}),
    ...(q ? { q } : {}),
    ...(eligibility !== 'all' ? { eligibility } : {}),
    ...(issues !== 'all' ? { issues } : {}),
  };
}

/**
 * Own the URL-backed, strictly server-driven review queue state.
 *
 * @returns {object} Reactive queue data, URL controls, and queue actions.
 */
export function useReviewQueue() {
  const urlState = useTableUrlState({
    defaultPageSize: 25,
    defaultSort: null,
    filters: {
      tab: 'needs-review',
      eligibility: 'all',
      issues: 'all',
    },
  });
  const items = ref([]);
  const meta = ref({ ...EMPTY_META });
  const loading = ref(false);
  const error = ref(null);
  let requestToken = 0;

  const tab = urlState.filters.tab;
  const eligibility = urlState.filters.eligibility;
  const issues = urlState.filters.issues;
  const controls = [
    urlState.page,
    urlState.pageSize,
    urlState.sort,
    urlState.search,
    tab,
    eligibility,
    issues,
  ];

  const hasFilters = computed(
    () => !!urlState.search.value || eligibility.value !== 'all' || issues.value !== 'all'
  );

  function currentParams() {
    return requestParams({
      page: urlState.page.value,
      pageSize: urlState.pageSize.value,
      sort: urlState.sort.value,
      search: urlState.search.value,
      tab: tab.value,
      eligibility: eligibility.value,
      issues: issues.value,
    });
  }

  async function load() {
    const token = ++requestToken;
    loading.value = true;

    try {
      const response = await getReviewQueue(currentParams());
      if (token !== requestToken) return null;
      items.value = response.data?.data || [];
      meta.value = { ...EMPTY_META, ...(response.data?.meta || {}) };
      error.value = null;
      return response.data;
    } catch (requestError) {
      if (token === requestToken) {
        error.value = requestError;
        window.logService?.error('Failed to fetch review queue', { error: requestError?.message });
      }
      return null;
    } finally {
      if (token === requestToken) loading.value = false;
    }
  }

  function retry() {
    return load();
  }

  function clearFilters() {
    urlState.clearAllFilters();
  }

  function setTab(nextTab) {
    tab.value = TAB_FILTERS[nextTab] ? nextTab : 'needs-review';
    urlState.resetPage();
  }

  watch(
    controls,
    (next, previous) => {
      const filtersChanged =
        previous?.length > 0 && [3, 4, 5, 6].some((index) => next[index] !== previous[index]);

      if (filtersChanged && urlState.page.value !== 1) {
        urlState.resetPage();
        return;
      }
      void load();
    },
    { immediate: true }
  );

  onScopeDispose(() => {
    requestToken += 1;
  });

  return {
    items,
    meta,
    loading,
    error,
    page: urlState.page,
    pageSize: urlState.pageSize,
    sort: urlState.sort,
    search: urlState.search,
    tab,
    eligibility,
    issues,
    hasFilters,
    load,
    retry,
    clearFilters,
    setTab,
  };
}
