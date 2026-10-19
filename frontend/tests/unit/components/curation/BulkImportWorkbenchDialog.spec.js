/**
 * Unit tests for BulkImportWorkbenchDialog.vue (Issue #554).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import { apiClient } from '@/api';
import BulkImportWorkbenchDialog from '@/components/curation/BulkImportWorkbenchDialog.vue';

vi.mock('@/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

let wrapper;

beforeEach(() => {
  vi.clearAllMocks();
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
});

function mountWorkbench() {
  const vuetify = createVuetify({
    components: vuetifyComponents,
    directives: vuetifyDirectives,
  });

  wrapper = mount(BulkImportWorkbenchDialog, {
    global: {
      plugins: [vuetify],
    },
    attachTo: document.body,
  });
  return wrapper;
}

describe('BulkImportWorkbenchDialog.vue', () => {
  it('renders bulk import trigger button with data-testid', () => {
    mountWorkbench();
    const btn = document.querySelector('[data-testid="bulk-import-workbench-btn"]');
    expect(btn).not.toBeNull();
    expect(btn.textContent).toContain('Bulk Import Workbench');
  });

  it('runs dry-run preview and renders validation report table', async () => {
    const mockReport = {
      dry_run: true,
      total_rows: 2,
      valid_rows: 1,
      invalid_rows: 1,
      committed_rows: 0,
      results: [
        {
          row_index: 0,
          phenopacket_id: 'BATCH-001',
          subject_id: 'SUB-001',
          valid: true,
          errors: [],
          warnings: [],
          already_exists: false,
        },
        {
          row_index: 1,
          phenopacket_id: 'BATCH-002',
          subject_id: '',
          valid: false,
          errors: ['Missing required field: subject.id'],
          warnings: [],
          already_exists: false,
        },
      ],
    };

    apiClient.post.mockResolvedValueOnce({ data: mockReport });

    mountWorkbench();
    const openBtn = document.querySelector('[data-testid="bulk-import-workbench-btn"]');
    openBtn.click();

    let textarea = null;
    await vi.waitFor(() => {
      textarea = document.querySelector('[data-testid="batch-json-input"] textarea');
      expect(textarea).not.toBeNull();
    });

    textarea.value = JSON.stringify([{ id: 'BATCH-001' }, { id: 'BATCH-002' }]);
    textarea.dispatchEvent(new Event('input'));

    const dryRunBtn = document.querySelector('[data-testid="run-dry-run-btn"]');
    dryRunBtn.click();

    expect(apiClient.post).toHaveBeenCalledWith(
      '/phenopackets/import-batch',
      { phenopackets: [{ id: 'BATCH-001' }, { id: 'BATCH-002' }] },
      { params: { dry_run: true } }
    );

    await vi.waitFor(() => {
      const table = document.querySelector('[data-testid="batch-report-table"]');
      expect(table).not.toBeNull();
      expect(table.textContent).toContain('BATCH-001');
      expect(table.textContent).toContain('BATCH-002');
      expect(table.textContent).toContain('Missing required field: subject.id');
    });
  });

  it('commits approved rows as drafts on button click', async () => {
    const mockReport = {
      dry_run: true,
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      committed_rows: 0,
      results: [
        {
          row_index: 0,
          phenopacket_id: 'BATCH-001',
          subject_id: 'SUB-001',
          valid: true,
          errors: [],
          warnings: [],
          already_exists: false,
        },
      ],
    };

    const mockCommitResponse = {
      dry_run: false,
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      committed_rows: 1,
      results: [
        {
          row_index: 0,
          phenopacket_id: 'BATCH-001',
          subject_id: 'SUB-001',
          valid: true,
          errors: [],
          warnings: [],
          already_exists: false,
        },
      ],
    };

    apiClient.post
      .mockResolvedValueOnce({ data: mockReport })
      .mockResolvedValueOnce({ data: mockCommitResponse });

    mountWorkbench();
    const openBtn = document.querySelector('[data-testid="bulk-import-workbench-btn"]');
    openBtn.click();

    let textarea = null;
    await vi.waitFor(() => {
      textarea = document.querySelector('[data-testid="batch-json-input"] textarea');
      expect(textarea).not.toBeNull();
    });

    textarea.value = JSON.stringify([{ id: 'BATCH-001' }]);
    textarea.dispatchEvent(new Event('input'));

    const dryRunBtn = document.querySelector('[data-testid="run-dry-run-btn"]');
    dryRunBtn.click();

    let commitBtn = null;
    await vi.waitFor(() => {
      commitBtn = document.querySelector('[data-testid="commit-batch-btn"]');
      expect(commitBtn).not.toBeNull();
      expect(commitBtn.hasAttribute('disabled')).toBe(false);
    });

    commitBtn.click();

    expect(apiClient.post).toHaveBeenLastCalledWith(
      '/phenopackets/import-batch',
      { phenopackets: [{ id: 'BATCH-001' }] },
      { params: { dry_run: false } }
    );

    await vi.waitFor(() => {
      const dialog = document.querySelector('[data-testid="bulk-import-workbench-dialog"]');
      expect(dialog.textContent).toContain('Successfully committed 1 phenopacket as drafts.');
    });
  });
});
