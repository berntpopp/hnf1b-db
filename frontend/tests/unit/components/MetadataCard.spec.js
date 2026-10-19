import { describe, expect, it } from 'vitest';

import MetadataCard from '@/components/phenopacket/MetadataCard.vue';

describe('MetadataCard publication attribution', () => {
  it('matches update publications by explicit identity and never by array position', () => {
    const context = {
      metaData: {
        externalReferences: [{ id: 'PMID:111' }, { id: 'PMID:222' }],
        updates: [
          { timestamp: '2025-01-01', publication: 'PMID:222' },
          { timestamp: '2025-01-02', publication: 'PMID:111' },
          { timestamp: '2025-01-03' },
        ],
      },
      getPmidNumber: MetadataCard.methods.getPmidNumber,
    };

    expect(
      MetadataCard.computed.enhancedUpdates.call(context).map((update) => update.pmid?.id || null)
    ).toEqual(['PMID:222', 'PMID:111', null]);
  });
});

describe('MetadataCard formatExternalReferenceUrl [SEC-04]', () => {
  const { formatExternalReferenceUrl } = MetadataCard.methods;

  it('allows valid https and http URLs in reference field', () => {
    expect(formatExternalReferenceUrl({ reference: 'https://example.com' })).toBe('https://example.com');
    expect(formatExternalReferenceUrl({ reference: 'http://example.com' })).toBe('http://example.com');
  });

  it('blocks javascript: URLs in reference field and falls back to "#"', () => {
    expect(formatExternalReferenceUrl({ reference: 'javascript:alert(1)' })).toBe('#');
    expect(formatExternalReferenceUrl({ reference: '  JAVASCRIPT:alert(1)  ' })).toBe('#');
  });

  it('constructs URLs for PMID and DOI IDs', () => {
    expect(formatExternalReferenceUrl({ id: 'PMID:12345678' })).toBe(
      'https://pubmed.ncbi.nlm.nih.gov/12345678/'
    );
    expect(formatExternalReferenceUrl({ id: 'DOI:10.1000/182' })).toBe(
      'https://doi.org/10.1000/182'
    );
  });

  it('falls back to "#" for unknown ID types or missing references', () => {
    expect(formatExternalReferenceUrl({ id: 'OTHER:123' })).toBe('#');
    expect(formatExternalReferenceUrl(null)).toBe('#');
  });
});
