import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ExternalLink from '@/components/common/ExternalLink.vue';

describe('ExternalLink', () => {
  it('renders an anchor with target=_blank and rel=noopener noreferrer', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Link text' },
    });
    const a = wrapper.get('a');
    expect(a.attributes('href')).toBe('https://example.com/a');
    expect(a.attributes('target')).toBe('_blank');
    expect(a.attributes('rel')).toBe('noopener noreferrer');
    expect(a.text()).toContain('Link text');
  });

  it('includes an mdi-open-in-new icon by default', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Link text' },
    });
    const icon = wrapper.find('[data-testid="external-link-icon"]');
    expect(icon.exists()).toBe(true);
    expect(icon.text()).toContain('mdi-open-in-new');
  });

  it('suppresses the icon when showIcon=false', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a', showIcon: false },
      slots: { default: 'Link text' },
    });
    expect(wrapper.find('[data-testid="external-link-icon"]').exists()).toBe(false);
  });

  it('applies aria-label when provided', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a', ariaLabel: 'Open example docs' },
      slots: { default: 'Docs' },
    });
    expect(wrapper.get('a').attributes('aria-label')).toBe('Open example docs');
  });

  it('omits aria-label attribute when not provided', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Link' },
    });
    expect(wrapper.get('a').attributes('aria-label')).toBeUndefined();
  });

  it('exposes a visually-hidden "opens in new tab" suffix for screen readers', () => {
    const wrapper = mount(ExternalLink, {
      props: { href: 'https://example.com/a' },
      slots: { default: 'Docs' },
    });
    const sr = wrapper.find('.sr-only');
    expect(sr.exists()).toBe(true);
    expect(sr.text()).toMatch(/opens in new tab/i);
  });
});
