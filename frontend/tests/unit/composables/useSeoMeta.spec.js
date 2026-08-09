/**
 * Regression fence for the MONDO id published in useGeneSeo's dataset
 * structured data (2026-07-30 defect).
 *
 * `MONDO:0010894` is "maturity-onset diabetes of the young type 3" (MODY3) --
 * the HNF1A disease, verified live against OLS4. This is an HNF1B database:
 * the correct term is `MONDO:0007669` "renal cysts and diabetes syndrome",
 * which is what the corpus stores in every record and what `index.html`'s
 * static Bioschemas block already used. `frontend/index.html:368,370` carried
 * the same wrong id and were fixed alongside this file; there is no
 * JS-importable equivalent to unit-test there, so this spec covers the one
 * function that emits the id programmatically.
 */
import { describe, it, expect, vi } from 'vitest';

// useSeoMeta.js calls useHead()/useSeoMeta() from @unhead/vue at module scope
// inside each exported composable; mock them so this test doesn't need the
// Unhead plugin installed, matching the pattern used by
// tests/unit/views/PageVariant.spec.js.
vi.mock('@unhead/vue', () => ({
  useHead: vi.fn(),
  useSeoMeta: vi.fn(),
}));

import { useVariantStructuredData } from '@/composables/useSeoMeta';

describe('useVariantStructuredData', () => {
  it('publishes the HNF1B disease MONDO id, not the HNF1A MODY3 id', () => {
    const { structuredData } = useVariantStructuredData({
      variant_id: 'v1',
      hgvs_c: 'c.544+1G>A',
    });

    const disease = structuredData.value.study.studySubject;
    expect(disease.code.codeValue).toBe('MONDO:0007669');
    expect(disease.code.codeValue).not.toBe('MONDO:0010894');
    expect(disease.name).toBe('Renal cysts and diabetes syndrome');
  });
});
