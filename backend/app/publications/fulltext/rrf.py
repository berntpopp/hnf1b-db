"""Reciprocal Rank Fusion for hybrid passage retrieval.

This module fuses two independently ranked passage lists (a lexical leg and a
dense leg) into a single ranking via Reciprocal Rank Fusion (RRF), optionally
adding per-section boosts so that passages from preferred sections (e.g. the
abstract) float to the top when their fused scores are otherwise comparable.

The module is pure: it performs no I/O and depends only on the standard
library.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def rrf_fuse(
    lexical_ids: Sequence[str],
    dense_ids: Sequence[str],
    *,
    k: int = 60,
    section_by_id: Mapping[str, str] | None = None,
    section_boosts: Mapping[str, float] | None = None,
) -> list[tuple[str, float]]:
    """Fuse two ranked passage-id lists via Reciprocal Rank Fusion.

    Each input list is ranked best-first, so the first element has rank 1. For
    every passage id, the fused score is the sum over the legs it appears in of
    ``1 / (k + rank)`` (rank is 1-based). When both ``section_by_id`` and
    ``section_boosts`` are provided, an additive section boost of
    ``section_boosts.get(section_by_id.get(passage_id), 0.0)`` is added to the
    passage's score.

    A passage that is ranked in only one leg contributes a single RRF term; a
    passage that appears multiple times within one leg contributes only its
    best (lowest) rank from that leg. When ``dense_ids`` is empty the fusion is
    lexical-only, but section boosts are still applied.

    Args:
        lexical_ids: Passage ids from the lexical leg, ranked best-first.
        dense_ids: Passage ids from the dense leg, ranked best-first. May be
            empty for lexical-only fusion.
        k: RRF damping constant; must be greater than 0.
        section_by_id: Optional mapping from passage id to its canonical
            section label. Required (together with ``section_boosts``) for
            section boosts to apply.
        section_boosts: Optional mapping from section label to an additive
            score boost. Required (together with ``section_by_id``) for section
            boosts to apply.

    Returns:
        A list of ``(passage_id, score)`` tuples for the union of all ids,
        sorted by score descending with ties broken by passage id ascending for
        determinism. Each passage id appears exactly once.

    Raises:
        ValueError: If ``k`` is not greater than 0.
    """
    if k <= 0:
        raise ValueError("k must be > 0")

    scores: dict[str, float] = {}
    for leg in (lexical_ids, dense_ids):
        seen_in_leg: set[str] = set()
        for rank, passage_id in enumerate(leg, start=1):
            if passage_id in seen_in_leg:
                continue
            seen_in_leg.add(passage_id)
            scores[passage_id] = scores.get(passage_id, 0.0) + 1.0 / (k + rank)

    if section_by_id is not None and section_boosts is not None:
        for passage_id in scores:
            section = section_by_id.get(passage_id)
            if section is not None:
                scores[passage_id] += section_boosts.get(section, 0.0)

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
