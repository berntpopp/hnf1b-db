"""Ontology conformance for ``frontend/src/utils/soTerms.js``'s ``SO_TERMS`` map.

The eighth hardcoded ontology map found while auditing this branch (2026-07-30):
`frontend/src/utils/soTerms.js`'s `SO_TERMS` maps VEP consequence names to
Sequence Ontology accessions and writes them straight into
`variationDescriptor.molecularConsequences[]` (see `annotate_route.py` and
`useVariantAnnotation`-style callers). Before this fix, that path was absent
from `app.ontology.conformance.ONTOLOGY_PATHS` entirely -- A3 never checked
it, so a wrong SO id/label pair could have been stored and
`ontology_preflight.py` would still report zero violations.

Unlike ``MORPHOLOGY_TERM_LABELS`` or ``HPOMapper.hpo_mappings``, ``SO_TERMS``
lives in a JS module with no Python-importable runtime object, so
``SO_TERMS_MIRROR`` below is a hand-maintained mirror of every entry in
``frontend/src/utils/soTerms.js``, kept in the same key: VEP-consequence-name
-> SO-id shape as the source. ``test_so_terms_mirror_matches_the_frontend_source``
below guards against the mirror drifting from the JS file it copies.

All 29 entries were verified live against OLS4
(`https://www.ebi.ac.uk/ols4/api/ontologies/so/terms?iri=...`, never
`/search`) on 2026-07-30: every VEP consequence key matches its SO id's live
canonical `label` exactly. No mismatches were found -- this test exists so a
*future* mismatch (e.g. a copy-paste id swap when a new consequence is added)
fails loudly instead of shipping silently, the same failure mode as the
MONDO/HPO defects this branch fixes elsewhere.
"""

import re
from pathlib import Path

from app.ontology.conformance import check_label

_SO_TERMS_JS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "src"
    / "utils"
    / "soTerms.js"
)

# Hand-maintained mirror of every entry in `frontend/src/utils/soTerms.js`'s
# `SO_TERMS` map, `{vep_consequence_name: so_id}` -- the same shape as the
# source. `check_label(so_id, vep_consequence_name)` corroborates each pair
# against the pinned ontology snapshot (A3): the VEP consequence name *is*
# SO's canonical machine name field for every one of these terms, so a
# conformant pair passes with no ``ALLOWED_DEVIATIONS`` entry needed.
SO_TERMS_MIRROR: dict[str, str] = {
    "transcript_ablation": "SO:0001893",
    "splice_acceptor_variant": "SO:0001574",
    "splice_donor_variant": "SO:0001575",
    "stop_gained": "SO:0001587",
    "frameshift_variant": "SO:0001589",
    "stop_lost": "SO:0001578",
    "start_lost": "SO:0002012",
    "transcript_amplification": "SO:0001889",
    "inframe_insertion": "SO:0001821",
    "inframe_deletion": "SO:0001822",
    "missense_variant": "SO:0001583",
    "protein_altering_variant": "SO:0001818",
    "splice_region_variant": "SO:0001630",
    "incomplete_terminal_codon_variant": "SO:0001626",
    "start_retained_variant": "SO:0002019",
    "stop_retained_variant": "SO:0001567",
    "synonymous_variant": "SO:0001819",
    "coding_sequence_variant": "SO:0001580",
    "mature_miRNA_variant": "SO:0001620",
    "5_prime_UTR_variant": "SO:0001623",
    "3_prime_UTR_variant": "SO:0001624",
    "non_coding_transcript_exon_variant": "SO:0001792",
    "intron_variant": "SO:0001627",
    "NMD_transcript_variant": "SO:0001621",
    "non_coding_transcript_variant": "SO:0001619",
    "upstream_gene_variant": "SO:0001631",
    "downstream_gene_variant": "SO:0001632",
    "intergenic_variant": "SO:0001628",
    "SNV": "SO:0001483",
}


def _parse_so_terms_js() -> dict[str, str]:
    """Extract ``{key: "SO:xxxxxxx"}`` entries from the ``SO_TERMS`` JS object literal.

    A regex, not a JS parser -- the source is a flat object literal of
    ``identifier_or_quoted_key: 'SO:...'`` pairs with no nesting or
    computed keys, so this is unambiguous and avoids a JS-parser dependency
    in the Python test suite.
    """
    text = _SO_TERMS_JS_PATH.read_text(encoding="utf-8")
    match = re.search(r"export const SO_TERMS = \{(.*?)\n\};", text, re.DOTALL)
    assert match, "could not locate the SO_TERMS object literal in soTerms.js"
    body = match.group(1)

    entries: dict[str, str] = {}
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line or line.startswith("//"):
            continue
        key_part, _, value_part = line.partition(":")
        key = key_part.strip().strip("'\"")
        value = value_part.strip().strip("'\"")
        if key and value:
            entries[key] = value
    return entries


def test_so_terms_mirror_matches_the_frontend_source():
    """SO_TERMS_MIRROR must stay in lockstep with soTerms.js, not silently drift."""
    live_from_js = _parse_so_terms_js()
    assert live_from_js == SO_TERMS_MIRROR, (
        "SO_TERMS_MIRROR in this test file is out of sync with "
        "frontend/src/utils/soTerms.js's SO_TERMS map. Update the mirror "
        "(and re-verify the changed/added pairs against live OLS4) rather "
        "than just copying the new entries in unchecked."
    )


def test_so_terms_are_conformant():
    """Every SO_TERMS pair resolves to its claimed concept in the pinned snapshot.

    A genuine wrong-id defect here (e.g. a copy-paste swap between two SO
    accessions) fails with a label-mismatch message naming the pinned
    snapshot's actual canonical name for that id -- the same A3 shape as
    every other hardcoded-map conformance test in this suite.
    """
    violations = {
        vep_name: violation
        for vep_name, so_id in SO_TERMS_MIRROR.items()
        if (violation := check_label(so_id, vep_name)) is not None
    }
    assert not violations, violations
