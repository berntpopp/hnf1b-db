import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import VariantAnnotationForm from '@/components/VariantAnnotationForm.vue';
import { soIdFor } from '@/utils/soTerms';

const vuetify = createVuetify();
// The detailed-entry suite below queries rendered VSelect/VTextarea/
// VCombobox component instances (findAllComponents({name: ...})), which
// requires Vuetify's components/directives to actually be registered on the
// plugin instance -- the bare `createVuetify()` above is enough for the
// pre-existing tests (they only call exposed methods directly, never touch
// the DOM), matching the same distinction PhenopacketCreateEdit.spec.js
// draws for its own Case-section-controls suite.
const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

function mountForm() {
  return mount(VariantAnnotationForm, {
    props: { modelValue: [], subjectId: 'subject-1' },
    global: { plugins: [vuetify] },
  });
}

function descriptorOf(interpretation) {
  return interpretation.diagnosis.genomicInterpretations[0].variantInterpretation
    .variationDescriptor;
}

describe('VariantAnnotationForm payload shape', () => {
  it('sets moleculeContext to a GA4GH enum member, never a VEP consequence', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      consequence: 'missense_variant',
      consequenceSoId: 'SO:0001583',
    });

    expect(descriptorOf(interp).moleculeContext).toBe('genomic');
  });

  it('records the VEP consequence as an SO term in molecularConsequences', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      consequence: 'missense_variant',
      consequenceSoId: 'SO:0001583',
    });

    expect(descriptorOf(interp).molecularConsequences).toEqual([
      { id: 'SO:0001583', label: 'missense_variant' },
    ]);
  });

  it('omits molecularConsequences entirely when no consequence is known', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B');

    expect(descriptorOf(interp)).not.toHaveProperty('molecularConsequences');
  });

  it('never writes a non-VRS variation object', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B');

    expect(descriptorOf(interp)).not.toHaveProperty('variation');
  });

  it('records the notation as a VCF expression instead', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B');

    expect(descriptorOf(interp).expressions).toEqual([
      { syntax: 'vcf', value: 'chr17-36459258-A-G' },
    ]);
  });

  it('never writes impact or caddScore onto VariantInterpretation', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      impact: 'MODERATE',
      caddScore: 24.3,
    });
    const vi = interp.diagnosis.genomicInterpretations[0].variantInterpretation;

    expect(vi).not.toHaveProperty('impact');
    expect(vi).not.toHaveProperty('caddScore');
    expect(Object.keys(vi)).toEqual(['variationDescriptor']);
  });

  it('selects moleculeContext from the notation form', () => {
    const wrapper = mountForm();
    const t = (n) => descriptorOf(wrapper.vm.createInterpretation(n, 'HNF1B')).moleculeContext;

    expect(t('NM_000458.4:c.544+1G>A')).toBe('transcript');
    expect(t('NP_000449.1:p.Arg177Ter')).toBe('protein');
    expect(t('chr17-36459258-A-G')).toBe('genomic');
    expect(t('something-unrecognisable')).toBe('unspecified_molecule_context');
  });

  it('derives the SO id from the VEP term the annotate endpoint actually returns', () => {
    const wrapper = mountForm();
    // annotate_route.py:138 returns the term name only — no SO id.
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      consequence: 'missense_variant',
      consequenceSoId: soIdFor('missense_variant'),
    });

    expect(descriptorOf(interp).molecularConsequences).toEqual([
      { id: 'SO:0001583', label: 'missense_variant' },
    ]);
  });

  it('omits molecularConsequences for an unmapped consequence rather than guessing', () => {
    const wrapper = mountForm();
    const interp = wrapper.vm.createInterpretation('chr17-36459258-A-G', 'HNF1B', {
      consequence: 'some_new_vep_term',
      consequenceSoId: soIdFor('some_new_vep_term'),
    });

    expect(descriptorOf(interp)).not.toHaveProperty('molecularConsequences');
  });

  it('infers the expression syntax from the notation form', () => {
    const wrapper = mountForm();
    const syntaxOf = (n) =>
      descriptorOf(wrapper.vm.createInterpretation(n, 'HNF1B')).expressions[0].syntax;

    expect(syntaxOf('NM_000458.4:c.544+1G>A')).toBe('hgvs.c');
    expect(syntaxOf('NP_000449.1:p.Arg177Ter')).toBe('hgvs.p');
    expect(syntaxOf('NC_000017.11:g.37738879A>G')).toBe('hgvs.g');
    expect(syntaxOf('rs587776470')).toBe('dbsnp');
    expect(syntaxOf('chr17-36459258-A-G')).toBe('vcf');
  });
});

// ── Task 5: detailed variant entry (design spec §3.2) ──────────────────────
// The quick VEP-annotate path above is untouched; these exercise the new,
// parallel structured entry area covering VariantReported, VariantType,
// hg38/hg19, dbVar xrefs, Varsome (hgvs.c), segregation and allelic state,
// plus editing an already-added variant in place.
describe('VariantAnnotationForm — detailed variant entry (Task 5)', () => {
  beforeEach(() => {
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  const SEGREGATION_ITEMS = [
    { value: 'de_novo', label: 'De novo', description: null },
    {
      value: 'not_reported',
      label: 'Not reported',
      description: 'Source is silent on segregation',
    },
  ];
  const ALLELIC_STATE_ITEMS = [
    { id: 'GENO:0000135', label: 'heterozygous', description: 'Having one variant allele...' },
    {
      id: 'GENO:0000136',
      label: 'homozygous',
      description: 'Having two identical variant alleles',
    },
  ];
  const DETECTION_METHOD_ITEMS = [
    { value: 'ngs', label: 'Next-generation sequencing', description: null },
    {
      value: 'not_reported',
      label: 'Not reported',
      description: 'Source is silent on detection method',
    },
  ];

  function mountDetailedForm(props = {}) {
    return mount(VariantAnnotationForm, {
      props: {
        modelValue: [],
        subjectId: 'subject-1',
        detectionMethod: null,
        detectionMethodItems: DETECTION_METHOD_ITEMS,
        segregationItems: SEGREGATION_ITEMS,
        allelicStateItems: ALLELIC_STATE_ITEMS,
        ...props,
      },
      global: { plugins: [fullVuetify] },
    });
  }

  function findByLabel(wrapper, componentName, label) {
    return wrapper
      .findAllComponents({ name: componentName })
      .find((c) => c.props('label') === label);
  }

  function saveDetailedBtn(wrapper) {
    return wrapper.get('[data-testid="save-detailed-variant-btn"]');
  }

  async function setReported(wrapper, value) {
    const field = findByLabel(wrapper, 'VTextarea', 'Variant as reported');
    expect(field).toBeTruthy();
    await field.vm.$emit('update:modelValue', value);
  }

  function fixtureInterpretation(description) {
    return {
      id: `interpretation-${description}`,
      progressStatus: 'IN_PROGRESS',
      diagnosis: {
        genomicInterpretations: [
          {
            subjectOrBiosampleId: 'subject-1',
            interpretationStatus: 'UNKNOWN',
            variantInterpretation: {
              variationDescriptor: {
                id: `var:${description}`,
                label: description,
                description,
                geneContext: { valueId: 'HGNC:5024', symbol: 'HNF1B' },
                moleculeContext: 'unspecified_molecule_context',
              },
            },
          },
        ],
      },
    };
  }

  it('stores VariantReported byte-for-byte -- never trimmed, collapsed, or reformatted', async () => {
    const wrapper = mountDetailedForm();
    const raw = '  TCF2,  c.182T>G ,  V61G  ';

    await setReported(wrapper, raw);
    await saveDetailedBtn(wrapper).trigger('click');

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted).toBeTruthy();
    const interp = emitted[emitted.length - 1][0][0];

    expect(descriptorOf(interp).description).toBe(raw);
    // Not a "trimmed equals trimmed" comparison: identical, character for character.
    expect(descriptorOf(interp).description).not.toBe(raw.trim());
    expect(descriptorOf(interp).description.length).toBe(raw.length);
  });

  it('pushes hg38 before hg19 in expressions, and expressions.find(hgvs.g) resolves hg38', async () => {
    const wrapper = mountDetailedForm();
    await setReported(wrapper, 'test variant');

    const hg19Field = findByLabel(wrapper, 'VTextField', 'hg19 (GRCh37)');
    const hg38Field = findByLabel(wrapper, 'VTextField', 'hg38 (GRCh38)');
    expect(hg19Field).toBeTruthy();
    expect(hg38Field).toBeTruthy();

    // Enter hg19 FIRST to prove ordering doesn't just track entry order.
    await hg19Field.vm.$emit('update:modelValue', 'NC_000017.10:g.36895769T>C');
    await hg38Field.vm.$emit('update:modelValue', 'NC_000017.11:g.37739589T>C');

    await saveDetailedBtn(wrapper).trigger('click');

    const emitted = wrapper.emitted('update:modelValue');
    const interp = emitted[emitted.length - 1][0][0];
    const expressions = descriptorOf(interp).expressions;

    expect(expressions[0]).toEqual({
      syntax: 'hgvs.g',
      value: 'NC_000017.11:g.37739589T>C',
      version: 'GRCh38',
    });
    expect(expressions[1]).toEqual({
      syntax: 'hgvs.g',
      value: 'NC_000017.10:g.36895769T>C',
      version: 'GRCh37',
    });
    // The existing reader pattern (Phenopackets.vue, InterpretationsCard.vue).
    expect(expressions.find((e) => e.syntax === 'hgvs.g').value).toBe('NC_000017.11:g.37739589T>C');
  });

  it('stores Varsome as the canonical hgvs.c expression entry', async () => {
    const wrapper = mountDetailedForm();
    await setReported(wrapper, 'test variant');

    const varsomeField = findByLabel(wrapper, 'VTextField', 'Varsome (hgvs.c)');
    await varsomeField.vm.$emit('update:modelValue', 'NM_000458.4:c.395A>G');

    await saveDetailedBtn(wrapper).trigger('click');
    const emitted = wrapper.emitted('update:modelValue');
    const interp = emitted[emitted.length - 1][0][0];

    expect(descriptorOf(interp).expressions.find((e) => e.syntax === 'hgvs.c').value).toBe(
      'NM_000458.4:c.395A>G'
    );
  });

  it('stores VariantType as an {id,label} SO term object via the structured select', async () => {
    const wrapper = mountDetailedForm();
    await setReported(wrapper, 'test variant');

    const typeSelect = findByLabel(wrapper, 'VSelect', 'Variant type');
    expect(typeSelect).toBeTruthy();
    await typeSelect.vm.$emit('update:modelValue', { id: 'SO:0000159', label: 'deletion' });

    await saveDetailedBtn(wrapper).trigger('click');
    const emitted = wrapper.emitted('update:modelValue');
    const interp = emitted[emitted.length - 1][0][0];

    expect(descriptorOf(interp).structuralType).toEqual({ id: 'SO:0000159', label: 'deletion' });
  });

  it('stores allelicState as a clean {id,label} object, stripping vocabulary description', async () => {
    const wrapper = mountDetailedForm();
    await setReported(wrapper, 'test variant');

    const allelicSelect = findByLabel(wrapper, 'VSelect', 'Allelic state');
    expect(allelicSelect).toBeTruthy();
    await allelicSelect.vm.$emit('update:modelValue', ALLELIC_STATE_ITEMS[0]);

    await saveDetailedBtn(wrapper).trigger('click');
    const emitted = wrapper.emitted('update:modelValue');
    const interp = emitted[emitted.length - 1][0][0];

    expect(descriptorOf(interp).allelicState).toEqual({
      id: 'GENO:0000135',
      label: 'heterozygous',
    });
  });

  it('stores dbVar IDs as xrefs via the chips input', async () => {
    const wrapper = mountDetailedForm();
    await setReported(wrapper, 'test variant');

    const combobox = wrapper.findAllComponents({ name: 'VCombobox' })[0];
    expect(combobox).toBeTruthy();
    await combobox.vm.$emit('update:modelValue', ['dbVar:nssv1184554']);

    await saveDetailedBtn(wrapper).trigger('click');
    const emitted = wrapper.emitted('update:modelValue');
    const interp = emitted[emitted.length - 1][0][0];

    expect(descriptorOf(interp).xrefs).toEqual(['dbVar:nssv1184554']);
  });

  it('stores segregation on extensions[segregation].value.origin', async () => {
    const wrapper = mountDetailedForm();
    await setReported(wrapper, 'test variant');

    const segSelect = findByLabel(wrapper, 'VSelect', 'Segregation');
    expect(segSelect).toBeTruthy();
    await segSelect.vm.$emit('update:modelValue', 'not_reported');

    await saveDetailedBtn(wrapper).trigger('click');
    const emitted = wrapper.emitted('update:modelValue');
    const interp = emitted[emitted.length - 1][0][0];

    expect(descriptorOf(interp).extensions).toEqual([
      { name: 'segregation', value: { origin: 'not_reported' } },
    ]);
  });

  it('renders exactly one detection-method control for the whole case, not one per variant', async () => {
    const wrapper = mountDetailedForm({
      modelValue: [fixtureInterpretation('variant one'), fixtureInterpretation('variant two')],
    });

    const detectionSelects = wrapper
      .findAllComponents({ name: 'VSelect' })
      .filter((c) => c.props('label') === 'Detection method');
    expect(detectionSelects).toHaveLength(1);
  });

  it('emits update:detectionMethod (case-level, not per-variant) from that single control', async () => {
    const wrapper = mountDetailedForm();
    const detectionSelect = findByLabel(wrapper, 'VSelect', 'Detection method');
    expect(detectionSelect).toBeTruthy();

    await detectionSelect.vm.$emit('update:modelValue', 'ngs');

    expect(wrapper.emitted('update:detectionMethod')).toEqual([['ngs']]);
  });

  it('edits an already-added variant in place (not just appending), round-tripping a field', async () => {
    const wrapper = mountDetailedForm();

    await setReported(wrapper, 'original text');
    await saveDetailedBtn(wrapper).trigger('click');

    let emitted = wrapper.emitted('update:modelValue');
    const afterAdd = emitted[emitted.length - 1][0];
    await wrapper.setProps({ modelValue: afterAdd });

    const editBtn = wrapper.get('[data-testid="edit-variant-btn-0"]');
    await editBtn.trigger('click');

    const varsomeField = findByLabel(wrapper, 'VTextField', 'Varsome (hgvs.c)');
    await varsomeField.vm.$emit('update:modelValue', 'NM_000458.4:c.395A>G');

    await saveDetailedBtn(wrapper).trigger('click');

    emitted = wrapper.emitted('update:modelValue');
    const afterEdit = emitted[emitted.length - 1][0];

    // Edited in place: still exactly one variant, not appended as a second.
    expect(afterEdit).toHaveLength(1);
    expect(descriptorOf(afterEdit[0]).description).toBe('original text');
    expect(descriptorOf(afterEdit[0]).expressions.find((e) => e.syntax === 'hgvs.c').value).toBe(
      'NM_000458.4:c.395A>G'
    );
  });

  it('preserves an existing quick-add label/description when an edit leaves VariantReported untouched', async () => {
    const quickAddInterpretation = {
      id: 'interpretation-quick',
      progressStatus: 'IN_PROGRESS',
      diagnosis: {
        genomicInterpretations: [
          {
            subjectOrBiosampleId: 'subject-1',
            interpretationStatus: 'UNKNOWN',
            variantInterpretation: {
              variationDescriptor: {
                id: 'var:chr17-36459258-A-G',
                label: 'chr17-36459258-A-G',
                geneContext: { valueId: 'HGNC:5024', symbol: 'HNF1B' },
                moleculeContext: 'genomic',
                expressions: [{ syntax: 'vcf', value: 'chr17-36459258-A-G' }],
              },
            },
          },
        ],
      },
    };
    const wrapper = mountDetailedForm({ modelValue: [quickAddInterpretation] });

    const editBtn = wrapper.get('[data-testid="edit-variant-btn-0"]');
    await editBtn.trigger('click');

    // Only touch dbVar IDs -- never type into "Variant as reported".
    const combobox = wrapper.findAllComponents({ name: 'VCombobox' })[0];
    await combobox.vm.$emit('update:modelValue', ['dbVar:nssv1184554']);

    await saveDetailedBtn(wrapper).trigger('click');

    const emitted = wrapper.emitted('update:modelValue');
    const afterEdit = emitted[emitted.length - 1][0];

    expect(descriptorOf(afterEdit[0]).label).toBe('chr17-36459258-A-G');
    expect(descriptorOf(afterEdit[0]).xrefs).toEqual(['dbVar:nssv1184554']);
    // The quick-add's own vcf expression must survive the edit untouched.
    expect(descriptorOf(afterEdit[0]).expressions).toContainEqual({
      syntax: 'vcf',
      value: 'chr17-36459258-A-G',
    });
  });
});
