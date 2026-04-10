/**
 * Unit tests for the sanitize utility.
 *
 * Tests cover: script removal, event-handler stripping, javascript: URLs,
 * and preservation of the markdown-friendly tag whitelist.
 */
import { describe, it, expect } from 'vitest';
import { sanitize } from '@/utils/sanitize';

describe('sanitize', () => {
  it('strips <script> tags', () => {
    const dirty = 'hello <script>alert(1)</script> world';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('<script>');
    expect(clean).not.toContain('alert(1)');
    expect(clean).toContain('hello');
    expect(clean).toContain('world');
  });

  it('strips event handler attributes', () => {
    const dirty = '<a href="https://example.com" onclick="alert(1)">link</a>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('onclick');
    expect(clean).toContain('href="https://example.com"');
  });

  it('strips javascript: URLs', () => {
    const dirty = '<a href="javascript:alert(1)">click</a>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('javascript:');
  });

  it('preserves strong, em, and anchor tags used by markdown', () => {
    const dirty =
      '<strong>bold</strong> <em>italic</em> <a href="https://ok.test" target="_blank">link</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('<strong>bold</strong>');
    expect(clean).toContain('<em>italic</em>');
    expect(clean).toContain('<a ');
    expect(clean).toContain('href="https://ok.test"');
  });

  it('preserves paragraph and span tags', () => {
    const dirty = '<p>paragraph</p><span>span</span>';
    const clean = sanitize(dirty);
    expect(clean).toContain('<p>paragraph</p>');
    expect(clean).toContain('<span>span</span>');
  });

  it('returns empty string for null or undefined input', () => {
    expect(sanitize(null)).toBe('');
    expect(sanitize(undefined)).toBe('');
    expect(sanitize('')).toBe('');
  });
});
