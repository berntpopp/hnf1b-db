/**
 * Characterization test for FAQ.vue XSS resistance.
 *
 * Does not mount the full component (it fetches remote content
 * asynchronously). Instead tests the renderMarkdown + sanitize pipeline
 * directly by exercising the same transformation chain FAQ.vue uses.
 */
import { describe, it, expect } from 'vitest';
import { sanitize } from '@/utils/sanitize';

// Mirror the renderMarkdown function from FAQ.vue so tests stay focused
// on the sanitize integration without requiring component mount.
const renderMarkdown = (text) => {
  if (!text) return '';
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
};

describe('FAQ rendering pipeline (renderMarkdown + sanitize)', () => {
  it('strips injected <script> tags from markdown', () => {
    const input = 'Hello <script>alert("xss")</script> world';
    const output = sanitize(renderMarkdown(input));
    expect(output).not.toContain('<script>');
    expect(output).not.toContain('alert');
  });

  it('renders bold and italic markdown safely', () => {
    const input = '**bold** and *italic*';
    const output = sanitize(renderMarkdown(input));
    expect(output).toContain('<strong>bold</strong>');
    expect(output).toContain('<em>italic</em>');
  });

  it('renders safe external links with target blank', () => {
    const input = '[GA4GH](https://www.ga4gh.org)';
    const output = sanitize(renderMarkdown(input));
    expect(output).toContain('href="https://www.ga4gh.org"');
    expect(output).toContain('target="_blank"');
  });

  it('strips javascript: URLs in markdown links', () => {
    const input = '[evil](javascript:alert(1))';
    const output = sanitize(renderMarkdown(input));
    expect(output).not.toContain('javascript:');
  });

  it('strips HTML event handlers even if injected raw', () => {
    const input = '<a href="https://x.test" onclick="alert(1)">x</a>';
    const output = sanitize(input);
    expect(output).not.toContain('onclick');
  });
});
