# HNF1B-db MCP — live e2e transcript

**Server:** HNF1B-db (protocol 2025-11-25)
**Endpoint:** http://localhost:8788/mcp (Streamable HTTP, stateless)

**Tools (11):** hnf1b_find_individuals_by_phenotype, hnf1b_get_capabilities, hnf1b_get_gene_context, hnf1b_get_individual, hnf1b_get_individuals, hnf1b_get_publications, hnf1b_get_statistics, hnf1b_get_variant, hnf1b_resolve_terms, hnf1b_search, hnf1b_search_variants
**Resources:** hnf1b://schema/overview, hnf1b://schema/tool-guide

### hnf1b_get_statistics(metric=summary)
```json
{
  "metric": "summary",
  "result": {
    "total_phenopackets": 885,
    "with_variants": 864,
    "distinct_hpo_terms": 36,
    "distinct_publications": 141,
    "distinct_variants": 198,
    "male": 359,
    "female": 335,
    "unknown_sex": 191
  },
  "data_class": "curated_derived_analysis",
  "meta": {
    "response_mode": "compact",
    "effective_chars": 0,
    "elapsed_ms": 43.9
  }
}
```

### hnf1b_search_variants(classification=PATHOGENIC, page_size=2)
```json
{
  "variants": [
    {
      "simple_id": "Var1",
      "variant_id": "var:HNF1B:17:36459258-37832869:DEL",
      "label": "1.5Mb del (dbVar:nssv1184554)",
      "gene_symbol": "HNF1B",
      "structural_type": "deletion",
      "classification": "PATHOGENIC",
      "consequence": "Copy Number Loss",
      "hg38": "17:36459258-37832869:DEL",
      "transcript": null,
      "protein": null,
      "carrier_count": 379,
      "uri": "hnf1b://variant/var:HNF1B:17:36459258-37832869:DEL"
    },
    {
      "simple_id": "Var2",
      "variant_id": "var:HNF1B:17:36459258-37832869:DUP",
      "label": "1.37Mb dup (dbVar:nssv1184555)",
      "gene_symbol": "HNF1B",
      "structural_type": "duplication",
      "classification": "PATHOGENIC",
      "consequence": "Copy Number Gain",
      "hg38": "17:36459258-37832869:DUP",
      "transcript": null,
      "protein": null,
      "carrier_count": 34,
      "uri": "hnf1b://variant/var:HNF1B:17:36459258-37832869:DUP"
    }
  ],
  "total": 0,
  "page": 1,
  "page_size": 2,
  "data_class": "curated_hnf1b_evidence",
  "meta": {
    "response_mode": "compact",
    "effective_chars": 0,
    "elapsed_ms": 33.4
  }
}
```

### hnf1b_search(query=nephropathy, limit=3)
```json
{
  "query": "nephropathy",
  "hits": [
    {
      "type": "publication",
      "id": "pub_PMID:22583611",
      "label": "A complex microdeletion 17q12 phenotype in a patient with recurrent de novo membranous nephropathy.",
      "uri": "hnf1b://publication/PMID:22583611"
    },
    {
      "type": "publication",
      "id": "pub_PMID:14583183",
      "label": "Genetic variants of hepatocyte nuclear factor-1beta in Chinese young-onset diabetic patients with nephropathy.",
      "uri": "hnf1b://publication/PMID:14583183"
    },
    {
      "type": "publication",
      "id": "pub_PMID:12675839",
      "label": "Atypical familial juvenile hyperuricemic nephropathy associated with a hepatocyte nuclear factor-1beta gene mutation.",
      "uri": "hnf1b://publication/PMID:12675839"
    }
  ],
  "counts": {
    "publication": 3
  },
  "guidance": "Call hnf1b_get_individual / hnf1b_get_variant / hnf1b_get_publications for authoritative content.",
  "data_class": "operational_metadata",
  "meta": {
    "response_mode": "compact",
    "effective_chars": 0,
    "elapsed_ms": 4.1
  }
}
```

### hnf1b_get_gene_context() [trimmed]
```json
{
  "gene": {
    "id": "a09c8191-b0d5-4828-af87-042ddd7de013",
    "symbol": "HNF1B",
    "name": "HNF1 homeobox B [Source:HGNC Symbol;Acc:HGNC:11630]",
    "chromosome": "17",
    "start": 37686431,
    "end": 37745091,
    "strand": "-",
    "ensembl_id": "ENSG00000275410",
    "ncbi_gene_id": null,
    "hgnc_id": null,
    "omim_id": null,
    "source": "Ensembl REST API",
    "source_version": "GRCh38",
    "source_url": null,
    "extra_data": {
      "biotype": "protein_coding",
      "version": 7
    },
    "created_at": "2026-04-17T09:48:44.742052Z",
    "updated_at": "2026-04-17T09:48:44.742052Z",
    "transcripts": []
  },
  "uri": "hnf1b://gene/HNF1B",
  "data_class": "external_reference_identifier"
}
```

### hnf1b_get_publications(page_size=2)
```json
{
  "publications": [
    {
      "pmid": "",
      "recommended_citation": " (publication date unverified)",
      "date_confidence": "unverified",
      "journal": null,
      "year": null,
      "phenopacket_count": null,
      "uri": "hnf1b://publication/PMID:"
    },
    {
      "pmid": "",
      "recommended_citation": " (publication date unverified)",
      "date_confidence": "unverified",
      "journal": null,
      "year": null,
      "phenopacket_count": null,
      "uri": "hnf1b://publication/PMID:"
    }
  ],
  "total": 2,
  "page": {
    "currentPage": 1,
    "pageSize": 2,
    "totalPages": 69,
    "totalRecords": 138
  },
  "page_size": 2,
  "data_class": "curated_hnf1b_evidence",
  "meta": {
    "response_mode": "compact",
    "effective_chars": 0,
    "elapsed_ms": 23.7
  }
}
```

_Note: no denied/side-effecting endpoint (/metadata, /admin, /auth) is reachable — enforced by the code allowlist._
