# Phenotype Curation UI Implementation Plan

**Goal**: Create an elegant, user-friendly phenopacket curation interface that allows efficient data entry of complete GA4GH Phenopackets v2 compliant records.

## Core Requirements

### 1. System-Grouped Phenotype Selection (Priority 1)
**Vision**: Color-coded, organ system grouped phenotype checklist for quick presence/absence/unknown selection

**Design Decisions**:
- **Layout**: Expandable accordion sections per organ system (Kidney, Liver, Pancreas, etc.)
- **Color Coding**: Each system has distinct color (Material Design palette)
  - Kidney: Blue (primary)
  - Liver: Green (success)
  - Pancreas: Purple (secondary)
  - Metabolic: Orange (warning)
  - Other: Gray (neutral)
- **Selection Method**: Tri-state checkboxes
  - ✅ Present (checked, green)
  - ❌ Absent (indeterminate, red)
  - ⬜ Unknown/Not assessed (unchecked, gray)
- **Prioritization**: "Required" phenotypes shown first, then "Recommended", then expandable "All"
- **Quick Entry**: Keyboard shortcuts (Space = toggle present/absent, X = mark absent)

**API Integration**:
- Endpoint: `GET /api/v2/ontology/hpo/recommended` - get all curated HNF1B phenotypes grouped by system
- New backend endpoint needed for grouped phenotypes
- Returns: `{ "Kidney": [...], "Liver": [...], "Pancreas": [...] }`

**Component Structure**:
```
PhenotypicFeaturesSection.vue
├── SystemGroup.vue (per organ system)
│   ├── PhenotypeCheckbox.vue (tri-state checkbox)
│   └── OnsetSelector.vue (optional, inline)
└── PhenotypeDetails.vue (modifiers, evidence - expandable)
```

### 2. VEP Variant Annotation Integration (Priority 2)
**Vision**: Elegant variant input with automatic VEP annotation and visualization

**Features**:
- **Smart Input**: Auto-detect format (VCF: chr-pos-ref-alt, HGVS, rsID)
- **Real-time Validation**: Format validation as user types
- **VEP Integration**:
  - Call `/api/v2/variants/annotate?variant={input}`
  - Display consequences, CADD scores, gnomAD frequencies
  - Show affected transcripts with visual impact indicators
- **ACMG Classification**:
  - Guided classification wizard
  - Evidence selection (PVS1, PS1-4, PM1-6, PP1-5, BA1, BS1-4, BP1-7)
  - Auto-calculate classification from evidence
- **Variant Visualization**:
  - Protein domain visualization
  - Conservation scores
  - Population frequencies (bar chart)

**Component**: `VariantAnnotationForm.vue`

### 3. Complete Form Sections

**Subject Section** (Enhanced):
- ID, Sex (API-driven), Alternate IDs
- Age at last encounter
- Pedigree information (optional)

**Disease Section**:
- MONDO disease autocomplete
- Multiple diseases support
- Onset selection per disease
- Component: `DiseaseAutocomplete.vue`

**Evidence & References**:
- PubMed ID input with auto-fetch
- Evidence code selection (ECO ontology)
- Recorded date
- Component: `EvidenceManager.vue`

**Metadata**:
- Auto-generated (created date, creator)
- External references
- Resources (HPO, MONDO versions)

## Implementation Phases

### Phase 1: Backend API Enhancements (Day 1)
1. Create `/api/v2/ontology/hpo/grouped` endpoint
   - Returns HPO terms grouped by organ system
   - Filters by recommendation level (required/recommended)
   - Include term details (id, label, group, category, recommendation)

2. Enhance `/api/v2/variants/annotate` endpoint
   - Add more detailed VEP response parsing
   - Include transcript consequences
   - Add CADD/gnomAD data

### Phase 2: Frontend Components (Day 1-2)
1. **PhenotypicFeaturesSection.vue**
   - Organ system accordion groups
   - Color-coded headers
   - Tri-state checkboxes
   - Inline onset selection
   - Expandable details (modifiers, evidence)

2. **VariantAnnotationForm.vue**
   - Smart variant input
   - VEP annotation display
   - ACMG classification interface

3. **DiseaseAutocomplete.vue**
   - MONDO disease search
   - Multiple disease support
   - Onset per disease

4. **EvidenceManager.vue**
   - PubMed reference management
   - Evidence code selection
   - Date recording

### Phase 3: Integration & Testing (Day 2-3)
1. Integrate all components into PhenopacketCreateEdit.vue
2. Test with real phenopackets from database:
   - phenopacket-1 (8 phenotypic features)
   - phenopacket-13 (complex with variants)
3. Ensure data round-trips correctly (create → API → display)
4. Validation testing

### Phase 4: Automated Testing (Day 3)
1. Component unit tests (Vitest + Vue Test Utils)
2. Integration tests for form workflows
3. E2E tests with Playwright
4. API endpoint tests

## Technical Specifications

### Color Palette (Material Design 3)
```javascript
const SYSTEM_COLORS = {
  Kidney: { primary: '#1976D2', light: '#BBDEFB', dark: '#0D47A1' },
  Liver: { primary: '#388E3C', light: '#C8E6C9', dark: '#1B5E20' },
  Pancreas: { primary: '#7B1FA2', light: '#E1BEE7', dark: '#4A148C' },
  Metabolic: { primary: '#F57C00', light: '#FFE0B2', dark: '#E65100' },
  Cardiac: { primary: '#C62828', light: '#FFCDD2', dark: '#B71C1C' },
  Neurological: { primary: '#5E35B1', light: '#D1C4E9', dark: '#311B92' },
  Other: { primary: '#616161', light: '#E0E0E0', dark: '#424242' },
};
```

### Data Model (Tri-state Selection)
```javascript
{
  phenotypicFeatures: [
    {
      hpoTerm: { id: 'HP:0000107', label: 'Renal cyst' },
      status: 'present' | 'absent' | 'unknown',
      onset: { age: 'P1Y', ontologyClass: {...} },
      modifiers: [...],
      evidence: [...]
    }
  ]
}
```

### Performance Considerations
- Lazy load organ system sections (virtual scrolling if >100 terms)
- Debounce VEP API calls (300ms)
- Cache VEP results (localStorage, 1 hour TTL)
- Optimistic UI updates for checkbox toggles

## Success Metrics
1. ✅ Can enter complete phenopacket in <5 minutes
2. ✅ <3 clicks to mark phenotype present/absent
3. ✅ Variant annotation loads in <2 seconds
4. ✅ 100% of existing phenopackets can be recreated via UI
5. ✅ All tests pass (unit, integration, E2E)

## Next Steps
1. Create backend endpoint for grouped HPO terms
2. Implement PhenotypicFeaturesSection component
3. Test with real phenopacket data
4. Iterate based on UX feedback
