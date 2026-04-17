import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import AppDataTable from '@/components/common/AppDataTable.vue';

describe('AppDataTable', () => {
  it('renders title as an h1 by default', () => {
    const wrapper = mount(AppDataTable, {
      props: { title: 'Registry', headers: [], items: [] },
    });
    const h1 = wrapper.find('h1');
    expect(h1.exists()).toBe(true);
    expect(h1.text()).toBe('Registry');
  });

  it('respects titleTag override', () => {
    const wrapper = mount(AppDataTable, {
      props: { title: 'Sub-Registry', titleTag: 'h2', headers: [], items: [] },
    });
    expect(wrapper.find('h2').exists()).toBe(true);
    expect(wrapper.find('h2').text()).toBe('Sub-Registry');
  });

  it('does not render a title element when title prop is absent', () => {
    const wrapper = mount(AppDataTable, {
      props: { headers: [], items: [] },
    });
    expect(wrapper.find('h1').exists()).toBe(false);
  });
});
