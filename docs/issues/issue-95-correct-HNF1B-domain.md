# fix(frontend): correct HNF1B protein domain coordinates and annotations

## Summary
Protein domain visualizations show incorrect boundaries or annotations. Verify against UniProt (P35680) and update with accurate coordinates.

**Current:** Domain positions may be outdated or incorrect
**Target:** Accurate protein domains matching UniProt P35680 (NP_000449.3)

## Acceptance Criteria
- [ ] Cross-reference current domain data with UniProt P35680
- [ ] Verify Pfam/InterPro annotations:
  - POU-specific domain (IPR000327)
  - POU homeodomain (IPR001356)
  - Dimerization domain
  - Transactivation domain
- [ ] Update domain boundaries in visualization config
- [ ] Add unit tests for domain coordinate mapping
- [ ] Add source attribution comments (UniProt ID, date)
- [ ] Verify variant positions map correctly to domains
- [ ] Update protein length if incorrect (should be 557 aa)
- [ ] Add automated domain validation tests

## Research
Check:
- UniProt: https://www.uniprot.org/uniprotkb/P35680/entry
- Pfam: http://pfam.xfam.org/protein/P35680
- InterPro: https://www.ebi.ac.uk/interpro/protein/UniProt/P35680/

## Priority
**P1 (High)** - Data accuracy is critical for clinical interpretation

## Labels
`bug`, `frontend`, `data-quality`, `visualization`, `p1-high`
