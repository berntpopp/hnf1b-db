import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import CorrectionAppendPanel from '@/components/curation/reports/CorrectionAppendPanel.vue';

describe('CorrectionAppendPanel', () => {
  it('emits an append-only correction with exact preimage and predecessor', async () => {
    const wrapper = mount(CorrectionAppendPanel, {
      props: {
        observation: {
          observationId: 'report-1',
          variant: {
            reported: {
              raw: 'c.1A>G',
              sourceStatus: 'stated',
              value: 'NM_1:c.1A>G',
              correctionIds: ['correction-1'],
            },
          },
        },
        corrections: [
          {
            correctionId: 'correction-1',
            jsonPointer: '/observationsById/report-1/variant/reported/value',
            preimage: 'NM_1:c.1A>G',
            postimage: 'NM_1:c.1A>C',
            supersedesCorrectionId: null,
          },
        ],
      },
    });
    await wrapper.get('select').setValue('/observationsById/report-1/variant/reported/value');
    await wrapper.findAll('textarea')[0].setValue('"NM_1:c.1A>T"');
    await wrapper.findAll('textarea')[1].setValue('Corrected against the publication.');
    await wrapper.get('button').trigger('click');

    expect(wrapper.emitted('append')[0][0]).toEqual({
      jsonPointer: '/observationsById/report-1/variant/reported/value',
      preimage: 'NM_1:c.1A>C',
      postimage: 'NM_1:c.1A>T',
      reason: 'Corrected against the publication.',
      supersedesCorrectionId: 'correction-1',
    });
  });
});
