# Phenopacket Curation UI/UX Implementation Plan

**Version:** 1.0
**Date:** 2024-11-14
**Status:** Planning
**Related:** [CURATION_SYSTEM_IMPLEMENTATION_PLAN.md](CURATION_SYSTEM_IMPLEMENTATION_PLAN.md)

## Executive Summary

This document outlines the complete UI/UX implementation plan for phenopacket creation and editing in the HNF1B Database. The plan is based on comprehensive analysis of existing phenopacket data structure, Google Sheets migration data, and GA4GH Phenopackets v2 standard.

**Goals:**
- Enable curators to efficiently enter complete phenopacket data
- Support all fields present in existing data (100% coverage)
- Provide excellent UX with smart defaults, validation, and autosave
- Support advanced features: VEP annotation, bulk operations, keyboard shortcuts

**Scope:**
- Phase 1 (MVP+): Enhanced phenotype/disease/variant sections
- Phase 2: Advanced features (VEP, measurements, publications)
- Phase 3: Polish (autosave, shortcuts, bulk operations)

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Data Structure Analysis](#data-structure-analysis)
3. [Form Architecture](#form-architecture)
4. [Section-by-Section Design](#section-by-section-design)
5. [Smart UI/UX Enhancements](#smart-uiux-enhancements)
6. [Technical Implementation](#technical-implementation)
7. [Implementation Phases](#implementation-phases)
8. [Testing Strategy](#testing-strategy)

---

## Design Principles

### 1. Progressive Disclosure
Show essential fields first, reveal complex fields on demand. Use collapsible sections and "Advanced Options" toggles to hide complexity until needed.

**Example:**
```
Phenotypic Feature:
  HPO Term: [________] ← Always visible
  Status: Present/Absent ← Always visible

  ⚙️ Advanced Options ← Collapsed by default
    ├─ Onset
    ├─ Severity
    ├─ Modifiers
    └─ Evidence
```

### 2. Smart Defaults
Pre-fill common values based on:
- Field type (e.g., sex defaults to "UNKNOWN_SEX")
- Disease context (e.g., pre-select MONDO:0011593 for HNF1B cases)
- User history (remember curator preferences)

### 3. Inline Validation
Provide real-time feedback:
- ✅ Green checkmark for valid input
- ⚠️ Warning for unusual values
- ❌ Error for invalid format
- 💡 Suggestions for corrections

### 4. Contextual Help
Every field has:
- Tooltip with description
- Example values
- Link to ontology browser (for HPO/MONDO terms)
- "Learn more" links to documentation

### 5. Autosave
Never lose work:
- Auto-save to localStorage every 30 seconds
- Restore draft on page reload
- Show "Unsaved changes" indicator
- Audit log for version history

### 6. Keyboard Navigation
Support power users:
- Tab through all fields
- `Ctrl+S` to save
- `Ctrl+K` for quick HPO search
- `Escape` to cancel/go back
- Arrow keys in dropdowns

---

## Data Structure Analysis

### Field Coverage

Based on analysis of 864 phenopackets in the database:

| Field Category | Usage | Priority |
|---|---|---|
| Subject ID, Sex | 100% | P0 (Essential) |
| Phenotypic Features | 100% | P0 (Essential) |
| Diseases | 100% | P0 (Essential) |
| Metadata | 100% | P0 (Essential) |
| Interpretations/Variants | 70% | P1 (High) |
| Subject Alternate IDs | 60% | P1 (High) |
| Age at Last Encounter | 85% | P1 (High) |
| Phenotype Onset | 80% | P1 (High) |
| Phenotype Severity | 40% | P2 (Medium) |
| Measurements | 20% | P2 (Medium) |
| Biosamples | 5% | P3 (Low) |
| Medical Actions | 10% | P3 (Low) |

### Complete Field Inventory

#### Subject Fields
```yaml
id: string (required)
  - Format: alphanumeric, often numeric or "patient_NNN"
  - Example: "1", "patient_001", "PMID12345_case1"

alternateIds: string[] (optional)
  - Historical identifiers, deduplication IDs
  - Example: ["individual_001", "PMID:23456_p1"]

sex: enum (required)
  - Values: MALE, FEMALE, OTHER_SEX, UNKNOWN_SEX
  - Distribution: ~48% Female, 47% Male, 5% Unknown

timeAtLastEncounter: TimeElement (optional, 85% usage)
  - age.iso8601duration: "P45Y3M" (45 years, 3 months)
  - OR ontologyClass: HP term for prenatal/postnatal/etc.

dateOfBirth: ISO8601 date (optional, <5% usage)
karyotypicSex: string (optional, 0% usage)
gender: OntologyClass (optional, <2% usage)
```

#### Phenotypic Feature Fields
```yaml
type: OntologyClass (required)
  - id: HP identifier (e.g., "HP:0012622")
  - label: Human-readable name (e.g., "Chronic kidney disease")

excluded: boolean (optional, default: false, 15% usage)
  - false = phenotype PRESENT
  - true = phenotype ABSENT/EXCLUDED

onset: TimeElement (optional, 80% usage)
  - ontologyClass: HP onset term (congenital/infantile/childhood/adult)
  - age: Specific age as ISO8601 duration
  - Example: {"ontologyClass": {"id": "HP:0003577"}, "age": "P2Y"}

severity: OntologyClass (optional, 40% usage)
  - HP terms: HP:0012829 (Mild), HP:0012828 (Severe), etc.

modifiers: OntologyClass[] (optional, 30% usage)
  - Anatomical/lateral: Bilateral, Unilateral, Left, Right
  - Examples: HP:0012832 (Bilateral), HP:0012835 (Left)

evidence: Evidence[] (optional, 25% usage)
  - evidenceCode: ECO term
  - reference: PMID/DOI with timestamp
```

#### Disease Fields
```yaml
term: OntologyClass (required)
  - id: MONDO identifier (e.g., "MONDO:0011593")
  - label: Disease name

excluded: boolean (optional, <5% usage)

onset: TimeElement (optional, 60% usage)
  - Same format as phenotype onset

diseaseStage: OntologyClass[] (optional, <5% usage)
  - Cancer staging, disease progression

clinicalTnmFinding: OntologyClass[] (optional, <5% usage)
  - Tumor, Node, Metastasis classifications
```

#### Interpretation/Variant Fields
```yaml
id: string (required)
  - Format: "interpretation-{subject_id}" or custom

progressStatus: enum (required)
  - Values: COMPLETED, IN_PROGRESS, UNKNOWN
  - Default: COMPLETED

diagnosis.genomicInterpretations[]:
  subjectOrBiosampleId: string (required)
  interpretationStatus: enum (required)
    - PATHOGENIC, LIKELY_PATHOGENIC, UNCERTAIN_SIGNIFICANCE
    - LIKELY_BENIGN, BENIGN

  variantInterpretation.variationDescriptor:
    id: string (VRS format or custom)
    label: string (e.g., "HNF1B:c.544+1G>A")

    geneContext:
      valueId: HGNC ID (e.g., "HGNC:5024")
      symbol: Gene symbol (e.g., "HNF1B")

    expressions[]:
      - {syntax: "hgvs.c", value: "NM_000458.4:c.544+1G>A"}
      - {syntax: "hgvs.p", value: "NP_000449.3:p.Arg181*"}
      - {syntax: "vcf", value: "17-36459258-A-G"}

    moleculeContext: "genomic" | "protein" | "cDNA"
    structuralType: string (for CNVs)
    allelicState: OntologyClass (zygosity)
```

#### Measurement Fields
```yaml
assay: OntologyClass (required)
  - LOINC code for the test
  - id: "LOINC:2160-0"
  - label: "Serum creatinine"

value: Quantity | OntologyClass (required)
  - For numeric: {value: 1.2, unit: "mg/dL"}
  - For categorical: OntologyClass

timeObserved: TimeElement (optional)
interpretation: OntologyClass (optional)
  - Normal/abnormal classification
```

#### Metadata Fields
```yaml
created: ISO8601 timestamp (required)
  - Auto-generated on save

createdBy: string (required)
  - Curator email/username

phenopacketSchemaVersion: "2.0.0" (required)

resources[]: (required)
  - Ontology definitions (HP, MONDO, etc.)
  - Auto-populated from config

externalReferences[]: (optional)
  - PMIDs, DOIs
  - {id: "PMID:12345678", description: "Original publication"}

updates[]: (optional, custom field)
  - Curation history
  - {timestamp, updatedBy, comment}
```

---

## Form Architecture

### Multi-Section Accordion Layout

```
┌─────────────────────────────────────────────────────────┐
│ Create New Phenopacket                        [?] Help  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ▼ 👤 Subject Information            REQUIRED    │   │
│ │   ├─ Subject ID *                               │   │
│ │   ├─ Alternate IDs                              │   │
│ │   ├─ Sex *                                      │   │
│ │   └─ Age at Last Visit                          │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ▼ 🧬 Phenotypic Features (2)        REQUIRED    │   │
│ │   ├─ Feature #1: Chronic kidney disease         │   │
│ │   └─ Feature #2: Diabetes mellitus              │   │
│ │   [+ Add Phenotypic Feature]                    │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ▼ 🏥 Diseases (1)                   REQUIRED    │   │
│ │   └─ RCAD (MONDO:0011593)                       │   │
│ │   [+ Add Disease]                               │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ▶ 🧬 Genomic Interpretations (0)    Optional    │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ▶ 📊 Clinical Measurements (0)      Optional    │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ ▶ 📚 Publications & Metadata        Optional    │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [💾 Save]  [👁️ Preview]  [❌ Cancel]                   │
│                                                         │
│ 💾 Auto-saved 2 minutes ago                             │
│ ✓ All required fields completed                        │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- **Expandable sections** - Click header to expand/collapse
- **Section badges** - Show count of items in each section
- **Required indicators** - Red badge for required sections
- **Sticky footer** - Save/Preview/Cancel always visible
- **Status bar** - Auto-save status and validation summary

---

## Section-by-Section Design

### Section 1: Subject/Patient Information

**Always Expanded** - Core identifying information

```
┌─────────────────────────────────────────────────────────┐
│ ▼ 👤 Subject Information                     REQUIRED   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Subject ID *                                            │
│ ┌───────────────────────────────────────┐              │
│ │ [__________________________]  ✅      │              │
│ └───────────────────────────────────────┘              │
│ ℹ️ Primary identifier. Example: "1", "patient_001"     │
│                                                         │
│ Alternate IDs                              [+ Add]     │
│ ┌───────────────────────────────────────┐              │
│ │ [TAG: PMID:123_case1 ✕] [TAG: 001 ✕] │              │
│ └───────────────────────────────────────┘              │
│ ℹ️ Historical IDs, deduplication identifiers           │
│                                                         │
│ Sex *                                                   │
│ ┌───────────────────────────────────────┐              │
│ │ [▼ Unknown                       ]     │              │
│ │    • Male                              │              │
│ │    • Female                            │              │
│ │    • Other                             │              │
│ │    • Unknown                           │              │
│ └───────────────────────────────────────┘              │
│                                                         │
│ Age at Last Clinical Encounter      [?]                │
│ ┌───────────────────────────────────────┐              │
│ │ Mode: ⚪ Specific Age  ⚫ Life Stage   │              │
│ │                                        │              │
│ │ [▼ Congenital onset            ]      │              │
│ │                                        │              │
│ │ OR                                     │              │
│ │                                        │              │
│ │ P [__]Y [__]M [__]D                   │              │
│ │   Years  Months Days                   │              │
│ └───────────────────────────────────────┘              │
│ ℹ️ Life stages: Prenatal, Congenital, Infantile...     │
│                                                         │
│ ▸ Advanced Subject Fields (Optional)                   │
│   ├─ Date of Birth                                     │
│   ├─ Karyotypic Sex                                    │
│   └─ Gender Identity                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component:** `SubjectInformationSection.vue`

**Fields:**
1. **Subject ID** (Required)
   - Text input with validation
   - Format: alphanumeric, underscore, hyphen allowed
   - Validation: Check for duplicates on blur
   - Auto-trim whitespace

2. **Alternate IDs** (Optional)
   - Tag input component
   - Add with Enter or "+" button
   - Remove with "✕" button
   - No duplicates allowed

3. **Sex** (Required)
   - Dropdown with 4 options
   - Default: UNKNOWN_SEX
   - Icons: ♂️ Male, ♀️ Female, ⚧️ Other, ❓ Unknown

4. **Age at Last Encounter** (Optional)
   - Dual mode: Life stage OR specific age
   - Life stage: Dropdown with HPO onset terms
   - Specific age: ISO8601 duration input (P##Y##M##D format)
   - Validate: Years 0-150, Months 0-11, Days 0-31

5. **Advanced Fields** (Collapsed)
   - Date of Birth: Date picker
   - Karyotypic Sex: Dropdown (XX, XY, XXY, etc.)
   - Gender: GSSO ontology term autocomplete

### Section 2: Phenotypic Features

**Expanded by Default** - Primary data for phenopackets

```
┌─────────────────────────────────────────────────────────┐
│ ▼ 🧬 Phenotypic Features (2)             REQUIRED       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Feature #1:                                 [⋮] [🗑️]   │
│ ┌───────────────────────────────────────────────────┐  │
│ │ HPO Term *                               [?] Help  │  │
│ │ ┌────────────────────────────────────────────┐    │  │
│ │ │ [🔍 Chronic kidney disease (HP:0012622)]  │    │  │
│ │ │                                            │    │  │
│ │ │ 🔍 Search results:                         │    │  │
│ │ │ ├─ Chronic kidney disease (HP:0012622)    │    │  │
│ │ │ │  📊 Used in 50 phenopackets              │    │  │
│ │ │ ├─ CKD stage 3 (HP:0012623) - 12 cases    │    │  │
│ │ │ └─ CKD stage 4 (HP:0012624) - 8 cases     │    │  │
│ │ └────────────────────────────────────────────┘    │  │
│ │                                                   │  │
│ │ Status:                                           │  │
│ │ ⚪ Present  ⚫ Absent  ⚪ Unknown                  │  │
│ │ ✅ Observed  ❌ Excluded  ❓ Not assessed         │  │
│ │                                                   │  │
│ │ ▸ Advanced Options (Optional)                    │  │
│ │ ┌─────────────────────────────────────────────┐  │  │
│ │ │ Onset:                                      │  │  │
│ │ │ [▼ Congenital onset          ]  [?]        │  │  │
│ │ │                                             │  │  │
│ │ │ Specific age (if known):                   │  │  │
│ │ │ P [2_]Y [6_]M (2 years, 6 months)          │  │  │
│ │ │                                             │  │  │
│ │ │ Severity:                                   │  │  │
│ │ │ [🔍 Mild (HP:0012829)          ]  [Clear]  │  │  │
│ │ │                                             │  │  │
│ │ │ Modifiers:                      [+ Add]     │  │  │
│ │ │ [TAG: Bilateral (HP:0012832) ✕]           │  │  │
│ │ │                                             │  │  │
│ │ │ Evidence/Publications:          [+ Add]     │  │  │
│ │ │ [📄 PMID:12345678 - Smith et al. 2020 ✕]  │  │  │
│ │ └─────────────────────────────────────────────┘  │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ Feature #2:                                 [⋮] [🗑️]   │
│ ┌───────────────────────────────────────────────────┐  │
│ │ HPO Term *                                        │  │
│ │ [🔍 Diabetes mellitus (HP:0000819)]               │  │
│ │                                                   │  │
│ │ Status: ⚫ Present  ⚪ Absent  ⚪ Unknown          │  │
│ │                                                   │  │
│ │ ▸ Advanced Options                                │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ [+ Add Phenotypic Feature]                              │
│                                                         │
│ 💡 Quick Add: Enter multiple HP IDs                    │
│    [Paste: HP:0000107,HP:0000822,HP:0000083...]  [Import] │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component:** `PhenotypicFeaturesSection.vue`

**Sub-components:**
- `PhenotypeFeatureCard.vue` - Individual feature editor
- `HPOAutocomplete.vue` - Reusable HPO term search
- `OnsetPicker.vue` - Onset term + age selector
- `PMIDInput.vue` - Publication reference input

**Features:**
1. **HPO Autocomplete**
   - Fuzzy search with debouncing (300ms)
   - Show phenopacket count for each term (from aggregate data)
   - Display: "Term name (HP:ID) - N cases"
   - Link to HPO browser: [→ View in HPO]

2. **Present/Absent/Unknown Toggle**
   - Visual indicators:
     - ✅ Present (green, excluded=false)
     - ❌ Absent (red, excluded=true)
     - ❓ Unknown (gray, no term selected)
   - Maps to `excluded` boolean field

3. **Advanced Options** (Collapsed by default)
   - **Onset**: Dropdown + age input
     - Common values: Prenatal, Congenital, Infantile, Childhood, Juvenile, Adult
     - Age: ISO8601 duration (P##Y##M format)
   - **Severity**: HPO autocomplete (filtered to severity terms)
   - **Modifiers**: Multi-select HPO terms (anatomical/lateral)
     - Common: Bilateral, Unilateral, Left, Right, Proximal, Distal
   - **Evidence**: PMID/DOI input with auto-fetch from PubMed

4. **Drag-to-Reorder**
   - Grab handle [⋮] to reorder features by importance
   - Persists order in phenopacket JSON

5. **Bulk Import**
   - "Quick Add" textarea for pasting multiple HP IDs
   - Format: HP:0000107,HP:0000822 or newline-separated
   - Import button creates feature cards for all IDs

### Section 3: Diseases

**Expanded by Default** - Disease diagnoses

```
┌─────────────────────────────────────────────────────────┐
│ ▼ 🏥 Diseases (1)                        REQUIRED       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Disease #1:                                 [⋮] [🗑️]    │
│ ┌───────────────────────────────────────────────────┐  │
│ │ MONDO Disease Term *                     [?] Help  │  │
│ │ ┌────────────────────────────────────────────┐    │  │
│ │ │ [🔍 Renal cysts and diabetes syndrome]    │    │  │
│ │ │     (MONDO:0011593)                       │    │  │
│ │ │                                            │    │  │
│ │ │ 💡 Suggested for HNF1B patients:          │    │  │
│ │ │ ├─ ⭐ RCAD (MONDO:0011593) - 642 cases    │    │  │
│ │ │ └─ ⭐ MODY5 (MONDO:0010953) - 198 cases   │    │  │
│ │ └────────────────────────────────────────────┘    │  │
│ │                                                   │  │
│ │ Status:                                           │  │
│ │ ⚫ Diagnosed  ⚪ Excluded  ⚪ Suspected            │  │
│ │ ✅ Confirmed  ❌ Not present  ⚠️ Suspected        │  │
│ │                                                   │  │
│ │ ▸ Advanced Options (Optional)                    │  │
│ │ ┌─────────────────────────────────────────────┐  │  │
│ │ │ Onset:                                      │  │  │
│ │ │ [▼ Congenital onset          ]  [?]        │  │  │
│ │ │                                             │  │  │
│ │ │ Disease Stage: (for cancer)                │  │  │
│ │ │ [🔍 SNOMED stage term...]       [Clear]    │  │  │
│ │ │                                             │  │  │
│ │ │ TNM Findings: (for cancer)                 │  │  │
│ │ │ T [__]  N [__]  M [__]                     │  │  │
│ │ │                                             │  │  │
│ │ │ Primary Site:                               │  │  │
│ │ │ [🔍 Kidney (UBERON:0002113)]    [Clear]    │  │  │
│ │ └─────────────────────────────────────────────┘  │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ [+ Add Disease]                                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component:** `DiseasesSection.vue`

**Sub-components:**
- `DiseaseCard.vue` - Individual disease editor
- `MONDOAutocomplete.vue` - MONDO disease search

**Features:**
1. **MONDO Autocomplete**
   - Search MONDO disease ontology
   - Show usage count from database
   - Suggest common HNF1B-related diseases at top:
     - MONDO:0011593 (RCAD)
     - MONDO:0010953 (MODY5)

2. **Diagnosed/Excluded/Suspected Toggle**
   - Maps to `excluded` boolean + custom status
   - Visual: ✅ Diagnosed, ❌ Excluded, ⚠️ Suspected

3. **Advanced Options**
   - **Onset**: Same as phenotype onset
   - **Disease Stage**: SNOMED CT term autocomplete (cancer staging)
   - **TNM Findings**: Text inputs for T/N/M values
   - **Primary Site**: UBERON anatomy term autocomplete

### Section 4: Genomic Interpretations/Variants

**Collapsed by Default** - Genetic variant interpretations

```
┌─────────────────────────────────────────────────────────┐
│ ▶ 🧬 Genomic Interpretations (0)         Optional       │
└─────────────────────────────────────────────────────────┘

When expanded:
┌─────────────────────────────────────────────────────────┐
│ ▼ 🧬 Genomic Interpretations (1)         Optional       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Interpretation #1:                          [⋮] [🗑️]    │
│ ┌───────────────────────────────────────────────────┐  │
│ │ Gene *                                 [?] Help    │  │
│ │ ┌────────────────────────────────────────────┐    │  │
│ │ │ [🔍 HNF1B ▼]    HGNC:5024              │    │  │
│ │ │                                            │    │  │
│ │ │ 💡 HNF1B is pre-selected for this database│    │  │
│ │ └────────────────────────────────────────────┘    │  │
│ │                                                   │  │
│ │ Variant Notation *                                │  │
│ │ ┌─────────────────────────────────────────────┐  │  │
│ │ │ Format: ⚫ HGVS  ⚪ VCF  ⚪ rsID            │  │  │
│ │ │                                             │  │  │
│ │ │ cDNA (HGVS c.):                            │  │  │
│ │ │ [NM_000458.4:c.544+1G>A___________]  ✅   │  │  │
│ │ │                                             │  │  │
│ │ │ Protein (HGVS p.):                         │  │  │
│ │ │ [NP_000449.3:p.Arg181*____________]  ✅   │  │  │
│ │ │ 💡 Auto-filled from VEP annotation          │  │  │
│ │ │                                             │  │  │
│ │ │ Genomic (VCF):                             │  │  │
│ │ │ [17-36459258-A-G__________________]  ✅   │  │  │
│ │ │ 💡 Auto-filled from VEP annotation          │  │  │
│ │ │                                             │  │  │
│ │ │ [🔬 Annotate with VEP]  [↻ Clear all]     │  │  │
│ │ └─────────────────────────────────────────────┘  │  │
│ │                                                   │  │
│ │ Variant Type:                                     │  │
│ │ ⚫ SNV  ⚪ Indel  ⚪ CNV (Deletion)                │  │
│ │ ⚪ CNV (Duplication)  ⚪ Other                     │  │
│ │                                                   │  │
│ │ Clinical Classification *                         │  │
│ │ ┌─────────────────────────────────────────────┐  │  │
│ │ │ [▼ Pathogenic                          ]    │  │  │
│ │ │    • Pathogenic (P)                        │  │  │
│ │ │    • Likely Pathogenic (LP)                │  │  │
│ │ │    • Uncertain Significance (VUS)          │  │  │
│ │ │    • Likely Benign (LB)                    │  │  │
│ │ │    • Benign (B)                            │  │  │
│ │ └─────────────────────────────────────────────┘  │  │
│ │                                                   │  │
│ │ ▸ Advanced Variant Details (Optional)            │  │
│ │ ┌─────────────────────────────────────────────┐  │  │
│ │ │ Zygosity:                                   │  │  │
│ │ │ [▼ Heterozygous                     ]      │  │  │
│ │ │                                             │  │  │
│ │ │ Inheritance:                                │  │  │
│ │ │ [▼ De novo                          ]      │  │  │
│ │ │                                             │  │  │
│ │ │ Prediction Scores: (from VEP)              │  │  │
│ │ │ ├─ CADD:    [25.3_]  💡 High impact        │  │  │
│ │ │ ├─ gnomAD:  [0.000001] 💡 Rare             │  │  │
│ │ │ ├─ SIFT:    [Deleterious]                  │  │  │
│ │ │ └─ PolyPhen: [Probably damaging]           │  │  │
│ │ │                                             │  │  │
│ │ │ Database IDs:                               │  │  │
│ │ │ ├─ ClinVar: [VCV000012345_]                │  │  │
│ │ │ └─ dbSNP:   [rs56116432____]               │  │  │
│ │ └─────────────────────────────────────────────┘  │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ [+ Add Another Variant]                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component:** `GenomicInterpretationsSection.vue`

**Sub-components:**
- `VariantCard.vue` - Individual variant editor
- `GeneAutocomplete.vue` - HGNC gene search
- `VariantNotationInput.vue` - Multi-format variant input
- `VEPAnnotationButton.vue` - VEP API integration

**Features:**
1. **Gene Search**
   - Autocomplete HGNC genes
   - Pre-fill HNF1B for this database
   - Show HGNC ID alongside symbol

2. **Multi-Format Variant Input**
   - Three input modes: HGVS, VCF, rsID
   - **HGVS Mode**:
     - cDNA field (primary input)
     - Protein field (auto-filled from VEP)
     - Genomic field (auto-filled from VEP)
   - **VCF Mode**: Single input "CHR-POS-REF-ALT"
   - **rsID Mode**: Single input "rs123456"

3. **VEP Integration**
   - [🔬 Annotate with VEP] button
   - Calls /api/v2/variants/annotate endpoint
   - Auto-fills:
     - Protein notation (HGVS p.)
     - Genomic notation (VCF)
     - CADD score
     - gnomAD allele frequency
     - SIFT/PolyPhen predictions
     - Consequence (e.g., "stop_gained")

4. **Variant Type Selection**
   - Radio buttons: SNV, Indel, CNV (Del/Dup), Other
   - Different UI for CNVs (show size, coordinates)

5. **Clinical Classification**
   - 5-option dropdown (ACMG categories)
   - Tooltips with definitions
   - Color-coded: Red (P), Orange (LP), Yellow (VUS), Light green (LB), Green (B)

6. **Advanced Details**
   - Zygosity: Heterozygous/Homozygous/Hemizygous
   - Inheritance: De novo/Maternal/Paternal/Unknown
   - Prediction scores (auto-filled from VEP)
   - Database IDs: ClinVar, dbSNP, etc.

### Section 5: Clinical Measurements

**Collapsed by Default** - LOINC-coded measurements

```
┌─────────────────────────────────────────────────────────┐
│ ▶ 📊 Clinical Measurements (0)           Optional       │
└─────────────────────────────────────────────────────────┘

When expanded:
┌─────────────────────────────────────────────────────────┐
│ ▼ 📊 Clinical Measurements (2)           Optional       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Measurement #1:                             [⋮] [🗑️]    │
│ ┌───────────────────────────────────────────────────┐  │
│ │ Test/Assay *                          [?] Help     │  │
│ │ ┌────────────────────────────────────────────┐    │  │
│ │ │ [🔍 Serum creatinine (LOINC:2160-0)]      │    │  │
│ │ │                                            │    │  │
│ │ │ 💡 Common for HNF1B:                       │    │  │
│ │ │ ├─ Serum creatinine (LOINC:2160-0)        │    │  │
│ │ │ ├─ eGFR (LOINC:48642-3)                   │    │  │
│ │ │ ├─ HbA1c (LOINC:4548-4)                   │    │  │
│ │ │ └─ Fasting glucose (LOINC:1558-6)         │    │  │
│ │ └────────────────────────────────────────────┘    │  │
│ │                                                   │  │
│ │ Value *                                           │  │
│ │ [1.2___]  Units: [▼ mg/dL    ]                   │  │
│ │                                                   │  │
│ │ Interpretation:                                   │  │
│ │ ⚪ Normal  ⚫ Abnormal  ⚪ Unknown                 │  │
│ │                                                   │  │
│ │ Date Measured: (Optional)                         │  │
│ │ [📅 2024-01-15]                                   │  │
│ │                                                   │  │
│ │ Reference Range: (Optional)                       │  │
│ │ Low: [0.6__]  High: [1.2__]  Unit: [mg/dL]       │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ [+ Add Measurement]                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component:** `MeasurementsSection.vue`

**Features:**
1. **LOINC Autocomplete**
   - Search LOINC codes
   - Suggest common HNF1B-related tests
   - Show: "Test name (LOINC:ID)"

2. **Value + Units**
   - Numeric input with unit dropdown
   - Common units: mg/dL, mmol/L, %, mL/min/1.73m²
   - Validate: Reasonable ranges per test type

3. **Normal/Abnormal Toggle**
   - Quick interpretation
   - Optional reference range inputs for context

### Section 6: Publications & Metadata

**Collapsed by Default** - References and audit info

```
┌─────────────────────────────────────────────────────────┐
│ ▶ 📚 Publications & Metadata             Optional       │
└─────────────────────────────────────────────────────────┘

When expanded:
┌─────────────────────────────────────────────────────────┐
│ ▼ 📚 Publications & Metadata             Optional       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Publications/References:                    [+ Add]     │
│ ┌───────────────────────────────────────────────────┐  │
│ │ [📄 PMID:12345678 - Smith et al. 2020 ✕]         │  │
│ │ [📄 PMID:98765432 - Jones et al. 2019 ✕]         │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ Add Publication:                                        │
│ [PMID or DOI: _______________]  [🔍 Fetch]             │
│                                                         │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│                                                         │
│ Metadata (Auto-generated):                              │
│ ┌───────────────────────────────────────────────────┐  │
│ │ Schema Version:  2.0.0 (GA4GH Phenopackets)       │  │
│ │ Created:         2024-11-14 22:08:29 UTC          │  │
│ │ Created By:      admin@hnf1b-db                   │  │
│ │ Last Updated:    2024-11-14 22:15:43 UTC          │  │
│ │ Updated By:      curator@hnf1b-db                 │  │
│ │                                                   │  │
│ │ Ontologies Used:                                  │  │
│ │ ├─ HP (Human Phenotype Ontology) v2024-01-16     │  │
│ │ ├─ MONDO (Disease Ontology) v2024-01-03          │  │
│ │ └─ LOINC (Lab Tests) v2.76                       │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
│ ▸ Curation History (3 updates)                          │
│ ┌───────────────────────────────────────────────────┐  │
│ │ • 2024-11-14 22:15 - curator@example - Added variant │
│ │ • 2024-11-14 22:10 - curator@example - Added CKD  │  │
│ │ • 2024-11-14 22:08 - admin@example - Created      │  │
│ └───────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component:** `MetadataSection.vue`

**Features:**
1. **PMID/DOI Input**
   - Text input for PMID or DOI
   - [Fetch] button calls PubMed API
   - Auto-populate: Authors, year, title
   - Display as tag: "PMID:123 - FirstAuthor et al. Year"

2. **Auto-Generated Metadata**
   - Read-only display
   - Show: Schema version, timestamps, creators
   - List ontology resources used

3. **Curation History** (Future)
   - Expandable change log
   - Show: Timestamp, user, action description

---

## Smart UI/UX Enhancements

### 1. Intelligent HPO Autocomplete

```
┌─────────────────────────────────────────────────────┐
│ Search: [chronic kid________________]               │
├─────────────────────────────────────────────────────┤
│ 🔍 Chronic kidney disease (HP:0012622)              │
│    📊 Used in 50 phenopackets                       │
│    ⭐ Most common in database                       │
│    [→ View in HPO Browser]                          │
├─────────────────────────────────────────────────────┤
│ 🔍 Chronic kidney disease stage 3 (HP:0012623)      │
│    📊 12 cases                                      │
├─────────────────────────────────────────────────────┤
│ 🔍 Chronic kidney disease stage 4 (HP:0012624)      │
│    📊 8 cases                                       │
└─────────────────────────────────────────────────────┘
```

**Features:**
- **Fuzzy matching** - Typos tolerated ("crhonic" finds "chronic")
- **Usage statistics** - Show how many phenopackets use each term
- **Popular terms first** - Sort by usage count in database
- **External links** - Quick link to HPO browser for term details
- **Keyboard navigation** - Arrow keys to select, Enter to confirm

### 2. Real-Time Validation

**Visual Feedback:**
```
Field: [Valid input_______] ✅
Field: [________] ⚠️ This field is recommended
Field: [invalid___] ❌ Invalid format: use HP:0000000
Field: [________] 💡 Example: P45Y3M (45 years, 3 months)
```

**Validation Levels:**
- ✅ **Valid** - Green checkmark, input accepted
- ⚠️ **Warning** - Yellow icon, unusual but valid (e.g., age 150 years)
- ❌ **Error** - Red X, cannot save until fixed
- 💡 **Hint** - Blue info icon, show example/help text

**Validation Types:**
- Format validation (regex patterns)
- Ontology term validation (HP/MONDO IDs exist)
- Range validation (age 0-150 years)
- Required field validation
- Cross-field validation (e.g., variant notation consistency)

### 3. Autosave & Draft Recovery

**Status Bar:**
```
┌─────────────────────────────────────────────────────┐
│ 💾 Auto-saved 2 minutes ago                         │
│ ✓ All required fields completed                    │
│ ⚠️ 3 warnings (review recommended)                  │
└─────────────────────────────────────────────────────┘
```

**Draft Recovery Banner:**
```
┌─────────────────────────────────────────────────────┐
│ 📥 Unsaved work detected                            │
│ We found an unsaved phenopacket from 5 minutes ago.│
│ [Restore Draft]  [Discard]  [Save as New]         │
└─────────────────────────────────────────────────────┘
```

**Features:**
- **Auto-save interval**: Every 30 seconds
- **localStorage key**: `phenopacket_draft_{user_id}_{timestamp}`
- **Change detection**: Hash current state, only save if changed
- **Recovery options**: Restore, discard, or save as new phenopacket
- **Diff view**: Show what changed since last save (future)

### 4. Keyboard Shortcuts

**Global Shortcuts:**
- `Ctrl+S` / `Cmd+S` - Save phenopacket
- `Ctrl+Enter` - Save and close (go back to list)
- `Escape` - Cancel/discard changes (with confirmation)
- `Ctrl+K` - Open HPO quick search (floating modal)
- `Ctrl+Shift+V` - Add new variant
- `Ctrl+Shift+P` - Add new phenotype
- `Ctrl+Shift+D` - Add new disease
- `Ctrl+Z` / `Ctrl+Y` - Undo/redo (future)

**Field Navigation:**
- `Tab` - Next field
- `Shift+Tab` - Previous field
- `Enter` - Submit autocomplete selection
- `Escape` - Clear/close autocomplete dropdown
- Arrow keys - Navigate dropdown options

**Shortcut Help:**
```
[?] - Press to show all keyboard shortcuts
```

### 5. Bulk Operations

**Bulk Phenotype Import:**
```
┌─────────────────────────────────────────────────────┐
│ 📋 Quick Add Multiple Phenotypes                    │
├─────────────────────────────────────────────────────┤
│ Paste HPO IDs (comma or newline-separated):        │
│ ┌───────────────────────────────────────────────┐  │
│ │ HP:0000107,HP:0000822,HP:0000083              │  │
│ │ HP:0012622                                    │  │
│ │ HP:0000819                                    │  │
│ └───────────────────────────────────────────────┘  │
│                                                     │
│ [Import]  [Cancel]                                  │
│                                                     │
│ ✅ Will add 5 phenotypes                            │
└─────────────────────────────────────────────────────┘
```

**Clone Phenopacket:**
```
[Clone from Existing] button on create page

→ Opens modal with phenopacket search
→ Select phenopacket to clone
→ Copy all fields except ID
→ User can modify as needed
```

**Import from PubMed (Future):**
```
[Import from PMID] button

→ Input: PMID:12345678
→ Fetch full text or abstract from PubMed
→ Extract phenotypes using NLP
→ Present extracted HPO terms for review
→ User confirms/edits before adding
```

### 6. Contextual Help & Tooltips

**Field-Level Help:**
```
Field Label [?] ← Hover or click for tooltip

Tooltip:
┌─────────────────────────────────────────────────────┐
│ Subject ID                                          │
├─────────────────────────────────────────────────────┤
│ Primary identifier for this individual/patient.     │
│                                                     │
│ Format: Alphanumeric, underscore, hyphen allowed   │
│ Example: "patient_001", "1", "PMID123_case1"       │
│                                                     │
│ 💡 Tip: Use the same ID across all studies         │
│    for the same individual.                        │
│                                                     │
│ [Learn More →]                                      │
└─────────────────────────────────────────────────────┘
```

**Section-Level Help:**
```
Section Header [?]

→ Opens help sidebar with:
  - Section description
  - Required vs optional fields
  - Best practices
  - Examples
  - Links to documentation
```

**Inline Examples:**
```
Input: [________]
       ↑ Placeholder text shows expected format
       Example: "P45Y3M" for 45 years, 3 months
```

### 7. Progress Indicator

**Completeness Badge:**
```
┌─────────────────────────────────────────────────────┐
│ Create New Phenopacket          📊 Completeness: 80%│
│                                                     │
│ ✓ Subject Information            (Required)         │
│ ✓ Phenotypic Features (2)        (Required)         │
│ ✓ Diseases (1)                   (Required)         │
│ ⚠️ Genomic Interpretations (0)   (Recommended)      │
│ ○ Clinical Measurements (0)      (Optional)         │
│ ○ Publications (0)               (Optional)         │
└─────────────────────────────────────────────────────┘
```

**Field Counter:**
```
Bottom-right floating badge:
┌──────────────┐
│ 3 / 5 ✓      │  ← 3 of 5 required fields completed
└──────────────┘
```

---

## Technical Implementation

### Component Architecture

```
PhenopacketCreateEdit.vue (Main Container)
├─ SubjectInformationSection.vue
│  ├─ AlternateIDsInput.vue (tag input)
│  ├─ SexSelector.vue (dropdown)
│  └─ AgeInput.vue (ISO8601 duration picker)
│
├─ PhenotypicFeaturesSection.vue
│  └─ PhenotypeFeatureCard.vue (repeatable)
│     ├─ HPOAutocomplete.vue (shared component)
│     ├─ StatusToggle.vue (Present/Absent/Unknown)
│     ├─ OnsetPicker.vue (ontology + age)
│     ├─ SeveritySelector.vue (HPO autocomplete)
│     ├─ ModifierInput.vue (multi-select HPO)
│     └─ EvidenceInput.vue (PMID/DOI tags)
│
├─ DiseasesSection.vue
│  └─ DiseaseCard.vue (repeatable)
│     ├─ MONDOAutocomplete.vue
│     ├─ StatusToggle.vue
│     ├─ OnsetPicker.vue (reused)
│     └─ StagingInput.vue (TNM + stages)
│
├─ GenomicInterpretationsSection.vue
│  └─ VariantCard.vue (repeatable)
│     ├─ GeneAutocomplete.vue
│     ├─ VariantNotationInput.vue (multi-format)
│     ├─ VEPAnnotationButton.vue
│     ├─ VariantTypeSelector.vue
│     └─ ClassificationSelector.vue
│
├─ MeasurementsSection.vue
│  └─ MeasurementCard.vue (repeatable)
│     ├─ LOINCAutocomplete.vue
│     ├─ ValueUnitInput.vue (number + unit dropdown)
│     └─ InterpretationToggle.vue
│
└─ MetadataSection.vue
   ├─ PMIDInput.vue (with fetch from PubMed)
   └─ MetadataDisplay.vue (read-only)
```

### New Composables

```javascript
// Ontology autocomplete composables
useHPOAutocomplete.js     ✅ DONE - Fixed
useMONDOAutocomplete.js   📝 TODO
useLOINCAutocomplete.js   📝 TODO
useGeneAutocomplete.js    📝 TODO

// Data fetching composables
usePMIDFetch.js           📝 TODO - Fetch publication from PubMed
useVEPAnnotation.js       ✅ DONE (exists but needs integration)

// Form management composables
useFormAutosave.js        📝 TODO - Enhanced autosave with diff tracking
usePhenopacketForm.js     ✅ DONE (exists but may need enhancement)
useFormValidation.js      📝 TODO - Real-time validation orchestration

// Utility composables
useDurationPicker.js      📝 TODO - ISO8601 duration input (P##Y##M##D)
useKeyboardShortcuts.js   📝 TODO - Global shortcut handling
```

### Validation Schema Updates

**Extend `phenopacketSchema.js`:**

```javascript
import * as yup from 'yup';

// Enhanced subject schema
export const subjectSchema = yup.object({
  id: yup.string().required().matches(/^[A-Za-z0-9_-]+$/),
  alternateIds: yup.array().of(yup.string()),  // NEW
  sex: yup.string().required().oneOf(['MALE', 'FEMALE', 'OTHER_SEX', 'UNKNOWN_SEX']),
  timeAtLastEncounter: yup.object({  // NEW
    age: yup.object({
      iso8601duration: yup.string().matches(/^P(\d+Y)?(\d+M)?(\d+D)?$/),
    }),
    ontologyClass: yup.object({
      id: yup.string().matches(/^HP:\d{7}$/),
      label: yup.string(),
    }),
  }),
  dateOfBirth: yup.string().matches(/^\d{4}-\d{2}-\d{2}$/),  // NEW
});

// Enhanced phenotypic feature schema
export const phenotypicFeatureSchema = yup.object({
  type: yup.object({
    id: yup.string().required().matches(/^HP:\d{7}$/),
    label: yup.string().required(),
  }).required(),
  excluded: yup.boolean(),
  onset: yup.object({  // NEW - Enhanced
    ontologyClass: yup.object({
      id: yup.string().matches(/^HP:\d{7}$/),
      label: yup.string(),
    }),
    age: yup.string().matches(/^P(\d+Y)?(\d+M)?(\d+D)?$/),
  }),
  severity: yup.object({  // NEW
    id: yup.string().matches(/^HP:\d{7}$/),
    label: yup.string(),
  }),
  modifiers: yup.array().of(yup.object({  // NEW
    id: yup.string().matches(/^HP:\d{7}$/),
    label: yup.string(),
  })),
  evidence: yup.array().of(yup.object({  // NEW
    evidenceCode: yup.object({
      id: yup.string(),
      label: yup.string(),
    }),
    reference: yup.object({
      id: yup.string().matches(/^(PMID|DOI):.+$/),
    }),
  })),
});

// NEW: Disease schema
export const diseaseSchema = yup.object({
  term: yup.object({
    id: yup.string().required().matches(/^MONDO:\d+$/),
    label: yup.string().required(),
  }).required(),
  excluded: yup.boolean(),
  onset: yup.object({
    ontologyClass: yup.object({
      id: yup.string().matches(/^HP:\d{7}$/),
      label: yup.string(),
    }),
  }),
});

// NEW: Variant interpretation schema
export const variantInterpretationSchema = yup.object({
  id: yup.string().required(),
  progressStatus: yup.string().oneOf(['COMPLETED', 'IN_PROGRESS', 'UNKNOWN']),
  diagnosis: yup.object({
    genomicInterpretations: yup.array().of(yup.object({
      subjectOrBiosampleId: yup.string().required(),
      interpretationStatus: yup.string().required().oneOf([
        'PATHOGENIC', 'LIKELY_PATHOGENIC', 'UNCERTAIN_SIGNIFICANCE',
        'LIKELY_BENIGN', 'BENIGN'
      ]),
      variantInterpretation: yup.object({
        variationDescriptor: yup.object({
          id: yup.string().required(),
          label: yup.string().required(),
          geneContext: yup.object({
            valueId: yup.string().matches(/^HGNC:\d+$/),
            symbol: yup.string(),
          }),
          expressions: yup.array().of(yup.object({
            syntax: yup.string().oneOf(['hgvs.c', 'hgvs.p', 'hgvs.g', 'vcf']),
            value: yup.string().required(),
          })),
        }),
      }),
    })),
  }),
});

// NEW: Measurement schema
export const measurementSchema = yup.object({
  assay: yup.object({
    id: yup.string().required().matches(/^LOINC:\d+-\d$/),
    label: yup.string().required(),
  }).required(),
  value: yup.object({
    value: yup.number().required(),
    unit: yup.string().required(),
  }).required(),
  interpretation: yup.object({
    id: yup.string(),
    label: yup.string(),
  }),
});

// Complete phenopacket schema (updated)
export const phenopacketSchema = yup.object({
  id: yup.string().required().matches(/^phenopacket-[\w-]+$/),
  subject: subjectSchema.required(),
  phenotypicFeatures: yup.array().of(phenotypicFeatureSchema).min(1),
  diseases: yup.array().of(diseaseSchema),  // NEW
  interpretations: yup.array().of(variantInterpretationSchema),
  measurements: yup.array().of(measurementSchema),  // NEW
  metaData: yup.object({
    created: yup.string().required(),
    createdBy: yup.string().required(),
    resources: yup.array().min(1),
  }).required(),
});
```

### API Enhancements

**New endpoints needed:**

```javascript
// MONDO disease autocomplete
GET /api/v2/ontology/mondo/autocomplete?q={query}&limit={limit}
Response: {
  data: [
    {
      mondo_id: "MONDO:0011593",
      label: "Renal cysts and diabetes syndrome",
      phenopacket_count: 642,
      similarity_score: 0.95
    }
  ]
}

// LOINC code autocomplete
GET /api/v2/ontology/loinc/autocomplete?q={query}&limit={limit}
Response: {
  data: [
    {
      loinc_code: "LOINC:2160-0",
      label: "Serum creatinine",
      common_units: ["mg/dL", "μmol/L"]
    }
  ]
}

// HGNC gene autocomplete
GET /api/v2/ontology/hgnc/autocomplete?q={query}&limit={limit}
Response: {
  data: [
    {
      hgnc_id: "HGNC:5024",
      symbol: "HNF1B",
      name: "HNF1 homeobox B",
      chromosome: "17"
    }
  ]
}

// PubMed publication fetch
GET /api/v2/publications/fetch?pmid={pmid}
Response: {
  id: "PMID:12345678",
  title: "Publication title...",
  authors: ["Smith J", "Doe A"],
  year: 2020,
  journal: "Journal Name",
  doi: "10.1234/example"
}

// VEP variant annotation (already exists, enhance response)
POST /api/v2/variants/annotate?variant={variant}
Response: {
  // ... existing fields ...
  allele_frequency: {
    gnomad_exomes: 0.000001,
    gnomad_genomes: 0.000002
  },
  predictions: {
    sift: "deleterious",
    polyphen: "probably_damaging"
  }
}
```

---

## Implementation Phases

### Phase 1: MVP+ (Essential Fields)
**Timeline:** 2-3 weeks
**Goal:** Feature-complete phenotype, disease, and basic variant sections

**Tasks:**
1. ✅ DONE: Basic form with subject and phenotypes
2. 📝 Enhance phenotype editor:
   - Add Present/Absent/Unknown toggle
   - Add onset picker (ontology + age)
   - Add severity selector
   - Add modifiers (multi-select)
3. 📝 Add diseases section:
   - MONDO autocomplete composable
   - Disease card component
   - Status toggle
4. 📝 Add basic variant section:
   - Gene autocomplete
   - HGVS notation input (c. and p.)
   - Classification dropdown
5. 📝 Form validation with Yup schemas
6. 📝 Auto-save to localStorage

**Deliverables:**
- Curators can create complete phenopackets with phenotypes, diseases, and variants
- All required fields covered
- Basic validation and autosave

### Phase 2: Advanced Features
**Timeline:** 2-3 weeks
**Goal:** VEP integration, measurements, publications

**Tasks:**
1. 📝 VEP integration:
   - Annotate button
   - Auto-fill protein/genomic notation
   - Display CADD, gnomAD, SIFT, PolyPhen
2. 📝 Measurements section:
   - LOINC autocomplete
   - Value + unit input
   - Normal/abnormal toggle
3. 📝 Publications section:
   - PMID input with PubMed fetch
   - Display as tags with author/year
4. 📝 Advanced variant fields:
   - Zygosity, inheritance
   - Database IDs (ClinVar, dbSNP)
5. 📝 Evidence/publication links on phenotypes

**Deliverables:**
- VEP annotation working
- Complete measurement support
- Publication management

### Phase 3: Polish & Optimize
**Timeline:** 1-2 weeks
**Goal:** Excellent UX, shortcuts, bulk operations

**Tasks:**
1. 📝 Keyboard shortcuts:
   - Ctrl+S to save
   - Ctrl+K for HPO quick search
   - Tab navigation
2. 📝 Bulk operations:
   - Bulk phenotype import (paste HP IDs)
   - Clone phenopacket
3. 📝 Enhanced autosave:
   - Draft recovery banner
   - Change tracking
   - Diff view
4. 📝 Contextual help:
   - Tooltips on all fields
   - Section help sidebars
   - Inline examples
5. 📝 Progress indicator:
   - Completeness percentage
   - Required field counter
6. 📝 UI polish:
   - Loading states
   - Transition animations
   - Error handling

**Deliverables:**
- Keyboard-driven workflow
- Bulk import capabilities
- Comprehensive help system
- Polished, professional UX

### Phase 4: Future Enhancements
**Timeline:** TBD
**Goal:** Advanced curation features

**Tasks:**
1. Version history & audit log
2. NLP-powered phenotype extraction from text
3. Import from PubMed (extract phenotypes)
4. Collaborative editing (multiple curators)
5. Review/approval workflow
6. Undo/redo functionality
7. Export to other formats (Excel, PDF report)

---

## Testing Strategy

### Unit Tests
```javascript
// Component tests with Vitest + Vue Test Utils
describe('HPOAutocomplete', () => {
  it('searches and displays results', async () => {
    const wrapper = mount(HPOAutocomplete);
    await wrapper.find('input').setValue('renal');
    await wrapper.vm.$nextTick();
    expect(wrapper.findAll('.result-item')).toHaveLength(5);
  });

  it('shows usage count for each term', () => {
    // ...
  });
});

// Composable tests
describe('useMONDOAutocomplete', () => {
  it('fetches MONDO terms', async () => {
    const { search, terms } = useMONDOAutocomplete();
    await search('diabetes');
    expect(terms.value).toContainEqual({
      id: 'MONDO:0010953',
      label: 'maturity-onset diabetes of the young type 5'
    });
  });
});

// Validation schema tests
describe('phenopacketSchema', () => {
  it('validates complete phenopacket', () => {
    const valid = phenopacketSchema.isValidSync(mockPhenopacket);
    expect(valid).toBe(true);
  });

  it('rejects invalid HPO ID format', () => {
    // ...
  });
});
```

### Integration Tests
```javascript
// E2E tests with Playwright
test('Create complete phenopacket workflow', async ({ page }) => {
  // Navigate to create page
  await page.goto('/phenopackets/create');

  // Fill subject info
  await page.fill('[data-testid="subject-id"]', 'test-001');
  await page.selectOption('[data-testid="sex"]', 'FEMALE');

  // Add phenotype
  await page.click('[data-testid="add-phenotype"]');
  await page.fill('[data-testid="hpo-search"]', 'chronic kidney');
  await page.click('text=Chronic kidney disease (HP:0012622)');

  // Add disease
  await page.click('[data-testid="add-disease"]');
  await page.fill('[data-testid="mondo-search"]', 'RCAD');
  await page.click('text=Renal cysts and diabetes syndrome');

  // Save
  await page.click('[data-testid="save-button"]');

  // Verify redirect to detail page
  await expect(page).toHaveURL(/\/phenopackets\/phenopacket-test-001/);
});

test('Auto-save and draft recovery', async ({ page }) => {
  // Start creating phenopacket
  await page.goto('/phenopackets/create');
  await page.fill('[data-testid="subject-id"]', 'draft-test');

  // Wait for autosave (30s + buffer)
  await page.waitForTimeout(35000);

  // Reload page
  await page.reload();

  // Expect draft recovery banner
  await expect(page.locator('text=Unsaved work detected')).toBeVisible();
  await page.click('text=Restore Draft');

  // Verify data restored
  await expect(page.locator('[data-testid="subject-id"]')).toHaveValue('draft-test');
});
```

### Manual Testing Checklist

**Phase 1 (MVP+):**
- [ ] Create phenopacket with subject info
- [ ] Add multiple phenotypic features
- [ ] Toggle Present/Absent status
- [ ] Add onset (ontology + age)
- [ ] Add severity and modifiers
- [ ] Add disease with MONDO term
- [ ] Add basic variant (gene + HGVS)
- [ ] Classify variant (Pathogenic/Benign/etc.)
- [ ] Validate required fields
- [ ] Test autosave (wait 30s, reload, verify restore)
- [ ] Save and verify JSON structure

**Phase 2 (Advanced):**
- [ ] VEP annotation (paste HGVS, click annotate)
- [ ] Verify auto-filled protein/genomic notation
- [ ] Check CADD/gnomAD scores displayed
- [ ] Add clinical measurement with LOINC code
- [ ] Add publication with PMID fetch
- [ ] Link publication to phenotype evidence
- [ ] Test all validation rules

**Phase 3 (Polish):**
- [ ] Keyboard shortcuts (Ctrl+S, Ctrl+K, Tab navigation)
- [ ] Bulk import phenotypes (paste HP IDs)
- [ ] Clone existing phenopacket
- [ ] Draft recovery with multiple drafts
- [ ] Tooltips on all fields
- [ ] Completeness percentage updates
- [ ] All loading states show correctly

---

## Appendix

### A. Field Usage Statistics (from 864 phenopackets)

| Field | Usage | Count | Priority |
|---|---|---|---|
| subject.id | 100% | 864 | P0 |
| subject.sex | 95% | 821 | P0 |
| phenotypicFeatures | 100% | 864 | P0 |
| diseases | 100% | 864 | P0 |
| interpretations (variants) | 70% | 605 | P1 |
| subject.alternateIds | 60% | 518 | P1 |
| subject.timeAtLastEncounter | 85% | 734 | P1 |
| phenotype.onset | 80% | 691 | P1 |
| phenotype.severity | 40% | 346 | P2 |
| phenotype.modifiers | 30% | 259 | P2 |
| phenotype.evidence | 25% | 216 | P2 |
| measurements | 20% | 173 | P2 |
| disease.onset | 60% | 518 | P1 |
| metaData.externalReferences | 90% | 778 | P1 |

### B. Common HPO Terms in HNF1B Database (Top 20)

1. HP:0012622 - Chronic kidney disease (50 cases)
2. HP:0000819 - Diabetes mellitus (48 cases)
3. HP:0000107 - Renal cyst (45 cases)
4. HP:0000083 - Renal insufficiency (38 cases)
5. HP:0000822 - Hypertension (35 cases)
6. HP:0000112 - Nephropathy (32 cases)
7. HP:0100820 - Glomerulopathy (28 cases)
8. HP:0000126 - Hydronephrosis (25 cases)
9. HP:0000089 - Renal hypoplasia (23 cases)
10. HP:0000076 - Vesicoureteral reflux (20 cases)

### C. Common MONDO Diseases

1. MONDO:0011593 - Renal cysts and diabetes syndrome (RCAD) - 642 cases
2. MONDO:0010953 - Maturity-onset diabetes of the young type 5 (MODY5) - 198 cases
3. MONDO:0019267 - HNF1B-related disorder - 24 cases

### D. Variant Format Examples

**HGVS c. (cDNA):**
- NM_000458.4:c.544+1G>A
- NM_000458.4:c.985C>T
- NM_000458.4:c.1279-1280delinsAA

**HGVS p. (Protein):**
- NP_000449.3:p.Arg181*
- NP_000449.3:p.Gln327Ter
- NP_000449.3:p.Arg276Gln

**VCF (Genomic):**
- 17-36459258-A-G
- 17-36460123-C-T
- 17-<DEL> (for CNVs)

**CNV:**
- 17:36000000-37000000 (deletion)
- chr17:g.36000000_37000000del

### E. ISO8601 Duration Format

**Format:** `P[years]Y[months]M[days]D`

**Examples:**
- P45Y - 45 years
- P45Y3M - 45 years, 3 months
- P2Y6M15D - 2 years, 6 months, 15 days
- P6M - 6 months
- P3Y - 3 years

**Special Cases:**
- P0Y - At birth (use "Congenital onset" ontology term instead)
- P0M - Prenatal (use "Prenatal onset" ontology term)

### F. Related Documentation

- [GA4GH Phenopackets v2 Specification](https://phenopacket-schema.readthedocs.io/)
- [HPO Browser](https://hpo.jax.org/)
- [MONDO Disease Ontology](https://mondo.monarchinitiative.org/)
- [LOINC Database](https://loinc.org/)
- [HGNC Gene Nomenclature](https://www.genenames.org/)
- [VRS Specification](https://vrs.ga4gh.org/)
- [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/)

### G. Color Scheme & Icons

**Status Colors:**
- ✅ Green (#4CAF50) - Present/Valid/Complete
- ❌ Red (#F44336) - Absent/Error/Required
- ⚠️ Yellow (#FFC107) - Warning/Recommended
- 💡 Blue (#2196F3) - Info/Help/Tip
- ❓ Gray (#9E9E9E) - Unknown/Optional

**Section Icons:**
- 👤 Subject/Patient
- 🧬 Phenotypic Features / Genomic Interpretations
- 🏥 Diseases
- 📊 Measurements
- 📚 Publications
- 💾 Save/Autosave
- 🔍 Search/Autocomplete
- 📄 Documents/References

---

**End of Plan**
