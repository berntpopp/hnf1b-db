/**
 * Unit tests for VariantAnnotator.vue (Wave 6 Task 4)
 *
 * VariantAnnotator is an Options-API component that takes a variant
 * notation (HGVS / VCF / rsID), detects the format client-side, and
 * submits it to `annotateVariant` from @/api. Results drive a details
 * card; errors emit an `error` event and surface a v-alert.
 *
 * These tests verify:
 *   1. Mounts cleanly with no props.
 *   2. detectedFormat correctly classifies HGVS, VCF, rsID, and
 *      rejects unknown notation as 'Unknown'.
 *   3. handleAnnotate calls annotateVariant and emits `annotated`
 *      with the payload on success.
 *   4. handleAnnotate emits `error` and sets a user-visible message
 *      when the API returns a 404.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

const annotateVariant = vi.fn();

vi.mock('@/api', () => ({
  annotateVariant: (...args) => annotateVariant(...args),
}));

import VariantAnnotator from '@/components/VariantAnnotator.vue';

function mountAnnotator() {
  const vuetify = createVuetify({ components, directives });
  // window.logService is required by the component — see
  // AGENTS.md: "Never use console.log; use window.logService."
  window.logService = {
    info: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  };
  return mount(VariantAnnotator, {
    global: { plugins: [vuetify] },
  });
}

describe('VariantAnnotator', () => {
  beforeEach(() => {
    annotateVariant.mockReset();
  });

  it('mounts and renders the annotate button', () => {
    const wrapper = mountAnnotator();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain('Annotate Variant');
  });

  it('detectedFormat returns HGVS for HGVS notation', async () => {
    const wrapper = mountAnnotator();
    await wrapper.setData({ variantInput: 'NM_000458.4:c.544+1G>A' });
    expect(wrapper.vm.detectedFormat).toBe('HGVS');
  });

  it('detectedFormat returns VCF for VCF notation', async () => {
    const wrapper = mountAnnotator();
    await wrapper.setData({ variantInput: '17-36459258-A-G' });
    expect(wrapper.vm.detectedFormat).toBe('VCF');
  });

  it('detectedFormat returns rsID for rsID notation', async () => {
    const wrapper = mountAnnotator();
    await wrapper.setData({ variantInput: 'rs56116432' });
    expect(wrapper.vm.detectedFormat).toBe('rsID');
  });

  it('detectedFormat returns Unknown for garbage input', async () => {
    const wrapper = mountAnnotator();
    await wrapper.setData({ variantInput: 'not-a-variant' });
    expect(wrapper.vm.detectedFormat).toBe('Unknown');
  });

  it('handleAnnotate emits annotated event on success', async () => {
    const payload = { most_severe_consequence: 'missense_variant' };
    annotateVariant.mockResolvedValue({ data: payload });

    const wrapper = mountAnnotator();
    await wrapper.setData({ variantInput: 'rs56116432' });
    await wrapper.vm.handleAnnotate();
    await flushPromises();

    expect(annotateVariant).toHaveBeenCalledWith('rs56116432');
    expect(wrapper.emitted('annotated')).toBeTruthy();
    expect(wrapper.emitted('annotated')[0][0]).toEqual(payload);
  });

  it('handleAnnotate emits error and surfaces a message on 404', async () => {
    annotateVariant.mockRejectedValue({ response: { status: 404 } });

    const wrapper = mountAnnotator();
    await wrapper.setData({ variantInput: 'rs00000000' });
    await wrapper.vm.handleAnnotate();
    await flushPromises();

    expect(wrapper.emitted('error')).toBeTruthy();
    expect(wrapper.vm.errorMessage).toContain('Variant not found');
  });
});
