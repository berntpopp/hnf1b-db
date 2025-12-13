# Implementation Plan: Protein Domain Comparison for Kaplan-Meier Survival Analysis

**Issue**: [#155](https://github.com/berntpopp/hnf1b-db/issues/155)
**Priority**: Low (Priority 3)
**Labels**: Enhancement, Backend, Frontend, Data Visualization

---

## Overview

Add a new survival analysis comparison type that stratifies HNF1B variants by protein functional domain location. This enables clinicians to compare renal survival outcomes between patients with variants affecting different protein regions.

### Key Constraint

**Missense variants only** - This analysis requires amino acid position information from HGVS.p notation, which is only meaningful for missense (non-truncating) variants. CNVs, large deletions, and truncating variants are excluded.

---

## HNF1B Protein Domain Structure

Based on UniProt [P35680](https://www.uniprot.org/uniprotkb/P35680/entry) and published literature:

| Domain | Amino Acid Range | Function |
|--------|-----------------|----------|
| **Dimerization** | 1-32 | Homo/heterodimerization with HNF1A |
| **POU-S** | 90-173 | POU-specific DNA binding domain |
| **Linker** | 174-231 | Flexible region between POU domains |
| **POU-H** | 232-305 | POU-homeodomain for DNA binding |
| **TAD** | 314-557 | C-terminal transactivation domain |

**References:**
- [HNF1B Transcription Factor: Key Regulator in Renal Physiology and Pathogenesis](https://www.mdpi.com/1422-0067/25/19/10609)
- [Hepatocyte nuclear factor 1 beta: A perspective in cancer](https://pmc.ncbi.nlm.nih.gov/articles/PMC7940219/)
- [POU Domain Mutations in HNF1A](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5391926/)

---

## Architecture Overview

### Existing Patterns (Reuse for DRY)

The codebase already implements survival analysis handlers using the **Strategy Pattern**:

```
survival_handlers.py
├── SurvivalHandler (ABC)          # Abstract base class
├── VariantTypeHandler             # CNV vs Truncating vs Non-truncating
├── PathogenicityHandler           # P/LP vs VUS
├── DiseaseSubtypeHandler          # CAKUT vs CAKUT/MODY vs MODY vs Other
└── SurvivalHandlerFactory         # Factory for handler instantiation
```

**Key SQL fragments to reuse** (`sql_fragments.py`):
- `CURRENT_AGE_PATH` - Subject age extraction
- `INTERP_STATUS_PATH` - Pathogenicity status filtering
- `VD_EXPRESSIONS` - Variant expressions JSONB path

**Existing domain filtering logic** (`variant_query_builder.py:285-307`):
```python
def with_domain_filter(self, domain_start: int, domain_end: int):
    """Add protein domain position filter."""
    domain_clause = """EXISTS (
        SELECT 1
        FROM jsonb_array_elements(vd->'expressions') elem
        WHERE elem->>'syntax' = 'hgvs.p'
        AND (regexp_match(elem->>'value', 'p\\.[A-Z][a-z]{2}(\\d+)'))[1]::int
            BETWEEN :domain_start AND :domain_end
    )"""
```

---

## Implementation Tasks

### Phase 1: Backend - SQL Fragments (DRY)

**File**: `backend/app/phenopackets/routers/aggregations/sql_fragments.py`

Add reusable SQL fragments for protein domain analysis:

```python
# =============================================================================
# Protein Domain Constants (HNF1B)
# =============================================================================

HNF1B_PROTEIN_DOMAINS = {
    "POU-S": {"start": 90, "end": 173, "label": "POU-S (DNA Binding 1)"},
    "POU-H": {"start": 232, "end": 305, "label": "POU-H (DNA Binding 2)"},
    "TAD": {"start": 314, "end": 557, "label": "TAD (Transactivation)"},
}

# Regex for extracting amino acid position from HGVS.p notation
# Matches: p.Arg177Cys, p.Met1Val, etc.
HGVS_P_POSITION_REGEX = r"p\.[A-Z][a-z]{2}(\d+)"

# SQL to extract amino acid position from HGVS.p
AMINO_ACID_POSITION_SQL = """
(regexp_match(
    (SELECT elem->>'value'
     FROM jsonb_array_elements({vd_path}->'expressions') elem
     WHERE elem->>'syntax' = 'hgvs.p'
     LIMIT 1),
    'p\\.[A-Z][a-z]{2}(\\d+)'
))[1]::int
"""

# SQL filter for missense variants only (excludes truncating)
MISSENSE_ONLY_FILTER = """
EXISTS (
    SELECT 1
    FROM jsonb_array_elements({vd_path}->'expressions') elem
    WHERE elem->>'syntax' = 'hgvs.p'
    AND elem->>'value' ~ '^p\\.[A-Z][a-z]{2}\\d+[A-Z][a-z]{2}$'
    AND elem->>'value' !~ '(Ter|fs|\\*)'
)
"""

def get_domain_classification_sql(vd_path: str = "vd") -> str:
    """Generate SQL CASE for protein domain classification.

    Classifies missense variants into protein domains based on
    amino acid position from HGVS.p notation.

    Args:
        vd_path: Alias for variationDescriptor in query

    Returns:
        SQL CASE expression for domain classification
    """
    pos_sql = AMINO_ACID_POSITION_SQL.format(vd_path=vd_path)
    return f"""
CASE
    WHEN {pos_sql} BETWEEN 90 AND 173 THEN 'POU-S'
    WHEN {pos_sql} BETWEEN 232 AND 305 THEN 'POU-H'
    WHEN {pos_sql} BETWEEN 314 AND 557 THEN 'TAD'
    ELSE 'Other'
END
"""
```

### Phase 2: Backend - Survival Handler

**File**: `backend/app/phenopackets/routers/aggregations/survival_handlers.py`

Create new `ProteinDomainHandler` following the existing pattern:

```python
class ProteinDomainHandler(SurvivalHandler):
    """Handler for protein domain comparison (POU-S vs POU-H vs TAD vs Other).

    Stratifies missense variants by their location within HNF1B functional
    domains based on amino acid position extracted from HGVS.p notation.

    Note: Only includes missense variants with valid HGVS.p notation.
    CNVs, deletions, and truncating variants are excluded.
    """

    @property
    def comparison_type(self) -> str:
        return "protein_domain"

    @property
    def group_names(self) -> List[str]:
        return ["POU-S", "POU-H", "TAD", "Other"]

    @property
    def group_definitions(self) -> Dict[str, str]:
        return {
            "POU-S": "POU-specific domain (aa 90-173): DNA binding domain 1",
            "POU-H": "POU-homeodomain (aa 232-305): DNA binding domain 2",
            "TAD": "Transactivation domain (aa 314-557): Coactivator recruitment",
            "Other": "Variants outside defined domains or with unclassified position",
        }

    def get_group_field(self) -> str:
        return "domain_group"

    def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
        return {
            "inclusion_criteria": (
                "Missense variants with valid HGVS.p notation only. "
                "Pathogenic (P) and Likely Pathogenic (LP) classification. "
                "Requires CKD assessment data."
            ),
            "exclusion_criteria": (
                "CNVs and large deletions excluded (no amino acid position). "
                "Truncating variants excluded (frameshift, nonsense, splice). "
                "VUS, Likely Benign, and Benign variants excluded."
            ),
        }
```

**Key SQL patterns** (reusing existing fragments):

```python
def build_current_age_query(self) -> str:
    domain_sql = get_domain_classification_sql("gi->'variantInterpretation'->'variationDescriptor'")
    missense_filter = MISSENSE_ONLY_FILTER.format(
        vd_path="gi->'variantInterpretation'->'variationDescriptor'"
    )

    return f"""
    WITH domain_classification AS (
        SELECT DISTINCT
            p.phenopacket_id,
            {domain_sql} AS domain_group,
            {CURRENT_AGE_PATH} as current_age,
            EXISTS (...) as has_kidney_failure
        FROM phenopackets p,
            jsonb_array_elements(p.phenopacket->'interpretations') as interp,
            jsonb_array_elements(interp->'diagnosis'->'genomicInterpretations') as gi
        WHERE p.deleted_at IS NULL
            AND {CURRENT_AGE_PATH} IS NOT NULL
            AND {INTERP_STATUS_PATH} IN ('PATHOGENIC', 'LIKELY_PATHOGENIC')
            AND {missense_filter}  -- Only missense variants
            AND gi#>>'{{variantInterpretation,variationDescriptor,id}}' !~ ':(DEL|DUP)'
    )
    SELECT domain_group, current_age, has_kidney_failure
    FROM domain_classification
    """
```

**Register in factory**:

```python
class SurvivalHandlerFactory:
    _handlers: Dict[str, type] = {
        "variant_type": VariantTypeHandler,
        "pathogenicity": PathogenicityHandler,
        "disease_subtype": DiseaseSubtypeHandler,
        "protein_domain": ProteinDomainHandler,  # NEW
    }
```

### Phase 3: Frontend - Configuration

**File**: `frontend/src/utils/aggregationConfig.js`

Add new comparison type:

```javascript
export const SURVIVAL_COMPARISON_TYPES = [
  {
    label: 'Variant Type',
    value: 'variant_type',
    description: 'Compare CNV vs Truncating vs Non-truncating variants',
  },
  {
    label: 'Pathogenicity',
    value: 'pathogenicity',
    description: 'Compare Pathogenic/Likely Pathogenic vs VUS',
  },
  {
    label: 'Disease Subtype',
    value: 'disease_subtype',
    description: 'Compare CAKUT vs CAKUT+MODY vs MODY vs Other phenotypes',
  },
  {
    label: 'Protein Domain',  // NEW
    value: 'protein_domain',
    description: 'Compare variants by HNF1B protein domain location (missense only)',
  },
];
```

### Phase 4: Frontend - Chart Update

**File**: `frontend/src/components/analyses/KaplanMeierChart.vue`

Update the `getComparisonTitle` method to include the new type:

```javascript
getComparisonTitle(comparisonType) {
  const titles = {
    variant_type: 'By Variant Type',
    pathogenicity: 'By Pathogenicity Classification',
    disease_subtype: 'By Disease Subtype',
    protein_domain: 'By Protein Domain',  // NEW
  };
  return titles[comparisonType] || comparisonType;
},
```

### Phase 5: Testing

**File**: `backend/tests/test_survival_protein_domain.py`

```python
import pytest
from app.phenopackets.routers.aggregations.survival_handlers import (
    ProteinDomainHandler,
    SurvivalHandlerFactory,
)

class TestProteinDomainHandler:
    """Tests for protein domain survival analysis handler."""

    def test_factory_registration(self):
        """Verify protein_domain handler is registered."""
        handler = SurvivalHandlerFactory.get_handler("protein_domain")
        assert isinstance(handler, ProteinDomainHandler)

    def test_group_names(self):
        """Verify correct domain groups."""
        handler = ProteinDomainHandler()
        assert handler.group_names == ["POU-S", "POU-H", "TAD", "Other"]

    def test_comparison_type(self):
        """Verify comparison type identifier."""
        handler = ProteinDomainHandler()
        assert handler.comparison_type == "protein_domain"

    @pytest.mark.parametrize("hgvs_p,expected_domain", [
        ("p.Arg137Cys", "POU-S"),    # aa 137 in POU-S (90-173)
        ("p.Arg267His", "POU-H"),    # aa 267 in POU-H (232-305)
        ("p.Gly400Ser", "TAD"),      # aa 400 in TAD (314-557)
        ("p.Met1Val", "Other"),      # aa 1 outside defined domains
    ])
    def test_domain_classification(self, hgvs_p, expected_domain):
        """Test amino acid position extraction and domain classification."""
        # Test the regex and classification logic
        import re
        match = re.search(r'p\.[A-Z][a-z]{2}(\d+)', hgvs_p)
        position = int(match.group(1))

        if 90 <= position <= 173:
            domain = "POU-S"
        elif 232 <= position <= 305:
            domain = "POU-H"
        elif 314 <= position <= 557:
            domain = "TAD"
        else:
            domain = "Other"

        assert domain == expected_domain

    def test_missense_filter_excludes_truncating(self):
        """Verify truncating variants are excluded."""
        # Truncating patterns should NOT match missense filter
        truncating_patterns = [
            "p.Arg177Ter",     # Nonsense
            "p.Arg177*",       # Stop gained
            "p.Arg177fs",      # Frameshift
            "p.Arg177Glufs*2", # Frameshift with extension
        ]
        missense_pattern = r'^p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}$'

        import re
        for pattern in truncating_patterns:
            assert not re.match(missense_pattern, pattern)

    def test_missense_filter_includes_valid(self):
        """Verify valid missense variants are included."""
        valid_missense = [
            "p.Arg177Cys",
            "p.Met1Val",
            "p.Gly400Ser",
        ]
        missense_pattern = r'^p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}$'

        import re
        for pattern in valid_missense:
            assert re.match(missense_pattern, pattern)
```

---

## API Response Schema

The endpoint will return the standard survival analysis response with domain-specific metadata:

```json
{
  "comparison_type": "protein_domain",
  "endpoint": "CKD Stage 3+ (GFR <60)",
  "groups": [
    {
      "name": "POU-S",
      "n": 45,
      "events": 12,
      "survival_data": [
        {"time": 0, "survival_probability": 1.0, "ci_lower": 1.0, "ci_upper": 1.0, "at_risk": 45, "events": 0, "censored": 0},
        {"time": 5, "survival_probability": 0.89, "ci_lower": 0.78, "ci_upper": 0.95, "at_risk": 40, "events": 4, "censored": 1}
      ]
    },
    {
      "name": "POU-H",
      "n": 32,
      "events": 15,
      "survival_data": [...]
    },
    {
      "name": "TAD",
      "n": 78,
      "events": 8,
      "survival_data": [...]
    },
    {
      "name": "Other",
      "n": 12,
      "events": 2,
      "survival_data": [...]
    }
  ],
  "statistical_tests": [
    {"group1": "POU-S", "group2": "POU-H", "chi_square": 4.23, "p_value": 0.039, "p_value_corrected": 0.234},
    {"group1": "POU-S", "group2": "TAD", "chi_square": 8.91, "p_value": 0.003, "p_value_corrected": 0.018},
    {"group1": "POU-H", "group2": "TAD", "chi_square": 6.12, "p_value": 0.013, "p_value_corrected": 0.078}
  ],
  "metadata": {
    "event_definition": "Onset of CKD Stage 3+ (GFR <60)",
    "time_axis": "Age at phenotype onset (from phenotypicFeatures.onset)",
    "censoring": "Patients without the endpoint are censored at their last reported age",
    "group_definitions": {
      "POU-S": "POU-specific domain (aa 90-173): DNA binding domain 1",
      "POU-H": "POU-homeodomain (aa 232-305): DNA binding domain 2",
      "TAD": "Transactivation domain (aa 314-557): Coactivator recruitment",
      "Other": "Variants outside defined domains or with unclassified position"
    },
    "inclusion_criteria": "Missense variants with valid HGVS.p notation only...",
    "exclusion_criteria": "CNVs and large deletions excluded...",
    "domain_boundaries": {
      "POU-S": {"start": 90, "end": 173},
      "POU-H": {"start": 232, "end": 305},
      "TAD": {"start": 314, "end": 557}
    },
    "references": [
      "UniProt P35680",
      "doi:10.3390/ijms251910609"
    ]
  }
}
```

---

## Best Practices Applied

### SOLID Principles

1. **Single Responsibility**: `ProteinDomainHandler` only handles domain-based classification
2. **Open/Closed**: Extends `SurvivalHandler` without modifying base class
3. **Liskov Substitution**: Handler is interchangeable with other survival handlers
4. **Interface Segregation**: Uses same abstract interface as other handlers
5. **Dependency Inversion**: Depends on abstractions (`SurvivalHandler` ABC)

### DRY (Don't Repeat Yourself)

- Reuses `CURRENT_AGE_PATH`, `INTERP_STATUS_PATH` from `sql_fragments.py`
- Reuses missense filter pattern from `variant_query_builder.py`
- Reuses Kaplan-Meier calculation from `survival_analysis.py`
- Reuses log-rank test with Bonferroni correction

### KISS (Keep It Simple)

- Single SQL query per method (no nested complexity)
- Clear domain boundary constants
- Straightforward regex for position extraction

### Kaplan-Meier Best Practices

Based on [Kaplan-Meier Survival Analysis: Practical Insights for Clinicians](https://pubmed.ncbi.nlm.nih.gov/38631048/):

- Use `d3.curveStepAfter` for proper step function visualization
- Include 95% confidence intervals
- Apply Bonferroni correction for multiple comparisons
- Stratify by homogeneous subgroups (protein domains)
- Report number at risk at each time point

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/app/phenopackets/routers/aggregations/sql_fragments.py` | Modify | Add domain constants and SQL helpers |
| `backend/app/phenopackets/routers/aggregations/survival_handlers.py` | Modify | Add `ProteinDomainHandler` class |
| `frontend/src/utils/aggregationConfig.js` | Modify | Add protein_domain to comparison types |
| `frontend/src/components/analyses/KaplanMeierChart.vue` | Modify | Add title mapping for new type |
| `backend/tests/test_survival_protein_domain.py` | Create | Unit tests for domain handler |

---

## Acceptance Criteria

- [ ] "Protein Domain" option visible in survival comparison dropdown
- [ ] Only missense variants included (CNVs/truncating excluded)
- [ ] Correct domain classification based on amino acid position
- [ ] Up to 4 Kaplan-Meier curves (POU-S, POU-H, TAD, Other)
- [ ] Log-rank statistical tests between all group pairs
- [ ] Bonferroni-corrected p-values
- [ ] API metadata includes domain boundaries and references
- [ ] All existing tests pass
- [ ] New unit tests for domain handler pass
- [ ] `make check` passes in both backend and frontend

---

## References

- [Kaplan-Meier Survival Analysis: Practical Insights](https://pubmed.ncbi.nlm.nih.gov/38631048/)
- [HNF1B Transcription Factor Review](https://www.mdpi.com/1422-0067/25/19/10609)
- [UniProt P35680 - HNF1B Human](https://www.uniprot.org/uniprotkb/P35680/entry)
- [D3.js curveStepAfter Documentation](https://github.com/d3/d3/blob/main/docs/d3-shape/curve.md)
- [TRGAted: Protein Survival Analysis Tool](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6173115/)
