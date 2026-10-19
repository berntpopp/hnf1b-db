/**
 * Unit tests for PhenotypeSuggestionDrawer.vue (Issue #552).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import { apiClient } from '@/api';
import PhenotypeSuggestionDrawer from '@/components/curation/PhenotypeSuggestionDrawer.vue';

vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

let wrapper;

beforeEach(() => {
  vi.clearAllMocks();
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
});

function mountDrawer(props = {}) {
  const vuetify = createVuetify({
    components: vuetifyComponents,
    directives: vuetifyDirectives,
  });

  wrapper = mount(PhenotypeSuggestionDrawer, {
    props: {
      modelValue: [],
      pmid: 'PMID:12345678',
      evidenceCodeItems: [
        { id: 'ECO:0000033', label: 'author statement supported by traceable reference' },
      ],
      ...props,
    },
    global: {
      plugins: [vuetify],
    },
    attachTo: document.body,
  });
  return wrapper;
}

describe('PhenotypeSuggestionDrawer.vue', () => {
  it('renders suggest phenotypes button with data-testid', () => {
    mountDrawer();
    const btn = document.querySelector('[data-testid="suggest-phenotypes-btn"]');
    expect(btn).not.toBeNull();
    expect(btn.textContent).toContain('Suggest Phenotypes from PMID');
  });

  it('disables trigger button when pmid is empty', () => {
    mountDrawer({ pmid: '' });
    const btn = document.querySelector('[data-testid="suggest-phenotypes-btn"]');
    expect(btn).not.toBeNull();
    expect(btn.hasAttribute('disabled')).toBe(true);
  });

  it('fetches suggestions and opens drawer on button click', async () => {
    const mockSuggestions = [
      {
        hpo_id: 'HP:0000107',
        label: 'Renal cyst',
        excluded: false,
        section: 'results',
        passage_id: 'PMID:12345678:results:0',
        sentence: 'Renal cysts were observed in all patients.',
        score: 1.0,
      },
      {
        hpo_id: 'HP:0002917',
        label: 'Hypomagnesemia',
        excluded: true,
        section: 'results',
        passage_id: 'PMID:12345678:results:1',
        sentence: 'No hypomagnesemia was detected.',
        score: 1.0,
      },
    ];

    apiClient.get.mockResolvedValueOnce({
      data: {
        pmid: '12345678',
        suggestions: mockSuggestions,
      },
    });

    mountDrawer({ pmid: '12345678' });
    const btn = document.querySelector('[data-testid="suggest-phenotypes-btn"]');
    btn.click();

    expect(apiClient.get).toHaveBeenCalledWith('/publications/passages/suggest-phenotypes', {
      params: { pmid: '12345678' },
    });

    await vi.waitFor(() => {
      const dialog = document.querySelector('[data-testid="phenotype-suggestion-drawer"]');
      expect(dialog).not.toBeNull();
      expect(dialog.textContent).toContain('Renal cyst');
      expect(dialog.textContent).toContain('Hypomagnesemia');
      expect(dialog.textContent).toContain('Present');
      expect(dialog.textContent).toContain('Excluded');
    });
  });

  it('accepts selected phenotypes and emits update:modelValue with PMID evidence', async () => {
    const mockSuggestions = [
      {
        hpo_id: 'HP:0000107',
        label: 'Renal cyst',
        excluded: false,
        section: 'results',
        passage_id: 'PMID:12345678:results:0',
        sentence: 'Renal cysts were observed.',
        score: 1.0,
      },
    ];

    apiClient.get.mockResolvedValueOnce({
      data: {
        pmid: '12345678',
        suggestions: mockSuggestions,
      },
    });

    mountDrawer({ pmid: 'PMID:12345678', modelValue: [] });
    const triggerBtn = document.querySelector('[data-testid="suggest-phenotypes-btn"]');
    triggerBtn.click();

    let acceptBtn = null;
    await vi.waitFor(() => {
      acceptBtn = document.querySelector('[data-testid="accept-suggested-phenotypes-btn"]');
      expect(acceptBtn).not.toBeNull();
    });

    acceptBtn.click();

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted).toBeTruthy();
    expect(emitted[0][0]).toHaveLength(1);

    const accepted = emitted[0][0][0];
    expect(accepted.type.id).toBe('HP:0000107');
    expect(accepted.type.label).toBe('Renal cyst');
    expect(accepted.excluded).toBe(false);
    expect(accepted.evidence[0].reference.id).toBe('PMID:12345678');
  });
});
