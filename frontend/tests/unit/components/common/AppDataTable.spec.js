import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { ref } from 'vue';
import AppDataTable from '@/components/common/AppDataTable.vue';

const mockSmAndDown = ref(false);

vi.mock('vuetify', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useDisplay: () => ({
      ...actual.useDisplay?.(),
      smAndDown: mockSmAndDown,
    }),
  };
});

describe('AppDataTable', () => {
  const defaultStubs = {
    'v-card': { template: '<div class="v-card"><slot /></div>' },
    'v-skeleton-loader': { template: '<div class="v-skeleton-loader" />' },
    'v-data-table-server': {
      template:
        '<div class="v-data-table-server"><slot v-for="(_, name) in $slots" :key="name" :name="name" /></div>',
    },
    'v-data-table': {
      template:
        '<div class="v-data-table"><slot v-for="(_, name) in $slots" :key="name" :name="name" /></div>',
    },
  };

  beforeEach(() => {
    mockSmAndDown.value = false;
  });

  describe('title and title-actions', () => {
    it('renders title as an h1 by default', () => {
      const wrapper = mount(AppDataTable, {
        props: { title: 'Registry', headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      const h1 = wrapper.find('h1');
      expect(h1.exists()).toBe(true);
      expect(h1.text()).toBe('Registry');
    });

    it('respects titleTag override', () => {
      const wrapper = mount(AppDataTable, {
        props: { title: 'Sub-Registry', titleTag: 'h2', headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('h2').exists()).toBe(true);
      expect(wrapper.find('h2').text()).toBe('Sub-Registry');
    });

    it('does not render a title element when title prop is absent', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('h1').exists()).toBe(false);
      expect(wrapper.find('.table-title-bar').exists()).toBe(false);
    });

    it('renders title-actions slot alongside title', () => {
      const wrapper = mount(AppDataTable, {
        props: { title: 'Registry', headers: [], items: [] },
        slots: {
          'title-actions': '<button id="btn-export">Export</button>',
        },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('h1').text()).toBe('Registry');
      expect(wrapper.find('#btn-export').exists()).toBe(true);
    });

    it('renders title-actions slot even when title prop is not provided', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        slots: {
          'title-actions': '<button id="btn-action">Action</button>',
        },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('h1').exists()).toBe(false);
      expect(wrapper.find('.table-title-bar').exists()).toBe(true);
      expect(wrapper.find('#btn-action').exists()).toBe(true);
    });
  });

  describe('toolbar and filters slots', () => {
    it('renders toolbar slot when provided', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        slots: {
          toolbar: '<div id="test-toolbar">Search Toolbar</div>',
        },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.table-toolbar-container').exists()).toBe(true);
      expect(wrapper.find('#test-toolbar').exists()).toBe(true);
    });

    it('does not render toolbar container when slot is absent', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.table-toolbar-container').exists()).toBe(false);
    });

    it('renders filters slot when provided', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        slots: {
          filters: '<div id="test-filters">Filter Controls</div>',
        },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.table-filters').exists()).toBe(true);
      expect(wrapper.find('#test-filters').exists()).toBe(true);
    });

    it('does not render filters container when slot is absent', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.table-filters').exists()).toBe(false);
    });
  });

  describe('server-side vs client-side pagination table modes', () => {
    it('renders v-data-table-server when serverSide is true (default)', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.v-data-table-server').exists()).toBe(true);
      expect(wrapper.find('.v-data-table').exists()).toBe(false);
    });

    it('renders v-data-table when serverSide is false', () => {
      const wrapper = mount(AppDataTable, {
        props: { serverSide: false, headers: [], items: [] },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.v-data-table').exists()).toBe(true);
      expect(wrapper.find('.v-data-table-server').exists()).toBe(false);
    });
  });

  describe('slots passthrough and internal slots filtering', () => {
    it('passes custom slots to data table while filtering out internal slots', () => {
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        slots: {
          'title-actions': '<div id="internal-actions">Actions</div>',
          toolbar: '<div id="internal-toolbar">Toolbar</div>',
          filters: '<div id="internal-filters">Filters</div>',
          customSlot: '<div id="custom-slot-content">Custom Content</div>',
        },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.v-data-table-server #custom-slot-content').exists()).toBe(true);
      expect(wrapper.find('.v-data-table-server #internal-actions').exists()).toBe(false);
      expect(wrapper.find('.v-data-table-server #internal-toolbar').exists()).toBe(false);
      expect(wrapper.find('.v-data-table-server #internal-filters').exists()).toBe(false);
    });
  });

  describe('density prop validator', () => {
    it('validates allowed density values', () => {
      const validator = AppDataTable.props.density.validator;
      expect(validator('compact')).toBe(true);
      expect(validator('comfortable')).toBe(true);
      expect(validator('default')).toBe(true);
      expect(validator('dense')).toBe(false);
      expect(validator('large')).toBe(false);
    });
  });

  describe('mobile view and loading skeletons', () => {
    it('does not enable mobile mode when smAndDown is false', () => {
      mockSmAndDown.value = false;
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: true },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.is-mobile-cards').exists()).toBe(false);
      expect(wrapper.find('.mobile-skeletons').exists()).toBe(false);
    });

    it('respects disableMobile override when smAndDown is true', () => {
      mockSmAndDown.value = true;
      const wrapper = mount(AppDataTable, {
        props: { disableMobile: true, headers: [], items: [] },
        attrs: { loading: true },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.is-mobile-cards').exists()).toBe(false);
      expect(wrapper.find('.mobile-skeletons').exists()).toBe(false);
    });

    it('renders mobile skeletons when in mobile mode and loading is true', () => {
      mockSmAndDown.value = true;
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: true },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.is-mobile-cards').exists()).toBe(true);
      expect(wrapper.find('.mobile-skeletons').exists()).toBe(true);
      expect(wrapper.findAll('.mobile-skeleton-card')).toHaveLength(10);
    });

    it('recognizes empty string and string "true" loading attributes', () => {
      mockSmAndDown.value = true;
      const wrapperEmpty = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: '' },
        global: { stubs: defaultStubs },
      });
      expect(wrapperEmpty.find('.mobile-skeletons').exists()).toBe(true);

      const wrapperString = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: 'true' },
        global: { stubs: defaultStubs },
      });
      expect(wrapperString.find('.mobile-skeletons').exists()).toBe(true);
    });

    it('does not show skeletons when loading is false or missing', () => {
      mockSmAndDown.value = true;
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: false },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.find('.mobile-skeletons').exists()).toBe(false);
    });

    it('calculates skeletonCount based on items-per-page attribute', () => {
      mockSmAndDown.value = true;
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: true, 'items-per-page': '5' },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.findAll('.mobile-skeleton-card')).toHaveLength(5);
    });

    it('caps skeletonCount at 12 when itemsPerPage is large', () => {
      mockSmAndDown.value = true;
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: true, itemsPerPage: 25 },
        global: { stubs: defaultStubs },
      });
      expect(wrapper.findAll('.mobile-skeleton-card')).toHaveLength(12);
    });

    it('defaults skeletonCount to 10 when itemsPerPage is <= 0 or invalid', () => {
      mockSmAndDown.value = true;
      const wrapperNegative = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: true, itemsPerPage: -1 },
        global: { stubs: defaultStubs },
      });
      expect(wrapperNegative.findAll('.mobile-skeleton-card')).toHaveLength(10);

      const wrapperInvalid = mount(AppDataTable, {
        props: { headers: [], items: [] },
        attrs: { loading: true, itemsPerPage: 'all' },
        global: { stubs: defaultStubs },
      });
      expect(wrapperInvalid.findAll('.mobile-skeleton-card')).toHaveLength(10);
    });

    it('applies mobileSkeletonHeight to skeleton cards', () => {
      mockSmAndDown.value = true;
      const wrapper = mount(AppDataTable, {
        props: { headers: [], items: [], mobileSkeletonHeight: 180 },
        attrs: { loading: true },
        global: { stubs: defaultStubs },
      });
      const card = wrapper.find('.mobile-skeleton-card');
      expect(card.attributes('style')).toContain('min-height: 180px');
    });
  });
});
