# HNF1B-db Schema Overview

## Purpose

This document is a domain primer for the HNF1B-db MCP server. It describes the
key clinical and genomic concepts underpinning the database and explains the data
model that the MCP tools expose. Read this document before constructing complex
queries; it prevents common mistakes and improves result quality.

## What Is an "Individual" / Phenopacket?

An **individual** in HNF1B-db corresponds to a single patient record encoded
following the GA4GH Phenopacket Schema (v2). Each record bundles together:

- **Subject metadata** — anonymised identifiers, sex, and age of onset.
- **Phenotypic features** — a set of HPO (Human Phenotype Ontology) term IDs
  that describe observed and excluded clinical findings. In v1 of this API, HPO
  term IDs are supplied directly by the caller; the server does not perform
  free-text HPO lookup or proxy the OLS HPO API.
- **Diseases** — OMIM/Orphanet disease identifiers associated with the subject,
  derived from curated interpretation.
- **Interpretations** — one or more variant interpretations linking the subject
  to specific genomic variants with an ACMG pathogenicity class and a clinical
  significance statement.
- **Biosamples** (optional) — tissue-level provenance when available.
- **Metadata block** — provenance, curation date, data-class tags, and citation
  information.

The root `phenopacket_id` is a stable, opaque string identifier. Use
`hnf1b_get_individual` with this ID for full detail retrieval; use
`hnf1b_search` to discover IDs by phenotype, variant, or free text.

## HNF1B Disease Spectrum

HNF1B encodes hepatocyte nuclear factor 1-beta, a transcription factor expressed
in the kidney, pancreas, liver, and genital tract. Pathogenic variants cause an
autosomal dominant disorder with substantial phenotypic variability.

### RCAD — Renal Cysts and Diabetes Syndrome

RCAD (OMIM #137920), also called **HNF1B-related disease**, is the most
common clinical presentation. Cardinal features include:

- **Renal structural anomalies** — cysts (ranging from single cysts to diffuse
  polycystic appearance), hyperechogenic kidneys, renal dysplasia, unilateral
  agenesis, and horseshoe kidney.
- **Renal functional impairment** — chronic kidney disease (CKD) with variable
  progression to end-stage renal disease.
- **Hypomagnesaemia** — caused by impaired FXYD2-mediated renal magnesium
  reabsorption; frequently detected incidentally.
- **Hyperuricaemia and gout** — reduced URAT1 expression.

### MODY5 — Maturity-Onset Diabetes of the Young, Type 5

A subset of individuals develops MODY5, a monogenic form of diabetes resulting
from HNF1B haploinsufficiency in pancreatic beta-cells. MODY5 is distinguished
from type 1/type 2 diabetes by:

- Early onset (usually before age 35).
- Autosomal dominant inheritance.
- Insulin-requiring but without autoantibodies.
- Frequent association with pancreatic exocrine insufficiency (low faecal
  elastase) and characteristic pancreatic structural changes (pancreatic
  atrophy, agenesis of dorsal pancreas).

### 17q12 Deletion Syndrome (Whole-Gene Deletion)

Approximately 50 % of individuals with pathogenic HNF1B alterations carry a
**heterozygous ~1.4 Mb microdeletion of chromosome 17q12** that removes the
entire HNF1B gene along with flanking genes (including LHX1). This contiguous
gene deletion syndrome can additionally cause:

- Neurodevelopmental features: autism spectrum disorder, intellectual
  disability, and psychiatric illness (more prevalent than with intragenic
  variants).
- Müllerian duct anomalies in females.

The 17q12 deletion is typically classified as a **copy-number variant (CNV)**
and is distinguished from intragenic sequence variants in the data model.

## Variant Types

HNF1B variants in the database fall into two broad categories:

### Intragenic Sequence Variants

Single-nucleotide variants (SNVs) and small insertions/deletions (indels)
affecting the HNF1B coding sequence or splice sites. These are represented
with HGVS notation (`hgvs_c` and `hgvs_p` fields), and include:

- **Missense variants** — amino-acid substitutions.
- **Nonsense / stop-gained variants** — premature termination codons.
- **Frameshift variants** — insertions or deletions disrupting the reading frame.
- **Splice-site variants** — variants at canonical (GT/AG) or near-canonical
  splice positions.

### Whole-Gene / Copy-Number Variants (CNVs)

The 17q12 microdeletion is the prototypical whole-gene CNV. Additional CNVs
include partial intragenic duplications and deletions detected by MLPA, array-
CGH, or chromosomal microarray. These records typically lack individual HGVS
notation and instead carry a chromosomal coordinates field and a structural
variant type.

## ACMG Pathogenicity Classes

All variant interpretations in HNF1B-db are assigned one of the five ACMG/AMP
pathogenicity classes:

| Class | Meaning |
|---|---|
| `PATHOGENIC` | Sufficient evidence to classify as causative. |
| `LIKELY_PATHOGENIC` | Strong but incomplete evidence of pathogenicity. |
| `UNCERTAIN_SIGNIFICANCE` | Evidence is ambiguous or conflicting (VUS). |
| `LIKELY_BENIGN` | Strong evidence against pathogenicity. |
| `BENIGN` | Sufficient evidence to classify as non-causative. |

The `acmg_class` field on variant records uses these exact string values.
Most clinically actionable records are `PATHOGENIC` or `LIKELY_PATHOGENIC`.

## HPO Terms in v1

In version 1 of the HNF1B-db MCP API, **HPO term resolution is the caller's
responsibility**. The server does not:

- Proxy the HPO OLS API.
- Convert free-text phenotype descriptions to HPO IDs.
- Perform fuzzy matching on term labels.

To use `hnf1b_find_individuals_by_phenotype`, supply exact HPO term IDs (e.g.
`HP:0000093` for proteinuria). Callers should resolve HPO terms through a
dedicated ontology service before querying this MCP server.

## Data Provenance and Classes

Every response carries a `data_class` field indicating provenance trust:

- `curated_hnf1b_evidence` — data manually curated from published case series.
- `curated_derived_analysis` — computed or aggregated results derived from
  curated data (statistics, cohort summaries).
- `external_reference_identifier` — stable identifiers pointing to external
  systems (HPO IDs, OMIM numbers, PubMed IDs).
- `operational_metadata` — server-internal metadata (pagination tokens,
  schema versions, timestamps).

## Research Use and Limitations

HNF1B-db and this MCP server are intended for **research use only**. The data
and tools are not validated for clinical decision support. Variant
classifications may differ from clinical laboratory reports. All retrieved text
should be treated as research evidence requiring independent expert verification.
