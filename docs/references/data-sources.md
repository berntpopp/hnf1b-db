# Reference Genome Data Sources

Authoritative data sources and citations for genomic annotations.

**Last Updated:** 2025-01-18

---

## Table of Contents

- [Overview](#overview)
- [Primary Data Sources](#primary-data-sources)
  - [Gene Annotations](#gene-annotations)
  - [Protein Domains](#protein-domains)
  - [Transcripts and Exons](#transcripts-and-exons)
  - [Genome Assemblies](#genome-assemblies)
- [Data Verification](#data-verification)
- [Update Schedule](#update-schedule)
- [Citations](#citations)

---

## Overview

All genomic reference data in the HNF1B Database is sourced from authoritative public databases. This document provides:

- **Source URLs** for all annotations
- **Verification dates** for data accuracy
- **Update schedules** for maintaining current data
- **Citations** for publications and databases

**Data Integrity Principles:**
1. **Single Source of Truth** - Database is authoritative, no frontend duplication
2. **Provenance Tracking** - All records include `source`, `source_version`, `source_url`
3. **Cross-Verification** - Data cross-referenced with multiple databases
4. **Audit Trail** - Timestamps track when annotations were added/updated

---

## Primary Data Sources

### Gene Annotations

#### HNF1B Gene (HGNC:11630)

**Primary Source:** NCBI Gene
- **Gene ID:** 6928
- **URL:** https://www.ncbi.nlm.nih.gov/gene/6928
- **Coordinates (GRCh38):** chr17:36,098,063-36,112,306
- **Coordinates (GRCh37):** chr17:37,686,430-37,745,059
- **Last Verified:** 2025-01-17

**Alternative IDs:**
- **HGNC ID:** HGNC:11630
- **Ensembl ID:** ENSG00000275410
- **OMIM ID:** 189907
- **Aliases:** TCF2, MODY5

**Cross-References:**
- **Ensembl:** https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG00000275410
- **UCSC Genome Browser:** https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38&position=chr17:36098063-36112306
- **GeneCards:** https://www.genecards.org/cgi-bin/carddisp.pl?gene=HNF1B

#### chr17q12 Region Genes

**Data Source:** Manual curation from multiple sources
- **Genes:** 29 genes in 17q12 deletion syndrome region
- **Region (GRCh38):** chr17:36,000,000-39,900,000 (3.9 Mb)
- **File:** `frontend/src/data/chr17q12_genes.json`
- **Last Updated:** 2025-01

**Sources for Each Gene:**
- NCBI Gene: https://www.ncbi.nlm.nih.gov/gene/
- OMIM: https://www.omim.org/
- DECIPHER: https://www.deciphergenomics.org/syndrome/80

**Critical Genes in Region:**
- **HNF1B** (189907) - Transcription factor, MODY5
- **LHX1** (612302) - LIM homeobox 1
- **ACACA** (200350) - Acetyl-CoA carboxylase alpha
- **ERBB2** (164870) - Erb-b2 receptor tyrosine kinase 2

---

### Protein Domains

#### HNF1B Protein (UniProt P35680)

**Primary Source:** UniProt
- **Accession:** P35680
- **URL:** https://www.uniprot.org/uniprotkb/P35680/entry
- **Protein Length:** 557 amino acids
- **Last Verified:** 2025-01-17

**Domains:**

| Domain | Start | End | Length | Source Database |
|--------|-------|-----|--------|-----------------|
| Dimerization Domain | 1 | 31 | 31 aa | UniProt |
| POU-Specific Domain | 8 | 173 | 166 aa | Pfam PF00157, InterPro IPR000327 |
| POU Homeodomain | 232 | 305 | 74 aa | InterPro IPR001356 |
| Transactivation Domain | 314 | 557 | 244 aa | UniProt |

**Pfam Domains:**
- **POU-Specific Domain:** PF00157
- **URL:** http://pfam.xfam.org/family/PF00157

**InterPro Domains:**
- **POU-Specific Domain:** IPR000327
- **POU Homeodomain:** IPR001356
- **URL:** https://www.ebi.ac.uk/interpro/

**Functional Information:**
- **DNA Binding:** POU-Specific + POU Homeodomain work together
- **Dimerization:** Forms homodimers or heterodimers with HNF1A
- **Transactivation:** C-terminal domain recruits transcriptional machinery

---

### Transcripts and Exons

#### Canonical Transcript: NM_000458.4

**Primary Source:** NCBI RefSeq
- **Transcript ID:** NM_000458.4
- **Protein ID:** NP_000449.3
- **URL:** https://www.ncbi.nlm.nih.gov/nuccore/NM_000458.4
- **Status:** MANE Select (Matched Annotation from NCBI and EMBL-EBI)
- **Last Verified:** 2025-01-17

**Exon Structure:**
- **Exon Count:** 9 exons
- **CDS:** 1,674 bp (558 codons)
- **5' UTR:** Exon 1
- **3' UTR:** Exon 9

**Exon Coordinates (GRCh38, chr17, minus strand):**

| Exon | Start | End | Size | Domain |
|------|-------|-----|------|--------|
| 1 | 36,098,063 | 36,098,372 | 309 bp | 5' UTR |
| 2 | 36,099,035 | 36,099,371 | 336 bp | Dimerization |
| 3 | 36,102,283 | 36,102,437 | 154 bp | POU-S |
| 4 | 36,103,407 | 36,103,619 | 212 bp | POU-S |
| 5 | 36,104,458 | 36,104,588 | 130 bp | POU-H |
| 6 | 36,105,361 | 36,105,505 | 144 bp | POU-H |
| 7 | 36,106,626 | 36,106,784 | 158 bp | Transactivation |
| 8 | 36,108,060 | 36,108,311 | 251 bp | Transactivation |
| 9 | 36,111,731 | 36,112,306 | 575 bp | 3' UTR |

**Cross-References:**
- **Ensembl:** ENST00000617300.4
- **UCSC:** NM_000458.4 (RefSeq Genes track)

---

### Genome Assemblies

#### GRCh38 / hg38 (Current Reference)

**Primary Source:** Genome Reference Consortium (GRC)
- **Assembly Name:** GRCh38.p14
- **UCSC Name:** hg38
- **NCBI Name:** GCA_000001405.28
- **Release Date:** December 21, 2017
- **URL:** https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.40/

**Key Features:**
- **Chromosomes:** 22 autosomes + X + Y + MT
- **Patches:** p14 (patch release 14)
- **Alternate Loci:** Yes (for complex regions)

**Download:**
- **FASTA:** ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.28_GRCh38.p14/

#### GRCh37 / hg19 (Legacy Reference)

**Primary Source:** Genome Reference Consortium (GRC)
- **Assembly Name:** GRCh37.p13
- **UCSC Name:** hg19
- **NCBI Name:** GCA_000001405.14
- **Release Date:** February 27, 2009
- **URL:** https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.25/

**Usage:**
- Legacy assembly for backward compatibility
- Many published variants use GRCh37 coordinates
- Liftover tools can convert between GRCh37 and GRCh38

**Download:**
- **FASTA:** ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.14_GRCh37.p13/

---

## Data Verification

### Verification Process

All genomic annotations are cross-verified with at least two independent sources:

1. **Gene Coordinates:**
   - Primary: NCBI Gene
   - Verify: Ensembl, UCSC Genome Browser
   - Check: Chromosome, start, end, strand

2. **Protein Domains:**
   - Primary: UniProt
   - Verify: Pfam, InterPro
   - Check: Domain boundaries, function

3. **Transcripts:**
   - Primary: NCBI RefSeq
   - Verify: Ensembl, MANE Select
   - Check: Exon count, CDS boundaries

### Discrepancy Resolution

If sources disagree:
1. **Prefer MANE Select** for canonical transcripts
2. **Prefer UniProt** for protein domains (manually curated)
3. **Prefer NCBI Gene** for gene coordinates (authoritative)
4. **Document conflicts** in `extra_data` JSONB field

---

## Update Schedule

| Data Type | Check Frequency | Last Checked | Next Check |
|-----------|-----------------|--------------|------------|
| Gene coordinates | Quarterly | 2025-01-17 | 2025-04-17 |
| Protein domains | Quarterly | 2025-01-17 | 2025-04-17 |
| Transcripts | Semi-annually | 2025-01-17 | 2025-07-17 |
| Genome assemblies | Annually | 2025-01-17 | 2026-01-17 |

**Monitoring:**
- Subscribe to UniProt release notes: https://www.uniprot.org/help/release-notes
- Monitor NCBI Gene updates: https://www.ncbi.nlm.nih.gov/gene/
- Track MANE Select updates: https://www.ncbi.nlm.nih.gov/refseq/MANE/

---

## Citations

### Databases

**NCBI Gene**
> Sayers EW, Bolton EE, Brister JR, et al. Database resources of the National Center for Biotechnology Information. Nucleic Acids Research. 2024;52(D1):D33-D43. doi:10.1093/nar/gkad1044

**UniProt**
> The UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2024. Nucleic Acids Research. 2024;52(D1):D523-D531. doi:10.1093/nar/gkad1052

**Ensembl**
> Martin FJ, Amode MR, Aneja A, et al. Ensembl 2024. Nucleic Acids Research. 2024;52(D1):D891-D899. doi:10.1093/nar/gkad1049

**RefSeq**
> O'Leary NA, Wright MW, Brister JR, et al. Reference sequence (RefSeq) database at NCBI: current status, taxonomic expansion, and functional annotation. Nucleic Acids Research. 2016;44(D1):D733-D745. doi:10.1093/nar/gkv1189

**Pfam**
> Mistry J, Chuguransky S, Williams L, et al. Pfam: The protein families database in 2021. Nucleic Acids Research. 2021;49(D1):D412-D419. doi:10.1093/nar/gkaa913

**InterPro**
> Paysan-Lafosse T, Blum M, Chuguransky S, et al. InterPro in 2024. Nucleic Acids Research. 2024;52(D1):D418-D426. doi:10.1093/nar/gkad1060

**MANE (Matched Annotation from NCBI and EMBL-EBI)**
> Morales J, Pujar S, Loveland JE, et al. A joint NCBI and EMBL-EBI transcript set for clinical genomics and research. Nature. 2022;604(7905):310-315. doi:10.1038/s41586-022-04558-8

---

### HNF1B-Specific Publications

**Gene Function**
> Coffinier C, Barra J, Babinet C, Yaniv M. Expression of the vHNF1/HNF1beta homeoprotein gene during mouse organogenesis. Mechanisms of Development. 1999;89(1-2):211-213. doi:10.1016/s0925-4773(99)00221-x

**MODY5 / Renal Disease**
> Bellanne-Chantelot C, Chauveau D, Gautier JF, et al. Clinical spectrum associated with hepatocyte nuclear factor-1beta mutations. Annals of Internal Medicine. 2004;140(7):510-517. doi:10.7326/0003-4819-140-7-200404060-00009

**17q12 Deletion Syndrome**
> Mefford HC, Clauin S, Sharp AJ, et al. Recurrent reciprocal genomic rearrangements of 17q12 are associated with renal disease, diabetes, and epilepsy. American Journal of Human Genetics. 2007;81(5):1057-1069. doi:10.1086/522591

**Structural Studies**
> Baumhueter S, Mendel DB, Conley PB, et al. HNF-1 shares three sequence motifs with the POU domain proteins and is identical to LF-B1. Genes & Development. 1990;4(3):372-379. doi:10.1101/gad.4.3.372

---

### Genome Assembly References

**GRCh38**
> Schneider VA, Graves-Lindsay T, Howe K, et al. Evaluation of GRCh38 and de novo haploid genome assemblies demonstrates the enduring quality of the reference assembly. Genome Research. 2017;27(5):849-864. doi:10.1101/gr.213611.116

**GRCh37**
> Lander ES, Linton LM, Birren B, et al. Initial sequencing and analysis of the human genome. Nature. 2001;409(6822):860-921. doi:10.1038/35057062

---

## Data Attribution

When using HNF1B Database data in publications, please cite:

1. **The database itself:**
   ```
   HNF1B Database (2025). Genomic and phenotypic data for HNF1B-related disorders.
   Available at: [URL]
   ```

2. **Primary data sources** as listed above (NCBI, UniProt, etc.)

3. **Specific gene/protein entries:**
   ```
   HNF1B gene data (HGNC:11630) from NCBI Gene (Gene ID: 6928),
   retrieved 2025-01-17 via HNF1B Database.

   HNF1B protein domains from UniProt P35680,
   retrieved 2025-01-17 via HNF1B Database.
   ```

---

## Data Licenses

All reference genome data is sourced from public databases with open access policies:

- **NCBI:** Public domain (US government work)
- **UniProt:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Ensembl:** Open access (no restrictions)
- **Pfam:** Creative Commons Zero (CC0 1.0)
- **InterPro:** Open access

**HNF1B Database License:** [Specify your license here]

---

## See Also

- [API Documentation](../api/reference-genome-api.md)
- [Database Schema](../database/reference-schema.md)
- [Admin Guide: Updating Annotations](../admin/update-annotations.md)
