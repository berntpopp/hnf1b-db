/**
 * Characterization test for ProteinStructure3D.vue.
 *
 * The component uses NGL Viewer which requires WebGL. In happy-dom
 * there is no WebGL context, so NGL is mocked. The spec verifies
 * the component mounts, accepts the expected props, and renders a
 * container element for NGL to attach to.
 *
 * NGL import shape in component:
 *   import * as NGL from 'ngl'
 *   new NGL.Stage(this.$refs.nglContainer, { ... })
 *
 * So the mock must expose named exports (Stage, etc.) rather than a
 * default export.
 *
 * Component props (from ProteinStructure3D.vue):
 *   - variants: Array (default: [])
 *   - currentVariantId: String (default: null)
 *   - showAllVariants: Boolean (default: false)
 * There is no pdbId prop; the structure is loaded from GET /reference/genes/HNF1B/structure.
 */
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';

// Mock NGL before importing the component. The component uses
// `import * as NGL from 'ngl'`, so we expose named exports here.
vi.mock('ngl', () => {
  const structureComponent = {
    addRepresentation: vi.fn(() => ({})),
    removeRepresentation: vi.fn(),
    removeAllRepresentations: vi.fn(),
    autoView: vi.fn(),
    structure: { atomStore: { count: 0 }, eachAtom: vi.fn() },
  };
  const stage = {
    loadFile: vi.fn().mockResolvedValue(structureComponent),
    dispose: vi.fn(),
    handleResize: vi.fn(),
    setParameters: vi.fn(),
    removeAllComponents: vi.fn(),
    removeComponent: vi.fn(),
    addComponentFromObject: vi.fn(() => ({
      addRepresentation: vi.fn(),
    })),
    autoView: vi.fn(),
  };
  return {
    Stage: vi.fn(() => stage),
    Shape: vi.fn(() => ({ addCylinder: vi.fn(), addText: vi.fn() })),
    autoLoad: vi.fn(),
  };
});

// Mock the DNA distance calculator utility (imported by the component).
// It reaches into NGL structures, which would be brittle to fake in tests.
vi.mock('@/utils/dnaDistanceCalculator', () => ({
  DNADistanceCalculator: vi.fn().mockImplementation(() => ({
    initialize: vi.fn(),
    calculateResidueToHelixDistance: vi.fn(() => null),
    getDistanceLineCoordinates: vi.fn(() => null),
  })),
  STRUCTURE_START: 90,
  STRUCTURE_END: 308,
}));

// Provide a window.logService stub (component may call it on errors).
globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

async function mountViewer(props = {}) {
  const ProteinStructure3D = (await import('@/components/gene/ProteinStructure3D.vue')).default;
  return mount(ProteinStructure3D, {
    props: { variants: [], ...props },
  });
}

describe('ProteinStructure3D.vue (characterization)', () => {
  it('mounts without throwing', async () => {
    const wrapper = await mountViewer();
    expect(wrapper.exists()).toBe(true);
  });

  it('renders a container element for NGL', async () => {
    const wrapper = await mountViewer();
    // The component template uses <div ref="nglContainer" class="ngl-viewport" />
    const container = wrapper.find('.ngl-viewport');
    expect(container.exists()).toBe(true);
  });

  it('accepts a variants array prop', async () => {
    const variants = [
      { variant_id: 'V1', hgvs_p: 'p.Arg100Gly' },
      { variant_id: 'V2', hgvs_p: 'p.Lys200Asn' },
    ];
    const wrapper = await mountViewer({ variants });
    expect(wrapper.props('variants')).toEqual(variants);
  });

  it('accepts a currentVariantId prop', async () => {
    const wrapper = await mountViewer({ currentVariantId: 'V1' });
    expect(wrapper.props('currentVariantId')).toBe('V1');
  });

  it('accepts a showAllVariants prop', async () => {
    const wrapper = await mountViewer({ showAllVariants: true });
    expect(wrapper.props('showAllVariants')).toBe(true);
  });
});

describe('ProteinStructure3D.vue variant search', () => {
  it('filters the in-structure variants by protein, transcript or id', async () => {
    const variants = [
      { variant_id: 'V1', simple_id: 'Var1', protein: 'p.Arg177Gln', transcript: 'c.530G>A' },
      { variant_id: 'V2', simple_id: 'Var2', protein: 'p.Lys200Asn', transcript: 'c.600G>C' },
    ];
    const wrapper = await mountViewer({ variants, showAllVariants: true });
    wrapper.vm.clearFilters(); // widen past the missense-only default
    const ids = () => wrapper.vm.filteredAndSortedVariants.map((v) => v.variant_id);

    expect(ids()).toEqual(['V1', 'V2']);
    wrapper.vm.search = 'arg177';
    expect(ids()).toEqual(['V1']);
    wrapper.vm.search = ' c.600 ';
    expect(ids()).toEqual(['V2']);
    wrapper.vm.search = 'var1';
    expect(ids()).toEqual(['V1']);
    wrapper.vm.clearFilters();
    expect(wrapper.vm.search).toBe('');
  });
});

describe('ProteinStructure3D.vue pinned variants', () => {
  it('toggles pinned variants and only passes in-structure ones to the viewer', async () => {
    const variants = [
      { variant_id: 'V1', protein: 'p.Arg177Gln' },
      { variant_id: 'V2', protein: 'p.Lys200Asn' },
      { variant_id: 'V3', protein: 'p.Gln10Ter' }, // outside 90-308
    ];
    const wrapper = await mountViewer({ variants, showAllVariants: true });
    wrapper.vm.toggleShown(variants[0]);
    wrapper.vm.toggleShown(variants[2]);
    expect(wrapper.vm.shownVariants.map((v) => v.variant_id)).toEqual(['V1']);
    wrapper.vm.toggleShown(variants[0]);
    expect(wrapper.vm.shownVariantIds).toEqual(['V3']);
  });
});
