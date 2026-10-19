import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import AppDataTable from '@/components/common/AppDataTable.vue';

function mountTable(options = {}) {
  const vuetify = createVuetify({ components, directives });
  const { props = {}, slots = {}, attrs = {} } = options;
  return mount(AppDataTable, {
    props: {
      headers: [{ title: 'Name', key: 'name' }],
      items: [{ name: 'row-one' }],
      ...props,
    },
    attrs,
    slots,
    global: { plugins: [vuetify] },
  });
}

describe('AppDataTable', () => {
  it('renders title as an h1 by default', () => {
    const wrapper = mountTable({
      props: { title: 'Registry' },
    });
    const h1 = wrapper.find('h1');
    expect(h1.exists()).toBe(true);
    expect(h1.text()).toBe('Registry');
  });

  it('respects titleTag override', () => {
    const wrapper = mountTable({
      props: { title: 'Sub-Registry', titleTag: 'h2' },
    });
    expect(wrapper.find('h2').exists()).toBe(true);
    expect(wrapper.find('h2').text()).toBe('Sub-Registry');
  });

  it('does not render a title element when title prop is absent', () => {
    const wrapper = mountTable();
    expect(wrapper.find('h1').exists()).toBe(false);
  });

  it('renders title-actions slot when provided without title', () => {
    const wrapper = mountTable({
      slots: {
        'title-actions': '<button id="test-action">Action</button>',
      },
    });
    expect(wrapper.find('#test-action').exists()).toBe(true);
    expect(wrapper.find('h1').exists()).toBe(false);
  });

  it('renders title and title-actions together', () => {
    const wrapper = mountTable({
      props: { title: 'Registry' },
      slots: {
        'title-actions': '<button id="test-action">Export</button>',
      },
    });
    expect(wrapper.find('h1').text()).toBe('Registry');
    expect(wrapper.find('#test-action').exists()).toBe(true);
  });

  it('renders toolbar slot when provided', () => {
    const wrapper = mountTable({
      slots: {
        toolbar: '<div id="test-toolbar">Search Toolbar</div>',
      },
    });
    expect(wrapper.find('#test-toolbar').exists()).toBe(true);
  });

  it('renders legacy filters slot when provided', () => {
    const wrapper = mountTable({
      slots: {
        filters: '<div id="test-filters">Filters</div>',
      },
    });
    expect(wrapper.find('#test-filters').exists()).toBe(true);
  });

  it('renders v-data-table-server when serverSide is true (default)', () => {
    const wrapper = mountTable({
      props: { serverSide: true },
    });
    expect(wrapper.findComponent({ name: 'VDataTableServer' }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'VDataTable' }).exists()).toBe(false);
  });

  it('renders v-data-table when serverSide is false', () => {
    const wrapper = mountTable({
      props: { serverSide: false },
    });
    expect(wrapper.findComponent({ name: 'VDataTable' }).exists()).toBe(true);
  });

  it('passes density and disableMobile props', () => {
    const wrapper = mountTable({
      props: { density: 'comfortable', disableMobile: true },
    });
    const table = wrapper.findComponent({ name: 'VDataTableServer' });
    expect(table.props('density')).toBe('comfortable');
    expect(table.props('mobile')).toBe(false);
  });

  it('handles loading state and itemsPerPage for skeletonCount', () => {
    const wrapper = mountTable({
      attrs: {
        loading: true,
        itemsPerPage: 5,
      },
    });
    expect(wrapper.exists()).toBe(true);
  });

  it('handles string loading attributes and items-per-page attribute', () => {
    const wrapper1 = mountTable({
      attrs: {
        loading: 'true',
        'items-per-page': '20',
      },
    });
    expect(wrapper1.exists()).toBe(true);

    const wrapper2 = mountTable({
      attrs: {
        loading: '',
        'items-per-page': -1,
      },
    });
    expect(wrapper2.exists()).toBe(true);
  });

  it('forwards custom slots to data table', () => {
    const wrapper = mountTable({
      slots: {
        top: '<div id="custom-top">Top slot</div>',
      },
    });
    expect(wrapper.find('#custom-top').exists()).toBe(true);
  });
});
