import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import VariantAnnotationForm from '@/components/VariantAnnotationForm.vue';
import { soIdFor } from '@/utils/soTerms';

const vuetify = createVuetify();

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
