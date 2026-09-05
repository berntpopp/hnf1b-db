import { describe, expect, it, vi } from 'vitest';

import { archiveE2ERecord } from '@/../tests/e2e/helpers/records.js';

function response(status, body) {
  return {
    ok: () => status >= 200 && status < 300,
    status: () => status,
    text: async () => JSON.stringify(body),
  };
}

describe('archiveE2ERecord', () => {
  it('verifies the record and archives its exact current revision', async () => {
    const req = {
      get: vi.fn().mockResolvedValue(response(200, { effective_state: 'in_review', revision: 7 })),
      post: vi
        .fn()
        .mockResolvedValue(
          response(200, { phenopacket: { effective_state: 'archived', revision: 8 } })
        ),
    };

    const result = await archiveE2ERecord(
      req,
      'http://localhost:8000/api/v2',
      'admin-token',
      'e2e-record',
      { recordCreated: true }
    );

    expect(req.get).toHaveBeenCalledWith('http://localhost:8000/api/v2/phenopackets/e2e-record', {
      headers: { Authorization: 'Bearer admin-token' },
    });
    expect(req.post).toHaveBeenCalledWith(
      'http://localhost:8000/api/v2/phenopackets/e2e-record/transitions',
      {
        headers: { Authorization: 'Bearer admin-token' },
        data: {
          to_state: 'archived',
          reason: 'Archive completed E2E record',
          revision: 7,
        },
      }
    );
    expect(result).toEqual({ archived: true, alreadyArchived: false });
  });

  it('accepts a missing record only when creation never completed', async () => {
    const req = {
      get: vi.fn().mockResolvedValue(response(404, { detail: 'Phenopacket not found' })),
      post: vi.fn(),
    };

    await expect(
      archiveE2ERecord(req, 'http://localhost:8000/api/v2', 'admin-token', 'not-created', {
        recordCreated: false,
      })
    ).resolves.toEqual({ archived: false, alreadyArchived: false });
    expect(req.post).not.toHaveBeenCalled();
  });

  it('does not silently accept a failed archive response for a created record', async () => {
    const req = {
      get: vi.fn().mockResolvedValue(response(200, { effective_state: 'draft', revision: 3 })),
      post: vi.fn().mockResolvedValue(response(409, { detail: { code: 'revision_mismatch' } })),
    };

    await expect(
      archiveE2ERecord(req, 'http://localhost:8000/api/v2', 'admin-token', 'created-record', {
        recordCreated: true,
      })
    ).rejects.toThrow('archive created-record: 409');
  });

  it('preserves the primary failure and attaches a verified cleanup failure', async () => {
    const primaryError = new Error('principal assertion failed');
    const req = {
      get: vi.fn().mockResolvedValue(response(500, { detail: 'Internal server error' })),
      post: vi.fn(),
    };

    await expect(
      archiveE2ERecord(req, 'http://localhost:8000/api/v2', 'admin-token', 'failed-record', {
        recordCreated: true,
        primaryError,
      })
    ).resolves.toEqual({ archived: false, alreadyArchived: false });
    expect(primaryError.message).toContain('principal assertion failed');
    expect(primaryError.message).toContain('cleanup failed for failed-record');
    expect(primaryError.cleanupError).toBeInstanceOf(Error);
    expect(req.post).not.toHaveBeenCalled();
  });
});
