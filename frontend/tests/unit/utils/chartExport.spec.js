import { describe, it, expect, vi, beforeEach } from 'vitest';
import { buildExportFilename } from '@/utils/chartExport';

describe('buildExportFilename', () => {
  it('formats as hnf1b-db_<kebab>_<date>.<ext>', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T12:00:00Z'));
    expect(buildExportFilename('Sex Distribution', 'png')).toBe(
      'hnf1b-db_sex-distribution_2026-05-11.png'
    );
    vi.useRealTimers();
  });

  it('kebab-cases multi-word names with mixed case and underscores', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-11T00:00:00Z'));
    expect(buildExportFilename('Kaplan_Meier survivalCurve', 'csv')).toBe(
      'hnf1b-db_kaplan-meier-survival-curve_2026-05-11.csv'
    );
    vi.useRealTimers();
  });
});

describe('exportDataAsCsv', () => {
  let saveAsMock;
  beforeEach(() => {
    vi.resetModules();
    saveAsMock = vi.fn();
    vi.doMock('file-saver', () => ({ saveAs: saveAsMock, default: { saveAs: saveAsMock } }));
  });

  it('writes BOM + headers + rows with CRLF line endings', async () => {
    const { exportDataAsCsv: fn } = await import('@/utils/chartExport');
    fn(
      [
        { label: 'Male', count: 389 },
        { label: 'Female', count: 416 },
      ],
      [
        { key: 'label', label: 'Group' },
        { key: 'count', label: 'N' },
      ],
      'test.csv'
    );
    expect(saveAsMock).toHaveBeenCalledOnce();
    const [blob, filename] = saveAsMock.mock.calls[0];
    expect(filename).toBe('test.csv');
    expect(blob.type).toBe('text/csv;charset=utf-8');
    const text = await blob.text();
    expect(text).toBe('﻿Group,N\r\nMale,389\r\nFemale,416\r\n');
  });

  it('quotes fields containing commas, quotes, or newlines (RFC 4180)', async () => {
    const { exportDataAsCsv: fn } = await import('@/utils/chartExport');
    fn(
      [{ a: 'has, comma', b: 'has "quote"', c: 'has\nnewline' }],
      [
        { key: 'a', label: 'A' },
        { key: 'b', label: 'B' },
        { key: 'c', label: 'C' },
      ],
      'test.csv'
    );
    const [blob] = saveAsMock.mock.calls[0];
    const text = await blob.text();
    expect(text).toBe('﻿A,B,C\r\n"has, comma","has ""quote""","has\nnewline"\r\n');
  });

  it('renders null / undefined as empty fields', async () => {
    const { exportDataAsCsv: fn } = await import('@/utils/chartExport');
    fn(
      [{ a: null, b: undefined, c: 0 }],
      [
        { key: 'a', label: 'A' },
        { key: 'b', label: 'B' },
        { key: 'c', label: 'C' },
      ],
      'test.csv'
    );
    const [blob] = saveAsMock.mock.calls[0];
    const text = await blob.text();
    expect(text).toBe('﻿A,B,C\r\n,,0\r\n');
  });
});

describe('exportSvgAsSvg', () => {
  let saveAsMock;
  beforeEach(() => {
    saveAsMock = vi.fn();
    vi.resetModules();
    vi.doMock('file-saver', () => ({ saveAs: saveAsMock, default: { saveAs: saveAsMock } }));
  });

  it('serializes the SVG element and saves with image/svg+xml MIME', async () => {
    const { exportSvgAsSvg: fn } = await import('@/utils/chartExport');
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('width', '100');
    svgEl.setAttribute('height', '50');
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', '10');
    circle.setAttribute('cy', '10');
    circle.setAttribute('r', '5');
    svgEl.appendChild(circle);

    fn(svgEl, 'chart.svg');

    expect(saveAsMock).toHaveBeenCalledOnce();
    const [blob, filename] = saveAsMock.mock.calls[0];
    expect(filename).toBe('chart.svg');
    expect(blob.type).toBe('image/svg+xml;charset=utf-8');
    const text = await blob.text();
    expect(text).toContain('<svg');
    expect(text).toContain('<circle');
  });
});
