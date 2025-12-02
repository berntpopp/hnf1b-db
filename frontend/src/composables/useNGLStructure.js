/**
 * Composable for NGL 3D protein structure visualization.
 *
 * Manages NGL Stage lifecycle, structure loading, and representation
 * management. Handles Vue 3 Proxy conflicts with Three.js by using
 * module-level variables and markRaw().
 *
 * @param {Object} options - Configuration options
 * @param {Ref<HTMLElement>} options.containerRef - Vue ref to the container element
 * @param {string} options.pdbUrl - URL to load the PDB/CIF structure from
 * @param {Object} options.stageOptions - NGL Stage options (default: white bg, medium quality)
 * @returns {{
 *   loading: Ref<boolean>,
 *   error: Ref<string|null>,
 *   structureLoaded: Ref<boolean>,
 *   stage: Object,
 *   structureComponent: Object,
 *   loadStructure: Function,
 *   addRepresentation: Function,
 *   removeAllRepresentations: Function,
 *   autoView: Function,
 *   handleResize: Function,
 *   cleanup: Function
 * }}
 *
 * @example
 * const containerRef = ref(null)
 * const ngl = useNGLStructure({
 *   containerRef,
 *   pdbUrl: 'https://www.ebi.ac.uk/pdbe/entry-files/2h8r.cif'
 * })
 *
 * onMounted(async () => {
 *   await ngl.loadStructure()
 *   ngl.addRepresentation('cartoon', { color: 'chainid' })
 * })
 *
 * onUnmounted(() => ngl.cleanup())
 */

import { ref, markRaw } from 'vue';
import * as NGL from 'ngl';

// Module-level storage to avoid Vue Proxy conflicts with Three.js
const stageInstances = new Map();
const structureInstances = new Map();
let instanceCounter = 0;

export function useNGLStructure(options = {}) {
  const {
    containerRef,
    pdbUrl,
    stageOptions = {
      backgroundColor: 'white',
      quality: 'medium',
      impostor: true,
      workerDefault: true,
    },
  } = options;

  const instanceId = ++instanceCounter;
  const loading = ref(false);
  const error = ref(null);
  const structureLoaded = ref(false);

  // Getters for module-level instances
  const getStage = () => stageInstances.get(instanceId);
  const getStructure = () => structureInstances.get(instanceId);

  const loadStructure = async () => {
    if (!containerRef?.value) {
      error.value = 'Container element not available';
      return;
    }

    loading.value = true;
    error.value = null;

    try {
      // Create NGL Stage
      const stage = markRaw(new NGL.Stage(containerRef.value, stageOptions));
      stageInstances.set(instanceId, stage);

      window.logService.info('Loading NGL structure', { url: pdbUrl });

      // Load structure
      const ext = pdbUrl.endsWith('.cif') ? 'cif' : 'pdb';
      const structure = markRaw(
        await stage.loadFile(pdbUrl, {
          defaultRepresentation: false,
          ext,
        })
      );
      structureInstances.set(instanceId, structure);

      structureLoaded.value = true;

      // Handle resize after load
      setTimeout(() => {
        const currentStage = getStage();
        if (currentStage) {
          currentStage.handleResize();
          currentStage.autoView();
        }
      }, 100);

      window.logService.info('NGL structure loaded successfully');
      return structure;
    } catch (e) {
      error.value = `Failed to load structure: ${e.message}`;
      window.logService.error('NGL structure load failed', { error: e.message });
      throw e;
    } finally {
      loading.value = false;
    }
  };

  const addRepresentation = (type, params = {}) => {
    const structure = getStructure();
    if (!structure) return null;
    return structure.addRepresentation(type, params);
  };

  const removeAllRepresentations = () => {
    const structure = getStructure();
    if (structure) {
      structure.removeAllRepresentations();
    }
  };

  const removeRepresentation = (repr) => {
    const structure = getStructure();
    if (structure && repr) {
      structure.removeRepresentation(repr);
    }
  };

  const autoView = (selection = null, duration = 1000) => {
    const structure = getStructure();
    if (structure) {
      structure.autoView(selection, duration);
    }
  };

  const handleResize = () => {
    const stage = getStage();
    if (stage) {
      stage.handleResize();
    }
  };

  const addComponentFromObject = (obj) => {
    const stage = getStage();
    if (stage) {
      return stage.addComponentFromObject(obj);
    }
    return null;
  };

  const removeComponent = (component) => {
    const stage = getStage();
    if (stage && component) {
      stage.removeComponent(component);
    }
  };

  const cleanup = () => {
    const stage = getStage();
    if (stage) {
      stage.dispose();
    }
    stageInstances.delete(instanceId);
    structureInstances.delete(instanceId);
    structureLoaded.value = false;
  };

  return {
    loading,
    error,
    structureLoaded,
    // Expose getters for direct access when needed
    get stage() {
      return getStage();
    },
    get structureComponent() {
      return getStructure();
    },
    loadStructure,
    addRepresentation,
    removeAllRepresentations,
    removeRepresentation,
    autoView,
    handleResize,
    addComponentFromObject,
    removeComponent,
    cleanup,
  };
}
