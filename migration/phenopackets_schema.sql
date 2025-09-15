-- Phenopackets v2 Database Schema for HNF1B-API
-- Complete replacement of normalized PostgreSQL structure
-- GA4GH Phenopackets v2 compliant

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Drop existing schema if requested (use with caution in production)
-- DROP SCHEMA IF EXISTS public CASCADE;
-- CREATE SCHEMA public;

-- Core phenopackets storage table
CREATE TABLE IF NOT EXISTS phenopackets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(10) DEFAULT '2.0',
    phenopacket JSONB NOT NULL,  -- Complete phenopacket document
    
    -- Denormalized fields for fast queries (generated from JSONB)
    subject_id VARCHAR(100) GENERATED ALWAYS AS (phenopacket->'subject'->>'id') STORED,
    subject_sex VARCHAR(20) GENERATED ALWAYS AS (phenopacket->'subject'->>'sex') STORED,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    schema_version VARCHAR(20) DEFAULT '2.0.0',
    
    -- Validation constraint
    CONSTRAINT valid_phenopacket CHECK (jsonb_typeof(phenopacket) = 'object')
);

-- Family/Cohort relationships table
CREATE TABLE IF NOT EXISTS families (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id VARCHAR(100) UNIQUE NOT NULL,
    family_phenopacket JSONB NOT NULL,  -- GA4GH Family message
    proband_id VARCHAR(100),
    pedigree JSONB,
    files JSONB DEFAULT '[]'::jsonb,
    meta_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_family CHECK (jsonb_typeof(family_phenopacket) = 'object')
);

-- Cohorts for population studies
CREATE TABLE IF NOT EXISTS cohorts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id VARCHAR(100) UNIQUE NOT NULL,
    cohort_phenopacket JSONB NOT NULL,  -- GA4GH Cohort message
    description TEXT,
    members JSONB DEFAULT '[]'::jsonb,  -- Array of phenopacket_ids
    meta_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_cohort CHECK (jsonb_typeof(cohort_phenopacket) = 'object')
);

-- Resource metadata (for tracking data sources and ontologies)
CREATE TABLE IF NOT EXISTS resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    namespace_prefix VARCHAR(50),
    url TEXT,
    version VARCHAR(50),
    iri_prefix TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log table for tracking changes
CREATE TABLE IF NOT EXISTS phenopacket_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phenopacket_id VARCHAR(100) NOT NULL,
    action VARCHAR(20) NOT NULL, -- INSERT, UPDATE, DELETE
    old_value JSONB,
    new_value JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    change_reason TEXT
);

-- Create comprehensive indexes for phenopacket queries
CREATE INDEX IF NOT EXISTS idx_phenopacket_subject ON phenopackets USING GIN ((phenopacket->'subject'));
CREATE INDEX IF NOT EXISTS idx_phenopacket_features ON phenopackets USING GIN ((phenopacket->'phenotypicFeatures'));
CREATE INDEX IF NOT EXISTS idx_phenopacket_diseases ON phenopackets USING GIN ((phenopacket->'diseases'));
CREATE INDEX IF NOT EXISTS idx_phenopacket_interpretations ON phenopackets USING GIN ((phenopacket->'interpretations'));
CREATE INDEX IF NOT EXISTS idx_phenopacket_measurements ON phenopackets USING GIN ((phenopacket->'measurements'));
CREATE INDEX IF NOT EXISTS idx_phenopacket_medical_actions ON phenopackets USING GIN ((phenopacket->'medicalActions'));
CREATE INDEX IF NOT EXISTS idx_phenopacket_subject_id ON phenopackets (subject_id);
CREATE INDEX IF NOT EXISTS idx_phenopacket_sex ON phenopackets (subject_sex);
CREATE INDEX IF NOT EXISTS idx_phenopacket_created ON phenopackets (created_at DESC);

-- Full text search index
CREATE INDEX IF NOT EXISTS idx_phenopacket_text_search ON phenopackets 
    USING GIN (to_tsvector('english', phenopacket::text));

-- Specific indexes for common queries
CREATE INDEX IF NOT EXISTS idx_phenopacket_hpo_terms ON phenopackets 
    USING GIN ((phenopacket->'phenotypicFeatures' @> '[{"type": {}}]'::jsonb));

CREATE INDEX IF NOT EXISTS idx_phenopacket_variant_labels ON phenopackets 
    USING GIN ((phenopacket->'interpretations' @> '[{"diagnosis": {"genomicInterpretations": []}}]'::jsonb));

-- Family and cohort indexes
CREATE INDEX IF NOT EXISTS idx_family_proband ON families (proband_id);
CREATE INDEX IF NOT EXISTS idx_cohort_members ON cohorts USING GIN (members);

-- Create views for common queries
CREATE OR REPLACE VIEW individual_phenotypes AS
SELECT 
    p.phenopacket_id,
    p.subject_id,
    p.subject_sex,
    feature->>'type' as hpo_term,
    feature->'type'->>'id' as hpo_id,
    feature->'type'->>'label' as hpo_label,
    COALESCE((feature->>'excluded')::boolean, false) as excluded,
    feature->'severity'->>'label' as severity,
    feature->'modifiers' as modifiers,
    feature->'onset' as onset,
    feature->'evidence' as evidence
FROM 
    phenopackets p,
    LATERAL jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature;

CREATE OR REPLACE VIEW individual_variants AS
SELECT 
    p.phenopacket_id,
    p.subject_id,
    interp->>'id' as interpretation_id,
    interp->>'progressStatus' as progress_status,
    gi->>'interpretationStatus' as interpretation_status,
    vi->'variationDescriptor'->>'label' as variant_label,
    vi->'variationDescriptor'->'geneContext'->>'symbol' as gene_symbol,
    vi->>'acmgPathogenicityClassification' as acmg_classification,
    vi->'variationDescriptor'->'allelicState'->>'label' as allelic_state
FROM 
    phenopackets p,
    LATERAL jsonb_array_elements(p.phenopacket->'interpretations') as interp,
    LATERAL jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi,
    LATERAL jsonb_path_query(gi, '$.variantInterpretation') as vi;

CREATE OR REPLACE VIEW individual_diseases AS
SELECT 
    p.phenopacket_id,
    p.subject_id,
    disease->'term'->>'id' as disease_id,
    disease->'term'->>'label' as disease_label,
    disease->'onset' as onset,
    disease->'diseaseStage' as disease_stage
FROM 
    phenopackets p,
    LATERAL jsonb_array_elements(p.phenopacket->'diseases') as disease;

CREATE OR REPLACE VIEW individual_measurements AS
SELECT 
    p.phenopacket_id,
    p.subject_id,
    measurement->'assay'->>'id' as assay_id,
    measurement->'assay'->>'label' as assay_label,
    measurement->'value'->'quantity'->>'value' as quantity_value,
    measurement->'value'->'quantity'->'unit'->>'label' as unit_label,
    measurement->'interpretation'->>'id' as interpretation_id,
    measurement->'interpretation'->>'label' as interpretation_label,
    measurement->'timeObserved'->>'timestamp' as time_observed
FROM 
    phenopackets p,
    LATERAL jsonb_array_elements(p.phenopacket->'measurements') as measurement;

-- Functions for common operations
CREATE OR REPLACE FUNCTION get_phenopacket_by_subject(subject_identifier VARCHAR)
RETURNS JSONB AS $$
BEGIN
    RETURN (
        SELECT phenopacket 
        FROM phenopackets 
        WHERE subject_id = subject_identifier 
        ORDER BY created_at DESC 
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION search_phenopackets_by_hpo(hpo_terms VARCHAR[])
RETURNS TABLE(phenopacket_id VARCHAR, subject_id VARCHAR, matching_features JSONB) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.phenopacket_id::VARCHAR,
        p.subject_id::VARCHAR,
        jsonb_agg(feature) as matching_features
    FROM 
        phenopackets p,
        LATERAL jsonb_array_elements(p.phenopacket->'phenotypicFeatures') as feature
    WHERE 
        feature->'type'->>'id' = ANY(hpo_terms)
    GROUP BY 
        p.phenopacket_id, p.subject_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updating the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER phenopackets_updated_at 
    BEFORE UPDATE ON phenopackets 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER families_updated_at 
    BEFORE UPDATE ON families 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER cohorts_updated_at 
    BEFORE UPDATE ON cohorts 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at();

-- Audit trigger for phenopackets
CREATE OR REPLACE FUNCTION audit_phenopacket_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO phenopacket_audit (phenopacket_id, action, new_value, changed_by)
        VALUES (NEW.phenopacket_id, 'INSERT', NEW.phenopacket, NEW.created_by);
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO phenopacket_audit (phenopacket_id, action, old_value, new_value, changed_by)
        VALUES (NEW.phenopacket_id, 'UPDATE', OLD.phenopacket, NEW.phenopacket, NEW.updated_by);
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO phenopacket_audit (phenopacket_id, action, old_value, changed_by)
        VALUES (OLD.phenopacket_id, 'DELETE', OLD.phenopacket, current_user);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER phenopacket_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON phenopackets
    FOR EACH ROW
    EXECUTE FUNCTION audit_phenopacket_changes();

-- Insert default resources (ontologies)
INSERT INTO resources (resource_id, name, namespace_prefix, url, version, iri_prefix) VALUES
    ('hpo', 'Human Phenotype Ontology', 'HP', 'https://hpo.jax.org', '2024-01-01', 'http://purl.obolibrary.org/obo/HP_'),
    ('mondo', 'Mondo Disease Ontology', 'MONDO', 'https://mondo.monarchinitiative.org', '2024-01-01', 'http://purl.obolibrary.org/obo/MONDO_'),
    ('loinc', 'Logical Observation Identifiers Names and Codes', 'LOINC', 'https://loinc.org', '2.76', 'https://loinc.org/'),
    ('omim', 'Online Mendelian Inheritance in Man', 'OMIM', 'https://omim.org', '2024-01-01', 'https://omim.org/entry/'),
    ('ncit', 'NCI Thesaurus', 'NCIT', 'https://ncithesaurus.nci.nih.gov', '24.01', 'http://purl.obolibrary.org/obo/NCIT_'),
    ('geno', 'Genotype Ontology', 'GENO', 'http://purl.obolibrary.org/obo/geno.owl', '2023-10-08', 'http://purl.obolibrary.org/obo/GENO_'),
    ('eco', 'Evidence and Conclusion Ontology', 'ECO', 'http://purl.obolibrary.org/obo/eco.owl', '2024-01-01', 'http://purl.obolibrary.org/obo/ECO_'),
    ('ncbitaxon', 'NCBI Taxonomy', 'NCBITaxon', 'https://www.ncbi.nlm.nih.gov/taxonomy', '2024-01-01', 'http://purl.obolibrary.org/obo/NCBITaxon_'),
    ('chebi', 'Chemical Entities of Biological Interest', 'CHEBI', 'https://www.ebi.ac.uk/chebi', '231', 'http://purl.obolibrary.org/obo/CHEBI_'),
    ('ucum', 'Unified Code for Units of Measure', 'UCUM', 'https://ucum.org', '2.1', 'https://ucum.org/')
ON CONFLICT (resource_id) DO NOTHING;