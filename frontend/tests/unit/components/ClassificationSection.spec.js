/**
 * Unit tests for ClassificationSection.vue (curation console plan Task 6;
 * design spec §3.3). Renders inside PhenopacketCreateEdit.vue's
 * <CurationSection id="classification">, operating on the SAME primary
 * variant (`phenopacket.interpretations[0]`) Task 5's VariantAnnotationForm
 * edits, plus the three case-level `hnf1bCuration.classification*` fields.
 *
 * ── THE non-negotiable (ADR 0003 D1) ────────────────────────────────────
 * `VariantInterpretation` has exactly three fields: `variationDescriptor`,
 * `therapeuticActionability`, and the GA4GH-conformant
 * `acmgPathogenicityClassification`. The corpus and every reader
 * (`sql_fragments/paths.py:22`'s P/LP filter, aggregations,
 * `InterpretationsCard.vue:261`, MCP `individuals.py:160`) instead reads the
 * verdict off `genomicInterpretations[].interpretationStatus`. This console
 * must write ONLY `interpretationStatus`, never
 * `acmgPathogenicityClassification` -- writing the conformant field in
 * addition to (or instead of) `interpretationStatus` would silently break
 * that filter for any record this console touches. See the
 * "non-negotiable" describe block below.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import ClassificationSection from '@/components/curation/ClassificationSection.vue';

const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

const INTERPRETATION_STATUS_ITEMS = [
  { value: 'PATHOGENIC', label: 'Pathogenic', description: null },
  { value: 'LIKELY_PATHOGENIC', label: 'Likely pathogenic', description: null },
  { value: 'UNCERTAIN_SIGNIFICANCE', label: 'Uncertain significance', description: null },
];
const CLASSIFICATION_SYSTEM_ITEMS = [
  { value: 'acmg', label: 'ACMG', description: null },
  { value: 'clingen_cnv', label: 'ClinGen CNV', description: null },
];

function fixtureInterpretation({ interpretationStatus = 'UNKNOWN', extensions } = {}) {
  return {
    id: 'interpretation-1',
    progressStatus: 'IN_PROGRESS',
    diagnosis: {
      genomicInterpretations: [
        {
          subjectOrBiosampleId: 'subject-1',
          interpretationStatus,
          variantInterpretation: {
            variationDescriptor: { id: 'var:1', label: 'test variant' },
            ...(extensions ? { extensions } : {}),
          },
        },
      ],
    },
  };
}

function mountSection(props = {}) {
  return mount(ClassificationSection, {
    props: {
      modelValue: [],
      classificationSystem: null,
      classificationDate: null,
      classificationComment: null,
      interpretationStatusItems: INTERPRETATION_STATUS_ITEMS,
      classificationSystemItems: CLASSIFICATION_SYSTEM_ITEMS,
      ...props,
    },
    global: { plugins: [fullVuetify] },
  });
}

function findByLabel(wrapper, componentName, label) {
  return wrapper.findAllComponents({ name: componentName }).find((c) => c.props('label') === label);
}

beforeEach(() => {
  window.logService = {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };
});

// ── THE non-negotiable (ADR 0003 D1) ───────────────────────────────────────
describe('ClassificationSection — ACMG verdict placement (ADR 0003 D1 non-negotiable)', () => {
  it('setting a verdict writes ONLY interpretationStatus, never acmgPathogenicityClassification', async () => {
    const wrapper = mountSection({ modelValue: [fixtureInterpretation()] });

    const verdictSelect = findByLabel(wrapper, 'VSelect', 'ACMG verdict');
    expect(verdictSelect).toBeTruthy();

    await verdictSelect.vm.$emit('update:model-value', 'PATHOGENIC');

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted).toBeTruthy();
    const interpretations = emitted[emitted.length - 1][0];
    const gi = interpretations[0].diagnosis.genomicInterpretations[0];

    expect(gi.interpretationStatus).toBe('PATHOGENIC');
    expect(gi.variantInterpretation.acmgPathogenicityClassification).toBeUndefined();
    expect(Object.keys(gi.variantInterpretation)).not.toContain('acmgPathogenicityClassification');
  });

  it('never writes acmgPathogenicityClassification for any of the vocabulary verdict values', async () => {
    for (const item of INTERPRETATION_STATUS_ITEMS) {
      const wrapper = mountSection({ modelValue: [fixtureInterpretation()] });
      const verdictSelect = findByLabel(wrapper, 'VSelect', 'ACMG verdict');
      await verdictSelect.vm.$emit('update:model-value', item.value);

      const emitted = wrapper.emitted('update:modelValue');
      const gi = emitted[emitted.length - 1][0][0].diagnosis.genomicInterpretations[0];
      expect(gi.interpretationStatus).toBe(item.value);
      expect(gi.variantInterpretation.acmgPathogenicityClassification).toBeUndefined();
    }
  });
});

describe('ClassificationSection — verdict control', () => {
  it('reads the current verdict off interpretations[0].diagnosis.genomicInterpretations[0].interpretationStatus', () => {
    const wrapper = mountSection({
      modelValue: [fixtureInterpretation({ interpretationStatus: 'LIKELY_PATHOGENIC' })],
    });
    const verdictSelect = findByLabel(wrapper, 'VSelect', 'ACMG verdict');
    expect(verdictSelect.props('modelValue')).toBe('LIKELY_PATHOGENIC');
  });

  it('preserves every other field on the interpretation/genomicInterpretation when the verdict changes', async () => {
    const wrapper = mountSection({
      modelValue: [fixtureInterpretation({ interpretationStatus: 'UNKNOWN' })],
    });
    const verdictSelect = findByLabel(wrapper, 'VSelect', 'ACMG verdict');
    await verdictSelect.vm.$emit('update:model-value', 'BENIGN');

    const emitted = wrapper.emitted('update:modelValue');
    const interpretation = emitted[emitted.length - 1][0][0];
    expect(interpretation.id).toBe('interpretation-1');
    expect(interpretation.progressStatus).toBe('IN_PROGRESS');
    const gi = interpretation.diagnosis.genomicInterpretations[0];
    expect(gi.subjectOrBiosampleId).toBe('subject-1');
    expect(gi.variantInterpretation.variationDescriptor).toEqual({
      id: 'var:1',
      label: 'test variant',
    });
  });

  it('disables the verdict control and hints to add a variant first when there is no primary variant', () => {
    const wrapper = mountSection({ modelValue: [] });
    const verdictSelect = findByLabel(wrapper, 'VSelect', 'ACMG verdict');
    expect(verdictSelect.props('disabled')).toBe(true);
    expect(wrapper.text()).toContain('variant');
  });
});

describe('ClassificationSection — criteria: picker + free text (design spec §3.3)', () => {
  it('the free-text field is the actual write path -- typing directly into it writes the criteria string', async () => {
    const wrapper = mountSection({ modelValue: [fixtureInterpretation()] });
    const criteriaField = findByLabel(wrapper, 'VTextarea', 'Classification criteria (free text)');
    expect(criteriaField).toBeTruthy();

    await criteriaField.vm.$emit('update:model-value', 'PM2_Supporting, BP4_Supporting');

    const emitted = wrapper.emitted('update:modelValue');
    const gi = emitted[emitted.length - 1][0][0].diagnosis.genomicInterpretations[0];
    const ext = gi.variantInterpretation.extensions.find(
      (e) => e.name === 'classification_criteria'
    );
    expect(ext.value.criteria).toBe('PM2_Supporting, BP4_Supporting');
  });

  it('the picker assembles PM1(Moderate)+PM2(Supporting)+PP2(Supporting)+PP3(Supporting) into the exact stored corpus format', async () => {
    const wrapper = mountSection({ modelValue: [fixtureInterpretation()] });

    const picker = findByLabel(wrapper, 'VSelect', 'Add ACMG criteria');
    expect(picker).toBeTruthy();
    await picker.vm.$emit('update:model-value', ['PM1', 'PM2', 'PP2', 'PP3']);

    // PM1/PP2/PP3 default strengths already match; PM2 defaults to Moderate
    // and must be lowered to Supporting via its own per-code strength select.
    // Rows render in pickerCodes order (PM1, PM2, PP2, PP3), so PM2 is row 1.
    const strengthRows = wrapper.findAll('.classification-section__strength-row');
    expect(strengthRows).toHaveLength(4);
    const pm2Select = strengthRows[1].findComponent({ name: 'VSelect' });
    expect(pm2Select.exists()).toBe(true);
    await pm2Select.vm.$emit('update:model-value', 'Supporting');

    const emitted = wrapper.emitted('update:modelValue');
    const gi = emitted[emitted.length - 1][0][0].diagnosis.genomicInterpretations[0];
    const ext = gi.variantInterpretation.extensions.find(
      (e) => e.name === 'classification_criteria'
    );

    expect(ext.value.criteria).toBe('PM1_Moderate, PM2_Supporting, PP2_Supporting, PP3_Supporting');
  });

  it("a hand-edit of the free-text field is NOT silently overwritten by the picker's (unchanged) assembled string", async () => {
    const wrapper = mountSection({
      modelValue: [
        fixtureInterpretation({
          extensions: [
            {
              name: 'classification_criteria',
              value: { criteria: 'PM2_Supporting', guidelines: 'ACMG' },
            },
          ],
        }),
      ],
    });

    const criteriaField = findByLabel(wrapper, 'VTextarea', 'Classification criteria (free text)');
    await criteriaField.vm.$emit(
      'update:model-value',
      'PM2_Supporting; curator note appended by hand'
    );

    const emitted = wrapper.emitted('update:modelValue');
    const lastCount = emitted.length;
    const gi = emitted[lastCount - 1][0][0].diagnosis.genomicInterpretations[0];
    const ext = gi.variantInterpretation.extensions.find(
      (e) => e.name === 'classification_criteria'
    );
    expect(ext.value.criteria).toBe('PM2_Supporting; curator note appended by hand');

    // Feed the updated interpretations back in (as the parent would) and let
    // the component settle -- nothing should re-derive/rewrite the text just
    // from re-rendering with the same underlying variant identity.
    await wrapper.setProps({ modelValue: emitted[lastCount - 1][0] });
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted('update:modelValue').length).toBe(lastCount);
    const stillField = findByLabel(wrapper, 'VTextarea', 'Classification criteria (free text)');
    expect(stillField.props('modelValue')).toBe('PM2_Supporting; curator note appended by hand');
  });

  it('picking further picker criteria after a hand-edit DOES overwrite the free text -- the picker is explicitly driving that write', async () => {
    const wrapper = mountSection({ modelValue: [fixtureInterpretation()] });

    const criteriaField = findByLabel(wrapper, 'VTextarea', 'Classification criteria (free text)');
    await criteriaField.vm.$emit('update:model-value', 'hand-typed only');

    const picker = findByLabel(wrapper, 'VSelect', 'Add ACMG criteria');
    await picker.vm.$emit('update:model-value', ['BP4']);

    const emitted = wrapper.emitted('update:modelValue');
    const gi = emitted[emitted.length - 1][0][0].diagnosis.genomicInterpretations[0];
    const ext = gi.variantInterpretation.extensions.find(
      (e) => e.name === 'classification_criteria'
    );
    expect(ext.value.criteria).toBe('BP4_Supporting');
  });

  it('disables the criteria picker and free text when there is no primary variant', () => {
    const wrapper = mountSection({ modelValue: [] });
    const picker = findByLabel(wrapper, 'VSelect', 'Add ACMG criteria');
    const criteriaField = findByLabel(wrapper, 'VTextarea', 'Classification criteria (free text)');
    expect(picker.props('disabled')).toBe(true);
    expect(criteriaField.props('disabled')).toBe(true);
  });
});

describe('ClassificationSection — classificationSystem keeps extensions.guidelines in sync', () => {
  it('acmg -> "ACMG"', async () => {
    const wrapper = mountSection({
      modelValue: [
        fixtureInterpretation({
          extensions: [{ name: 'classification_criteria', value: { criteria: 'PM2_Supporting' } }],
        }),
      ],
    });

    const systemSelect = findByLabel(wrapper, 'VSelect', 'Classification system');
    await systemSelect.vm.$emit('update:model-value', 'acmg');

    expect(wrapper.emitted('update:classificationSystem')).toEqual([['acmg']]);

    const emittedModel = wrapper.emitted('update:modelValue');
    const gi = emittedModel[emittedModel.length - 1][0][0].diagnosis.genomicInterpretations[0];
    const ext = gi.variantInterpretation.extensions.find(
      (e) => e.name === 'classification_criteria'
    );
    expect(ext.value.guidelines).toBe('ACMG');
    // The criteria text itself must survive the sync untouched.
    expect(ext.value.criteria).toBe('PM2_Supporting');
  });

  it('clingen_cnv -> "ClinGen CNV"', async () => {
    const wrapper = mountSection({
      modelValue: [
        fixtureInterpretation({
          extensions: [{ name: 'classification_criteria', value: { criteria: '1A, 2A' } }],
        }),
      ],
    });

    const systemSelect = findByLabel(wrapper, 'VSelect', 'Classification system');
    await systemSelect.vm.$emit('update:model-value', 'clingen_cnv');

    const emittedModel = wrapper.emitted('update:modelValue');
    const gi = emittedModel[emittedModel.length - 1][0][0].diagnosis.genomicInterpretations[0];
    const ext = gi.variantInterpretation.extensions.find(
      (e) => e.name === 'classification_criteria'
    );
    expect(ext.value.guidelines).toBe('ClinGen CNV');
  });

  it('the System select still works (emits update:classificationSystem) with no primary variant, but there is no extension to sync', async () => {
    const wrapper = mountSection({ modelValue: [] });
    const systemSelect = findByLabel(wrapper, 'VSelect', 'Classification system');
    expect(systemSelect.props('disabled')).toBe(false);

    await systemSelect.vm.$emit('update:model-value', 'acmg');
    expect(wrapper.emitted('update:classificationSystem')).toEqual([['acmg']]);
    // No variant to write the extension onto -- must not throw or emit modelValue.
    expect(wrapper.emitted('update:modelValue')).toBeFalsy();
  });
});

describe('ClassificationSection — case-level fields always available', () => {
  it('classificationSystem/Date/Comment controls are enabled even with zero interpretations', () => {
    const wrapper = mountSection({ modelValue: [] });
    const systemSelect = findByLabel(wrapper, 'VSelect', 'Classification system');
    const dateField = findByLabel(wrapper, 'VTextField', 'Classification date');
    const commentField = findByLabel(wrapper, 'VTextarea', 'Classification comment');

    expect(systemSelect.props('disabled')).toBe(false);
    expect(dateField.props('disabled')).toBeFalsy();
    expect(commentField.props('disabled')).toBeFalsy();
  });

  it('emits update:classificationDate / update:classificationComment on edit', async () => {
    const wrapper = mountSection({ modelValue: [] });

    const dateField = findByLabel(wrapper, 'VTextField', 'Classification date');
    await dateField.vm.$emit('update:model-value', '2024-03-01');
    expect(wrapper.emitted('update:classificationDate')).toEqual([['2024-03-01']]);

    const commentField = findByLabel(wrapper, 'VTextarea', 'Classification comment');
    await commentField.vm.$emit('update:model-value', 'Reviewed after functional study.');
    expect(wrapper.emitted('update:classificationComment')).toEqual([
      ['Reviewed after functional study.'],
    ]);
  });
});
