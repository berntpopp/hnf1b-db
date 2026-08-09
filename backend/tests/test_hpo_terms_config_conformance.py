"""Ontology conformance for ``HPOTermsConfig`` (spec §3.3).

The sixth independent hardcoded ontology map documented in
docs/ontology-defect-report-2026-07-30.md §2 (T12, T13) -- found by running
the same `check_label` sweep already applied to `MORPHOLOGY_TERM_LABELS`
(test_clinical_queries_morphology.py, the fifth map) and `HPOMapper`'s
fallback dict (test_ontology_conformance.py, T7-T11) against every entry in
``app.core.config.HPOTermsConfig``.

``any_kidney`` listed ``HP:0000108`` as "Multiple glomerular cysts" and
``HP:0001970`` as "Oligomeganephronia". Both ids denote something else
entirely -- ``HP:0000108`` is "Renal corticomedullary cysts" and
``HP:0001970`` is "Tubulointerstitial nephritis" -- and both appear in zero
stored records. The corpus stores the intended concepts as ``HP:0100611``
(103 features) and ``ORPHA:2260`` (75 features); the label was always the
curator's real intent, exactly the T7-T11/T9 shape. Commit 83b3868 fixed
those two but left a seventh: ``any_kidney`` also listed ``HP:0033133``
("Renal cortical hypoechogeneity") -- the exact id the sibling
HP:0033133->HP:0033132 data migration (ca9950e) established was wrong,
appearing in zero stored records while the corpus carries 460 occurrences of
HP:0033132 ("Renal cortical hyperechogenicity", the correct, characteristic
HNF1B finding).

That seventh defect survived specifically *because* the previous version of
this file hardcoded its own ``HPO_TERMS_CONFIG_LABELS`` mirror of
config.py's inline ``# label`` comments, rather than reading them from the
live source: ``"HP:0033133": "Renal cortical hypoechogeneity"`` passed
``check_label`` cleanly, because that mirror entry's label agreed with
config.py's inline comment, which itself had already been normalised to the
wrong id's own canonical name -- the exact A3 bypass ``conformance.py``
documents (a label edited to agree with whatever identifier is already
stored proves nothing about whether the identifier is right). A
hand-maintained copy of the data cannot catch a defect in the data it was
copied from; it can only agree with it. So this module now extracts the
``(id, label)`` pairs directly from ``app/core/config.py``'s source via an
AST + trailing-comment pass at test time -- the same mechanical pass
mentioned in the original docstring, but now run by the test itself instead
of hand-transcribed once and left to drift.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.core.config import HPOTermsConfig, settings
from app.ontology.conformance import check_label

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "core" / "config.py"


def _extract_hpo_terms_config_id_label_pairs() -> set[tuple[str, str]]:
    """AST-parse the live ``app/core/config.py`` and pull every
    ``"HP:..."``/``"ORPHA:..."`` string literal inside the ``HPOTermsConfig``
    class body, paired with whatever trailing ``# ...`` comment sits on the
    same source line.

    Deduplicated by ``(id, label)`` -- the same id can legitimately carry
    different-but-consistent wording across sibling lists (e.g.
    ``HP:0012622``'s "Chronic kidney disease (unspecified)" in ``any_kidney``
    vs. the identical wording on its ``chronic_kidney_disease`` scalar
    alias), and both forms are checked independently.

    Reads the real file on disk, not a copy, so a future edit to
    ``HPOTermsConfig`` (a new id, a changed comment, a moved list) is picked
    up automatically the next time this test runs -- there is nothing here
    to fall out of sync.
    """
    source = _CONFIG_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_CONFIG_PATH))

    class_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "HPOTermsConfig"
    )

    lines = source.splitlines()
    pairs: set[tuple[str, str]] = set()

    for node in ast.walk(class_node):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value
        if not (value.startswith("HP:") or value.startswith("ORPHA:")):
            continue
        line = lines[node.lineno - 1]
        if "#" not in line:
            continue
        comment = line.split("#", 1)[1].strip()
        if comment:
            pairs.add((value, comment))

    return pairs


def test_hpo_terms_config_labels_are_conformant():
    """Every id/label pair actually present in ``HPOTermsConfig``'s live
    source is A3-conformant.

    Unlike the prior version of this test, ``HPO_TERMS_CONFIG_LABELS`` is
    gone: the pairs checked here come from
    ``_extract_hpo_terms_config_id_label_pairs``, which reads
    ``app/core/config.py`` itself. A genuine wrong-identifier defect (the
    T12/T13/H1 shape, e.g. an id whose inline comment was normalised to that
    id's own canonical name while the intended concept lives at a different
    id) fails with a *label mismatch* message naming the pinned snapshot's
    actual canonical name/synonyms for that id.
    """
    pairs = _extract_hpo_terms_config_id_label_pairs()
    assert pairs, (
        "AST extraction found no HPOTermsConfig id/label pairs -- extractor is broken"
    )

    violations = {
        (term_id, label): violation
        for term_id, label in pairs
        if (violation := check_label(term_id, label)) is not None
    }
    assert not violations, violations


def test_every_hpo_terms_config_id_is_reachable():
    """Every id actually present in HPOTermsConfig's runtime fields has at
    least one commented occurrence in the source that the extractor above
    would have swept.

    Guards against a value that carries no inline ``# label`` comment
    anywhere in the class body -- such an id would silently escape
    ``test_hpo_terms_config_labels_are_conformant`` because the extractor
    has nothing to pair it with. ``mody`` is excluded deliberately: it
    carries no inline label comment in config.py, so there is nothing to
    check it against; its correctness was not in question for this task.
    """
    cfg = HPOTermsConfig()
    all_ids: set[str] = set()
    for field in (
        cfg.cakut,
        cfg.any_kidney,
        cfg.ckd_stages,
        cfg.kidney_failure,
        cfg.ckd_stage_3_plus,
        cfg.stage_5_ckd,
    ):
        all_ids.update(field)
    all_ids.update(
        {cfg.genital, cfg.chronic_kidney_disease, cfg.ckd_stage_4, cfg.ckd_stage_5}
    )
    all_ids.discard(cfg.mody)

    covered_ids = {
        term_id for term_id, _label in _extract_hpo_terms_config_id_label_pairs()
    }
    uncovered = all_ids - covered_ids
    assert not uncovered, (
        f"HPOTermsConfig ids with no inline '# label' comment anywhere in "
        f"the source: {uncovered}. Add one so the AST sweep above can check "
        "it, rather than leaving it unchecked."
    )


def test_any_kidney_no_longer_uses_the_wrong_glomerular_cyst_oligomeganephronia_or_echogenicity_ids():
    """Regression fence for the T12/T13/H1 defects.

    `HP:0000108` denotes "Renal corticomedullary cysts", not "Multiple
    glomerular cysts", and `HP:0001970` denotes "Tubulointerstitial
    nephritis", not "Oligomeganephronia" -- both appeared in zero stored
    records (T12/T13, fixed by commit 83b3868). `HP:0033133` denotes "Renal
    cortical hypoechogeneity", the retired id the sibling data migration
    (ca9950e) rewrote to `HP:0033132` "Renal cortical hyperechogenicity" in
    all 460 stored occurrences after finding the corpus meant the opposite
    ultrasound finding (H1). The corpus stores the intended concepts as
    `HP:0100611` (103 features), `ORPHA:2260` (75 features), and `HP:0033132`
    (460 features). Any filter built on `any_kidney` with the wrong ids
    silently excluded all of those stored feature rows.
    """
    any_kidney = settings.hpo_terms.any_kidney
    assert "HP:0000108" not in any_kidney
    assert "HP:0001970" not in any_kidney
    assert "HP:0033133" not in any_kidney
    assert "HP:0100611" in any_kidney
    assert "ORPHA:2260" in any_kidney
    assert "HP:0033132" in any_kidney
