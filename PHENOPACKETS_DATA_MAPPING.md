# Phenopackets Data Mapping Documentation

## Overview
This document describes the exact mapping between Google Sheets columns and GA4GH Phenopackets v2 fields.

## Data Source
- **Spreadsheet ID**: 1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw
- **Main Sheet (GID=0)**: Contains 939 rows representing 864 unique individuals

## Phenopacket Structure and Data Sources

### 1. Subject (Patient Information)
```json
{
  "id": "individual_id column",
  "alternateIds": ["IndividualIdentifier column"],
  "sex": "Sex column → mapped to FEMALE/MALE/UNKNOWN_SEX",
  "timeAtLastEncounter": {
    "iso8601duration": "Parsed from AgeReported column"
  }
}
```

**Column Mappings:**
- `individual_id` → subject.id (internal database ID: "1", "2", "3"...)
- `IndividualIdentifier` → subject.alternateIds (e.g., "Pinon_Tab2 Case5", "stiles2018_patient")
- `Sex` → subject.sex (mapped values: "female"→"FEMALE", "male"→"MALE", "unspecified"→"UNKNOWN_SEX")
- `AgeReported` → subject.timeAtLastEncounter (age at last clinical encounter)
- `AgeOnset` → Used for disease.onset (age when disease first manifested)

### 2. Phenotypic Features (Clinical Manifestations)
```json
"phenotypicFeatures": [
  {
    "type": {
      "id": "HPO term",
      "label": "HPO label"
    },
    "excluded": false,
    "modifiers": [...]  // For bilateral/unilateral features
  }
]
```

**Column Mappings (each column mapped to specific HPO term):**
- `RenalInsufficancy` → HP:0000083 (Renal insufficiency)
- `Hyperechogenicity` → HP:0010935 (Increased echogenicity of kidneys)
- `RenalCysts` → HP:0000107 (Renal cyst)
- `MulticysticDysplasticKidney` → HP:0000003 (Multicystic kidney dysplasia)
- `KidneyBiopsy` → HP:0100611 or HP:0004719 (Multiple glomerular cysts or Oligomeganephronia)
- `RenalHypoplasia` → HP:0000089 (Renal hypoplasia)
- `SolitaryKidney` → HP:0004729 (Solitary functioning kidney)
- `UrinaryTractMalformation` → HP:0000079 (Abnormality of the urinary system)
- `GenitalTractAbnormality` → HP:0000078 (Abnormality of the genital system)
- `AntenatalRenalAbnormalities` → HP:0010945 (Fetal renal anomaly)
- `Hypomagnesemia` → HP:0002917 (Hypomagnesemia)
- `Hypokalemia` → HP:0002900 (Hypokalemia)
- `Hyperuricemia` → HP:0002149 (Hyperuricemia)
- `Gout` → HP:0001997 (Gout)
- `MODY` → HP:0004904 (Maturity-onset diabetes of the young)
- `PancreaticHypoplasia` → HP:0100575 (Pancreatic hypoplasia)
- `ExocrinePancreaticInsufficiency` → HP:0001738 (Exocrine pancreatic insufficiency)
- `Hyperparathyroidism` → HP:0000843 (Hyperparathyroidism)
- `NeurodevelopmentalDisorder` → HP:0012759 (Neurodevelopmental abnormality)
- `MentalDisease` → HP:0000708 (Behavioral abnormality)
- `Seizures` → HP:0001250 (Seizures)
- `BrainAbnormality` → HP:0012443 (Abnormality of brain morphology)
- `PrematureBirth` → HP:0001622 (Premature birth)
- `CongenitalCardiacAnomalies` → HP:0001627 (Abnormal heart morphology)
- `EyeAbnormality` → HP:0000478 (Abnormality of the eye)
- `ShortStature` → HP:0004322 (Short stature)
- `MusculoskeletalFeatures` → HP:0033127 (Abnormality of the musculoskeletal system)
- `DysmorphicFeatures` → HP:0001999 (Abnormal facial shape)
- `ElevatedHepaticTransaminase` → HP:0002910 (Elevated hepatic transaminase)
- `AbnormalLiverPhysiology` → HP:0031865 (Abnormal liver physiology)

**Value Interpretation:**
- "yes", "present", or specific values → Feature is present
- "no", "absent" → Feature is excluded (excluded: true)
- "not reported", empty → Feature is not included
- "bilateral", "unilateral", "left", "right" → Added as modifiers

### 3. Genetic Variants (Interpretations)
```json
"interpretations": [
  {
    "id": "interpretation-001",
    "progressStatus": "COMPLETED",
    "diagnosis": {
      "disease": {
        "id": "MONDO:0018874",
        "label": "HNF1B-related disorder"
      },
      "genomicInterpretations": [
        {
          "subjectOrBiosampleId": "patient identifier",
          "interpretationStatus": "PATHOGENIC/LIKELY_PATHOGENIC/etc",
          "variantInterpretation": {
            "variationDescriptor": {
              "id": "unique variant ID",
              "label": "human readable label",
              "geneContext": {
                "valueId": "HGNC:5024",
                "symbol": "HNF1B"
              },
              "expressions": [
                // HGVS expressions
              ],
              "moleculeContext": "genomic",
              "allelicState": {...}  // If segregation data available
            }
          }
        }
      ]
    }
  }
]
```

**Column Mappings (Priority Order):**

1. **PRIMARY SOURCE - Varsome column** (GA4GH compliant format):
   - Example: `HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)`
   - Parsed to extract:
     - Transcript: NM_000458.4
     - c.dot notation: c.406C>G
     - p.dot notation: p.Gln136Glu

2. **SECONDARY SOURCE - VariantReported column**:
   - Example: `c.406C>G, p.Gln136Glu`
   - Parsed for c. and p. notations

3. **TERTIARY SOURCE - hg38 column**:
   - Example: `chr17-37739578-G-C` (SNV)
   - Example: `chr17-36459258-T-<DEL>` (Deletion)
   - Used when Varsome not available

**Additional Variant Fields:**
- `VariantType` → Determines variant type (SNV, Deletion, Duplication, indel)
- `verdict_classification` → interpretationStatus mapping:
  - "Pathogenic" → "PATHOGENIC"
  - "Likely Pathogenic" → "LIKELY_PATHOGENIC"
  - "Uncertain significance" → "UNCERTAIN_SIGNIFICANCE"
  - "Likely Benign" → "LIKELY_BENIGN"
  - "Benign" → "BENIGN"
- `Segregation` → allelicState (e.g., "De novo" → heterozygous)
- `DetectionMethod` → Can be added to variant metadata

### 4. Diseases
```json
"diseases": [
  {
    "term": {
      "id": "MONDO:0018874",
      "label": "HNF1B-related disorder"
    },
    "onset": {
      "age": {"iso8601duration": "P21Y"}  // OR
      "ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}
    }
  }
]
```

**Mappings:**
- Primary disease: Always MONDO:0018874 (HNF1B-related disorder)
- If MODY column = "yes": Add MONDO:0010953 (MODY type 5)
- Onset: Uses `AgeOnset` column if available, otherwise defaults to congenital

### 5. Metadata
```json
"metaData": {
  "created": "timestamp",
  "createdBy": "HNF1B-DB Direct Migration",
  "resources": [...],  // HPO and MONDO ontology references
  "phenopacketSchemaVersion": "2.0.0",
  "externalReferences": [...]  // Publication references
}
```

**Column Mappings:**
- `Publication` → externalReferences (publication identifiers)
- `ReviewBy` → Could be added to submittedBy
- `ReviewDate` → Could be used for review metadata
- `Comment` → Could be stored in custom metadata field

## Variant Type Detection

The system detects variant types from multiple sources:

1. **VariantType column** (explicit):
   - "SNV" → Single Nucleotide Variant
   - "Deletion" → Deletion variant
   - "Duplication" → Duplication variant
   - "indel" → Insertion/Deletion

2. **hg38 notation patterns**:
   - `chr17-position-REF-ALT` → SNV (e.g., chr17-37739578-G-C)
   - `chr17-position-REF-<DEL>` → Deletion
   - `chr17-position-REF-<DUP>` → Duplication

3. **Varsome/VariantReported patterns**:
   - `c.###X>Y` → SNV (e.g., c.406C>G)
   - `c.###_###del` → Deletion (e.g., c.211_217del)
   - `c.###_###dup` → Duplication
   - `c.###_###insX` → Insertion

## Data Quality Notes

1. **Variant Information Availability**:
   - ~476 rows have Varsome data (GA4GH compliant)
   - Most deletions lack Varsome notation (use hg38 instead)
   - Some variants only have descriptive text in VariantReported

2. **Individual Identification**:
   - IndividualIdentifier provides meaningful IDs (e.g., study_patient format)
   - individual_id is numeric internal ID (1, 2, 3...)

3. **Multiple Reports per Individual**:
   - Some individuals have multiple rows (different reports/visits)
   - Phenotypes are aggregated across all reports for an individual
   - Variants are collected from all reports

## Example Data Flow

For Individual 52 (BellanneChantelot_04):
1. **Input**: Varsome = "HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)"
2. **Processing**: Parse to extract c.406C>G and p.Gln136Glu
3. **Output**: Creates HGVS expressions with proper transcript reference
4. **Classification**: verdict_classification "Likely Pathogenic" → "LIKELY_PATHOGENIC"
5. **Type**: VariantType "SNV" confirms single nucleotide variant