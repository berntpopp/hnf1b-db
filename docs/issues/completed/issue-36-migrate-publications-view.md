# Issue #36: feat(frontend): migrate publications view to external references

## Overview

Publications view needs migration from separate publications table to extract PMIDs from `phenopacket.metaData.externalReferences[]`.

**Current:** `/publications` → Shows publications table (404)
**Target:** `/publications` → Display publications aggregated from phenopackets

## Data Extraction

Publications are in:
```javascript
phenopacket.metaData.externalReferences: [
  {
    id: "PMID:30791938",
    reference: "https://pubmed.ncbi.nlm.nih.gov/30791938",
    description: "DOI:10.1186/s13052-019-0617-y"
  }
]
```

## Required Endpoint (Backend)

```http
GET /api/v2/phenopackets/aggregate/publications

Response:
[
  {
    pmid: "PMID:30791938",
    url: "https://pubmed.ncbi.nlm.nih.gov/30791938",
    doi: "10.1186/s13052-019-0617-y",
    phenopacket_count: 45,
    first_added: "2024-01-01T00:00:00Z"
  }
]
```

## Table Structure

| Column | Source | Sortable |
|--------|--------|----------|
| PMID | `pmid` | Yes |
| DOI | `doi` | Yes |
| Individuals | `phenopacket_count` | Yes |
| Added | `first_added` | Yes |

## Implementation Checklist

- [ ] Backend: Create `/aggregate/publications` endpoint
- [ ] API: Add `getPublicationsAggregation()`
- [ ] View: Update Publications.vue table
- [ ] Add PMID links to PubMed
- [ ] Add DOI links
- [ ] Make phenopacket count clickable

## Acceptance Criteria

- [ ] Table displays all publications
- [ ] PMID links to PubMed
- [ ] DOI links work
- [ ] Shows phenopacket count per publication
- [ ] Clicking count filters phenopackets list

## Dependencies

**Depends On:** #30 (API client)
**Blocks:** #37 (Publication detail), #43 (Timeline)

## Timeline

8 hours (1 day)

## Labels

`frontend`, `views`, `phenopackets`, `p1`
