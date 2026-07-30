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
curator's real intent, exactly the T7-T11/T9 shape.

Unlike ``MORPHOLOGY_TERM_LABELS`` and ``HPOMapper.hpo_mappings``, the fields
on ``HPOTermsConfig`` are plain ``List[str]``/``str`` -- there is no runtime
``{id: label}`` object to import and iterate. ``HPO_TERMS_CONFIG_LABELS``
below is therefore a hand-maintained mirror of every inline ``# label``
comment in ``app/core/config.py``'s ``HPOTermsConfig`` class body, verified
against the live source via a mechanical AST + comment extraction pass
during the T12/T13 fix (every id/label pair the extractor found was folded
in here; nothing was hand-picked). If a future edit to config.py adds a term
without updating this dict, ``test_every_hpo_terms_config_id_is_reachable``
below catches the drift.

``mody`` (``HP:0004904``) carries no inline label comment in config.py, so
there is nothing to check it against here; its correctness was not in
question for this task.
"""

from app.core.config import HPOTermsConfig, settings
from app.ontology.conformance import check_label

# Mirrors every ``# label`` comment on an HPO/ORPHA id literal inside
# HPOTermsConfig, deduplicated by (id, label) -- the same id can carry
# different-but-consistent wording across sibling lists (e.g. any_kidney's
# "Stage 4 chronic kidney disease" vs a since-aligned scalar alias), and
# both forms are checked independently.
HPO_TERMS_CONFIG_LABELS: dict[str, str] = {
    "HP:0000003": "Multicystic kidney dysplasia",
    "HP:0000122": "Unilateral renal agenesis",
    "HP:0000089": "Renal hypoplasia",
    "HP:0012210": "Abnormal renal morphology",
    "HP:0000078": "Abnormality of the genital system",
    "HP:0012622": "Chronic kidney disease (unspecified)",
    "HP:0012623": "Stage 1 chronic kidney disease",
    "HP:0012624": "Stage 2 chronic kidney disease",
    "HP:0012625": "Stage 3 chronic kidney disease",
    "HP:0012626": "Stage 4 chronic kidney disease",
    "HP:0003774": "Stage 5 chronic kidney disease",
    "HP:0000107": "Renal cyst",
    "HP:0033133": "Renal cortical hypoechogeneity",
    "HP:0100611": "Multiple glomerular cysts",
    "ORPHA:2260": "Oligomeganephronia",
}


def test_hpo_terms_config_labels_are_conformant():
    """Every id/label pair mirrored from HPOTermsConfig is A3-conformant.

    A genuine wrong-identifier defect (the T12/T13 shape this test guards
    against, e.g. `HP:0000108` labelled "Multiple glomerular cysts") fails
    with a *label mismatch* message naming the pinned snapshot's actual
    canonical name/synonyms for that id. There is no snapshot-coverage gap
    to document here: `HP:0100611` and `ORPHA:2260` were both already in the
    pinned snapshot before this fix landed, so no snapshot refresh was
    required.
    """
    violations = {
        term_id: violation
        for term_id, label in HPO_TERMS_CONFIG_LABELS.items()
        if (violation := check_label(term_id, label)) is not None
    }
    assert not violations, violations


def test_every_hpo_terms_config_id_is_reachable():
    """Every id actually present in HPOTermsConfig's fields is covered above.

    Guards against config.py drift: a new id added to any list/scalar field
    without a matching entry in ``HPO_TERMS_CONFIG_LABELS`` would silently
    escape ``test_hpo_terms_config_labels_are_conformant`` above. ``mody``
    is excluded deliberately -- see the module docstring.
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

    uncovered = all_ids - HPO_TERMS_CONFIG_LABELS.keys()
    assert not uncovered, (
        f"HPOTermsConfig ids without a HPO_TERMS_CONFIG_LABELS entry: "
        f"{uncovered}. Add the id's intended label to the dict above (and "
        "verify it with check_label) rather than leaving it unchecked."
    )


def test_any_kidney_no_longer_uses_the_wrong_glomerular_cyst_or_oligomeganephronia_ids():
    """Regression fence for the T12/T13 defect.

    `HP:0000108` denotes "Renal corticomedullary cysts", not "Multiple
    glomerular cysts", and `HP:0001970` denotes "Tubulointerstitial
    nephritis", not "Oligomeganephronia". Both appeared in zero stored
    records; the corpus stores the intended concepts as `HP:0100611` (103
    features) and `ORPHA:2260` (75 features). Any filter built on
    `any_kidney` with the wrong ids silently excluded all 178 of those
    stored feature rows.
    """
    any_kidney = settings.hpo_terms.any_kidney
    assert "HP:0000108" not in any_kidney
    assert "HP:0001970" not in any_kidney
    assert "HP:0100611" in any_kidney
    assert "ORPHA:2260" in any_kidney
