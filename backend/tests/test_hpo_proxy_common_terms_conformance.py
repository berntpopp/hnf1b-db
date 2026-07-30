"""Ontology conformance for ``app.hpo_proxy.COMMON_HPO_TERMS`` (spec §3.3).

The eighth hardcoded ontology map found while auditing this branch
(2026-07-30): ``GET /api/v2/hpo/common-terms`` serves 14 hardcoded
``{id, label}`` pairs directly to phenotype selectors. All 14 were already
correct, but -- unlike ``ADDITIONAL_TERMS``
(``test_ontology_service_hardcoded_terms_are_conformant``,
test_ontology_conformance.py) and ``HPOMapper.hpo_mappings``
(``test_hpo_mapper_fallback_is_conformant``, same file) -- nothing swept it,
so a future plausible-but-wrong id would have shipped silently. Hoisted to a
module-level constant (``COMMON_HPO_TERMS`` in ``app/hpo_proxy.py``)
specifically so this test can import and check every entry, rather than a
dict built inline inside the endpoint function body -- the same reason
``ADDITIONAL_TERMS`` is a module constant (see
test_ontology_conformance.py's docstring).
"""

from app.hpo_proxy import COMMON_HPO_TERMS
from app.ontology.conformance import check_label


def test_common_hpo_terms_are_conformant():
    """Every (id, label) pair served by GET /common-terms is A3-conformant.

    A genuine wrong-identifier defect here (a plausible-but-wrong id, the
    same shape as the T7-T13 defects elsewhere in this codebase) fails with
    a label-mismatch message naming the pinned snapshot's actual canonical
    name/synonyms for that id.
    """
    violations = {}
    for category, terms in COMMON_HPO_TERMS.items():
        for term in terms:
            violation = check_label(term["id"], term["label"])
            if violation is not None:
                violations[(category, term["id"], term["label"])] = violation
    assert not violations, violations


def test_common_hpo_terms_has_the_expected_three_categories_and_fourteen_entries():
    """Guards the shape this conformance sweep assumes, not just its content."""
    assert set(COMMON_HPO_TERMS) == {"renal", "metabolic", "developmental"}
    total = sum(len(terms) for terms in COMMON_HPO_TERMS.values())
    assert total == 14
