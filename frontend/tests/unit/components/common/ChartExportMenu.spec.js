/**
 * Unit tests for ChartExportMenu component
 *
 * Tests cover:
 * - Component renders export button
 * - PNG option emits 'export-png' event
 * - CSV option emits 'export-csv' event
 * - CSV option hidden when showCsv=false
 *
 * Note: Uses shallowMount with Vuetify stubs to avoid full Vuetify resolution.
 *
 * @module tests/unit/components/common/ChartExportMenu
 */

import { describe, it, expect } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import ChartExportMenu from '@/components/common/ChartExportMenu.vue';

// Stub Vuetify components to avoid resolution errors
const vuetifyStubs = {
  'v-menu': {
    template: '<div class="v-menu"><slot /><slot name="activator" :props="{}" /></div>',
  },
  'v-btn': {
    template: '<button class="v-btn" @click="$emit(\'click\')"><slot /></button>',
    props: ['variant', 'size', 'color'],
    emits: ['click'],
  },
  'v-icon': {
    template: '<i class="v-icon"><slot /></i>',
    props: ['start', 'size'],
  },
  'v-list': {
    template: '<div class="v-list"><slot /></div>',
    props: ['density'],
  },
  'v-list-item': {
    template:
      '<div class="v-list-item" @click="$emit(\'click\')"><slot /><slot name="prepend" /></div>',
    emits: ['click'],
  },
  'v-list-item-title': {
    template: '<span class="v-list-item-title"><slot /></span>',
  },
};

/**
 * Helper function to mount ChartExportMenu with common options
 * @param {Object} props - Component props
 * @returns {Wrapper} Vue test utils wrapper
 */
function mountMenu(props = {}) {
  return shallowMount(ChartExportMenu, {
    props,
    global: {
      stubs: vuetifyStubs,
    },
  });
}

describe('ChartExportMenu', () => {
  describe('rendering', () => {
    it('renders export button', () => {
      const wrapper = mountMenu();
      const button = wrapper.find('.v-btn');

      expect(button.exists()).toBe(true);
      expect(wrapper.text()).toContain('Export');
    });

    it('renders download icon in button', () => {
      const wrapper = mountMenu();
      const icon = wrapper.find('.v-btn .v-icon');

      expect(icon.exists()).toBe(true);
      expect(icon.text()).toContain('mdi-download');
    });

    it('renders menu with list items', () => {
      const wrapper = mountMenu();
      const menu = wrapper.find('.v-menu');
      const list = wrapper.find('.v-list');

      expect(menu.exists()).toBe(true);
      expect(list.exists()).toBe(true);
    });

    it('renders PNG option', () => {
      const wrapper = mountMenu();

      expect(wrapper.text()).toContain('Download PNG');
    });

    it('renders CSV option by default', () => {
      const wrapper = mountMenu();

      expect(wrapper.text()).toContain('Download CSV');
    });

    it('renders image icon for PNG option', () => {
      const wrapper = mountMenu();
      const listItems = wrapper.findAll('.v-list-item');
      const pngItem = listItems[0];

      expect(pngItem.text()).toContain('mdi-image');
    });

    it('renders file icon for CSV option', () => {
      const wrapper = mountMenu();
      const listItems = wrapper.findAll('.v-list-item');
      const csvItem = listItems[1];

      expect(csvItem.text()).toContain('mdi-file-delimited');
    });
  });

  describe('showCsv prop', () => {
    it('hides CSV option when showCsv is false', () => {
      const wrapper = mountMenu({ showCsv: false });

      expect(wrapper.text()).not.toContain('Download CSV');
    });

    it('shows CSV option when showCsv is true', () => {
      const wrapper = mountMenu({ showCsv: true });

      expect(wrapper.text()).toContain('Download CSV');
    });

    it('shows PNG option regardless of showCsv', () => {
      const wrapper = mountMenu({ showCsv: false });

      expect(wrapper.text()).toContain('Download PNG');
    });

    it('defaults showCsv to true', () => {
      const wrapper = mountMenu();

      expect(wrapper.props('showCsv')).toBe(true);
    });
  });

  describe('events', () => {
    it('emits export-png when PNG option is clicked', async () => {
      const wrapper = mountMenu();
      const listItems = wrapper.findAll('.v-list-item');
      const pngItem = listItems[0];

      await pngItem.trigger('click');

      expect(wrapper.emitted('export-png')).toHaveLength(1);
    });

    it('emits export-csv when CSV option is clicked', async () => {
      const wrapper = mountMenu({ showCsv: true });
      const listItems = wrapper.findAll('.v-list-item');
      const csvItem = listItems[1];

      await csvItem.trigger('click');

      expect(wrapper.emitted('export-csv')).toHaveLength(1);
    });

    it('declares both emits', () => {
      const wrapper = mountMenu();
      const emits = wrapper.vm.$options.emits;

      expect(emits).toContain('export-png');
      expect(emits).toContain('export-csv');
    });
  });

  describe('component definition', () => {
    it('has correct component name', () => {
      const wrapper = mountMenu();

      expect(wrapper.vm.$options.name).toBe('ChartExportMenu');
    });

    it('has showCsv prop with correct type', () => {
      const wrapper = mountMenu();
      const props = wrapper.vm.$options.props;

      expect(props.showCsv.type).toBe(Boolean);
      expect(props.showCsv.default).toBe(true);
    });
  });
});
