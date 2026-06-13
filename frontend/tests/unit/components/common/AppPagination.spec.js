import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import AppPagination from '@/components/common/AppPagination.vue';

const baseProps = {
  currentCount: 10,
  currentPage: 2,
  pageSize: 10,
  totalPages: 5,
  totalRecords: 50,
};

describe('AppPagination', () => {
  it('renders the range text', () => {
    const wrapper = mount(AppPagination, { props: baseProps });
    expect(wrapper.text()).toContain('1');
    expect(wrapper.text()).toContain('50');
  });

  it('emits go-to-page when a navigation button is clicked', async () => {
    const wrapper = mount(AppPagination, { props: baseProps });
    const nextBtn = wrapper.find('[aria-label="Next page"]');
    await nextBtn.trigger('click');
    expect(wrapper.emitted('go-to-page')).toBeTruthy();
    expect(wrapper.emitted('go-to-page')[0]).toEqual([3]);
  });

  it('disables First/Previous on the first page', () => {
    const wrapper = mount(AppPagination, {
      props: { ...baseProps, currentPage: 1 },
    });
    const first = wrapper.find('[aria-label="First page"]');
    expect(first.attributes('disabled')).toBeDefined();
  });

  it('exposes accessible labels for all nav controls', () => {
    const wrapper = mount(AppPagination, { props: baseProps });
    ['First page', 'Previous page', 'Next page', 'Last page'].forEach((label) => {
      expect(wrapper.find(`[aria-label="${label}"]`).exists()).toBe(true);
    });
  });
});
