# refactor(api): migrate genomic annotations from frontend to database and API

## Summary
All genomic reference data (gene structures, exons, protein domains, transcripts) is currently hardcoded in frontend files. This violates single-source-of-truth principles and makes updates require redeployment.

**Current:** 14KB `chr17q12_genes.json`, hardcoded domains in Vue components, scattered gene coordinates
**Target:** Reference data in PostgreSQL served via versioned API endpoints

## Problem Statement

### Hardcoded Data Locations
1. **`frontend/src/data/chr17q12_genes.json`** (14KB)
   - 12 genes in chr17q12 region
   - Gene coordinates, symbols, names, exons, transcripts

2. **`frontend/src/components/gene/HNF1BProteinVisualization.vue`** (lines 300-330)
   - Protein domains: Dimerization (1-32), POU-Specific (101-157), POU-Homeodomain (183-243), Transactivation (400-557)

3. **`frontend/src/config/app.js`**
   - HNF1B gene coordinates (chr17:37680000-37750000)

4. **`frontend/src/utils/variants.js`**
   - Duplicate HNF1B boundaries (36098063-36112306)

### Issues
- ❌ **No version tracking** - Cannot distinguish GRCh37 vs GRCh38
- ❌ **Deployment required** - Updating domain coordinates requires frontend rebuild
- ❌ **Data duplication** - Gene coordinates exist in 3+ places
- ❌ **No audit trail** - Cannot track when/why annotations changed
- ❌ **Related to #95** - Protein domain corrections need database solution

## Acceptance Criteria

### Backend: Database Schema
- [ ] Create `reference_genomes` table (GRCh37, GRCh38, T2T-CHM13)
- [ ] Create `genes` table (symbol, name, chromosome, start, end, strand, genome_id)
- [ ] Create `transcripts` table (RefSeq ID, gene_id, exon boundaries, CDS)
- [ ] Create `protein_domains` table (UniProt/Pfam/InterPro, start, end, name, source, evidence)
- [ ] Create `exons` table (exon number, genomic coordinates, transcript_id)
- [ ] Add foreign keys and indexes for performance
- [ ] Include `created_at`, `updated_at`, `source`, `version` for all tables

### Backend: API Endpoints
- [ ] `GET /api/v2/reference/genomes` - List available genome builds
- [ ] `GET /api/v2/reference/genes` - Query genes by symbol/region
- [ ] `GET /api/v2/reference/genes/{symbol}` - Get gene details with exons
- [ ] `GET /api/v2/reference/genes/{symbol}/transcripts` - All isoforms
- [ ] `GET /api/v2/reference/genes/{symbol}/domains` - Protein domains
- [ ] `GET /api/v2/reference/regions/{chr}:{start}-{end}` - Genes in region
- [ ] Add caching headers (Cache-Control: max-age=86400)
- [ ] Include `genome_build` query parameter (default: GRCh38)

### Backend: Data Migration
- [ ] Script to load HNF1B gene data from NCBI/Ensembl
- [ ] Import protein domains from UniProt P35680
- [ ] Validate against existing `chr17q12_genes.json`
- [ ] Load chr17q12 region genes (12 genes)
- [ ] Add data provenance (source URLs, dates, versions)

### Frontend: Refactor
- [ ] Remove `frontend/src/data/chr17q12_genes.json`
- [ ] Create `src/api/reference.js` service layer
- [ ] Update `HNF1BProteinVisualization.vue` to fetch domains from API
- [ ] Update `HNF1BGeneVisualization.vue` to fetch gene structure from API
- [ ] Remove hardcoded coordinates from `config/app.js` and `utils/variants.js`
- [ ] Add loading states during reference data fetch
- [ ] Cache reference data in Pinia store (refresh on mount)
- [ ] Handle API errors gracefully (fallback to last known data)

### Documentation
- [ ] API documentation for reference endpoints
- [ ] Database schema diagram
- [ ] Instructions for updating annotations (admin guide)
- [ ] Data sources and citations (UniProt, NCBI, Ensembl)

## Benefits

1. **Single Source of Truth** - Database is authoritative, no frontend duplication
2. **Version Control** - Track GRCh37 vs GRCh38 coordinates explicitly
3. **Easy Updates** - Change protein domains without frontend deployment
4. **Audit Trail** - Log when/who/why annotations changed
5. **Extensibility** - Can add more genes, transcripts, genomes
6. **Performance** - API caching reduces load, faster than bundling JSON

## Dependencies
- Related to #95 (protein domain corrections) - This provides the infrastructure
- Related to #91 (config refactor) - Removes hardcoded values

## Migration Plan

### Phase 1: Backend Infrastructure
1. Create database schema
2. Implement API endpoints
3. Add data migration scripts
4. Test with HNF1B gene only

### Phase 2: Frontend Integration
1. Create API service layer
2. Update protein visualization component
3. Verify visualizations match current output
4. Add error handling and caching

### Phase 3: Expand Coverage
1. Add remaining chr17q12 genes
2. Add GRCh37 coordinates for legacy support
3. Document data update procedures

### Phase 4: Cleanup
1. Remove static JSON files
2. Remove hardcoded constants
3. Update tests to mock API calls

## Example API Response
```json
GET /api/v2/reference/genes/HNF1B/domains

{
  "gene": "HNF1B",
  "protein": "NP_000449.3",
  "uniprot": "P35680",
  "length": 557,
  "domains": [
    {
      "name": "Dimerization Domain",
      "start": 1,
      "end": 32,
      "source": "UniProt",
      "evidence": "ECO:0000255"
    },
    {
      "name": "POU-Specific Domain",
      "start": 101,
      "end": 157,
      "pfam": "PF00157",
      "interpro": "IPR000327"
    }
  ],
  "genome_build": "GRCh38",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

## Priority
**P1 (High)** - Architectural improvement blocking #95, improves maintainability and data accuracy

## Labels
`enhancement`, `backend`, `api`, `frontend`, `data-quality`, `p1-high`
