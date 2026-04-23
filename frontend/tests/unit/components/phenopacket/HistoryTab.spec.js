import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HistoryTab from '@/components/phenopacket/HistoryTab.vue';

describe('HistoryTab', () => {
  beforeEach(() => {
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('renders a loading state while history is being fetched', () => {
    const wrapper = mount(HistoryTab, {
      props: {
        entries: [],
        loading: true,
        error: null,
      },
    });

    expect(wrapper.text()).toContain('Loading history');
  });

  it('renders an error state when history loading fails', () => {
    const wrapper = mount(HistoryTab, {
      props: {
        entries: [],
        loading: false,
        error: 'Unable to load revision history',
      },
    });

    expect(wrapper.text()).toContain('Unable to load revision history');
  });

  it('renders revision rows with state, actor, timestamp, and reason', () => {
    const wrapper = mount(HistoryTab, {
      props: {
        entries: [
          {
            id: '12',
            revisionNumber: 12,
            state: 'approved',
            actor: 'curator.alice',
            timestamp: '2026-04-23T08:30:00Z',
            summary: 'Approved after review',
          },
          {
            id: '11',
            revisionNumber: 11,
            state: null,
            actor: null,
            timestamp: '2026-04-22T18:15:00Z',
            summary: 'Imported legacy record',
          },
        ],
        loading: false,
        error: null,
      },
    });

    expect(wrapper.text()).toContain('Revision 12');
    expect(wrapper.text()).toContain('approved');
    expect(wrapper.text()).toContain('curator.alice');
    expect(wrapper.text()).toContain('Approved after review');
    expect(wrapper.text()).toContain('Imported legacy record');
  });
});
