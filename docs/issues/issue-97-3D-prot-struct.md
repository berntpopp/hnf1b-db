# Issue #90: feat(frontend): add 3D protein structure visualization for missense variants

## Summary

Add interactive 3D protein structure viewer showing missense variants mapped onto HNF1B structure.

**Current:** Text-only variant display
**Target:** NGL.js 3D viewer with variants color-coded by pathogenicity

## Reference Implementation

**hnf1b-protein-page:** https://github.com/halbritter-lab/hnf1b-protein-page
- Uses NGL.js v2 for 3D rendering
- PDB structure: 2H8R (residues 170-280)
- Color-coded variants by pathogenicity
- Cartoon/surface/ball-stick representations

## Implementation

### 1. Install NGL.js

```bash
cd frontend
npm install ngl
```

### 2. Create Component

**File:** `frontend/src/components/variant/ProteinStructure3D.vue` (NEW)

```vue
<template>
  <v-card>
    <v-card-title>3D Protein Structure</v-card-title>
    <v-card-text>
      <div id="ngl-viewport" style="width: 100%; height: 600px;"></div>

      <v-btn-group>
        <v-btn @click="setRepresentation('cartoon')">Cartoon</v-btn>
        <v-btn @click="setRepresentation('surface')">Surface</v-btn>
        <v-btn @click="setRepresentation('ball+stick')">Ball+Stick</v-btn>
      </v-btn-group>
    </v-card-text>
  </v-card>
</template>

<script setup>
import * as NGL from 'ngl'
import { onMounted } from 'vue'

const props = defineProps({
  variant: Object,
  allVariants: Array
})

let stage = null

onMounted(async () => {
  stage = new NGL.Stage('ngl-viewport')
  await stage.loadFile('rcsb://2H8R', { defaultRepresentation: true })

  // Highlight variants
  props.allVariants.forEach(v => {
    if (v.proteinPosition) {
      const color = getPathogenicityColor(v.pathogenicity)
      stage.getRepresentationsByName('structure').setSelection(
        `${v.proteinPosition}`,
        { color }
      )
    }
  })

  // Focus on current variant
  if (props.variant?.proteinPosition) {
    stage.centerView(`:${props.variant.proteinPosition}`)
  }
})

function getPathogenicityColor(path) {
  return {
    'Pathogenic': 0xFF0000,
    'Likely pathogenic': 0xFF6600,
    'VUS': 0xFFFF00,
    'Benign': 0x00FF00
  }[path] || 0xCCCCCC
}

function setRepresentation(type) {
  stage.eachRepresentation(rep => rep.setVisibility(false))
  stage.addRepresentation(type)
}
</script>
```

### 3. Add to Variant Detail Page

**File:** `frontend/src/views/VariantDetail.vue` (MODIFY)

```vue
<template>
