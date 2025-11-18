# Reference Genome API Documentation

API endpoints for accessing genomic reference data (genes, transcripts, exons, protein domains).

**Base URL:** `/api/v2/reference`

**Version:** 2.0
**Last Updated:** 2025-01-18

---

## Table of Contents

- [Overview](#overview)
- [Endpoints](#endpoints)
  - [List Genome Assemblies](#list-genome-assemblies)
  - [Query Genes](#query-genes)
  - [Get Gene Details](#get-gene-details)
  - [Get Gene Transcripts](#get-gene-transcripts)
  - [Get Protein Domains](#get-protein-domains)
  - [Get Genes in Region](#get-genes-in-region)
- [Data Models](#data-models)
- [Caching](#caching)
- [Error Handling](#error-handling)

---

## Overview

The Reference Genome API provides access to curated genomic reference data including:

- **Genome assemblies** (GRCh38, GRCh37)
- **Gene structures** (coordinates, exons, transcripts)
- **Protein domains** (UniProt, Pfam, InterPro annotations)
- **Regional queries** (all genes in a genomic region)

All endpoints support versioned genome assemblies via the `genome_build` parameter (default: GRCh38).

---

## Endpoints

### List Genome Assemblies

Get all available genome assembly versions.

**Endpoint:** `GET /api/v2/reference/genomes`

**Parameters:** None

**Response:**
```json
{
  "genomes": [
    {
      "name": "GRCh38",
      "ucsc_name": "hg38",
      "ensembl_name": "GRCh38",
      "ncbi_name": "GCA_000001405.28",
      "version": "p14",
      "release_date": "2017-12-21",
      "is_default": true,
      "source_url": "https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.40/"
    },
    {
      "name": "GRCh37",
      "ucsc_name": "hg19",
      "ensembl_name": "GRCh37",
      "ncbi_name": "GCA_000001405.14",
      "version": "p13",
      "release_date": "2009-02-27",
      "is_default": false,
      "source_url": "https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.25/"
    }
  ]
}
```

**Caching:** `Cache-Control: max-age=86400` (24 hours)

---

### Query Genes

Search genes by symbol, chromosome, or region.

**Endpoint:** `GET /api/v2/reference/genes`

**Parameters:**
- `symbol` (string, optional): Gene symbol (e.g., "HNF1B")
- `chromosome` (string, optional): Chromosome number (e.g., "17")
- `genome_build` (string, optional): Genome assembly (default: "GRCh38")

**Example Requests:**
```bash
# Get HNF1B gene
GET /api/v2/reference/genes?symbol=HNF1B

# Get all genes on chromosome 17
GET /api/v2/reference/genes?chromosome=17

# Get gene in GRCh37 coordinates
GET /api/v2/reference/genes?symbol=HNF1B&genome_build=GRCh37
```

**Response:**
```json
{
  "genes": [
    {
      "symbol": "HNF1B",
      "name": "HNF1 homeobox B",
      "chromosome": "17",
      "start": 36098063,
      "end": 36112306,
      "strand": "-",
      "ensembl_id": "ENSG00000275410",
      "ncbi_gene_id": "6928",
      "hgnc_id": "HGNC:11630",
      "omim_id": "189907",
      "genome_build": "GRCh38",
      "source": "NCBI Gene",
      "source_url": "https://www.ncbi.nlm.nih.gov/gene/6928",
      "updated_at": "2025-01-17T10:30:00Z"
    }
  ]
}
```

**Caching:** `Cache-Control: max-age=86400` (24 hours)

---

### Get Gene Details

Get detailed information about a specific gene including transcript isoforms.

**Endpoint:** `GET /api/v2/reference/genes/{symbol}`

**Parameters:**
- `symbol` (string, required): Gene symbol (e.g., "HNF1B")
- `genome_build` (string, optional): Genome assembly (default: "GRCh38")

**Example Request:**
```bash
GET /api/v2/reference/genes/HNF1B?genome_build=GRCh38
```

**Response:**
```json
{
  "gene": {
    "symbol": "HNF1B",
    "name": "HNF1 homeobox B",
    "chromosome": "17",
    "start": 36098063,
    "end": 36112306,
    "strand": "-",
    "ensembl_id": "ENSG00000275410",
    "ncbi_gene_id": "6928",
    "hgnc_id": "HGNC:11630",
    "omim_id": "189907",
    "genome_build": "GRCh38"
  },
  "transcripts": [
    {
      "transcript_id": "NM_000458.4",
      "protein_id": "NP_000449.3",
      "is_canonical": true,
      "exon_count": 9
    }
  ]
}
```

**Caching:** `Cache-Control: max-age=86400` (24 hours)

---

### Get Gene Transcripts

Get all transcript isoforms for a gene with exon coordinates.

**Endpoint:** `GET /api/v2/reference/genes/{symbol}/transcripts`

**Parameters:**
- `symbol` (string, required): Gene symbol (e.g., "HNF1B")
- `genome_build` (string, optional): Genome assembly (default: "GRCh38")

**Example Request:**
```bash
GET /api/v2/reference/genes/HNF1B/transcripts
```

**Response:**
```json
{
  "gene": "HNF1B",
  "genome_build": "GRCh38",
  "transcripts": [
    {
      "transcript_id": "NM_000458.4",
      "protein_id": "NP_000449.3",
      "is_canonical": true,
      "cds_start": 36098301,
      "cds_end": 36111805,
      "exon_count": 9,
      "exons": [
        {
          "exon_number": 1,
          "chromosome": "17",
          "start": 36098063,
          "end": 36098372,
          "strand": "-"
        }
      ]
    }
  ]
}
```

**Caching:** `Cache-Control: max-age=86400` (24 hours)

---

### Get Protein Domains

Get protein domain annotations for a gene's canonical transcript.

**Endpoint:** `GET /api/v2/reference/genes/{symbol}/domains`

**Parameters:**
- `symbol` (string, required): Gene symbol (e.g., "HNF1B")
- `genome_build` (string, optional): Genome assembly (default: "GRCh38")

**Example Request:**
```bash
GET /api/v2/reference/genes/HNF1B/domains
```

**Response:**
```json
{
  "gene": "HNF1B",
  "protein": "NP_000449.3",
  "uniprot": "P35680",
  "length": 557,
  "domains": [
    {
      "name": "Dimerization Domain",
      "short_name": "Dim",
      "start": 1,
      "end": 31,
      "length": 31,
      "function": "Mediates homodimer or heterodimer formation",
      "source": "UniProt",
      "uniprot_id": "P35680"
    },
    {
      "name": "POU-Specific Domain",
      "short_name": "POU-S",
      "start": 8,
      "end": 173,
      "length": 166,
      "function": "DNA binding (part 1)",
      "pfam_id": "PF00157",
      "interpro_id": "IPR000327",
      "source": "UniProt",
      "uniprot_id": "P35680"
    },
    {
      "name": "POU Homeodomain",
      "short_name": "POU-H",
      "start": 232,
      "end": 305,
      "length": 74,
      "function": "DNA binding (part 2)",
      "interpro_id": "IPR001356",
      "source": "UniProt",
      "uniprot_id": "P35680"
    },
    {
      "name": "Transactivation Domain",
      "short_name": "TAD",
      "start": 314,
      "end": 557,
      "length": 244,
      "function": "Transcriptional activation",
      "source": "UniProt",
      "uniprot_id": "P35680"
    }
  ],
  "genome_build": "GRCh38",
  "updated_at": "2025-01-17T10:30:00Z"
}
```

**Caching:** `Cache-Control: max-age=86400` (24 hours)

**Data Source:** UniProt P35680 (verified 2025-01-17)

---

### Get Genes in Region

Get all genes within a specified genomic region.

**Endpoint:** `GET /api/v2/reference/regions/{region}`

**Parameters:**
- `region` (string, required): Genomic region in format "chr:start-end" (e.g., "17:36000000-39900000")
- `genome_build` (string, optional): Genome assembly (default: "GRCh38")

**Example Request:**
```bash
# Get all genes in chr17q12 region (17q12 deletion syndrome region)
GET /api/v2/reference/regions/17:36000000-39900000
```

**Response:**
```json
{
  "region": "17:36000000-39900000",
  "genome_build": "GRCh38",
  "gene_count": 29,
  "genes": [
    {
      "symbol": "HNF1B",
      "name": "HNF1 homeobox B",
      "chromosome": "17",
      "start": 36098063,
      "end": 36112306,
      "strand": "-",
      "extra_data": {
        "transcript_id": "NM_000458.4",
        "mim": "189907",
        "clinical_significance": "critical",
        "function": "Transcription factor for kidney and pancreas development"
      }
    },
    {
      "symbol": "LHX1",
      "name": "LIM homeobox 1",
      "chromosome": "17",
      "start": 36114574,
      "end": 36148741,
      "strand": "-",
      "extra_data": {
        "clinical_significance": "high"
      }
    }
  ]
}
```

**Caching:** `Cache-Control: max-age=86400` (24 hours)

---

## Data Models

### Gene
```typescript
{
  symbol: string;           // HGNC gene symbol
  name: string;             // Full gene name
  chromosome: string;       // Chromosome (1-22, X, Y, MT)
  start: number;            // Genomic start position (0-based)
  end: number;              // Genomic end position
  strand: string;           // Strand (+ or -)
  ensembl_id?: string;      // Ensembl gene ID
  ncbi_gene_id?: string;    // NCBI Gene ID
  hgnc_id?: string;         // HGNC ID
  omim_id?: string;         // OMIM ID
  genome_build: string;     // Genome assembly (GRCh38, GRCh37)
  source: string;           // Data source (e.g., "NCBI Gene")
  source_url?: string;      // Source URL
  updated_at: string;       // ISO 8601 timestamp
  extra_data?: object;      // Additional metadata (JSONB)
}
```

### Transcript
```typescript
{
  transcript_id: string;    // RefSeq transcript ID (e.g., NM_000458.4)
  protein_id?: string;      // RefSeq protein ID (e.g., NP_000449.3)
  is_canonical: boolean;    // Is this the canonical/MANE transcript?
  cds_start?: number;       // CDS start position
  cds_end?: number;         // CDS end position
  exon_count: number;       // Number of exons
  exons?: Exon[];           // Exon coordinates (if requested)
}
```

### Exon
```typescript
{
  exon_number: number;      // Exon number (1-indexed)
  chromosome: string;       // Chromosome
  start: number;            // Exon start position
  end: number;              // Exon end position
  strand: string;           // Strand (+ or -)
}
```

### ProteinDomain
```typescript
{
  name: string;             // Domain name
  short_name?: string;      // Short name/abbreviation
  start: number;            // Domain start position (amino acid)
  end: number;              // Domain end position (amino acid)
  length: number;           // Domain length (amino acids)
  pfam_id?: string;         // Pfam ID
  interpro_id?: string;     // InterPro ID
  uniprot_id?: string;      // UniProt accession
  function?: string;        // Domain function description
  source: string;           // Data source (UniProt, Pfam, InterPro)
}
```

---

## Caching

All reference genome endpoints return caching headers:

```http
Cache-Control: max-age=86400
```

**Cache Duration:** 24 hours (86400 seconds)

**Rationale:** Reference genome data changes infrequently. Caching reduces server load and improves client performance.

**Cache Invalidation:** Clients should refresh cached data when:
- Genome assembly is updated (rare - happens every few years)
- New genes or annotations are added
- Protein domain corrections are applied

---

## Error Handling

### Common Error Responses

**404 Not Found** - Gene or resource not found:
```json
{
  "detail": "Gene 'INVALID' not found in genome assembly GRCh38"
}
```

**400 Bad Request** - Invalid parameters:
```json
{
  "detail": "Invalid region format. Expected 'chr:start-end' (e.g., '17:36000000-39900000')"
}
```

**422 Validation Error** - Invalid input data:
```json
{
  "detail": [
    {
      "loc": ["query", "genome_build"],
      "msg": "Invalid genome assembly. Must be one of: GRCh38, GRCh37",
      "type": "value_error"
    }
  ]
}
```

**500 Internal Server Error** - Server error:
```json
{
  "detail": "Internal server error"
}
```

---

## Interactive Documentation

For interactive API exploration, visit the Swagger UI:

**URL:** `http://localhost:8000/docs` (when running locally)

The Swagger UI provides:
- Interactive request/response testing
- Complete schema definitions
- Example requests and responses
- Authentication testing (if applicable)

---

## Version History

| Version | Date       | Changes |
|---------|------------|---------|
| 2.0     | 2025-01-18 | Initial release of Reference Genome API |

---

## See Also

- [Database Schema](../database/reference-schema.md)
- [Admin Guide: Updating Annotations](../admin/update-annotations.md)
- [Data Sources](../references/data-sources.md)
