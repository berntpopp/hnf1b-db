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
