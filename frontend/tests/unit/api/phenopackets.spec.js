import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDelete = vi.fn();

vi.mock('@/api/transport', () => ({
  apiClient: {
    delete: mockDelete,
  },
}));

describe('phenopackets API domain helper', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends revision and change_reason in the delete request body', async () => {
    const { deletePhenopacket } = await import('@/api/domain/phenopackets');

    await deletePhenopacket('PP-1', 7, 'cleanup duplicate record');

    expect(mockDelete).toHaveBeenCalledWith('/phenopackets/PP-1', {
      data: {
        revision: 7,
        change_reason: 'cleanup duplicate record',
      },
    });
  });
});
