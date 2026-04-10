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

  it('strips uncommon on* event handler attributes (not just the enumerated ones)', () => {
    // These are handlers that were NOT in the old FORBID_ATTR list.
    // The uponSanitizeAttribute hook should drop them too.
    const dirty =
      '<a href="https://example.com" onanimationstart="x" onpointerenter="y" onwheel="z">link</a>';
    const clean = sanitize(dirty);
    expect(clean).not.toContain('onanimationstart');
    expect(clean).not.toContain('onpointerenter');
    expect(clean).not.toContain('onwheel');
    expect(clean).toContain('href="https://example.com"');
  });

  it('strips on* handlers regardless of attribute-name casing', () => {
    const dirty = '<span OnClick="alert(1)" ONMOUSEOVER="alert(2)">x</span>';
    const clean = sanitize(dirty);
    expect(clean.toLowerCase()).not.toContain('onclick');
    expect(clean.toLowerCase()).not.toContain('onmouseover');
  });

  it('forces rel="noopener noreferrer" on target="_blank" anchors', () => {
    const dirty = '<a href="https://example.com" target="_blank">link</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('target="_blank"');
    expect(clean).toContain('rel="noopener noreferrer"');
  });

  it('does not add rel to anchors without target="_blank"', () => {
    const dirty = '<a href="https://example.com">internal</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('href="https://example.com"');
    expect(clean).not.toContain('rel=');
  });

  it('overrides insecure rel values when target="_blank"', () => {
    // Even if the author supplied a weak rel, force the safe value.
    const dirty = '<a href="https://x.test" target="_blank" rel="opener">x</a>';
    const clean = sanitize(dirty);
    expect(clean).toContain('rel="noopener noreferrer"');
    expect(clean).not.toContain('rel="opener"');
  });
});
