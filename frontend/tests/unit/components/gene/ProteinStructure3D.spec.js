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
 * There is no pdbId prop; the PDB file path (/2h8r.cif) is hardcoded.
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
