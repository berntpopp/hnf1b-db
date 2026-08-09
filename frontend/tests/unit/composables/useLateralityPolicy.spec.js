import { describe, it, expect, vi, beforeEach } from 'vitest';

// Same hoisting requirement as usePhenopacketVocabularies.spec.js: the
// composable imports the named export `apiClient` from '@/api', and
// `vi.mock` factories are hoisted above the rest of the module.
const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/api', () => ({ apiClient: { get } }));

import { useLateralityPolicy } from '@/composables/useLateralityPolicy';

// Real shape confirmed live via psql against hpo_terms_lookup (2026-07-31):
// 6 terms admit at least one modifier; HP:0000122 admits exactly
// {Unilateral, Left, Right} and NOT Bilateral.
const REAL_POLICY_ROWS = [
  {
    hpo_id: 'HP:0000003',
    allowed_modifiers: ['HP:0012832', 'HP:0012833', 'HP:0012835', 'HP:0012834'],
  },
  {
    hpo_id: 'HP:0000079',
    allowed_modifiers: ['HP:0012832', 'HP:0012833', 'HP:0012835', 'HP:0012834'],
  },
  {
    hpo_id: 'HP:0000089',
    allowed_modifiers: ['HP:0012832', 'HP:0012833', 'HP:0012835', 'HP:0012834'],
  },
  {
    hpo_id: 'HP:0000107',
    allowed_modifiers: ['HP:0012832', 'HP:0012833', 'HP:0012835', 'HP:0012834'],
  },
  { hpo_id: 'HP:0000122', allowed_modifiers: ['HP:0012833', 'HP:0012835', 'HP:0012834'] },
  {
    hpo_id: 'HP:0033132',
    allowed_modifiers: ['HP:0012832', 'HP:0012833', 'HP:0012835', 'HP:0012834'],
  },
];

describe('useLateralityPolicy', () => {
  beforeEach(() => {
    get.mockReset();
    get.mockResolvedValue({ data: { data: REAL_POLICY_ROWS } });
    window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  });

  it('fetches /ontology/laterality-policy', async () => {
    const { fetchPolicy } = useLateralityPolicy();
    await fetchPolicy();
    expect(get).toHaveBeenCalledWith('/ontology/laterality-policy');
  });

  it('builds a hpo_id -> allowed_modifiers map', async () => {
    const { policy, fetchPolicy } = useLateralityPolicy();
    await fetchPolicy();

    expect(Object.keys(policy.value).sort()).toEqual(
      ['HP:0000003', 'HP:0000079', 'HP:0000089', 'HP:0000107', 'HP:0000122', 'HP:0033132'].sort()
    );
  });

  it('HP:0000122 admits Unilateral/Left/Right and NOT Bilateral', async () => {
    const { policy, fetchPolicy } = useLateralityPolicy();
    await fetchPolicy();

    expect(policy.value['HP:0000122'].sort()).toEqual(
      ['HP:0012833', 'HP:0012834', 'HP:0012835'].sort()
    );
    expect(policy.value['HP:0000122']).not.toContain('HP:0012832'); // Bilateral
  });

  it('a term absent from the response has no entry in the map', async () => {
    const { policy, fetchPolicy } = useLateralityPolicy();
    await fetchPolicy();

    expect(policy.value['HP:9999999']).toBeUndefined();
  });
});
