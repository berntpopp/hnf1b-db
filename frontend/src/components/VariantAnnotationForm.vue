<!-- src/components/VariantAnnotationForm.vue -->
<!--
  Variant section content for the curation console (curation console design
  spec §3.2; plan Task 5). Renders inside PhenopacketCreateEdit.vue's
  <CurationSection id="variant">, which already provides the section chrome
  (title, completeness badge, collapse) -- this component owns no card of
  its own.

  Two entry paths coexist:
  - The original quick VEP-annotate flow (`variantInput`/`annotate()`/
    `addAnnotatedVariant()`/`addVariantDirect()`), unchanged, for fast entry
    + gene-context/molecular-consequence lookup.
  - A detailed structured editor covering the ten fields §3.2 maps to
    storage the quick path never touches (VariantReported, VariantType,
    hg38/hg19, dbVar xrefs, Varsome, segregation, allelic state). It doubles
    as the edit affordance for any already-added variant (quick-added or
    detailed) via the per-row pencil icon -- a curator revisiting a case
    needs to fix a typo, not just append.

  Detection method (design spec §3.2) is case-level, not per-variant, so it
  gets exactly one control here (not one per variant row), wired to the
  parent via `detectionMethod`/`update:detectionMethod` rather than living
  inside `modelValue`.
-->
<template>
  <div class="variant-annotation-form">
    <!-- Case-level: one control for the whole case, not one per variant. -->
    <v-select
      :model-value="detectionMethod"
      :items="detectionMethodItems"
      item-title="label"
      item-value="value"
      label="Detection method"
      :loading="vocabulariesLoading"
      :disabled="vocabulariesLoading"
      clearable
      class="mb-4"
      @update:model-value="$emit('update:detectionMethod', $event)"
    />

    <!-- List of added variants -->
    <div v-if="variants.length > 0" class="mb-4">
      <v-list density="compact">
        <v-list-item
          v-for="(variant, index) in variants"
          :key="index"
          class="mb-2"
          :class="{ 'variant-annotation-form__item--editing': editingIndex === index }"
          border
        >
          <template #prepend>
            <v-icon color="primary">mdi-dna</v-icon>
          </template>

          <v-list-item-title>
            {{ variant.label }}
          </v-list-item-title>

          <v-list-item-subtitle v-if="variant.geneSymbol">
            Gene: {{ variant.geneSymbol }}
            <span v-if="variant.consequence"> | {{ variant.consequence }}</span>
          </v-list-item-subtitle>

          <template #append>
            <v-btn
              :data-testid="`edit-variant-btn-${index}`"
              icon="mdi-pencil"
              variant="text"
              size="small"
              :aria-label="`Edit variant ${index + 1}`"
              @click="startEditVariant(index)"
            />
            <v-btn
              icon="mdi-delete"
              variant="text"
              size="small"
              color="error"
              :aria-label="`Remove variant ${index + 1}`"
              @click="removeVariant(index)"
            />
          </template>
        </v-list-item>
      </v-list>
    </div>

    <v-divider v-if="variants.length > 0" class="mb-4" />

    <!-- Quick add: VEP-annotate path (unchanged) -->
    <div class="mb-6">
      <div class="text-subtitle-2 text-medium-emphasis mb-2">Quick add (VEP lookup)</div>
      <v-text-field
        v-model="variantInput"
        label="Variant Notation"
        hint="HGVS, VCF, or rsID format (e.g., chr17-37739455-G-A, NM_000458.4:c.544+1G>A)"
        persistent-hint
        :loading="loading"
        :error-messages="error ? [error] : []"
        clearable
        @keyup.enter="annotate"
      >
        <template #append>
          <v-btn
            v-if="variantInput"
            color="primary"
            variant="text"
            size="small"
            :loading="loading"
            @click="annotate"
          >
            Annotate
          </v-btn>
        </template>
      </v-text-field>

      <!-- Annotation result -->
      <div v-if="annotation" class="mt-2">
        <v-alert type="success" variant="tonal">
          <div class="font-weight-bold">{{ annotation.gene_symbol }}</div>
          <div class="text-caption">
            {{ annotation.most_severe_consequence }}
            <span v-if="annotation.impact">({{ annotation.impact }})</span>
          </div>
          <div v-if="annotation.cadd_score" class="text-caption">
            CADD Score: {{ annotation.cadd_score.toFixed(1) }}
          </div>

          <v-btn
            color="success"
            size="small"
            class="mt-2"
            prepend-icon="mdi-plus"
            @click="addAnnotatedVariant"
          >
            Add Variant
          </v-btn>
        </v-alert>
      </div>

      <!-- Add without annotation button -->
      <v-btn
        v-if="variantInput && !annotation && !loading"
        color="primary"
        size="small"
        class="mt-2"
        prepend-icon="mdi-plus"
        @click="addVariantDirect"
      >
        Add Without Annotation
      </v-btn>
    </div>

    <v-divider class="mb-6" />

    <!-- Detailed variant entry (curation console design spec §3.2) -->
    <div>
      <div class="text-subtitle-2 text-medium-emphasis mb-2">
        {{ editingIndex !== null ? `Edit variant ${editingIndex + 1}` : 'Add variant (detailed)' }}
      </div>

      <v-textarea
        v-model="detailedEditor.variantReported"
        label="Variant as reported"
        hint="Verbatim, exactly as the source publication worded it -- never reformatted."
        persistent-hint
        rows="2"
        auto-grow
        class="mb-2"
      />

      <v-row>
        <v-col cols="12" md="6">
          <v-select
            v-model="detailedEditor.structuralType"
            :items="STRUCTURAL_VARIANT_TYPES"
            item-title="label"
            item-value="id"
            label="Variant type"
            return-object
            clearable
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-select
            v-model="detailedEditor.allelicState"
            :items="allelicStateItems"
            item-title="label"
            item-value="id"
            label="Allelic state"
            return-object
            :loading="vocabulariesLoading"
            :disabled="vocabulariesLoading"
            clearable
          />
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            v-model="detailedEditor.hg38"
            label="hg38 (GRCh38)"
            hint="Genomic HGVS, e.g. NC_000017.11:g.37739589T>C"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field
            v-model="detailedEditor.hg19"
            label="hg19 (GRCh37)"
            hint="Genomic HGVS on the GRCh37 assembly"
          />
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12" md="6">
          <v-text-field
            v-model="detailedEditor.varsome"
            label="Varsome (hgvs.c)"
            hint="Coding HGVS, e.g. NM_000458.4:c.395A>G"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-combobox
            v-model="detailedEditor.dbVarIds"
            label="dbVar ID(s)"
            hint="Press enter to add, e.g. dbVar:nssv1184554"
            persistent-hint
            chips
            multiple
            closable-chips
          />
        </v-col>
      </v-row>

      <v-select
        v-model="detailedEditor.segregation"
        :items="segregationItems"
        item-title="label"
        item-value="value"
        label="Segregation"
        :loading="vocabulariesLoading"
        :disabled="vocabulariesLoading"
        clearable
        class="mb-2"
      />

      <div v-if="coordinatesDisplay" class="text-caption text-medium-emphasis mb-2">
        Coordinates (read-only, from legacy import): {{ coordinatesDisplay }}
      </div>

      <div class="d-flex ga-2">
        <v-btn
          data-testid="save-detailed-variant-btn"
          color="primary"
          prepend-icon="mdi-plus"
          :disabled="editingIndex === null && !detailedEditor.variantReported"
          @click="saveDetailedVariant"
        >
          {{ editingIndex !== null ? 'Save changes' : 'Add variant' }}
        </v-btn>
        <v-btn v-if="editingIndex !== null" variant="text" @click="cancelEdit"> Cancel </v-btn>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useVariantAnnotation } from '@/composables/useVariantAnnotation';
import { soIdFor, STRUCTURAL_VARIANT_TYPES } from '@/utils/soTerms';

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  subjectId: {
    type: String,
    default: 'subject-1',
  },
  // Case-level (design spec §3.2): one detectionMethod for the whole case,
  // not one per variant -- lives on phenopacket.hnf1bCuration, not on any
  // single interpretation, so it is wired through props/emit rather than
  // through `modelValue`.
  detectionMethod: {
    type: String,
    default: null,
  },
  detectionMethodItems: {
    type: Array,
    default: () => [],
  },
  segregationItems: {
    type: Array,
    default: () => [],
  },
  allelicStateItems: {
    type: Array,
    default: () => [],
  },
  vocabulariesLoading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['update:modelValue', 'update:detectionMethod']);

const { annotation, loading, error, annotateVariant, reset } = useVariantAnnotation();

const variantInput = ref('');

/**
 * Extract simplified variant info from interpretations array
 * For display purposes only
 */
const variants = computed(() => {
  return (props.modelValue || [])
    .map((interp) => {
      const genomicInterps = interp.diagnosis?.genomicInterpretations || [];
      if (genomicInterps.length === 0) return null;

      const variantInterp = genomicInterps[0].variantInterpretation;
      const descriptor = variantInterp?.variationDescriptor;

      if (!descriptor) return null;

      return {
        label: descriptor.label || descriptor.id || 'Unknown variant',
        geneSymbol: descriptor.geneContext?.symbol,
        consequence: descriptor.molecularConsequences?.[0]?.label,
        moleculeContext: descriptor.moleculeContext,
      };
    })
    .filter(Boolean);
});

/**
 * Annotate variant using VEP
 */
const annotate = async () => {
  if (!variantInput.value) return;

  reset();

  try {
    await annotateVariant(variantInput.value);
  } catch (err) {
    // Error handled by composable
    window.logService.error('Failed to annotate variant', {
      variant: variantInput.value,
      error: err.message,
    });
  }
};

/**
 * Add variant with VEP annotation
 */
const addAnnotatedVariant = () => {
  if (!annotation.value || !variantInput.value) return;

  const interpretation = createInterpretation(
    variantInput.value,
    annotation.value.gene_symbol || 'HNF1B',
    {
      consequence: annotation.value.most_severe_consequence,
      consequenceSoId: soIdFor(annotation.value.most_severe_consequence),
    }
  );

  const updatedInterpretations = [...props.modelValue, interpretation];
  emit('update:modelValue', updatedInterpretations);

  window.logService.info('Variant added to phenopacket', {
    variant: variantInput.value,
    geneSymbol: annotation.value.gene_symbol,
  });

  // Clear form
  variantInput.value = '';
  reset();
};

/**
 * Add variant without annotation (direct entry)
 */
const addVariantDirect = () => {
  if (!variantInput.value) return;

  const interpretation = createInterpretation(variantInput.value, 'HNF1B');

  const updatedInterpretations = [...props.modelValue, interpretation];
  emit('update:modelValue', updatedInterpretations);

  window.logService.info('Variant added to phenopacket (no annotation)', {
    variant: variantInput.value,
  });

  // Clear form
  variantInput.value = '';
  reset();
};

/**
 * Remove variant from list
 */
const removeVariant = (index) => {
  const updatedInterpretations = props.modelValue.filter((_, i) => i !== index);
  emit('update:modelValue', updatedInterpretations);

  if (editingIndex.value === index) {
    cancelEdit();
  } else if (editingIndex.value !== null && index < editingIndex.value) {
    editingIndex.value -= 1;
  }

  window.logService.info('Variant removed from phenopacket', { index });
};

/**
 * Pick the GA4GH MoleculeContext enum member implied by a notation.
 * GA4GH v2 admits exactly: unspecified_molecule_context | genomic | transcript | protein.
 */
const inferMoleculeContext = (notation) => {
  if (/:c\.|:n\./.test(notation)) return 'transcript';
  if (/:p\./.test(notation)) return 'protein';
  if (/^(chr)?[0-9XYMT]+[-:]/.test(notation) || /:g\./.test(notation)) return 'genomic';
  return 'unspecified_molecule_context';
};

/** Pick the VRSATILE expression syntax implied by a notation. */
const inferExpressionSyntax = (notation) => {
  if (/:c\./.test(notation)) return 'hgvs.c';
  if (/:p\./.test(notation)) return 'hgvs.p';
  if (/:g\./.test(notation)) return 'hgvs.g';
  if (/^rs\d+$/i.test(notation)) return 'dbsnp';
  return 'vcf';
};

/**
 * Create a GA4GH Phenopackets v2 interpretation.
 *
 * Deliberately does NOT write:
 *  - the VEP consequence into moleculeContext (it is an enum; the consequence
 *    goes to molecularConsequences as an SO term, matching the 424 corpus records)
 *  - a `variation` key (GA4GH requires a VRS Variation object; the notation is
 *    carried as a VCF expression instead)
 *  - impact / caddScore onto VariantInterpretation (it has exactly three fields:
 *    acmgPathogenicityClassification, therapeuticActionability, variationDescriptor).
 *    Both are derived annotation, re-fetchable from POST /api/v2/variants/annotate.
 */
const createInterpretation = (variantNotation, geneSymbol, annotationData = {}) => {
  const interpretationId = `interpretation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  const variationDescriptor = {
    id: `var:${variantNotation}`,
    label: variantNotation,
    geneContext: {
      valueId: geneSymbol === 'HNF1B' ? 'HGNC:5024' : '',
      symbol: geneSymbol,
    },
    moleculeContext: inferMoleculeContext(variantNotation),
    expressions: [{ syntax: inferExpressionSyntax(variantNotation), value: variantNotation }],
  };

  if (annotationData.consequenceSoId && annotationData.consequence) {
    variationDescriptor.molecularConsequences = [
      { id: annotationData.consequenceSoId, label: annotationData.consequence },
    ];
  }

  return {
    id: interpretationId,
    progressStatus: 'IN_PROGRESS',
    diagnosis: {
      genomicInterpretations: [
        {
          subjectOrBiosampleId: props.subjectId,
          interpretationStatus: 'UNKNOWN',
          variantInterpretation: { variationDescriptor },
        },
      ],
    },
  };
};

// ── Detailed variant entry (design spec §3.2) ───────────────────────────────

function createEmptyEditor() {
  return {
    variantReported: '',
    structuralType: null,
    hg38: '',
    hg19: '',
    varsome: '',
    dbVarIds: [],
    segregation: null,
    allelicState: null,
  };
}

const detailedEditor = ref(createEmptyEditor());
// null = adding a new variant; otherwise the index into props.modelValue
// currently being edited.
const editingIndex = ref(null);

const coordinatesDisplay = computed(() => {
  if (editingIndex.value === null) return null;
  const target = props.modelValue[editingIndex.value];
  const descriptor =
    target?.diagnosis?.genomicInterpretations?.[0]?.variantInterpretation?.variationDescriptor;
  const coords = descriptor?.extensions?.find((e) => e.name === 'coordinates')?.value;
  if (!coords) return null;
  const range = [coords.start, coords.end].filter((v) => v !== undefined && v !== null).join('-');
  return `${coords.assembly ? `${coords.assembly} ` : ''}chr${coords.chromosome || '?'}:${range || '?'}`;
});

/** Populate the detailed editor from an existing variationDescriptor, for editing. */
function editorFromDescriptor(descriptor) {
  const expressions = descriptor?.expressions || [];
  return {
    // Seeded from `description` only, deliberately NOT from `label` -- a
    // quick-added variant has no `description` at all, and falling back to
    // `label` here would make Save (see buildVariationDescriptor) look like
    // it derived VariantReported from something else. Leaving this blank
    // for a quick-add variant is correct: the curator hasn't reported
    // anything verbatim yet.
    variantReported: descriptor?.description ?? '',
    structuralType: descriptor?.structuralType ?? null,
    hg38: expressions.find((e) => e.syntax === 'hgvs.g' && e.version === 'GRCh38')?.value ?? '',
    hg19: expressions.find((e) => e.syntax === 'hgvs.g' && e.version === 'GRCh37')?.value ?? '',
    varsome: expressions.find((e) => e.syntax === 'hgvs.c')?.value ?? '',
    dbVarIds: [...(descriptor?.xrefs || [])],
    segregation:
      descriptor?.extensions?.find((e) => e.name === 'segregation')?.value?.origin ?? null,
    allelicState: descriptor?.allelicState ?? null,
  };
}

/**
 * Build (or update) a variationDescriptor from the detailed editor's state.
 *
 * When `existingDescriptor` is given (editing), fields NOT covered by this
 * editor -- id, geneContext, moleculeContext (if already set), molecularConsequences,
 * the `coordinates`/`external_reference`/`classification_criteria` extensions,
 * any non-hg38/hg19/hgvs.c expression entries -- are preserved untouched, so
 * editing e.g. only the dbVar IDs on a quick-added variant never destroys
 * its VEP-derived data or a later task's classification extension.
 */
function buildVariationDescriptor(editor, existingDescriptor) {
  const descriptor = existingDescriptor ? { ...existingDescriptor } : {};

  descriptor.id = descriptor.id || `var:${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

  // VariantReported (design spec §3.2) is the single most important field in
  // this section: stored verbatim on `description`, byte-for-byte, never
  // trimmed/collapsed/reformatted. Mirrored onto `label` (what the variant
  // list and other readers display) too, but ONLY when the curator has
  // actually typed something on this save -- an empty field while editing
  // means "I didn't touch this", not "clear it", so a quick-add variant's
  // existing label survives an edit that only touches e.g. dbVar IDs (see
  // editorFromDescriptor above for why it starts blank in that case).
  if (editor.variantReported) {
    descriptor.label = editor.variantReported;
    descriptor.description = editor.variantReported;
  }

  descriptor.geneContext = descriptor.geneContext || { valueId: 'HGNC:5024', symbol: 'HNF1B' };
  descriptor.moleculeContext =
    descriptor.moleculeContext ||
    inferMoleculeContext(editor.hg38 || editor.hg19 || editor.varsome || '');

  if (editor.structuralType) {
    // Strip to {id,label}: the STRUCTURAL_VARIANT_TYPES items are already
    // clean, but defend against accidental extra keys regardless.
    descriptor.structuralType = {
      id: editor.structuralType.id,
      label: editor.structuralType.label,
    };
  } else {
    delete descriptor.structuralType;
  }

  if (editor.allelicState) {
    // Strip the vocabulary's `description` field: the corpus's OntologyClass
    // shape is exactly {id,label}, matching GA4GH.
    descriptor.allelicState = { id: editor.allelicState.id, label: editor.allelicState.label };
  } else {
    delete descriptor.allelicState;
  }

  if (editor.dbVarIds && editor.dbVarIds.length > 0) {
    descriptor.xrefs = [...editor.dbVarIds];
  } else {
    delete descriptor.xrefs;
  }

  // hg38 MUST land before hg19: both use syntax 'hgvs.g', and existing
  // readers do `expressions.find(e => e.syntax === 'hgvs.g')`
  // (Phenopackets.vue, InterpretationsCard.vue), which resolves to whichever
  // entry appears first -- hg38 stays the one they see by default. Both are
  // tagged with `version` so a curator or future reader can tell them apart
  // despite the shared syntax.
  const preservedExpressions = (descriptor.expressions || []).filter((e) => {
    const isHg38 = e.syntax === 'hgvs.g' && e.version === 'GRCh38';
    const isHg19 = e.syntax === 'hgvs.g' && e.version === 'GRCh37';
    const isVarsome = e.syntax === 'hgvs.c';
    return !isHg38 && !isHg19 && !isVarsome;
  });
  const editorExpressions = [];
  if (editor.hg38) {
    editorExpressions.push({ syntax: 'hgvs.g', value: editor.hg38, version: 'GRCh38' });
  }
  if (editor.hg19) {
    editorExpressions.push({ syntax: 'hgvs.g', value: editor.hg19, version: 'GRCh37' });
  }
  if (editor.varsome) {
    // Varsome maps to hgvs.c (design spec §3.2): "the one canonical hgvs.c
    // entry (matches existing single-entry convention -- no versioning
    // needed here)".
    editorExpressions.push({ syntax: 'hgvs.c', value: editor.varsome });
  }
  const nextExpressions = [...editorExpressions, ...preservedExpressions];
  if (nextExpressions.length > 0) {
    descriptor.expressions = nextExpressions;
  } else {
    delete descriptor.expressions;
  }

  const preservedExtensions = (descriptor.extensions || []).filter((e) => e.name !== 'segregation');
  const nextExtensions = editor.segregation
    ? [...preservedExtensions, { name: 'segregation', value: { origin: editor.segregation } }]
    : preservedExtensions;
  if (nextExtensions.length > 0) {
    descriptor.extensions = nextExtensions;
  } else {
    delete descriptor.extensions;
  }

  return descriptor;
}

function startEditVariant(index) {
  const target = props.modelValue[index];
  const descriptor =
    target?.diagnosis?.genomicInterpretations?.[0]?.variantInterpretation?.variationDescriptor;
  if (!descriptor) return;
  detailedEditor.value = editorFromDescriptor(descriptor);
  editingIndex.value = index;
}

function cancelEdit() {
  detailedEditor.value = createEmptyEditor();
  editingIndex.value = null;
}

function saveDetailedVariant() {
  const editor = detailedEditor.value;
  if (editingIndex.value === null && !editor.variantReported) return;

  if (editingIndex.value !== null) {
    const targetInterpretation = props.modelValue[editingIndex.value];
    const genomicInterpretations = targetInterpretation.diagnosis.genomicInterpretations;
    const existingDescriptor =
      genomicInterpretations[0]?.variantInterpretation?.variationDescriptor;
    const updatedDescriptor = buildVariationDescriptor(editor, existingDescriptor);

    const updatedInterpretation = {
      ...targetInterpretation,
      diagnosis: {
        ...targetInterpretation.diagnosis,
        genomicInterpretations: [
          {
            ...genomicInterpretations[0],
            variantInterpretation: {
              ...genomicInterpretations[0].variantInterpretation,
              variationDescriptor: updatedDescriptor,
            },
          },
          ...genomicInterpretations.slice(1),
        ],
      },
    };

    const updated = [...props.modelValue];
    updated[editingIndex.value] = updatedInterpretation;
    emit('update:modelValue', updated);

    window.logService.info('Variant updated via detailed editor', { index: editingIndex.value });
  } else {
    const descriptor = buildVariationDescriptor(editor, null);
    const interpretation = {
      id: `interpretation-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      progressStatus: 'IN_PROGRESS',
      diagnosis: {
        genomicInterpretations: [
          {
            subjectOrBiosampleId: props.subjectId,
            interpretationStatus: 'UNKNOWN',
            variantInterpretation: { variationDescriptor: descriptor },
          },
        ],
      },
    };

    emit('update:modelValue', [...props.modelValue, interpretation]);

    window.logService.info('Variant added via detailed editor', {
      variantReported: editor.variantReported,
    });
  }

  cancelEdit();
}

defineExpose({
  createInterpretation,
  inferMoleculeContext,
  buildVariationDescriptor,
  detailedEditor,
  editingIndex,
});
</script>

<style scoped>
.v-list-item {
  background-color: rgba(0, 0, 0, 0.02);
}

.variant-annotation-form__item--editing {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}
</style>
