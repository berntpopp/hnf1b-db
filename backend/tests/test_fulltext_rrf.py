from __future__ import annotations

import math

import pytest

from app.publications.fulltext.rrf import rrf_fuse


def test_pure_rrf_ordering_and_tiebreak():
    lexical = ["a", "b", "c"]
    dense = ["b", "a", "d"]
    result = rrf_fuse(lexical, dense, k=60)

    score_by_id = dict(result)
    # a: lexical rank1 + dense rank2 = 1/61 + 1/62
    assert math.isclose(score_by_id["a"], 1 / 61 + 1 / 62)
    # b: lexical rank2 + dense rank1 = 1/62 + 1/61
    assert math.isclose(score_by_id["b"], 1 / 62 + 1 / 61)
    # c: lexical rank3 = 1/63
    assert math.isclose(score_by_id["c"], 1 / 63)
    # d: dense rank3 = 1/63
    assert math.isclose(score_by_id["d"], 1 / 63)

    # Union, deduped.
    assert len(result) == 4
    assert {pid for pid, _ in result} == {"a", "b", "c", "d"}

    ids_in_order = [pid for pid, _ in result]
    # a and b are top-2 (equal scores -> tiebreak by id -> a before b).
    assert ids_in_order[:2] == ["a", "b"]
    assert math.isclose(score_by_id["a"], score_by_id["b"])
    # c and d have equal score (both 1/63) -> tiebreak by id -> c before d.
    assert ids_in_order[2:] == ["c", "d"]


def test_dense_empty_lexical_only():
    result = rrf_fuse(["x", "y"], [], k=60)
    assert result == [("x", 1 / 61), ("y", 1 / 62)]


def test_section_boost_lifts_abstract_above_intro():
    lexical = ["a", "b"]
    dense = ["b", "a"]
    section_by_id = {"a": "intro", "b": "abstract"}
    section_boosts = {"abstract": 0.1}

    # Without boosts, a and b have equal base scores (1/61 + 1/62 each),
    # so a wins the id tiebreak.
    base = rrf_fuse(lexical, dense, k=60)
    assert [pid for pid, _ in base][:2] == ["a", "b"]

    boosted = rrf_fuse(
        lexical,
        dense,
        k=60,
        section_by_id=section_by_id,
        section_boosts=section_boosts,
    )
    ids = [pid for pid, _ in boosted]
    score_by_id = dict(boosted)
    # b is boosted above a despite equal base scores.
    assert ids[0] == "b"
    assert ids[1] == "a"
    assert math.isclose(score_by_id["b"], 1 / 61 + 1 / 62 + 0.1)
    assert math.isclose(score_by_id["a"], 1 / 61 + 1 / 62)
    assert score_by_id["b"] > score_by_id["a"]


def test_determinism_equal_scores_tiebreak_by_id_ascending():
    # All ids appear at lexical rank 1 only across separate single-leg fuses
    # would be ambiguous; instead give every id the same single-leg rank by
    # supplying them each as the sole lexical entry is not possible in one call,
    # so construct equal scores via identical ranks in both legs.
    lexical = ["d", "c", "b", "a"]
    dense = ["d", "c", "b", "a"]
    result = rrf_fuse(lexical, dense, k=60)
    ids = [pid for pid, _ in result]
    # Scores strictly decrease by rank, so order follows rank, not id here.
    assert ids == ["d", "c", "b", "a"]

    # Now force a true score tie: two ids each appear once at the same rank
    # position across the two legs.
    tie = rrf_fuse(["z", "a"], ["a", "z"], k=60)
    tie_ids = [pid for pid, _ in tie]
    tie_scores = dict(tie)
    assert math.isclose(tie_scores["a"], tie_scores["z"])
    # Equal scores -> ascending id -> a before z.
    assert tie_ids == ["a", "z"]


def test_repeated_id_in_leg_uses_best_rank():
    # "a" appears twice in the lexical leg; only its best (rank 1) counts.
    result = rrf_fuse(["a", "b", "a"], [], k=60)
    score_by_id = dict(result)
    assert math.isclose(score_by_id["a"], 1 / 61)
    assert math.isclose(score_by_id["b"], 1 / 62)
    assert len(result) == 2


def test_invalid_k_raises():
    with pytest.raises(ValueError):
        rrf_fuse(["a"], ["b"], k=0)
    with pytest.raises(ValueError):
        rrf_fuse(["a"], ["b"], k=-5)


def test_boosts_require_both_maps():
    # Only section_by_id provided -> no boost applied.
    only_sections = rrf_fuse(
        ["a", "b"],
        ["b", "a"],
        k=60,
        section_by_id={"a": "intro", "b": "abstract"},
    )
    only_boosts = rrf_fuse(
        ["a", "b"],
        ["b", "a"],
        k=60,
        section_boosts={"abstract": 0.1},
    )
    plain = rrf_fuse(["a", "b"], ["b", "a"], k=60)
    assert only_sections == plain
    assert only_boosts == plain
