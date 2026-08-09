#!/usr/bin/env python3
"""Refresh the pinned ontology snapshot consumed by `app.ontology.conformance`.

Spec: docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.3.

`app/ontology/conformance.py`'s A3 check (`check_label`) resolves every stored
`(id, label)` pair against a **pinned, committed** snapshot rather than a live
API — a test that calls `ontology.jax.org` on every run is nondeterministic,
fails offline, and turns an upstream HPO rename into a red build for every
unrelated PR. This script is the explicit, reviewable way that snapshot gets
updated: run it, and the diff shows exactly what changed upstream.

Covers **six** ontologies:

- HPO, via `https://ontology.jax.org/api/hp/terms/{id}` (field `name`, not
  `label`; field `definition`, not `description`).
- MONDO, Orphanet (ORDO), ECO, SO and GENO, via EBI OLS4 **term lookup by
  IRI**: `https://www.ebi.ac.uk/ols4/api/ontologies/{ont}/terms?iri={iri}`.
  Deliberately NOT OLS4's `/search` endpoint — `/search` does free-text
  matching and can return a plausible-looking but wrong term for an
  identifier query (it would report `MONDO:0011593` as "seizures, benign
  familial infantile, 2" only because that happens to be correct; for other
  ids it silently returns unrelated matches). `/terms?iri=...` is an exact
  identifier lookup.

SO and GENO cover the ids the importer emits for `structuralType` /
`allelicState` (`migration/phenopackets/extractors.py`,
`migration/vrs/cnv_parser.py`) — `_SO_GENO_TERM_IDS` below. Added
2026-07-30: `ontology_preflight.py` was failing on three of them
(`SO:1000035` duplication, `SO:0000159` deletion, `GENO:0000135`
heterozygous) even though all three are stored correctly — the snapshot
simply never covered these two ontologies before. Verified live against
OLS4 at the time: neither `so` nor `geno` was previously in
`_OLS4_ONTOLOGY_BY_PREFIX`.

The term list itself must not depend on Task 4 (the curation-sheet re-sync,
which runs later), so it is built from three **already-committed** sources:

1. `app/ontology/data/curation_vocabulary.csv` — the curation sheet's
   `Phenotype` and `Phenotype_modifier` tabs, exported once (this task) with
   no individual-level data (ADR 0003's PII constraint).
2. `migration/phenopackets/laterality.py`'s four modifier constants.
3. An explicit list of onset, disease and evidence ids the importer
   hardcodes outside the sheet (`age_parser.py`, `builder_simple.py` /
   `cnv_parser.py`, `evidence_builder.py`), plus `HP:0033132` —
   `hpo_mapper.py`'s corrected "hyperechogenicity" id (commit `2acfe03`).
   The curation sheet itself still names the wrong id, `HP:0033133`, for that
   category (the T1 defect Task 4 will correct at the source); the snapshot
   needs `HP:0033132` too so `check_source_row` can name it as the term
   `HP:0033133`'s own description actually describes.

Usage:
    uv run python scripts/refresh_ontology_snapshot.py          # write the snapshot
    uv run python scripts/refresh_ontology_snapshot.py --check  # exit 1 on drift
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger("refresh_ontology_snapshot")

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_ROOT / "app" / "ontology" / "data"
_SNAPSHOT_PATH = _DATA_DIR / "ontology_snapshot.json"
_VOCAB_CSV_PATH = _DATA_DIR / "curation_vocabulary.csv"

_REQUEST_TIMEOUT_SECONDS = 15

# migration/phenopackets/laterality.py's four HPO modifier constants.
_LATERALITY_IDS = ["HP:0012832", "HP:0012833", "HP:0012835", "HP:0012834"]

# Onset (age_parser.py), disease (builder_simple.py / cnv_parser.py) and
# evidence (evidence_builder.py) ids the importer hardcodes outside the
# curation sheet, plus HP:0033132 (see module docstring point 3), plus
# hpo_mapper.py's fallback dictionary and ontology_service.py's
# ADDITIONAL_TERMS entries that are not already covered by the sheet
# vocabulary CSV above (Task 6, ontology data-quality plan). HP:0012759 is a
# coverage gap, not a defect: "Neurodevelopmental abnormality" is the
# correct name for that id, it was simply absent from the pinned snapshot.
_EXPLICIT_TERM_IDS = [
    "HP:0003577",  # Congenital onset
    "HP:0003593",  # Infantile onset
    "HP:0011463",  # Childhood onset
    "HP:0003581",  # Adult onset
    "HP:0003674",  # Onset (abstract parent; HPO has no discrete postnatal term)
    "MONDO:0007669",  # renal cysts and diabetes syndrome
    "ECO:0000033",  # author statement supported by traceable reference
    "HP:0033132",  # Renal cortical hyperechogenicity (corrected id)
    "HP:0012759",  # Neurodevelopmental abnormality (hpo_mapper.py fallback)
    "HP:0000083",  # Renal insufficiency (ontology_service.py ADDITIONAL_TERMS)
    "HP:0000819",  # Diabetes mellitus (ontology_service.py ADDITIONAL_TERMS)
    "MONDO:0005147",  # type 1 diabetes mellitus (ontology_service.py ADDITIONAL_TERMS)
    # clinical_queries.py's MORPHOLOGY_TERM_LABELS (backend/tests/
    # test_clinical_queries_morphology.py). Coverage gaps, not defects --
    # both verified live against OLS4 2026-07-30 and both match the map's
    # stored label exactly:
    #   HP:0000110 -> "Renal dysplasia"
    #   HP:0000113 -> "Polycystic kidney dysplasia"
    "HP:0000110",  # Renal dysplasia
    "HP:0000113",  # Polycystic kidney dysplasia
    # app/hpo_proxy.py's GET /common-terms "developmental" category.
    # Coverage gaps, not defects -- both verified live against OLS4
    # 2026-07-30 and both match hpo_proxy.py's stored label exactly.
    "HP:0001737",  # Pancreatic cysts
    "HP:0001732",  # Abnormality of the pancreas
]

# SO and GENO ids the importer emits for structuralType / allelicState
# (migration/phenopackets/extractors.py, migration/vrs/cnv_parser.py).
# SO:0000159, SO:1000035 and GENO:0000135 are the ones actually present in
# the corpus today (confirmed by querying every distinct id at both paths,
# working copies and head-published revisions, 2026-07-30); the other three
# are included too so the coverage gap does not reopen the moment a
# different structural type is imported -- extractors.py's molecular-
# consequence branch already emits them. All six verified live against OLS4
# 2026-07-30. SO:1000032's canonical OLS4 label is "delins" -- SO renamed it
# from "indel" in 2019 to align with HGVS nomenclature -- but "indel", the
# label the importer actually stores, remains a listed synonym, so it is
# conformant, not a defect.
_SO_GENO_TERM_IDS = [
    "SO:0000159",  # deletion
    "SO:1000035",  # duplication
    "GENO:0000135",  # heterozygous
    "SO:0001483",  # SNV
    "SO:1000032",  # canonical label "delins"; "indel" (stored) is a listed synonym
    "SO:0000667",  # insertion
]

# Every SO id `frontend/src/utils/soTerms.js`'s `SO_TERMS` map can write to
# `variationDescriptor.molecularConsequences[]` (added this branch; see
# `ONTOLOGY_PATHS` in `app/ontology/conformance.py`, which previously omitted
# that path entirely -- a wrong SO id/label pair there would never have been
# checked by A3). All 29 verified live against OLS4 2026-07-30: every VEP
# consequence key in `SO_TERMS` matches its SO id's canonical `label` exactly
# (no mismatches found). Six overlap with `_SO_GENO_TERM_IDS` above
# (`SO:0001483` SNV) and are de-duplicated by `build_term_id_list`.
_FRONTEND_SO_TERM_IDS = [
    "SO:0001893",  # transcript_ablation
    "SO:0001574",  # splice_acceptor_variant
    "SO:0001575",  # splice_donor_variant
    "SO:0001587",  # stop_gained
    "SO:0001589",  # frameshift_variant
    "SO:0001578",  # stop_lost
    "SO:0002012",  # start_lost
    "SO:0001889",  # transcript_amplification
    "SO:0001821",  # inframe_insertion
    "SO:0001822",  # inframe_deletion
    "SO:0001583",  # missense_variant
    "SO:0001818",  # protein_altering_variant
    "SO:0001630",  # splice_region_variant
    "SO:0001626",  # incomplete_terminal_codon_variant
    "SO:0002019",  # start_retained_variant
    "SO:0001567",  # stop_retained_variant
    "SO:0001819",  # synonymous_variant
    "SO:0001580",  # coding_sequence_variant
    "SO:0001620",  # mature_miRNA_variant
    "SO:0001623",  # 5_prime_UTR_variant
    "SO:0001624",  # 3_prime_UTR_variant
    "SO:0001792",  # non_coding_transcript_exon_variant
    "SO:0001627",  # intron_variant
    "SO:0001621",  # NMD_transcript_variant
    "SO:0001619",  # non_coding_transcript_variant
    "SO:0001631",  # upstream_gene_variant
    "SO:0001632",  # downstream_gene_variant
    "SO:0001628",  # intergenic_variant
    "SO:0001483",  # SNV (already in _SO_GENO_TERM_IDS; de-duplicated)
]

# OLS4 ontology key + IRI-building function for each non-HPO prefix this
# script covers. Orphanet's OLS4 IRI segment is "Orphanet_<number>" — NOT
# "ORPHA_<number>", which `term_id.replace(":", "_")` would naively produce
# and which 404s (verified live). MONDO, ECO, SO and GENO use their own
# prefix as the OBO Foundry local-id segment, so the naive substitution is
# correct there (verified live for SO_1000035 and GENO_0000135, 2026-07-30).
_OLS4_ONTOLOGY_BY_PREFIX: dict[str, tuple[str, str]] = {
    "MONDO:": ("mondo", "http://purl.obolibrary.org/obo/MONDO_{}"),
    "ORPHA:": ("ordo", "http://www.orpha.net/ORDO/Orphanet_{}"),
    "ECO:": ("eco", "http://purl.obolibrary.org/obo/ECO_{}"),
    "SO:": ("so", "http://purl.obolibrary.org/obo/SO_{}"),
    "GENO:": ("geno", "http://purl.obolibrary.org/obo/GENO_{}"),
}


def _term_ids_from_vocabulary_csv(path: Path) -> list[str]:
    """Read every `phenotype_id` from the committed curation vocabulary CSV."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [row["phenotype_id"] for row in reader if row.get("phenotype_id")]


def build_term_id_list() -> list[str]:
    """Union of the sheet vocabulary, laterality constants and explicit ids.

    Order-preserving de-duplication so the snapshot's resolution order (and
    any warnings) are stable across runs.
    """
    ids = [
        *_term_ids_from_vocabulary_csv(_VOCAB_CSV_PATH),
        *_LATERALITY_IDS,
        *_EXPLICIT_TERM_IDS,
        *_SO_GENO_TERM_IDS,
        *_FRONTEND_SO_TERM_IDS,
    ]
    seen: set[str] = set()
    unique_ids: list[str] = []
    for term_id in ids:
        if term_id not in seen:
            seen.add(term_id)
            unique_ids.append(term_id)
    return unique_ids


def _fetch_hpo(term_id: str) -> Optional[dict[str, Any]]:
    """Fetch `{name, synonyms, definition}` for an `HP:` id from ontology.jax.org.

    Note the response field is `name` (not `label`) and `definition` (not
    `description`); the id in the path is used as-is, no colon encoding.
    """
    url = f"https://ontology.jax.org/api/hp/terms/{term_id}"
    try:
        response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("HPO lookup for %s failed: %s", term_id, exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "HPO lookup for %s returned HTTP %s", term_id, response.status_code
        )
        return None

    data = response.json()
    name = data.get("name")
    if not name:
        logger.warning(
            "HPO lookup for %s returned no name (obsolete or unknown id)", term_id
        )
        return None

    return {
        "name": name,
        "synonyms": data.get("synonyms", []) or [],
        "definition": data.get("definition") or "",
    }


def _fetch_ols4(term_id: str) -> Optional[dict[str, Any]]:
    """Fetch `{name, synonyms, definition}` for a MONDO:/ORPHA:/ECO: id via OLS4.

    Uses `/ontologies/{ont}/terms?iri=...` (exact identifier lookup), never
    `/search` — see the module docstring for why.

    Symmetric with `_fetch_hpo`'s validation: a malformed, obsolete, or
    mismatched response is logged and skipped (returns `None`) rather than
    silently written into the snapshot. An unvalidated OLS4 response could
    put a wrong or empty name in the pinned snapshot, which would make A3
    endorse a wrong term — the exact defect class this module exists to
    prevent.
    """
    for prefix, (ontology, iri_template) in _OLS4_ONTOLOGY_BY_PREFIX.items():
        if not term_id.startswith(prefix):
            continue

        iri = iri_template.format(term_id.split(":", 1)[1])
        url = f"https://www.ebi.ac.uk/ols4/api/ontologies/{ontology}/terms"
        try:
            response = requests.get(
                url, params={"iri": iri}, timeout=_REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            logger.warning("OLS4 lookup for %s failed: %s", term_id, exc)
            return None

        if response.status_code != 200:
            logger.warning(
                "OLS4 lookup for %s returned HTTP %s", term_id, response.status_code
            )
            return None

        data = response.json()
        terms = data.get("_embedded", {}).get("terms", [])
        if not terms:
            logger.warning("OLS4 lookup for %s returned no terms", term_id)
            return None

        term = terms[0]

        returned_iri = term.get("iri")
        if returned_iri != iri:
            logger.warning(
                "OLS4 lookup for %s returned a term whose iri (%s) does not "
                "match the requested iri (%s); skipping",
                term_id,
                returned_iri,
                iri,
            )
            return None

        if term.get("is_obsolete"):
            logger.warning(
                "OLS4 lookup for %s returned an obsolete term; skipping", term_id
            )
            return None

        name = term.get("label") or ""
        if not name:
            logger.warning(
                "OLS4 lookup for %s returned an empty label; skipping", term_id
            )
            return None

        description = term.get("description") or []
        return {
            "name": name,
            "synonyms": term.get("synonyms", []) or [],
            "definition": description[0] if description else "",
        }

    return None


def resolve_term(term_id: str) -> Optional[dict[str, Any]]:
    """Resolve one term id against whichever of the four covered ontologies owns it."""
    if term_id.startswith("HP:"):
        return _fetch_hpo(term_id)
    if any(term_id.startswith(prefix) for prefix in _OLS4_ONTOLOGY_BY_PREFIX):
        return _fetch_ols4(term_id)

    logger.warning(
        "No resolver configured for %s (ontology outside this script's four-"
        "ontology scope); skipping.",
        term_id,
    )
    return None


def _ontology_version(ontology_key: str) -> str:
    """Fetch an ontology's release version string from OLS4's ontology metadata."""
    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/{ontology_key}"
    try:
        response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Could not fetch %s ontology version: %s", ontology_key, exc)
        return "unknown"

    data = response.json()
    return data.get("version") or "unknown"


def build_snapshot() -> dict[str, Any]:
    """Resolve every term id and assemble the snapshot document."""
    term_ids = build_term_id_list()

    terms: dict[str, Any] = {}
    unresolved: list[str] = []
    for term_id in term_ids:
        resolved = resolve_term(term_id)
        if resolved is None:
            unresolved.append(term_id)
            continue
        terms[term_id] = resolved

    if unresolved:
        logger.warning(
            "%d term(s) could not be resolved and are absent from the snapshot: %s",
            len(unresolved),
            ", ".join(unresolved),
        )

    # OLS4 mirrors HPO under the "hp" ontology key; its version string is the
    # same HPO release date used throughout this codebase's provenance
    # comments. ontology.jax.org's term API itself carries no release
    # metadata, so the version is sourced from OLS4 even though the term data
    # for HP: ids comes from ontology.jax.org per the module docstring.
    generated_against = {
        "hp": _ontology_version("hp"),
        "mondo": _ontology_version("mondo"),
        "ordo": _ontology_version("ordo"),
        "eco": _ontology_version("eco"),
        "so": _ontology_version("so"),
        "geno": _ontology_version("geno"),
    }

    return {"_generated_against": generated_against, "terms": terms}


def _render(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point: refresh by default, or `--check` to exit 1 on drift."""
    parser = argparse.ArgumentParser(
        description="Refresh the pinned ontology snapshot (spec §3.3)."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the snapshot would change; write nothing.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    snapshot = build_snapshot()
    rendered = _render(snapshot)

    if args.check:
        if not _SNAPSHOT_PATH.exists():
            print(f"{_SNAPSHOT_PATH} does not exist.", file=sys.stderr)
            return 1
        current = _SNAPSHOT_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(
                "Ontology snapshot is out of date. Run "
                "`make refresh-ontology-snapshot` and review the diff.",
                file=sys.stderr,
            )
            return 1
        print("Ontology snapshot is up to date.")
        return 0

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _SNAPSHOT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {_SNAPSHOT_PATH} ({len(snapshot['terms'])} terms).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
