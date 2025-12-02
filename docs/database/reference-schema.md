# Reference Genome Database Schema

Database schema for storing genomic reference data (genes, transcripts, exons, protein domains).

**Database:** PostgreSQL 14+
**Last Updated:** 2025-01-18

---

## Table of Contents

- [Overview](#overview)
- [Entity Relationship Diagram](#entity-relationship-diagram)
- [Table Definitions](#table-definitions)
  - [reference_genomes](#reference_genomes)
  - [genes](#genes)
  - [transcripts](#transcripts)
  - [exons](#exons)
  - [protein_domains](#protein_domains)
- [Indexes](#indexes)
- [Constraints](#constraints)
- [Data Provenance](#data-provenance)

---

## Overview

The reference genome schema provides normalized storage for:

- **Genome assemblies** (GRCh38, GRCh37, T2T-CHM13)
- **Gene structures** (chromosomal coordinates, metadata)
- **Transcripts** (RefSeq IDs, isoforms, CDS boundaries)
- **Exons** (exon coordinates per transcript)
- **Protein domains** (UniProt, Pfam, InterPro annotations)

**Key Features:**
- Supports multiple genome assemblies via `genome_id` foreign keys
- Tracks data provenance (source, version, URLs)
- Audit trail with `created_at` and `updated_at` timestamps
- Flexible metadata storage using JSONB `extra_data` fields

---

## Entity Relationship Diagram

```
┌─────────────────────────┐
│  reference_genomes      │
│─────────────────────────│
│ * id (UUID, PK)         │
│   name (VARCHAR)        │◄─────┐
│   ucsc_name (VARCHAR)   │      │
│   ensembl_name (VARCHAR)│      │
│   ncbi_name (VARCHAR)   │      │
│   version (VARCHAR)     │      │
│   release_date (DATE)   │      │
│   is_default (BOOLEAN)  │      │
│   source_url (TEXT)     │      │
│   extra_data (JSONB)    │      │
│   created_at (TIMESTAMP)│      │
│   updated_at (TIMESTAMP)│      │
└─────────────────────────┘      │
                                  │
                                  │ genome_id (FK)
┌─────────────────────────┐      │
│  genes                  │      │
│─────────────────────────│      │
│ * id (UUID, PK)         │      │
│   symbol (VARCHAR)      │      │
│   name (TEXT)           │      │
│   chromosome (VARCHAR)  │      │
│   start (INTEGER)       │      │
│   end (INTEGER)         │      │
│   strand (VARCHAR)      │      │
│   ensembl_id (VARCHAR)  │      │
│   ncbi_gene_id (VARCHAR)│      │
│   hgnc_id (VARCHAR)     │      │
│   omim_id (VARCHAR)     │      │
│ * genome_id (UUID, FK)  ├──────┘
│   source (VARCHAR)      │
│   source_version (VAR)  │
│   source_url (TEXT)     │
│   extra_data (JSONB)    │◄─────┐
│   created_at (TIMESTAMP)│      │
│   updated_at (TIMESTAMP)│      │
└─────────────────────────┘      │
        ▲                         │
        │ gene_id (FK)            │
        │                         │
┌─────────────────────────┐      │
│  transcripts            │      │
│─────────────────────────│      │
│ * id (UUID, PK)         │      │
│   transcript_id (VARCHAR)│     │
│   protein_id (VARCHAR)  │      │
│   is_canonical (BOOLEAN)│      │
│   cds_start (INTEGER)   │      │
│   cds_end (INTEGER)     │      │
│   exon_count (INTEGER)  │      │
│ * gene_id (UUID, FK)    ├──────┘
│   source (VARCHAR)      │
│   source_url (TEXT)     │
│   extra_data (JSONB)    │
│   created_at (TIMESTAMP)│
│   updated_at (TIMESTAMP)│
└─────────────────────────┘
        ▲                  ▲
        │                  │
        │ transcript_id    │ transcript_id
        │ (FK)             │ (FK)
        │                  │
┌──────────────────────┐  │
│  exons               │  │
│──────────────────────│  │
│ * id (UUID, PK)      │  │
│   exon_number (INT)  │  │
│   chromosome (VAR)   │  │
│   start (INTEGER)    │  │
│   end (INTEGER)      │  │
│   strand (VARCHAR)   │  │
│ * transcript_id (FK) ├──┘
│   source (VARCHAR)   │
│   created_at (TS)    │
│   updated_at (TS)    │
└──────────────────────┘

┌─────────────────────────┐
│  protein_domains        │
│─────────────────────────│
│ * id (UUID, PK)         │
│   name (VARCHAR)        │
│   short_name (VARCHAR)  │
│   start (INTEGER)       │  <- amino acid position
│   end (INTEGER)         │  <- amino acid position
│   length (INTEGER)      │
│   pfam_id (VARCHAR)     │
│   interpro_id (VARCHAR) │
│   uniprot_id (VARCHAR)  │
│   function (TEXT)       │
│ * transcript_id (UUID FK)├──┘
│   source (VARCHAR)      │
│   source_url (TEXT)     │
│   extra_data (JSONB)    │
│   created_at (TIMESTAMP)│
│   updated_at (TIMESTAMP)│
└─────────────────────────┘

Legend:
  * = Primary Key or Foreign Key
  FK = Foreign Key
  PK = Primary Key
  VARCHAR = Variable Character
  TS = Timestamp
```

---

## Table Definitions

### reference_genomes

Stores genome assembly versions (GRCh38, GRCh37, etc.).

```sql
CREATE TABLE reference_genomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,              -- e.g., "GRCh38"
    ucsc_name VARCHAR(50),                         -- e.g., "hg38"
    ensembl_name VARCHAR(50),                      -- e.g., "GRCh38"
    ncbi_name VARCHAR(100),                        -- e.g., "GCA_000001405.28"
    version VARCHAR(20),                           -- e.g., "p14"
    release_date DATE,                             -- Assembly release date
    is_default BOOLEAN DEFAULT FALSE,              -- Default assembly for queries
    source_url TEXT,                               -- NCBI/Ensembl URL
    extra_data JSONB DEFAULT '{}'::jsonb,          -- Additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_reference_genomes_name ON reference_genomes(name);
CREATE INDEX idx_reference_genomes_is_default ON reference_genomes(is_default) WHERE is_default = TRUE;
```

**Sample Data:**
```sql
INSERT INTO reference_genomes (name, ucsc_name, ensembl_name, version, release_date, is_default)
VALUES
  ('GRCh38', 'hg38', 'GRCh38', 'p14', '2017-12-21', TRUE),
  ('GRCh37', 'hg19', 'GRCh37', 'p13', '2009-02-27', FALSE);
```

---

### genes

Stores gene information (symbol, coordinates, identifiers).

```sql
CREATE TABLE genes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,                   -- HGNC gene symbol (e.g., "HNF1B")
    name TEXT,                                     -- Full gene name
    chromosome VARCHAR(10) NOT NULL,               -- Chromosome (1-22, X, Y, MT)
    start INTEGER NOT NULL,                        -- Genomic start position (0-based)
    end INTEGER NOT NULL,                          -- Genomic end position
    strand VARCHAR(1) NOT NULL CHECK (strand IN ('+', '-')),
    ensembl_id VARCHAR(50),                        -- Ensembl gene ID
    ncbi_gene_id VARCHAR(50),                      -- NCBI Gene ID (EntrezGene)
    hgnc_id VARCHAR(50),                           -- HGNC ID
    omim_id VARCHAR(50),                           -- OMIM ID
    genome_id UUID NOT NULL REFERENCES reference_genomes(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL,                  -- Data source (e.g., "NCBI Gene")
    source_version VARCHAR(50),                    -- Source version/date
    source_url TEXT,                               -- Source URL
    extra_data JSONB DEFAULT '{}'::jsonb,          -- Additional metadata (aliases, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_gene_per_assembly UNIQUE (symbol, genome_id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_genes_symbol ON genes(symbol);
CREATE INDEX idx_genes_chromosome ON genes(chromosome);
CREATE INDEX idx_genes_genome_id ON genes(genome_id);
CREATE INDEX idx_genes_coordinates ON genes(chromosome, start, end);
CREATE INDEX idx_genes_extra_data ON genes USING GIN (extra_data);
```

**Sample Data:**
```sql
INSERT INTO genes (symbol, name, chromosome, start, end, strand, genome_id, source)
VALUES ('HNF1B', 'HNF1 homeobox B', '17', 36098063, 36112306, '-',
        (SELECT id FROM reference_genomes WHERE name = 'GRCh38'), 'NCBI Gene');
```

---

### transcripts

Stores transcript isoforms (RefSeq IDs, CDS boundaries, exon counts).

```sql
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id VARCHAR(50) NOT NULL UNIQUE,     -- RefSeq ID (e.g., "NM_000458.4")
    protein_id VARCHAR(50),                        -- RefSeq protein ID (e.g., "NP_000449.3")
    is_canonical BOOLEAN DEFAULT FALSE,            -- Is this the MANE/canonical transcript?
    cds_start INTEGER,                             -- CDS start position
    cds_end INTEGER,                               -- CDS end position
    exon_count INTEGER NOT NULL,                   -- Number of exons
    gene_id UUID NOT NULL REFERENCES genes(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL,                  -- Data source (e.g., "RefSeq")
    source_url TEXT,                               -- Source URL
    extra_data JSONB DEFAULT '{}'::jsonb,          -- Additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_transcripts_gene_id ON transcripts(gene_id);
CREATE INDEX idx_transcripts_transcript_id ON transcripts(transcript_id);
CREATE INDEX idx_transcripts_is_canonical ON transcripts(is_canonical) WHERE is_canonical = TRUE;
```

**Sample Data:**
```sql
INSERT INTO transcripts (transcript_id, protein_id, is_canonical, exon_count, gene_id, source)
VALUES ('NM_000458.4', 'NP_000449.3', TRUE, 9,
        (SELECT id FROM genes WHERE symbol = 'HNF1B'), 'RefSeq');
```

---

### exons

Stores exon coordinates for each transcript.

```sql
CREATE TABLE exons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exon_number INTEGER NOT NULL,                  -- Exon number (1-indexed)
    chromosome VARCHAR(10) NOT NULL,               -- Chromosome
    start INTEGER NOT NULL,                        -- Exon start position
    end INTEGER NOT NULL,                          -- Exon end position
    strand VARCHAR(1) NOT NULL CHECK (strand IN ('+', '-')),
    transcript_id UUID NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL,                  -- Data source
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_exon_per_transcript UNIQUE (transcript_id, exon_number)
);
```

**Indexes:**
```sql
CREATE INDEX idx_exons_transcript_id ON exons(transcript_id);
CREATE INDEX idx_exons_coordinates ON exons(chromosome, start, end);
```

**Sample Data:**
```sql
INSERT INTO exons (exon_number, chromosome, start, end, strand, transcript_id, source)
VALUES (1, '17', 36098063, 36098372, '-',
        (SELECT id FROM transcripts WHERE transcript_id = 'NM_000458.4'), 'NCBI RefSeq');
```

---

### protein_domains

Stores protein domain annotations (UniProt, Pfam, InterPro).

```sql
CREATE TABLE protein_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,                    -- Domain name
    short_name VARCHAR(50),                        -- Short name/abbreviation
    start INTEGER NOT NULL,                        -- Domain start (amino acid position, 1-indexed)
    end INTEGER NOT NULL,                          -- Domain end (amino acid position)
    length INTEGER GENERATED ALWAYS AS (end - start + 1) STORED,
    pfam_id VARCHAR(50),                           -- Pfam ID (e.g., "PF00157")
    interpro_id VARCHAR(50),                       -- InterPro ID (e.g., "IPR000327")
    uniprot_id VARCHAR(50),                        -- UniProt accession (e.g., "P35680")
    function TEXT,                                 -- Domain function description
    transcript_id UUID NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL,                  -- Data source (UniProt, Pfam, etc.)
    source_url TEXT,                               -- Source URL
    extra_data JSONB DEFAULT '{}'::jsonb,          -- Additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_protein_domains_transcript_id ON protein_domains(transcript_id);
CREATE INDEX idx_protein_domains_pfam_id ON protein_domains(pfam_id) WHERE pfam_id IS NOT NULL;
CREATE INDEX idx_protein_domains_interpro_id ON protein_domains(interpro_id) WHERE interpro_id IS NOT NULL;
CREATE INDEX idx_protein_domains_uniprot_id ON protein_domains(uniprot_id) WHERE uniprot_id IS NOT NULL;
```

**Sample Data:**
```sql
INSERT INTO protein_domains (name, short_name, start, end, pfam_id, interpro_id, transcript_id, source)
VALUES ('POU-Specific Domain', 'POU-S', 8, 173, 'PF00157', 'IPR000327',
        (SELECT id FROM transcripts WHERE transcript_id = 'NM_000458.4'), 'UniProt');
```

---

## Indexes

### Performance Optimization

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| `reference_genomes` | `idx_reference_genomes_name` | B-tree | Fast lookup by assembly name |
| `genes` | `idx_genes_symbol` | B-tree | Gene symbol queries |
| `genes` | `idx_genes_chromosome` | B-tree | Chromosome-based queries |
| `genes` | `idx_genes_coordinates` | B-tree (composite) | Region queries |
| `genes` | `idx_genes_extra_data` | GIN | JSONB metadata searches |
| `transcripts` | `idx_transcripts_gene_id` | B-tree | Transcript lookup by gene |
| `transcripts` | `idx_transcripts_is_canonical` | B-tree (partial) | Fast canonical transcript lookup |
| `exons` | `idx_exons_transcript_id` | B-tree | Exon lookup by transcript |
| `protein_domains` | `idx_protein_domains_transcript_id` | B-tree | Domain lookup by transcript |

---

## Constraints

### Foreign Keys

- `genes.genome_id` → `reference_genomes.id` (CASCADE DELETE)
- `transcripts.gene_id` → `genes.id` (CASCADE DELETE)
- `exons.transcript_id` → `transcripts.id` (CASCADE DELETE)
- `protein_domains.transcript_id` → `transcripts.id` (CASCADE DELETE)

**Rationale:** Cascade deletes ensure referential integrity when deleting genome assemblies or genes.

### Unique Constraints

- `reference_genomes.name` - Genome assembly names must be unique
- `genes (symbol, genome_id)` - Gene symbols are unique per assembly
- `transcripts.transcript_id` - RefSeq transcript IDs are globally unique
- `exons (transcript_id, exon_number)` - Exon numbers are unique per transcript

### Check Constraints

- `genes.strand IN ('+', '-')` - Strand must be + or -
- `exons.strand IN ('+', '-')` - Strand must be + or -

---

## Data Provenance

All tables include provenance tracking:

| Field | Purpose | Example |
|-------|---------|---------|
| `source` | Data source name | "NCBI Gene", "UniProt", "RefSeq" |
| `source_version` | Source version/date | "2025-01", "Release 2024_05" |
| `source_url` | Source URL | "https://www.ncbi.nlm.nih.gov/gene/6928" |
| `extra_data` | Additional metadata (JSONB) | `{"verified_date": "2025-01-17"}` |
| `created_at` | Record creation timestamp | Auto-populated |
| `updated_at` | Last update timestamp | Auto-updated via trigger |

### Update Trigger

Automatically update `updated_at` timestamp on record modification:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_genes_updated_at BEFORE UPDATE ON genes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Repeat for other tables: transcripts, exons, protein_domains, reference_genomes
```

---

## Migration Scripts

Database migrations are managed via Alembic:

```bash
# Create new migration
cd backend
alembic revision -m "Add reference genome schema"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

**Migration Files:**
- `backend/alembic/versions/*_add_reference_genome_tables.py`

---

## See Also

- [API Documentation](../api/reference-genome-api.md)
- [Admin Guide: Updating Annotations](../admin/update-annotations.md)
- [Data Sources](../references/data-sources.md)
