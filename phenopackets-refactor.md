# HNF1B-API Phenopackets Integration Plan

This document outlines a comprehensive plan for refactoring the HNF1B-API database to incorporate GA4GH Phenopackets v2 standard while maintaining compatibility with the existing Google Sheets data source and preserving all current functionality.

## Executive Summary

**Goal**: Refactor the HNF1B-API to use Phenopackets v2 standard for clinical and phenotypic data representation while maintaining current functionality and Google Sheets as the primary data source.

**Key Benefits**:
- **Standards Compliance**: Adopt GA4GH international standard for phenotypic data
- **Interoperability**: Enable data exchange with other phenopacket-compliant systems
- **Rich Data Model**: Support for measurements, time series, and complex clinical relationships
- **Future-Proof**: Align with global genomics and health data standards
- **Maintain Compatibility**: Keep existing features and data sources intact

## Current State Analysis

### Existing Architecture
- **Data Source**: Google Sheets containing clinical, genetic, and publication data
- **Database**: PostgreSQL with normalized tables and JSONB fields for complex data
- **Phenotype Storage**: JSONB field in reports table with custom structure
- **API**: FastAPI endpoints serving data in custom JSON format
- **Features**: Renal insufficiency, genital tract abnormalities, diabetes, etc.

### Current Phenotype Structure
```json
{
  "renalInsufficiency": {
    "phenotype_id": "HP:0012622",
    "name": "chronic kidney disease, not specified",
    "group": "Kidney",
    "described": "stage 3"
  },
  "kidneyBiopsy": {
    "HP:0100611": {
      "phenotype_id": "HP:0100611",
      "name": "Multiple glomerular cysts",
      "described": "yes"
    }
  }
}
```

## Phenopackets v2 Integration Strategy

### Phase 1: Schema Design & Data Model Extension
*Estimated Time: 1-2 weeks*

#### 1.1 Database Schema Updates

```sql
-- Core Phenopackets table (main container)
CREATE TABLE phenopackets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id VARCHAR(50) UNIQUE NOT NULL,
    subject JSONB NOT NULL,  -- Individual or Biosample reference
    phenotypic_features JSONB DEFAULT '[]',
    measurements JSONB DEFAULT '[]',
    biosamples JSONB DEFAULT '[]',
    interpretations JSONB DEFAULT '[]',
    diseases JSONB DEFAULT '[]',
    medical_actions JSONB DEFAULT '[]',
    files JSONB DEFAULT '[]',
    meta_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Link phenopackets to existing individuals
CREATE TABLE individual_phenopackets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id UUID NOT NULL REFERENCES individuals(id) ON DELETE CASCADE,
    phenopacket_id UUID NOT NULL REFERENCES phenopackets(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(individual_id, phenopacket_id)
);

-- Phenotypic features normalized table (for efficient querying)
CREATE TABLE phenotypic_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id UUID NOT NULL REFERENCES phenopackets(id) ON DELETE CASCADE,
    type_ontology_class JSONB NOT NULL,  -- HPO term
    excluded BOOLEAN DEFAULT FALSE,
    severity JSONB,
    modifiers JSONB DEFAULT '[]',
    onset JSONB,
    resolution JSONB,
    evidence JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Measurements table (lab values, clinical measurements)
CREATE TABLE measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id UUID NOT NULL REFERENCES phenopackets(id) ON DELETE CASCADE,
    assay JSONB NOT NULL,
    value JSONB NOT NULL,  -- Can be quantity, ontology class, or categorical
    complex_value JSONB,
    time_observed JSONB,
    procedure JSONB,
    reference_range JSONB,
    interpretation JSONB,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Disease table
CREATE TABLE diseases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id UUID NOT NULL REFERENCES phenopackets(id) ON DELETE CASCADE,
    term JSONB NOT NULL,  -- Disease ontology term
    excluded BOOLEAN DEFAULT FALSE,
    onset JSONB,
    resolution JSONB,
    disease_stage JSONB DEFAULT '[]',
    clinical_tnm_finding JSONB DEFAULT '[]',
    primary_site JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_phenopackets_subject ON phenopackets USING GIN(subject);
CREATE INDEX idx_phenopackets_phenotypic_features ON phenopackets USING GIN(phenotypic_features);
CREATE INDEX idx_phenotypic_features_type ON phenotypic_features USING GIN(type_ontology_class);
CREATE INDEX idx_measurements_assay ON measurements USING GIN(assay);
CREATE INDEX idx_diseases_term ON diseases USING GIN(term);
```

#### 1.2 Preserve Existing Structure
- Keep current `reports` table with phenotypes JSONB field
- Maintain backward compatibility during transition
- Create views to serve both old and new formats

### Phase 2: Data Migration & Transformation
*Estimated Time: 2-3 weeks*

#### 2.1 Google Sheets to Phenopackets Mapper

```python
# migration/modules/phenopackets_converter.py

class PhenopacketConverter:
    """Convert existing phenotype data to Phenopackets v2 format."""
    
    def convert_individual_to_phenopacket(self, individual_data, report_data):
        """Transform individual + report data to phenopacket format."""
        
        phenopacket = {
            "id": f"phenopacket_{individual_data['individual_id']}",
            "subject": {
                "id": individual_data["individual_id"],
                "timeAtLastEncounter": {
                    "age": self._parse_age(report_data.get("age_reported"))
                },
                "sex": self._map_sex(individual_data.get("sex")),
                "karyotypicSex": "UNKNOWN_KARYOTYPE"
            },
            "phenotypicFeatures": self._convert_phenotypes(report_data.get("phenotypes", {})),
            "measurements": self._extract_measurements(report_data),
            "diseases": self._map_diseases(report_data),
            "metaData": self._create_metadata()
        }
        
        return phenopacket
    
    def _convert_phenotypes(self, phenotypes_json):
        """Convert existing phenotype structure to Phenopackets format."""
        features = []
        
        # Map renal insufficiency
        if "renalInsufficiency" in phenotypes_json:
            renal = phenotypes_json["renalInsufficiency"]
            features.append({
                "type": {
                    "id": renal.get("phenotype_id"),
                    "label": renal.get("name")
                },
                "excluded": renal.get("described") == "no",
                "modifiers": self._get_stage_modifiers(renal.get("described"))
            })
        
        # Map kidney biopsy findings
        if "kidneyBiopsy" in phenotypes_json:
            for hpo_id, details in phenotypes_json["kidneyBiopsy"].items():
                features.append({
                    "type": {
                        "id": details.get("phenotype_id"),
                        "label": details.get("name")
                    },
                    "excluded": details.get("described") == "no"
                })
        
        # Map other phenotypes similarly
        return features
    
    def _extract_measurements(self, report_data):
        """Extract quantitative measurements from report data."""
        measurements = []
        
        # Extract eGFR if available
        if "egfr_value" in report_data:
            measurements.append({
                "assay": {
                    "id": "LOINC:33914-3",
                    "label": "Glomerular filtration rate/1.73 sq M.predicted"
                },
                "value": {
                    "quantity": {
                        "unit": {
                            "id": "UCUM:mL/min/{1.73_m2}",
                            "label": "milliliter per minute per 1.73 square meter"
                        },
                        "value": report_data["egfr_value"]
                    }
                }
            })
        
        return measurements
```

#### 2.2 Migration Script Updates

```python
# migration/migrate_to_phenopackets.py

async def migrate_to_phenopackets(session: AsyncSession, test_mode: bool = False):
    """Migrate existing data to phenopackets format while preserving original."""
    
    # Step 1: Fetch existing data
    individuals = await fetch_all_individuals(session)
    reports = await fetch_all_reports(session)
    
    # Step 2: Convert to phenopackets
    converter = PhenopacketConverter()
    phenopackets = []
    
    for individual in individuals:
        individual_reports = [r for r in reports if r.individual_id == individual.id]
        
        for report in individual_reports:
            phenopacket = converter.convert_individual_to_phenopacket(
                individual.__dict__,
                report.__dict__
            )
            phenopackets.append(phenopacket)
    
    # Step 3: Store phenopackets
    await store_phenopackets(session, phenopackets)
    
    # Step 4: Create links to individuals
    await link_phenopackets_to_individuals(session, phenopackets)
```

### Phase 3: API Layer Adaptation
*Estimated Time: 2 weeks*

#### 3.1 Dual-Format API Support

```python
# app/endpoints/phenopackets.py

@router.get("/api/phenopackets/{individual_id}")
async def get_phenopacket(
    individual_id: str,
    format: str = Query("phenopacket", enum=["phenopacket", "legacy"]),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve phenotypic data in Phenopacket or legacy format."""
    
    if format == "phenopacket":
        # Return GA4GH Phenopacket v2 format
        phenopacket = await fetch_phenopacket(db, individual_id)
        return phenopacket
    else:
        # Return legacy format for backward compatibility
        report = await fetch_legacy_report(db, individual_id)
        return report

@router.post("/api/phenopackets/search")
async def search_phenopackets(
    phenotypes: List[str],
    measurements: Optional[Dict] = None,
    db: AsyncSession = Depends(get_db)
):
    """Search individuals by phenotypes using Phenopacket structure."""
    
    query = build_phenotype_search_query(phenotypes, measurements)
    results = await execute_search(db, query)
    return results
```

#### 3.2 Feature Preservation Mapping

```python
# app/services/feature_mapper.py

class FeatureMapper:
    """Map between legacy features and Phenopacket structure."""
    
    FEATURE_MAPPINGS = {
        "renalInsufficiency": {
            "phenopacket_path": "phenotypicFeatures",
            "hpo_terms": ["HP:0012622", "HP:0012623", "HP:0012624", 
                         "HP:0012625", "HP:0012626", "HP:0003774"],
            "category": "Kidney"
        },
        "genitalTractAbnormalities": {
            "phenopacket_path": "phenotypicFeatures",
            "hpo_terms": ["HP:0000078", "HP:0000079", "HP:0000080"],
            "category": "Genitourinary"
        },
        "diabetes": {
            "phenopacket_path": "diseases",
            "mondo_terms": ["MONDO:0005015", "MONDO:0005147"],
            "category": "Endocrine"
        },
        "hypomagnesemia": {
            "phenopacket_path": "measurements",
            "loinc_code": "LOINC:2601-3",
            "category": "Laboratory"
        }
    }
    
    def get_feature_from_phenopacket(self, phenopacket, feature_name):
        """Extract legacy feature from phenopacket structure."""
        mapping = self.FEATURE_MAPPINGS.get(feature_name)
        if not mapping:
            return None
        
        if mapping["phenopacket_path"] == "phenotypicFeatures":
            return self._extract_phenotypic_feature(phenopacket, mapping)
        elif mapping["phenopacket_path"] == "measurements":
            return self._extract_measurement(phenopacket, mapping)
        elif mapping["phenopacket_path"] == "diseases":
            return self._extract_disease(phenopacket, mapping)
```

### Phase 4: Data Import Pipeline Update
*Estimated Time: 1-2 weeks*

#### 4.1 Google Sheets to Phenopackets Pipeline

```python
# migration/modules/sheets_to_phenopackets.py

class SheetsToPhenopacketsImporter:
    """Import Google Sheets data directly as Phenopackets."""
    
    async def import_from_sheets(self, sheets_service, test_mode=False):
        """Main import function."""
        
        # Step 1: Authenticate and fetch sheets
        individuals_df = await fetch_sheet(sheets_service, "Individuals")
        reports_df = await fetch_sheet(sheets_service, "Reports")
        phenotypes_df = await fetch_sheet(sheets_service, "Phenotypes")
        
        # Step 2: Process and validate
        validated_data = await validate_sheets_data(
            individuals_df, reports_df, phenotypes_df
        )
        
        # Step 3: Convert to Phenopackets
        phenopackets = []
        for idx, row in validated_data.iterrows():
            phenopacket = self._create_phenopacket_from_row(row)
            phenopackets.append(phenopacket)
        
        # Step 4: Store in database
        await store_phenopackets_batch(phenopackets)
        
        # Step 5: Create backward compatibility layer
        await create_legacy_views(phenopackets)
```

#### 4.2 Validation & Quality Checks

```python
# migration/modules/phenopacket_validator.py

class PhenopacketValidator:
    """Validate Phenopackets against schema and business rules."""
    
    def validate_phenopacket(self, phenopacket):
        """Comprehensive validation."""
        errors = []
        
        # Schema validation
        if not self._validate_schema(phenopacket):
            errors.append("Invalid Phenopacket schema")
        
        # HPO term validation
        for feature in phenopacket.get("phenotypicFeatures", []):
            if not self._validate_hpo_term(feature["type"]["id"]):
                errors.append(f"Invalid HPO term: {feature['type']['id']}")
        
        # Required fields for HNF1B
        if not self._has_required_hnf1b_data(phenopacket):
            errors.append("Missing required HNF1B-specific data")
        
        return errors
```

### Phase 5: Testing & Validation
*Estimated Time: 1 week*

#### 5.1 Test Suite Development

```python
# tests/test_phenopackets_integration.py

class TestPhenopacketsIntegration:
    """Test phenopackets integration."""
    
    async def test_legacy_to_phenopacket_conversion(self):
        """Ensure accurate conversion from legacy format."""
        legacy_data = load_legacy_test_data()
        phenopacket = convert_to_phenopacket(legacy_data)
        
        # Verify all features preserved
        assert_renal_features_preserved(legacy_data, phenopacket)
        assert_genital_features_preserved(legacy_data, phenopacket)
        assert_measurements_preserved(legacy_data, phenopacket)
    
    async def test_phenopacket_search(self):
        """Test searching with phenopacket structure."""
        results = await search_by_phenotypes(["HP:0012622", "HP:0000078"])
        assert len(results) > 0
        assert_search_accuracy(results)
    
    async def test_backward_compatibility(self):
        """Ensure old API endpoints still work."""
        response = await get_individual_legacy_format("IND001")
        assert response.status_code == 200
        assert "phenotypes" in response.json()
```

#### 5.2 Data Validation Tests

```python
# tests/test_data_integrity.py

async def test_data_integrity_after_migration():
    """Verify no data loss during migration."""
    
    # Count checks
    original_count = await count_original_records()
    phenopacket_count = await count_phenopackets()
    assert phenopacket_count >= original_count
    
    # Feature preservation
    for individual in get_all_individuals():
        original = get_original_phenotypes(individual.id)
        phenopacket = get_phenopacket(individual.id)
        assert_features_match(original, phenopacket)
```

### Phase 6: Documentation & Training
*Estimated Time: 1 week*

#### 6.1 API Documentation Updates

- Update OpenAPI schemas for Phenopacket endpoints
- Create migration guide for API consumers
- Document feature mapping between legacy and Phenopacket formats
- Provide example queries and responses

#### 6.2 Developer Documentation

- Phenopacket schema reference for HNF1B data
- Conversion utilities documentation
- Troubleshooting guide for common issues
- Performance optimization guidelines

### Phase 7: Deployment & Migration
*Estimated Time: 1 week*

#### 7.1 Deployment Strategy

1. **Stage 1: Parallel Systems**
   - Deploy phenopackets tables alongside existing schema
   - Run dual writes to both systems
   - Monitor for inconsistencies

2. **Stage 2: Gradual Migration**
   - Enable phenopacket endpoints for beta users
   - Collect feedback and fix issues
   - Performance testing and optimization

3. **Stage 3: Full Migration**
   - Switch primary storage to phenopackets
   - Maintain legacy views for compatibility
   - Deprecate old endpoints with timeline

#### 7.2 Rollback Plan

```sql
-- Rollback script if needed
BEGIN;
    -- Restore original schema primacy
    ALTER TABLE reports SET (autovacuum_enabled = true);
    
    -- Re-enable legacy endpoints
    UPDATE api_config SET use_legacy = true WHERE service = 'phenotypes';
    
    -- Drop phenopacket tables if complete rollback needed
    -- DROP TABLE IF EXISTS phenopackets CASCADE;
COMMIT;
```

## Benefits & Outcomes

### Immediate Benefits
1. **Standards Compliance**: GA4GH Phenopackets v2 compliance
2. **Data Richness**: Support for measurements, time series, and complex relationships
3. **Interoperability**: Can exchange data with other phenopacket systems
4. **Maintained Compatibility**: All existing features preserved

### Long-term Benefits
1. **Future-Proof**: Aligned with international standards
2. **Research Collaboration**: Easier data sharing with research networks
3. **Enhanced Analytics**: Richer data model enables advanced queries
4. **Clinical Decision Support**: Better structure for clinical interpretations

## Risk Mitigation

### Technical Risks
- **Data Loss**: Mitigated by parallel systems and comprehensive testing
- **Performance Impact**: Addressed with proper indexing and query optimization
- **API Breaking Changes**: Prevented with dual-format support

### Process Risks
- **User Disruption**: Minimized with gradual rollout
- **Training Needs**: Addressed with documentation and examples
- **Integration Issues**: Handled with extensive testing

## Success Metrics

1. **Data Integrity**: 100% feature preservation
2. **Performance**: Query response times ≤ current system
3. **Compatibility**: All existing API endpoints functional
4. **Adoption**: 90% of queries using phenopacket format within 6 months
5. **Interoperability**: Successful data exchange with 1+ external system

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Schema Design | 1-2 weeks | None |
| Phase 2: Data Migration | 2-3 weeks | Phase 1 |
| Phase 3: API Adaptation | 2 weeks | Phase 2 |
| Phase 4: Import Pipeline | 1-2 weeks | Phase 2 |
| Phase 5: Testing | 1 week | Phases 3-4 |
| Phase 6: Documentation | 1 week | Phase 5 |
| Phase 7: Deployment | 1 week | Phase 6 |

**Total Timeline**: 9-12 weeks

## Next Steps

1. **Review & Approval**: Technical team review of this plan
2. **Environment Setup**: Create development branch for phenopackets work
3. **Schema Implementation**: Begin with Phase 1 database schema
4. **Prototype Development**: Build proof-of-concept with subset of data
5. **Stakeholder Communication**: Inform users of upcoming enhancements

## Appendix: Key Resources

- [GA4GH Phenopackets v2 Specification](https://phenopacket-schema.readthedocs.io/)
- [HPO (Human Phenotype Ontology)](https://hpo.jax.org/)
- [MONDO Disease Ontology](https://mondo.monarchinitiative.org/)
- [LOINC Laboratory Codes](https://loinc.org/)
- [Phenopackets Python Library](https://github.com/phenopackets/phenopacket-schema)