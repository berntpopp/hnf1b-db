import { describe, it, expect, vi, beforeEach } from 'vitest';

// The composable imports the NAMED export `apiClient` from '@/api'
// (usePhenopacketVocabularies.js:40), re-exported from src/api/index.js.
// Mocking '@/api/client' would not intercept anything — that module does not exist.
//
// `vi.mock` factories are hoisted above the rest of the module, so a plain
// `const get = vi.fn()` referenced inside one throws "Cannot access 'get'
// before initialization" — `vi.hoisted` is required to define it safely.
const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/api', () => ({ apiClient: { get } }));

import { usePhenopacketVocabularies } from '@/composables/usePhenopacketVocabularies';

const FIXTURES = {
  '/ontology/vocabularies/cohort': [
    { value: 'born', label: 'Born', description: null },
    { value: 'fetus', label: 'Fetus', description: null },
  ],
  '/ontology/vocabularies/detection-method': [{ value: 'mlpa', label: 'MLPA', description: null }],
  '/ontology/vocabularies/segregation': [{ value: 'de_novo', label: 'De novo', description: null }],
  '/ontology/vocabularies/family-history': [
    { value: 'positive', label: 'Positive', description: null },
  ],
};

describe('usePhenopacketVocabularies curation additions', () => {
  beforeEach(() => {
    get.mockReset();
    get.mockImplementation((url) => {
      const key = Object.keys(FIXTURES).find((k) => url.includes(k));
      return Promise.resolve({ data: { data: key ? FIXTURES[key] : [] } });
    });
    // loadAll() logs through window.logService (usePhenopacketVocabularies.js:62);
    // without this every test throws on the first log call.
    window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  });

  it('exposes the four curation vocabularies', () => {
    const v = usePhenopacketVocabularies();
    expect(v).toHaveProperty('cohort');
    expect(v).toHaveProperty('detectionMethod');
    expect(v).toHaveProperty('segregation');
    expect(v).toHaveProperty('familyHistory');
  });

  it('populates them from loadAll', async () => {
    const v = usePhenopacketVocabularies();
    await v.loadAll();

    expect(v.cohort.value.map((i) => i.value)).toEqual(['born', 'fetus']);
    expect(v.detectionMethod.value[0].label).toBe('MLPA');
    expect(v.segregation.value[0].value).toBe('de_novo');
    expect(v.familyHistory.value[0].value).toBe('positive');
  });

  it('still loads the five pre-existing vocabularies', async () => {
    const v = usePhenopacketVocabularies();
    await v.loadAll();
    expect(v).toHaveProperty('sex');
  });
});
