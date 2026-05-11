import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

const { announceMock } = vi.hoisted(() => ({ announceMock: vi.fn() }));

vi.mock('@/utils/chartExport', () => ({
  exportSvgAsPng: vi.fn().mockResolvedValue(),
  exportSvgAsSvg: vi.fn(),
  exportDataAsCsv: vi.fn(),
  buildExportFilename: vi.fn((name, ext) => `hnf1b-db_${name}_${ext}`),
}));

vi.mock('@/composables/useAccessibility', () => ({
  useAnnouncer: () => ({ announce: announceMock }),
}));

import ChartExportMenu from '@/components/analyses/ChartExportMenu.vue';
import { exportSvgAsPng, exportSvgAsSvg, exportDataAsCsv } from '@/utils/chartExport';

const vuetify = createVuetify({ components, directives });

describe('ChartExportMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function makeWrapper(propsOverrides = {}) {
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    return mount(ChartExportMenu, {
      global: { plugins: [vuetify] },
      props: {
        svgEl,
        rows: [{ a: 1 }],
        columns: [{ key: 'a', label: 'A' }],
        chartName: 'Test Chart',
        ...propsOverrides,
      },
    });
  }

  it('disables the menu button when svgEl is null', () => {
    const wrapper = mount(ChartExportMenu, {
      global: { plugins: [vuetify] },
      props: {
        svgEl: null,
        rows: [],
        columns: [],
        chartName: 'Test',
      },
    });
    const btn = wrapper.find('button');
    expect(btn.attributes('disabled')).toBeDefined();
  });

  it('invokes PNG export and announces on click', async () => {
    const wrapper = makeWrapper();
    await wrapper.vm.exportPng();
    expect(exportSvgAsPng).toHaveBeenCalledOnce();
    expect(announceMock).toHaveBeenCalledWith('Chart exported as PNG');
  });

  it('invokes CSV export and announces on click', async () => {
    const wrapper = makeWrapper();
    await wrapper.vm.exportCsv();
    expect(exportDataAsCsv).toHaveBeenCalledOnce();
    expect(announceMock).toHaveBeenCalledWith('Chart exported as CSV');
  });

  it('invokes SVG export and announces on click', async () => {
    const wrapper = makeWrapper();
    await wrapper.vm.exportSvg();
    expect(exportSvgAsSvg).toHaveBeenCalledOnce();
    expect(announceMock).toHaveBeenCalledWith('Chart exported as SVG');
  });
});
