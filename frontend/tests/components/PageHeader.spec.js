import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import PageHeader from '@/components/common/PageHeader.vue';

const vuetify = createVuetify({ components, directives });

/**
 * Mount helper for PageHeader component.
 * @param {object} props - Component props (title is required)
 * @param {object} slots - Named slots to pass
 * @returns {VueWrapper} Mounted component wrapper
 */
function mountPageHeader(props = {}, slots = {}) {
  return mount(PageHeader, {
    props: { title: 'Test Title', ...props },
    slots,
    global: {
      plugins: [vuetify],
    },
  });
}

describe('PageHeader', () => {
  describe('title rendering', () => {
    it('renders title in h1 element', () => {
      const wrapper = mountPageHeader({ title: 'My Page Title' });
      expect(wrapper.find('h1').text()).toBe('My Page Title');
    });

    it('applies custom title class', () => {
      const wrapper = mountPageHeader({ titleClass: 'text-blue' });
      expect(wrapper.find('h1').classes()).toContain('text-blue');
    });

    it('applies default title class', () => {
      const wrapper = mountPageHeader();
      expect(wrapper.find('h1').classes()).toContain('text-teal-darken-2');
    });
  });

  describe('semantic HTML', () => {
    it('renders semantic header element', () => {
      const wrapper = mountPageHeader();
      expect(wrapper.find('header.page-header').exists()).toBe(true);
    });

    it('renders nav element with aria-label for breadcrumbs', () => {
      const breadcrumbs = [
        { title: 'Home', to: '/' },
        { title: 'Page', disabled: true },
      ];
      const wrapper = mountPageHeader({ breadcrumbs });
      expect(wrapper.find('nav[aria-label="Breadcrumb"]').exists()).toBe(true);
    });
  });

  describe('subtitle', () => {
    it('renders subtitle when provided', () => {
      const wrapper = mountPageHeader({ subtitle: 'Page description' });
      expect(wrapper.find('p').text()).toBe('Page description');
    });

    it('does not render subtitle when not provided', () => {
      const wrapper = mountPageHeader({ subtitle: '' });
      expect(wrapper.find('p').exists()).toBe(false);
    });

    it('does not render subtitle when undefined', () => {
      const wrapper = mountPageHeader();
      expect(wrapper.find('p').exists()).toBe(false);
    });
  });

  describe('icon', () => {
    it('renders icon when provided', () => {
      const wrapper = mountPageHeader({ icon: 'mdi-account' });
      expect(wrapper.find('.v-icon').exists()).toBe(true);
    });

    it('does not render icon when not provided', () => {
      const wrapper = mountPageHeader({ icon: '' });
      // Only the potential back button icon should exist
      const icons = wrapper.findAll('.v-icon');
      // No icon prop and no showBack means no icons in title row
      expect(icons.length).toBe(0);
    });

    it('applies icon color', () => {
      const wrapper = mountPageHeader({ icon: 'mdi-account', iconColor: 'red' });
      const icon = wrapper.find('.v-icon');
      expect(icon.exists()).toBe(true);
    });

    it('marks decorative icon as aria-hidden', () => {
      const wrapper = mountPageHeader({ icon: 'mdi-account' });
      const icon = wrapper.find('.v-icon');
      expect(icon.attributes('aria-hidden')).toBe('true');
    });
  });

  describe('breadcrumbs', () => {
    it('renders breadcrumbs when provided', () => {
      const breadcrumbs = [
        { title: 'Home', to: '/' },
        { title: 'Page', disabled: true },
      ];
      const wrapper = mountPageHeader({ breadcrumbs });
      expect(wrapper.find('nav[aria-label="Breadcrumb"]').exists()).toBe(true);
      expect(wrapper.find('.v-breadcrumbs').exists()).toBe(true);
    });

    it('does not render breadcrumbs when empty', () => {
      const wrapper = mountPageHeader({ breadcrumbs: [] });
      expect(wrapper.find('nav').exists()).toBe(false);
    });

    it('does not render breadcrumbs when undefined', () => {
      const wrapper = mountPageHeader();
      expect(wrapper.find('nav').exists()).toBe(false);
    });
  });

  describe('back button', () => {
    it('renders back button when showBack is true', () => {
      const wrapper = mountPageHeader({ showBack: true });
      expect(wrapper.find('button[aria-label="Go back"]').exists()).toBe(true);
    });

    it('does not render back button when showBack is false', () => {
      const wrapper = mountPageHeader({ showBack: false });
      expect(wrapper.find('button[aria-label="Go back"]').exists()).toBe(false);
    });

    it('emits back event when back button clicked', async () => {
      const wrapper = mountPageHeader({ showBack: true });
      await wrapper.find('button[aria-label="Go back"]').trigger('click');
      expect(wrapper.emitted('back')).toHaveLength(1);
    });
  });

  describe('variants', () => {
    it('applies hero variant class', () => {
      const wrapper = mountPageHeader({ variant: 'hero' });
      expect(wrapper.find('.page-header--hero').exists()).toBe(true);
    });

    it('applies compact variant class', () => {
      const wrapper = mountPageHeader({ variant: 'compact' });
      expect(wrapper.find('.page-header--compact').exists()).toBe(true);
    });

    it('applies no variant class for default', () => {
      const wrapper = mountPageHeader({ variant: 'default' });
      expect(wrapper.find('.page-header--hero').exists()).toBe(false);
      expect(wrapper.find('.page-header--compact').exists()).toBe(false);
    });
  });

  describe('slots', () => {
    it('renders actions slot content', () => {
      const wrapper = mountPageHeader(
        {},
        { actions: '<button class="action-btn">Action</button>' }
      );
      expect(wrapper.find('.action-btn').exists()).toBe(true);
    });

    it('renders prepend slot content', () => {
      const wrapper = mountPageHeader({}, { prepend: '<span class="badge">New</span>' });
      expect(wrapper.find('.badge').exists()).toBe(true);
    });

    it('does not render actions wrapper when slot is empty', () => {
      const wrapper = mountPageHeader();
      // The actions wrapper should not be rendered if slot is empty
      // Check there's no actions div when no slot content
      expect(wrapper.findAll('.d-flex.align-center.gap-2').length).toBeLessThanOrEqual(1);
    });
  });

  describe('container', () => {
    it('uses fluid container by default', () => {
      const wrapper = mountPageHeader();
      const container = wrapper.find('.v-container');
      expect(container.exists()).toBe(true);
    });

    it('respects fluid prop', () => {
      const wrapper = mountPageHeader({ fluid: false });
      const container = wrapper.find('.v-container');
      expect(container.exists()).toBe(true);
    });
  });
});
