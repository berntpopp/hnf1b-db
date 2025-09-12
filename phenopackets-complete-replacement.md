# HNF1B-API Complete Phenopackets Restructuring Plan

This document outlines a complete replacement strategy for restructuring the HNF1B-API to use GA4GH Phenopackets v2 as the core data model, replacing the current PostgreSQL normalized structure.

## Executive Summary

**Goal**: Completely restructure HNF1B-API to use Phenopackets v2 as the primary data model, replacing the current multi-table PostgreSQL structure with a phenopacket-centric architecture.

**Approach**: Full migration from normalized relational model to document-oriented phenopackets structure with PostgreSQL JSONB storage for flexibility and performance.

**Key Changes**:
- Replace 13+ normalized tables with phenopacket-centric schema
- Store complete phenopackets as JSONB documents
- Maintain queryability through materialized views and indexes
- Transform Google Sheets directly into phenopackets format

## Architecture Transformation

### Current Architecture (To Be Replaced)
```
Google Sheets → Normalized PostgreSQL Tables → Custom JSON API
(13 tables with complex relationships)
```

### New Architecture
```
Google Sheets → Phenopackets Builder → PostgreSQL JSONB Storage → Phenopackets API
(3-4 core tables with rich JSONB documents)
```

## Phase 1: Complete Schema Redesign
*Estimated Time: 2 weeks*

### 1.1 New Database Schema (Complete Replacement)

```sql
-- Drop all existing tables (after backup)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

-- Core phenopackets storage
CREATE TABLE phenopackets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(10) DEFAULT '2.0',
    phenopacket JSONB NOT NULL,  -- Complete phenopacket document
    
    -- Denormalized fields for fast queries
    subject_id VARCHAR(100) GENERATED ALWAYS AS (phenopacket->'subject'->>'id') STORED,
    subject_sex VARCHAR(20) GENERATED ALWAYS AS (phenopacket->'subject'->>'sex') STORED,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    schema_version VARCHAR(20) DEFAULT '2.0.0',
    
    -- Indexing for search
    CONSTRAINT valid_phenopacket CHECK (jsonb_typeof(phenopacket) = 'object')
);

-- Family/Cohort relationships
CREATE TABLE families (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id VARCHAR(100) UNIQUE NOT NULL,
    family_phenopacket JSONB NOT NULL,  -- GA4GH Family message
    proband_id VARCHAR(100),
    pedigree JSONB,
    files JSONB DEFAULT '[]',
    meta_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cohorts for population studies
CREATE TABLE cohorts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id VARCHAR(100) UNIQUE NOT NULL,
    cohort_phenopacket JSONB NOT NULL,  -- GA4GH Cohort message
    description TEXT,
    members JSONB DEFAULT '[]',  -- Array of phenopacket_ids
    meta_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Resource metadata (for tracking data sources)
CREATE TABLE resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    namespace_prefix VARCHAR(50),
    url TEXT,
    version VARCHAR(50),
    iri_prefix TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create comprehensive indexes for phenopacket queries
CREATE INDEX idx_phenopacket_subject ON phenopackets USING GIN ((phenopacket->'subject'));
CREATE INDEX idx_phenopacket_features ON phenopackets USING GIN ((phenopacket->'phenotypicFeatures'));
CREATE INDEX idx_phenopacket_diseases ON phenopackets USING GIN ((phenopacket->'diseases'));
CREATE INDEX idx_phenopacket_variants ON phenopackets USING GIN ((phenopacket->'interpretations'));
CREATE INDEX idx_phenopacket_measurements ON phenopackets USING GIN ((phenopacket->'measurements'));
CREATE INDEX idx_phenopacket_subject_id ON phenopackets (subject_id);
CREATE INDEX idx_phenopacket_sex ON phenopackets (subject_sex);

-- Full text search index
CREATE INDEX idx_phenopacket_text_search ON phenopackets USING GIN (to_tsvector('english', phenopacket::text));
```

### 1.2 Phenopacket Document Structure

```json
{
  "id": "phenopacket:HNF1B:IND001",
  "subject": {
    "id": "IND001",
    "alternateIds": ["dup_check_id", "original_identifier"],
    "timeAtLastEncounter": {
      "age": {
        "iso8601duration": "P25Y"
      }
    },
    "sex": "FEMALE",
    "karyotypicSex": "XX",
    "taxonomy": {
      "id": "NCBITaxon:9606",
      "label": "Homo sapiens"
    }
  },
  "phenotypicFeatures": [
    {
      "type": {
        "id": "HP:0012622",
        "label": "Chronic kidney disease"
      },
      "severity": {
        "id": "HP:0012825",
        "label": "Mild"
      },
      "modifiers": [{
        "id": "HP:0012824",
        "label": "Stage 3"
      }],
      "onset": {
        "age": {
          "iso8601duration": "P15Y"
        }
      },
      "evidence": [{
        "evidenceCode": {
          "id": "ECO:0000033",
          "label": "author statement supported by traceable reference"
        },
        "reference": {
          "id": "PMID:12345678"
        }
      }]
    },
    {
      "type": {
        "id": "HP:0100611",
        "label": "Multiple glomerular cysts"
      },
      "excluded": false
    },
    {
      "type": {
        "id": "HP:0000078",
        "label": "Genital abnormality"
      },
      "modifiers": [{
        "id": "HP:0000079",
        "label": "Abnormality of the urinary system"
      }]
    }
  ],
  "measurements": [
    {
      "assay": {
        "id": "LOINC:33914-3",
        "label": "eGFR"
      },
      "value": {
        "quantity": {
          "unit": {
            "id": "UCUM:mL/min/{1.73_m2}",
            "label": "mL/min/1.73m²"
          },
          "value": 45.0
        }
      },
      "timeObserved": {
        "timestamp": "2024-01-15T10:00:00Z"
      }
    },
    {
      "assay": {
        "id": "LOINC:2601-3",
        "label": "Magnesium [Mass/volume] in Serum or Plasma"
      },
      "value": {
        "quantity": {
          "unit": {
            "id": "UCUM:mg/dL",
            "label": "mg/dL"
          },
          "value": 1.2
        }
      },
      "interpretation": {
        "id": "HP:0002917",
        "label": "Hypomagnesemia"
      }
    }
  ],
  "diseases": [
    {
      "term": {
        "id": "MONDO:0018874",
        "label": "HNF1B-related autosomal dominant tubulointerstitial kidney disease"
      },
      "onset": {
        "age": {
          "iso8601duration": "P10Y"
        }
      },
      "diseaseStage": [{
        "id": "HP:0012625",
        "label": "Stage 3 chronic kidney disease"
      }]
    },
    {
      "term": {
        "id": "MONDO:0005147",
        "label": "Type 2 diabetes mellitus"
      },
      "onset": {
        "age": {
          "iso8601duration": "P20Y"
        }
      }
    }
  ],
  "interpretations": [
    {
      "id": "interpretation-001",
      "progressStatus": "COMPLETED",
      "diagnosis": {
        "disease": {
          "id": "OMIM:137920",
          "label": "HNF1B-related disease"
        },
        "genomicInterpretations": [{
          "subjectOrBiosampleId": "IND001",
          "interpretationStatus": "PATHOGENIC",
          "variantInterpretation": {
            "acmgPathogenicityClassification": "PATHOGENIC",
            "therapeuticActionability": "UNKNOWN_ACTIONABILITY",
            "variationDescriptor": {
              "id": "var:HNF1B:c.544C>T",
              "variation": {
                "allele": {
                  "sequenceLocation": {
                    "sequenceId": "NM_000458.4",
                    "sequenceInterval": {
                      "startNumber": {
                        "value": 544
                      },
                      "endNumber": {
                        "value": 545
                      }
                    }
                  },
                  "literalSequenceExpression": {
                    "sequence": "T"
                  }
                }
              },
              "label": "HNF1B:c.544C>T (p.Arg182*)",
              "geneContext": {
                "valueId": "HGNC:11630",
                "symbol": "HNF1B"
              },
              "moleculeContext": "TRANSCRIPT",
              "allelicState": {
                "id": "GENO:0000135",
                "label": "heterozygous"
              }
            }
          }
        }]
      }
    }
  ],
  "medicalActions": [
    {
      "treatment": {
        "agent": {
          "id": "CHEBI:6801",
          "label": "Metformin"
        },
        "doseIntervals": [{
          "quantity": {
            "unit": {
              "id": "UCUM:mg",
              "label": "milligram"
            },
            "value": 500
          },
          "scheduleFrequency": {
            "id": "PATO:0000689",
            "label": "twice daily"
          }
        }]
      },
      "treatmentTarget": {
        "id": "MONDO:0005147",
        "label": "Type 2 diabetes mellitus"
      },
      "treatmentIntent": {
        "id": "HP:0033296",
        "label": "Glycemic control"
      }
    },
    {
      "procedure": {
        "code": {
          "id": "NCIT:C157952",
          "label": "Kidney Transplantation"
        },
        "performed": {
          "timestamp": "2023-06-15T00:00:00Z"
        }
      }
    }
  ],
  "files": [
    {
      "uri": "file:///data/vcf/IND001.vcf",
      "individualToFileIdentifiers": {
        "IND001": "sample_001"
      },
      "fileAttributes": {
        "fileFormat": "VCF",
        "genomeAssembly": "GRCh38"
      }
    }
  ],
  "metaData": {
    "created": "2024-01-01T00:00:00Z",
    "createdBy": "HNF1B-API",
    "submittedBy": "User123",
    "resources": [
      {
        "id": "hpo",
        "name": "Human Phenotype Ontology",
        "namespacePrefix": "HP",
        "url": "https://hpo.jax.org",
        "version": "2024-01-01",
        "iriPrefix": "http://purl.obolibrary.org/obo/HP_"
      },
      {
        "id": "mondo",
        "name": "Mondo Disease Ontology",
        "namespacePrefix": "MONDO",
        "url": "https://mondo.monarchinitiative.org",
        "version": "2024-01-01",
        "iriPrefix": "http://purl.obolibrary.org/obo/MONDO_"
      }
    ],
    "phenopacketSchemaVersion": "2.0.0",
    "externalReferences": [
      {
        "id": "PMID:12345678",
        "reference": "Publication reference",
        "description": "Original case report"
      }
    ]
  }
}
```

## Phase 2: Data Migration Strategy
*Estimated Time: 3 weeks*

### 2.1 Complete Data Transformation Pipeline

```python
# migration/phenopackets_complete_migration.py

from typing import Dict, List, Any
import pandas as pd
from datetime import datetime
import json

class CompletePhenopacketsMigration:
    """Complete migration from normalized PostgreSQL to Phenopackets."""
    
    def __init__(self):
        self.phenotype_mappings = self._load_phenotype_mappings()
        self.disease_mappings = self._load_disease_mappings()
        
    async def migrate_all_data(self, source_db, target_db):
        """Complete migration from old structure to phenopackets."""
        
        # Step 1: Backup existing database
        await self.backup_existing_database(source_db)
        
        # Step 2: Extract all data from normalized tables
        data = await self.extract_all_normalized_data(source_db)
        
        # Step 3: Transform to phenopackets
        phenopackets = self.transform_to_phenopackets(data)
        
        # Step 4: Validate phenopackets
        validated = self.validate_phenopackets(phenopackets)
        
        # Step 5: Store in new structure
        await self.store_phenopackets(target_db, validated)
        
        # Step 6: Verify migration
        await self.verify_migration(source_db, target_db)
    
    def transform_to_phenopackets(self, data: Dict) -> List[Dict]:
        """Transform normalized data to phenopackets format."""
        
        phenopackets = []
        
        for individual in data['individuals']:
            # Get related data
            reports = [r for r in data['reports'] 
                      if r['individual_id'] == individual['id']]
            variants = [v for v in data['variants'] 
                       if v['individual_id'] == individual['id']]
            
            # Build phenopacket
            phenopacket = {
                "id": f"phenopacket:HNF1B:{individual['individual_id']}",
                "subject": self._build_subject(individual, reports),
                "phenotypicFeatures": self._build_phenotypic_features(reports),
                "measurements": self._build_measurements(reports),
                "diseases": self._build_diseases(reports),
                "interpretations": self._build_interpretations(variants),
                "medicalActions": self._build_medical_actions(reports),
                "files": self._build_files(individual),
                "metaData": self._build_metadata(individual, reports)
            }
            
            phenopackets.append(phenopacket)
        
        return phenopackets
    
    def _build_phenotypic_features(self, reports: List[Dict]) -> List[Dict]:
        """Convert existing phenotypes to phenopacket features."""
        
        features = []
        
        for report in reports:
            phenotypes = report.get('phenotypes', {})
            
            # Convert renal insufficiency
            if 'renalInsufficiency' in phenotypes:
                renal = phenotypes['renalInsufficiency']
                feature = {
                    "type": {
                        "id": renal.get('phenotype_id', 'HP:0012622'),
                        "label": renal.get('name', 'Chronic kidney disease')
                    }
                }
                
                # Add stage as modifier
                if 'stage' in renal.get('described', ''):
                    stage_num = renal['described'].split()[-1]
                    feature['modifiers'] = [{
                        "id": f"HP:0012{623 + int(stage_num) - 1}",
                        "label": f"Stage {stage_num} chronic kidney disease"
                    }]
                
                features.append(feature)
            
            # Convert kidney biopsy findings
            if 'kidneyBiopsy' in phenotypes:
                for hpo_id, details in phenotypes['kidneyBiopsy'].items():
                    features.append({
                        "type": {
                            "id": details['phenotype_id'],
                            "label": details['name']
                        },
                        "excluded": details.get('described') == 'no'
                    })
            
            # Convert genital tract abnormalities
            if 'genitalTractAbnormalities' in phenotypes:
                genital = phenotypes['genitalTractAbnormalities']
                if genital.get('described') not in ['no', 'not reported']:
                    features.append({
                        "type": {
                            "id": "HP:0000078",
                            "label": "Genital abnormality"
                        },
                        "modifiers": self._parse_genital_modifiers(genital)
                    })
            
            # Convert diabetes
            if 'diabetes' in phenotypes:
                diabetes = phenotypes['diabetes']
                if diabetes.get('described') not in ['no', 'not reported']:
                    # Note: Diabetes goes in diseases section, not features
                    pass
            
            # Convert hypomagnesemia
            if 'hypomagnesemia' in phenotypes:
                hypo = phenotypes['hypomagnesemia']
                if hypo.get('described') == 'yes':
                    features.append({
                        "type": {
                            "id": "HP:0002917",
                            "label": "Hypomagnesemia"
                        }
                    })
            
            # Add all other phenotypes
            for key, value in phenotypes.items():
                if key not in ['renalInsufficiency', 'kidneyBiopsy', 
                              'genitalTractAbnormalities', 'diabetes', 
                              'hypomagnesemia']:
                    if isinstance(value, dict) and 'phenotype_id' in value:
                        features.append({
                            "type": {
                                "id": value['phenotype_id'],
                                "label": value.get('name', key)
                            },
                            "excluded": value.get('described') == 'no'
                        })
        
        return features
    
    def _build_diseases(self, reports: List[Dict]) -> List[Dict]:
        """Build disease entries from reports."""
        
        diseases = []
        
        for report in reports:
            phenotypes = report.get('phenotypes', {})
            
            # Add HNF1B disease as primary
            diseases.append({
                "term": {
                    "id": "MONDO:0018874",
                    "label": "HNF1B-related autosomal dominant tubulointerstitial kidney disease"
                },
                "onset": self._parse_onset(report.get('age_onset'))
            })
            
            # Add diabetes if present
            if 'diabetes' in phenotypes:
                diabetes = phenotypes['diabetes']
                if diabetes.get('described') not in ['no', 'not reported']:
                    diabetes_type = self._determine_diabetes_type(diabetes)
                    diseases.append({
                        "term": {
                            "id": diabetes_type['id'],
                            "label": diabetes_type['label']
                        },
                        "onset": self._parse_onset(diabetes.get('age_onset'))
                    })
        
        return diseases
    
    def _build_measurements(self, reports: List[Dict]) -> List[Dict]:
        """Extract and convert measurements."""
        
        measurements = []
        
        for report in reports:
            # Extract eGFR if available
            if 'egfr' in report:
                measurements.append({
                    "assay": {
                        "id": "LOINC:33914-3",
                        "label": "Glomerular filtration rate"
                    },
                    "value": {
                        "quantity": {
                            "unit": {
                                "id": "UCUM:mL/min/{1.73_m2}",
                                "label": "mL/min/1.73m²"
                            },
                            "value": float(report['egfr'])
                        }
                    },
                    "timeObserved": {
                        "timestamp": report.get('report_date', datetime.now().isoformat())
                    }
                })
            
            # Extract magnesium levels if hypomagnesemia
            phenotypes = report.get('phenotypes', {})
            if 'hypomagnesemia' in phenotypes:
                if phenotypes['hypomagnesemia'].get('described') == 'yes':
                    measurements.append({
                        "assay": {
                            "id": "LOINC:2601-3",
                            "label": "Magnesium [Mass/volume] in Serum or Plasma"
                        },
                        "interpretation": {
                            "id": "HP:0002917",
                            "label": "Hypomagnesemia"
                        }
                    })
        
        return measurements
```

### 2.2 Google Sheets Direct to Phenopackets

```python
# migration/sheets_to_phenopackets_direct.py

class SheetsToPhenopacketsDirect:
    """Direct conversion from Google Sheets to Phenopackets."""
    
    async def import_from_sheets(self, sheets_service):
        """Import directly from sheets to phenopackets format."""
        
        # Fetch all sheets
        individuals_df = await self.fetch_sheet(sheets_service, "Individuals")
        reports_df = await self.fetch_sheet(sheets_service, "Reports")
        phenotypes_df = await self.fetch_sheet(sheets_service, "Phenotypes")
        variants_df = await self.fetch_sheet(sheets_service, "Variants")
        publications_df = await self.fetch_sheet(sheets_service, "Publications")
        
        # Build phenopackets directly
        phenopackets = []
        
        for _, individual in individuals_df.iterrows():
            # Get related data
            ind_reports = reports_df[reports_df['individual_id'] == individual['individual_id']]
            ind_phenotypes = phenotypes_df[phenotypes_df['individual_id'] == individual['individual_id']]
            ind_variants = variants_df[variants_df['individual_id'] == individual['individual_id']]
            
            # Build phenopacket
            phenopacket = self._build_phenopacket_from_sheets(
                individual, ind_reports, ind_phenotypes, ind_variants
            )
            
            phenopackets.append(phenopacket)
        
        # Store phenopackets
        await self.store_phenopackets(phenopackets)
        
        return phenopackets
    
    def _build_phenopacket_from_sheets(self, individual, reports, phenotypes, variants):
        """Build a complete phenopacket from sheet data."""
        
        phenopacket = {
            "id": f"phenopacket:HNF1B:{individual['individual_id']}",
            "subject": {
                "id": individual['individual_id'],
                "sex": self._map_sex(individual.get('sex')),
                "alternateIds": [
                    individual.get('dup_check'),
                    individual.get('individual_identifier')
                ] if individual.get('dup_check') else []
            },
            "phenotypicFeatures": [],
            "measurements": [],
            "diseases": [],
            "interpretations": [],
            "metaData": self._create_metadata()
        }
        
        # Process each report
        for _, report in reports.iterrows():
            # Add age at report
            if pd.notna(report.get('age_reported')):
                phenopacket['subject']['timeAtLastEncounter'] = {
                    "age": self._parse_age_to_iso8601(report['age_reported'])
                }
            
            # Process phenotypes for this report
            report_phenotypes = phenotypes[phenotypes['report_id'] == report['report_id']]
            
            for _, phenotype in report_phenotypes.iterrows():
                feature = self._convert_phenotype_row_to_feature(phenotype)
                if feature:
                    phenopacket['phenotypicFeatures'].append(feature)
        
        # Process variants
        for _, variant in variants.iterrows():
            interpretation = self._convert_variant_to_interpretation(variant)
            if interpretation:
                phenopacket['interpretations'].append(interpretation)
        
        return phenopacket
```

## Phase 3: API Complete Redesign
*Estimated Time: 2 weeks*

### 3.1 New API Structure

```python
# app/main.py - Completely new structure

from fastapi import FastAPI
from app.endpoints import phenopackets, search, export

app = FastAPI(
    title="HNF1B Phenopackets API",
    description="GA4GH Phenopackets v2 compliant API for HNF1B disease data",
    version="2.0.0"
)

# New phenopacket-centric endpoints
app.include_router(phenopackets.router, prefix="/api/v2")
app.include_router(search.router, prefix="/api/v2")
app.include_router(export.router, prefix="/api/v2")
```

### 3.2 New Endpoint Structure

```python
# app/endpoints/phenopackets.py

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict
import json

router = APIRouter(tags=["phenopackets"])

@router.get("/phenopackets")
async def list_phenopackets(
    skip: int = 0,
    limit: int = 100,
    sex: Optional[str] = None,
    has_variants: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all phenopackets with filtering."""
    
    query = select(Phenopacket)
    
    if sex:
        query = query.where(Phenopacket.subject_sex == sex)
    
    if has_variants is not None:
        if has_variants:
            query = query.where(
                func.jsonb_array_length(Phenopacket.phenopacket['interpretations']) > 0
            )
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

@router.get("/phenopackets/{phenopacket_id}")
async def get_phenopacket(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a single phenopacket by ID."""
    
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    phenopacket = result.scalar_one_or_none()
    
    if not phenopacket:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    
    return phenopacket.phenopacket

@router.post("/phenopackets/search")
async def search_phenopackets(
    search_query: PhenopacketSearchQuery,
    db: AsyncSession = Depends(get_db)
):
    """Advanced search across phenopackets."""
    
    base_query = select(Phenopacket)
    
    # Search by phenotypes (HPO terms)
    if search_query.phenotypes:
        for hpo_term in search_query.phenotypes:
            base_query = base_query.where(
                Phenopacket.phenopacket['phenotypicFeatures'].contains(
                    [{"type": {"id": hpo_term}}]
                )
            )
    
    # Search by diseases (MONDO terms)
    if search_query.diseases:
        for disease_term in search_query.diseases:
            base_query = base_query.where(
                Phenopacket.phenopacket['diseases'].contains(
                    [{"term": {"id": disease_term}}]
                )
            )
    
    # Search by variants
    if search_query.variants:
        for variant in search_query.variants:
            base_query = base_query.where(
                Phenopacket.phenopacket['interpretations'].contains(
                    [{"diagnosis": {"genomicInterpretations": [
                        {"variantInterpretation": {"variationDescriptor": {"label": variant}}}
                    ]}}]
                )
            )
    
    # Search by measurements
    if search_query.measurements:
        for measurement in search_query.measurements:
            base_query = base_query.where(
                Phenopacket.phenopacket['measurements'].contains(
                    [{"assay": {"id": measurement['loinc_code']}}]
                )
            )
    
    result = await db.execute(base_query)
    return result.scalars().all()

@router.get("/phenopackets/{phenopacket_id}/features")
async def get_phenotypic_features(
    phenopacket_id: str,
    group: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get phenotypic features from a phenopacket."""
    
    result = await db.execute(
        select(Phenopacket.phenopacket['phenotypicFeatures']).where(
            Phenopacket.phenopacket_id == phenopacket_id
        )
    )
    features = result.scalar_one_or_none()
    
    if not features:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    
    # Filter by group if specified (requires group mapping)
    if group:
        features = [f for f in features if self._get_feature_group(f) == group]
    
    return features

@router.get("/phenopackets/aggregate/by-feature")
async def aggregate_by_feature(
    db: AsyncSession = Depends(get_db)
):
    """Aggregate phenopackets by phenotypic features."""
    
    query = """
    SELECT 
        feature->>'type' as hpo_term,
        COUNT(*) as count
    FROM 
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
    WHERE 
        NOT (feature->>'excluded')::boolean
    GROUP BY 
        feature->>'type'
    ORDER BY 
        count DESC
    """
    
    result = await db.execute(text(query))
    return result.fetchall()

@router.get("/phenopackets/aggregate/kidney-stages")
async def aggregate_kidney_stages(
    db: AsyncSession = Depends(get_db)
):
    """Get distribution of kidney disease stages."""
    
    query = """
    SELECT 
        modifier->>'label' as stage,
        COUNT(*) as count
    FROM 
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature,
        jsonb_array_elements(feature->'modifiers') as modifier
    WHERE 
        feature->'type'->>'id' LIKE 'HP:0012%'
        AND modifier->>'label' LIKE '%Stage%'
    GROUP BY 
        modifier->>'label'
    ORDER BY 
        stage
    """
    
    result = await db.execute(text(query))
    return result.fetchall()

@router.post("/phenopackets")
async def create_phenopacket(
    phenopacket: Dict,
    db: AsyncSession = Depends(get_db)
):
    """Create a new phenopacket."""
    
    # Validate phenopacket structure
    validator = PhenopacketValidator()
    errors = validator.validate(phenopacket)
    
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    
    # Store phenopacket
    new_phenopacket = Phenopacket(
        phenopacket_id=phenopacket['id'],
        phenopacket=phenopacket
    )
    
    db.add(new_phenopacket)
    await db.commit()
    
    return new_phenopacket

@router.put("/phenopackets/{phenopacket_id}")
async def update_phenopacket(
    phenopacket_id: str,
    phenopacket: Dict,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing phenopacket."""
    
    result = await db.execute(
        select(Phenopacket).where(Phenopacket.phenopacket_id == phenopacket_id)
    )
    existing = result.scalar_one_or_none()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Phenopacket not found")
    
    # Validate updated phenopacket
    validator = PhenopacketValidator()
    errors = validator.validate(phenopacket)
    
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    
    # Update
    existing.phenopacket = phenopacket
    existing.updated_at = datetime.now()
    
    await db.commit()
    
    return existing
```

### 3.3 Feature-Specific Query Endpoints

```python
# app/endpoints/clinical_features.py

@router.get("/clinical/renal-insufficiency")
async def get_renal_insufficiency_cases(
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all cases with renal insufficiency, optionally filtered by stage."""
    
    query = """
    SELECT 
        phenopacket_id,
        phenopacket->'subject'->>'id' as subject_id,
        feature,
        modifier->>'label' as stage
    FROM 
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature,
        jsonb_array_elements(feature->'modifiers') as modifier
    WHERE 
        feature->'type'->>'id' IN ('HP:0012622', 'HP:0012623', 'HP:0012624', 
                                   'HP:0012625', 'HP:0012626', 'HP:0003774')
    """
    
    if stage:
        query += f" AND modifier->>'label' LIKE '%{stage}%'"
    
    result = await db.execute(text(query))
    return result.fetchall()

@router.get("/clinical/genital-abnormalities")
async def get_genital_abnormalities(
    db: AsyncSession = Depends(get_db)
):
    """Get all cases with genital tract abnormalities."""
    
    query = """
    SELECT 
        phenopacket_id,
        phenopacket->'subject' as subject,
        feature
    FROM 
        phenopackets,
        jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
    WHERE 
        feature->'type'->>'id' IN ('HP:0000078', 'HP:0000079', 'HP:0000080')
        AND NOT (feature->>'excluded')::boolean
    """
    
    result = await db.execute(text(query))
    return result.fetchall()

@router.get("/clinical/diabetes")
async def get_diabetes_cases(
    diabetes_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all cases with diabetes."""
    
    query = """
    SELECT 
        phenopacket_id,
        phenopacket->'subject' as subject,
        disease
    FROM 
        phenopackets,
        jsonb_array_elements(phenopacket->'diseases') as disease
    WHERE 
        disease->'term'->>'label' LIKE '%diabetes%'
    """
    
    if diabetes_type:
        query += f" AND disease->'term'->>'label' LIKE '%{diabetes_type}%'"
    
    result = await db.execute(text(query))
    return result.fetchall()

@router.get("/clinical/hypomagnesemia")
async def get_hypomagnesemia_cases(
    db: AsyncSession = Depends(get_db)
):
    """Get all cases with hypomagnesemia."""
    
    query = """
    SELECT 
        phenopacket_id,
        phenopacket->'subject' as subject,
        measurement
    FROM 
        phenopackets,
        jsonb_array_elements(phenopacket->'measurements') as measurement
    WHERE 
        measurement->'interpretation'->>'id' = 'HP:0002917'
        OR measurement->'assay'->>'id' = 'LOINC:2601-3'
    """
    
    result = await db.execute(text(query))
    return result.fetchall()
```

## Phase 4: Testing & Validation
*Estimated Time: 1 week*

### 4.1 Migration Validation

```python
# tests/test_complete_migration.py

class TestCompleteMigration:
    """Test complete migration to phenopackets."""
    
    async def test_all_individuals_migrated(self):
        """Ensure all individuals are represented in phenopackets."""
        
        # Count original individuals
        original_count = await count_original_individuals()
        
        # Count phenopackets
        phenopacket_count = await count_phenopackets()
        
        assert phenopacket_count >= original_count
    
    async def test_feature_preservation(self):
        """Ensure all clinical features are preserved."""
        
        test_cases = [
            ("IND001", "renalInsufficiency", "HP:0012622"),
            ("IND002", "genitalTractAbnormalities", "HP:0000078"),
            ("IND003", "diabetes", "MONDO:0005147"),
            ("IND004", "hypomagnesemia", "HP:0002917")
        ]
        
        for individual_id, feature_name, expected_term in test_cases:
            phenopacket = await get_phenopacket(individual_id)
            
            if feature_name in ["renalInsufficiency", "genitalTractAbnormalities", "hypomagnesemia"]:
                # Check in phenotypicFeatures
                features = phenopacket['phenotypicFeatures']
                assert any(f['type']['id'] == expected_term for f in features)
            
            elif feature_name == "diabetes":
                # Check in diseases
                diseases = phenopacket['diseases']
                assert any(d['term']['id'] == expected_term for d in diseases)
    
    async def test_variant_preservation(self):
        """Ensure all variants are preserved in interpretations."""
        
        original_variants = await get_original_variants()
        
        for variant in original_variants:
            phenopacket = await get_phenopacket_for_individual(variant['individual_id'])
            interpretations = phenopacket['interpretations']
            
            # Check variant is present
            variant_found = False
            for interp in interpretations:
                for gi in interp['diagnosis']['genomicInterpretations']:
                    if variant['c_dot'] in gi['variantInterpretation']['variationDescriptor']['label']:
                        variant_found = True
                        break
            
            assert variant_found, f"Variant {variant['c_dot']} not found"
```

## Phase 5: Deployment Strategy
*Estimated Time: 1 week*

### 5.1 Complete Cutover Plan

```bash
# deployment/cutover.sh

#!/bin/bash

# Complete cutover to phenopackets structure

echo "Starting complete migration to Phenopackets..."

# 1. Backup current database
pg_dump $OLD_DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Create new database
createdb $NEW_DATABASE_NAME

# 3. Apply new schema
psql $NEW_DATABASE_URL < phenopackets_schema.sql

# 4. Run migration
python migration/phenopackets_complete_migration.py \
    --source $OLD_DATABASE_URL \
    --target $NEW_DATABASE_URL \
    --validate

# 5. Run verification tests
pytest tests/test_complete_migration.py

# 6. Update application configuration
sed -i 's/DATABASE_URL=.*/DATABASE_URL='$NEW_DATABASE_URL'/' .env

# 7. Deploy new API version
docker build -t hnf1b-api:v2.0.0 .
docker stop hnf1b-api-v1
docker run -d --name hnf1b-api-v2 hnf1b-api:v2.0.0

echo "Migration complete!"
```

### 5.2 Rollback Plan (Emergency Only)

```bash
# deployment/rollback.sh

#!/bin/bash

# Emergency rollback to original structure

echo "EMERGENCY: Rolling back to original structure..."

# 1. Stop new API
docker stop hnf1b-api-v2

# 2. Restore original database
psql $OLD_DATABASE_URL < backup_latest.sql

# 3. Restart original API
docker start hnf1b-api-v1

# 4. Alert team
send_alert "Rollback executed - investigate issues"

echo "Rollback complete - original system restored"
```

## Timeline & Milestones

| Phase | Duration | Key Deliverables |
|-------|----------|-----------------|
| Phase 1: Schema Redesign | 2 weeks | New phenopackets database schema |
| Phase 2: Data Migration | 3 weeks | Complete data transformation pipeline |
| Phase 3: API Redesign | 2 weeks | New phenopackets-centric API |
| Phase 4: Testing | 1 week | Validation of migration and features |
| Phase 5: Deployment | 1 week | Production cutover |

**Total Timeline**: 9 weeks

## Key Differences from Addition Approach

1. **Complete Replacement**: Old tables are dropped, not maintained
2. **Single Source of Truth**: Phenopackets become the only data model
3. **No Backward Compatibility**: API consumers must migrate to new format
4. **Simpler Architecture**: No dual systems or synchronization needed
5. **Document-Oriented**: JSONB storage instead of normalized tables

## Benefits of Complete Replacement

1. **Clean Architecture**: No legacy code or dual maintenance
2. **Full Standards Compliance**: Pure phenopackets implementation
3. **Better Performance**: Optimized for phenopackets queries
4. **Simpler Codebase**: One data model, one API structure
5. **Future-Proof**: Fully aligned with GA4GH standards

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| API Breaking Changes | High | Provide migration guide and tools |
| Data Loss | Critical | Comprehensive backup and validation |
| Performance Issues | Medium | Extensive testing and optimization |
| User Disruption | High | Clear communication and training |
| Integration Failures | Medium | Phased rollout with monitoring |

## Success Criteria

1. **100% Data Migration**: All data successfully transformed
2. **Feature Parity**: All current features available in new format
3. **Performance**: Equal or better query performance
4. **Standards Compliance**: Full GA4GH Phenopackets v2 compliance
5. **Zero Data Loss**: Complete data preservation verified

## Installation Requirements

### System Requirements

#### Core Infrastructure

1. **PostgreSQL 15+** (Required for advanced JSONB features)
   ```bash
   docker pull postgres:15-alpine
   # Or: sudo apt-get install postgresql-15 postgresql-contrib-15
   ```

2. **Python 3.10+** (Modern async support and type hints)
   ```bash
   python --version  # Should be 3.10 or higher
   ```

3. **UV Package Manager** (Already in project)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Python Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # Phenopackets specific
    "phenopackets>=2.0.0",  # GA4GH Phenopackets Python library
    "ga4gh-vrs>=2.0.0",  # Variation Representation Specification
    "ga4gh-vrsatile>=0.2.0",  # VRS Annotation and Terminology
    "protobuf>=4.25.0",  # For phenopackets serialization
    "jsonschema>=4.20.0",  # For phenopacket validation
    
    # Ontology handling
    "pronto>=2.5.0",  # For parsing OBO ontologies (HPO, MONDO)
    "oaklib>=0.5.0",  # Ontology Access Kit for term lookup
    
    # Data transformation
    "jsonpath-ng>=1.6.0",  # For complex JSON queries
    "deepdiff>=6.7.0",  # For comparing phenopackets during migration
    
    # Enhanced PostgreSQL JSONB support
    "sqlalchemy[asyncpg]>=2.0.0",  # Already present
    "asyncpg>=0.29.0",  # PostgreSQL async driver
]

[project.optional-dependencies]
migration = [
    "pandas>=2.0.0",  # Data manipulation
    "tqdm>=4.66.0",  # Progress bars
    "rich>=13.7.0",  # Better console output
]
```

### External Services & APIs

1. **Ontology Services**
   - **HPO (Human Phenotype Ontology)**: Download ~50MB OBO file
   - **MONDO Disease Ontology**: Download ~100MB OBO file
   - **LOINC**: Registration required for lab codes

   ```bash
   # Download ontologies
   mkdir -p data/ontologies
   wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo
   wget https://github.com/monarch-initiative/mondo/releases/latest/download/mondo.obo
   ```

2. **Genomic Services**
   - **Ensembl REST API**: No installation, rate limit 15 req/sec
   - **VEP**: Optional local installation for bulk processing

3. **Literature Services**
   - **PubMed/NCBI**: API key recommended (add to .env)

### Database Extensions

```sql
-- Required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- Cryptographic functions
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- GIN index support
```

### Environment Configuration

Create `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets
OLD_DATABASE_URL=postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db

# API Configuration
JWT_SECRET=your-secret-key-here
PHENOPACKET_SCHEMA_VERSION=2.0.0

# External Services
NCBI_API_KEY=optional_but_recommended
ENSEMBL_API_URL=https://rest.ensembl.org

# Ontology Paths
HPO_OBO_PATH=/data/ontologies/hp.obo
MONDO_OBO_PATH=/data/ontologies/mondo.obo

# Migration Settings
MIGRATION_BATCH_SIZE=1000
VALIDATE_PHENOPACKETS=true
```

### Storage & Memory Requirements

- **Disk Space**: ~6GB recommended
  - Database: ~3GB during migration
  - Ontologies: ~350MB
  - Backups: ~2GB
  
- **Memory**: 8GB minimum, 16GB recommended
  - PostgreSQL: 2-4GB
  - Application: 1-2GB
  - Migration: 4GB

### Quick Installation

```bash
# 1. Install dependencies
uv sync --all-extras

# 2. Download ontologies
mkdir -p data/ontologies && cd data/ontologies
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo
wget https://github.com/monarch-initiative/mondo/releases/latest/download/mondo.obo
cd ../..

# 3. Setup PostgreSQL
sudo -u postgres psql <<EOF
CREATE USER hnf1b_user WITH PASSWORD 'hnf1b_pass';
CREATE DATABASE hnf1b_phenopackets OWNER hnf1b_user;
EOF

# 4. Apply extensions and schema
psql -U hnf1b_user -d hnf1b_phenopackets < migration/phenopackets_schema.sql

# 5. Verify installation
python check_requirements.py
```

### Docker Alternative

```yaml
# docker-compose.phenopackets.yml
version: '3.8'
services:
  postgres-phenopackets:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: hnf1b_phenopackets
      POSTGRES_USER: hnf1b_user
      POSTGRES_PASSWORD: hnf1b_pass
    volumes:
      - ./migration/phenopackets_schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    ports:
      - "5434:5432"
```

## Conclusion

This complete replacement approach provides a clean break from the legacy structure and fully embraces the phenopackets standard. While more disruptive than an addition approach, it results in a simpler, more maintainable system that is fully aligned with international standards for clinical and genomic data exchange.