/**
 * Unit tests for PublicationSpecialty.vue (issue #11).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import { getPublicationSpecialty, updatePublicationSpecialty } from '@/api';
import PublicationSpecialty from '@/components/curation/PublicationSpecialty.vue';

vi.mock('@/api', () => ({
  getPublicationSpecialty: vi.fn(),
  updatePublicationSpecialty: vi.fn(),
}));

const auth = { isCurator: true };
vi.mock('@/stores/authStore', () => ({ useAuthStore: () => auth }));

const SUGGESTION_RESPONSE = {
  data: {
    pmid: 'PMID:16971658',
    medical_specialty: [],
    vocabulary: ['nephrology', 'diabetology', 'genetics', 'pediatrics'],
    suggestions: [
      { specialty: 'nephrology', score: 3, evidence: ['journal', 'first_author'] },
      { specialty: 'pediatrics', score: 1, evidence: ['first_author'] },
    ],
    suggestion_error: null,
  },
};

let wrapper;

beforeEach(() => {
  vi.clearAllMocks();
  auth.isCurator = true;
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
});

function mountIt(props = {}) {
  const vuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });
  wrapper = mount(PublicationSpecialty, {
    props: { pmid: '16971658', modelValue: [], ...props },
    global: { plugins: [vuetify] },
  });
  return wrapper;
}

const byId = (id) => wrapper.find(`[data-testid="${id}"]`);

describe('PublicationSpecialty', () => {
  it('shows saved specialties read-only to the public and hides when empty', async () => {
    auth.isCurator = false;
    mountIt({ modelValue: ['nephrology', 'pediatrics'] });
    expect(wrapper.text()).toContain('nephrology');
    expect(byId('specialty-edit-btn').exists()).toBe(false);

    await wrapper.setProps({ modelValue: [] });
    expect(byId('publication-specialty').exists()).toBe(false);
  });

  it('lets a curator see "Not yet curated" and open the editor with suggestions', async () => {
    getPublicationSpecialty.mockResolvedValue(SUGGESTION_RESPONSE);
    mountIt();
    expect(wrapper.text()).toContain('Not yet curated');

    await byId('specialty-edit-btn').trigger('click');
    await flushPromises();

    expect(getPublicationSpecialty).toHaveBeenCalledWith('16971658');
    expect(byId('specialty-suggestions').text()).toContain('nephrology');
    expect(byId('specialty-suggestion-pediatrics').exists()).toBe(true);
  });

  it('toggles suggestions into the draft in click order and saves', async () => {
    getPublicationSpecialty.mockResolvedValue(SUGGESTION_RESPONSE);
    updatePublicationSpecialty.mockResolvedValue({
      data: { medical_specialty: ['pediatrics', 'nephrology'] },
    });
    mountIt();
    await byId('specialty-edit-btn').trigger('click');
    await flushPromises();

    await byId('specialty-suggestion-pediatrics').trigger('click');
    await byId('specialty-suggestion-nephrology').trigger('click');
    await byId('specialty-save-btn').trigger('click');
    await flushPromises();

    expect(updatePublicationSpecialty).toHaveBeenCalledWith('16971658', [
      'pediatrics',
      'nephrology',
    ]);
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([['pediatrics', 'nephrology']]);
    expect(byId('specialty-editor').exists()).toBe(false);
  });

  it('"Use suggestions" replaces the draft with the ranked suggestions; re-click removes', async () => {
    getPublicationSpecialty.mockResolvedValue(SUGGESTION_RESPONSE);
    updatePublicationSpecialty.mockResolvedValue({ data: { medical_specialty: ['nephrology'] } });
    mountIt({ modelValue: ['genetics'] });
    await byId('specialty-edit-btn').trigger('click');
    await flushPromises();

    // Saved value is pre-filled into the editor as a labelled chip (not empty).
    const selectChips = byId('specialty-select').findAll('.v-chip');
    expect(selectChips.map((c) => c.text().trim())).toEqual(['genetics']);

    await byId('specialty-use-all').trigger('click');
    await byId('specialty-suggestion-pediatrics').trigger('click'); // toggle off
    await byId('specialty-save-btn').trigger('click');
    await flushPromises();

    expect(updatePublicationSpecialty).toHaveBeenCalledWith('16971658', ['nephrology']);
  });

  it('shows the degraded NCBI message but keeps the editor usable', async () => {
    getPublicationSpecialty.mockResolvedValue({
      data: { ...SUGGESTION_RESPONSE.data, suggestions: [], suggestion_error: 'NCBI unavailable' },
    });
    mountIt();
    await byId('specialty-edit-btn').trigger('click');
    await flushPromises();

    expect(byId('specialty-error').text()).toContain('NCBI unavailable');
    expect(byId('specialty-select').exists()).toBe(true);
  });

  it('keeps the editor open and reports a failed save', async () => {
    getPublicationSpecialty.mockResolvedValue(SUGGESTION_RESPONSE);
    updatePublicationSpecialty.mockRejectedValue({
      response: { status: 403, data: { detail: 'Curator or admin access required' } },
    });
    mountIt();
    await byId('specialty-edit-btn').trigger('click');
    await flushPromises();
    await byId('specialty-save-btn').trigger('click');
    await flushPromises();

    expect(byId('specialty-editor').exists()).toBe(true);
    expect(byId('specialty-error').text()).toContain('Curator or admin access required');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });
});
