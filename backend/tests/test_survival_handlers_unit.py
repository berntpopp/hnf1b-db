"""Unit tests for survival handler internals (Wave 3 coverage gap).

The endpoint smoke tests in ``test_survival_endpoint.py`` cover the
``/survival-data`` route and the factory dispatch, but with an empty
test database every handler method's data-processing branches go
unexercised. Codecov reported the following uncovered lines on PR #231:

- ``survival/handlers/base.py``: 48 missing lines (57% patch coverage) —
  the body of ``_handle_current_age``, ``_handle_standard``, and the
  non-empty branches of ``_calculate_survival_curves`` and
  ``_calculate_statistical_tests``.
- ``survival/handlers/disease_subtype.py``: 26 missing lines (63%) —
  ``_handle_current_age_with_params`` and ``_handle_standard_with_params``
  data-processing loops.

These are all pure data-processing functions. Rather than wait for
real phenopacket fixtures in the test DB (Wave 4+ concern), this
module tests them in isolation by constructing fake row objects and
mocking the ``AsyncSession`` so the handlers run without any SQL.

Row objects are modelled with ``types.SimpleNamespace`` so they support
the attribute-access pattern (``row.current_age``, ``row.variant_group``,
etc.) the handlers use. The ``AsyncSession`` mock uses
``unittest.mock.AsyncMock`` with ``execute`` returning a synchronous
mock result whose ``fetchall()`` returns a canned row list.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.phenopackets.routers.aggregations.survival.handlers import (
    DiseaseSubtypeHandler,
    PathogenicityHandler,
    SurvivalHandler,
    SurvivalHandlerFactory,
    VariantTypeHandler,
)


def _make_async_session(fetchall_returns: List[List[Any]]) -> AsyncMock:
    """Build an AsyncMock ``AsyncSession`` that returns pre-canned rows.

    Each call to ``session.execute()`` returns a mock result object whose
    ``fetchall()`` pops the next list from ``fetchall_returns``. This
    models SQLAlchemy's ``Result`` interface closely enough for the
    handlers to run without a real database.

    Handlers call ``db.execute(...)`` with the query (and optionally a
    params dict); we don't assert on the arguments — the value of this
    test is exercising the row-processing branches, not the SQL.
    """
    session = AsyncMock()
    return_iter = iter(fetchall_returns)

    def _execute_side_effect(*_args: Any, **_kwargs: Any) -> MagicMock:
        result = MagicMock()
        result.fetchall.return_value = next(return_iter)
        return result

    session.execute.side_effect = _execute_side_effect
    return session


# --------------------------------------------------------------------------
# _sql_list — happy path + ValueError raise (covers base.py:83)
# --------------------------------------------------------------------------


class TestSqlList:
    """Unit tests for ``SurvivalHandler._sql_list``."""

    def test_canonical_hpo_ids_render_as_sql_in_clause(self) -> None:
        """Happy path: canonical HPO IDs → ``('HP:0012626', 'HP:0003774')``."""
        result = SurvivalHandler._sql_list(["HP:0012626", "HP:0003774"])
        assert result == "('HP:0012626', 'HP:0003774')"

    def test_single_term_produces_one_element_tuple(self) -> None:
        """A single-element list still renders as a valid SQL tuple literal."""
        result = SurvivalHandler._sql_list(["HP:0000107"])
        assert result == "('HP:0000107')"

    def test_empty_list_produces_empty_tuple_literal(self) -> None:
        """An empty list produces ``()`` — callers are responsible for not
        passing empty lists into IN clauses that would then be invalid SQL.
        """
        assert SurvivalHandler._sql_list([]) == "()"

    @pytest.mark.parametrize(
        "bad_term",
        [
            "HP:007",  # too few digits
            "HP:12345678",  # too many digits
            "HP:ABCDEFG",  # non-digits
            "hp:0012626",  # lowercase prefix
            "HP0012626",  # missing colon
            "MONDO:0012345",  # wrong ontology
            "HP:0012626'); DROP TABLE phenopackets;--",  # SQL injection attempt
            "",  # empty
        ],
    )
    def test_invalid_term_raises_value_error(self, bad_term: str) -> None:
        """Anything that does not match ``HP:\\d{7}`` is rejected — this is
        the defense-in-depth guard that closes the theoretical SQL injection
        surface opened by string-literal interpolation.
        """
        with pytest.raises(ValueError, match="canonical HPO IDs"):
            SurvivalHandler._sql_list(["HP:0012626", bad_term])

    def test_sql_list_accessible_via_concrete_subclass_self(self) -> None:
        """Concrete subclasses call ``self._sql_list(...)`` — verify it
        works via instance access (not just classmethod).
        """
        handler = VariantTypeHandler()
        result = handler._sql_list(["HP:0012625"])
        assert result == "('HP:0012625')"


# --------------------------------------------------------------------------
# get_group_field — default implementation (covers base.py:57)
# --------------------------------------------------------------------------


class TestGetGroupField:
    """Unit tests for ``SurvivalHandler.get_group_field`` defaults."""

    def test_pathogenicity_handler_uses_pathogenicity_group(self) -> None:
        """PathogenicityHandler's override returns ``pathogenicity_group``."""
        assert PathogenicityHandler().get_group_field() == "pathogenicity_group"

    def test_variant_type_handler_overrides_to_variant_group(self) -> None:
        """VariantTypeHandler overrides the default to ``variant_group``."""
        assert VariantTypeHandler().get_group_field() == "variant_group"

    def test_disease_subtype_handler_overrides_to_disease_group(self) -> None:
        """DiseaseSubtypeHandler's override returns ``disease_group``.

        DiseaseSubtypeHandler overrides ``handle()`` and processes rows
        via hardcoded ``row.disease_group`` access, so the overriding
        ``get_group_field`` is not called during normal operation. This
        test exists so the override isn't silently orphaned and to keep
        the explicit-is-better-than-implicit name visible to the reader.
        """
        assert DiseaseSubtypeHandler().get_group_field() == "disease_group"

    def test_base_default_uses_comparison_type_group_pattern(self) -> None:
        """The ``SurvivalHandler`` base implementation is
        ``f'{comparison_type}_group'`` and is used by concrete handlers
        that don't override it. Exercised here via a test-only concrete
        subclass so the base implementation stays covered even when all
        shipped handlers override it.
        """

        class _DefaultGroupFieldHandler(SurvivalHandler):
            """Bare-minimum concrete handler that uses the base default."""

            @property
            def comparison_type(self) -> str:
                return "custom"

            @property
            def group_names(self) -> List[str]:
                return ["A", "B"]

            @property
            def group_definitions(self) -> Dict[str, str]:
                return {"A": "group A", "B": "group B"}

            def build_current_age_query(self) -> str:
                return ""

            def build_standard_query(self, endpoint_hpo_terms: List[str]) -> str:
                return ""

            def _build_censored_query(self, endpoint_hpo_terms: List[str]) -> str:
                return ""

            def _get_inclusion_exclusion_criteria(self) -> Dict[str, str]:
                return {"inclusion_criteria": "all", "exclusion_criteria": "none"}

        handler = _DefaultGroupFieldHandler()
        # Does NOT override get_group_field → uses the base default.
        assert handler.get_group_field() == "custom_group"


# --------------------------------------------------------------------------
# SurvivalHandler._handle_current_age (covers base.py:118-134)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHandleCurrentAge:
    """Exercise the ``_handle_current_age`` data-processing branch.

    Uses VariantTypeHandler as a concrete subclass — its
    ``build_current_age_query`` returns a non-empty SQL string so the
    handler will call ``db.execute`` and iterate the mocked rows.
    """

    async def test_groups_rows_by_variant_group_and_parses_ages(self) -> None:
        """Every row whose current_age parses gets appended to its group."""
        rows = [
            SimpleNamespace(
                variant_group="CNV",
                current_age="P30Y",
                has_kidney_failure=True,
            ),
            SimpleNamespace(
                variant_group="Truncating",
                current_age="P25Y6M",
                has_kidney_failure=False,
            ),
            SimpleNamespace(
                variant_group="Non-truncating",
                current_age="P40Y",
                has_kidney_failure=True,
            ),
            # Second CNV row to exercise the append path
            SimpleNamespace(
                variant_group="CNV",
                current_age="P15Y",
                has_kidney_failure=False,
            ),
        ]
        db = _make_async_session([rows])

        handler = VariantTypeHandler()
        result = await handler._handle_current_age(db, "Any CKD")

        assert result["comparison_type"] == "variant_type"
        assert result["endpoint"] == "Any CKD"
        # Every non-empty group made it into the response
        group_names = {g["name"] for g in result["groups"]}
        assert group_names == {"CNV", "Truncating", "Non-truncating"}
        # CNV group has 2 members
        cnv = next(g for g in result["groups"] if g["name"] == "CNV")
        assert cnv["n"] == 2
        assert cnv["events"] == 1  # Only one has_kidney_failure=True
        # Metadata from _get_current_age_metadata is embedded
        assert "event_definition" in result["metadata"]
        assert "group_definitions" in result["metadata"]

    async def test_rows_with_unparseable_age_are_dropped(self) -> None:
        """``parse_iso8601_age`` returns None for invalid age strings → skip."""
        rows = [
            SimpleNamespace(
                variant_group="CNV",
                current_age="garbage",  # unparseable
                has_kidney_failure=False,
            ),
            SimpleNamespace(
                variant_group="CNV",
                current_age="P20Y",
                has_kidney_failure=True,
            ),
        ]
        db = _make_async_session([rows])

        handler = VariantTypeHandler()
        result = await handler._handle_current_age(db, "Any CKD")

        cnv_group = next(g for g in result["groups"] if g["name"] == "CNV")
        assert cnv_group["n"] == 1  # garbage row dropped

    async def test_rows_with_unknown_group_name_are_ignored(self) -> None:
        """Rows with a ``variant_group`` not in ``group_names`` are silently
        skipped — defensive because the SQL CASE could produce unexpected
        values in edge cases.
        """
        rows = [
            SimpleNamespace(
                variant_group="BogusGroup",
                current_age="P30Y",
                has_kidney_failure=False,
            ),
            SimpleNamespace(
                variant_group="Truncating",
                current_age="P25Y",
                has_kidney_failure=True,
            ),
        ]
        db = _make_async_session([rows])

        handler = VariantTypeHandler()
        result = await handler._handle_current_age(db, "Any CKD")

        # Only Truncating has a member; BogusGroup was dropped
        group_names = {g["name"] for g in result["groups"]}
        assert group_names == {"Truncating"}

    async def test_empty_rows_returns_empty_groups(self) -> None:
        """Empty row list → every group is empty → groups list is empty."""
        db = _make_async_session([[]])
        handler = VariantTypeHandler()
        result = await handler._handle_current_age(db, "Any CKD")

        assert result["groups"] == []


# --------------------------------------------------------------------------
# SurvivalHandler._handle_standard (covers base.py:148-181)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHandleStandard:
    """Exercise the ``_handle_standard`` data-processing branch.

    Fires two ``db.execute`` calls: one for the primary query (event
    rows) and one for the censored query. The mock session returns
    each pre-canned list in turn.
    """

    async def test_event_and_censored_rows_are_both_grouped(self) -> None:
        """Event rows become (onset_age, True); censored become
        (current_age, False); both land in the same groups dict.
        """
        event_rows = [
            SimpleNamespace(
                variant_group="CNV",
                current_age=None,
                onset_age="P20Y",
                onset=None,
            ),
            SimpleNamespace(
                variant_group="Truncating",
                current_age=None,
                onset_age="P30Y",
                onset=None,
            ),
        ]
        censored_rows = [
            SimpleNamespace(
                variant_group="CNV",
                current_age="P40Y",
                onset_age=None,
                onset=None,
            ),
            SimpleNamespace(
                variant_group="Non-truncating",
                current_age="P50Y",
                onset_age=None,
                onset=None,
            ),
        ]
        db = _make_async_session([event_rows, censored_rows])

        handler = VariantTypeHandler()
        result = await handler._handle_standard(db, "CKD Stage 3+", ["HP:0012625"])

        assert result["comparison_type"] == "variant_type"
        assert result["endpoint"] == "CKD Stage 3+"

        # CNV: 1 event + 1 censored = 2 members, 1 event
        cnv = next(g for g in result["groups"] if g["name"] == "CNV")
        assert cnv["n"] == 2
        assert cnv["events"] == 1
        # Truncating: 1 event
        trunc = next(g for g in result["groups"] if g["name"] == "Truncating")
        assert trunc["n"] == 1
        assert trunc["events"] == 1
        # Non-truncating: 1 censored, 0 events
        non = next(g for g in result["groups"] if g["name"] == "Non-truncating")
        assert non["n"] == 1
        assert non["events"] == 0

        # _get_standard_metadata is embedded
        assert "event_definition" in result["metadata"]
        assert "CKD Stage 3+" in result["metadata"]["event_definition"]

    async def test_onset_label_falls_back_when_onset_age_missing(self) -> None:
        """If ``row.onset_age`` is None, the handler falls back to
        ``row.onset`` as the age string — covers the ``elif row.onset``
        branch.
        """
        event_rows = [
            SimpleNamespace(
                variant_group="CNV",
                current_age=None,
                onset_age=None,
                onset="P35Y",
            ),
        ]
        db = _make_async_session([event_rows, []])

        handler = VariantTypeHandler()
        result = await handler._handle_standard(db, "CKD Stage 3+", ["HP:0012625"])

        cnv = next(g for g in result["groups"] if g["name"] == "CNV")
        assert cnv["n"] == 1
        assert cnv["events"] == 1

    async def test_unparseable_event_age_is_dropped(self) -> None:
        """Rows where both ``onset_age`` and ``onset`` fail to parse
        (or are None) are silently skipped.
        """
        event_rows = [
            SimpleNamespace(
                variant_group="CNV",
                current_age=None,
                onset_age=None,
                onset=None,
            ),
        ]
        db = _make_async_session([event_rows, []])

        handler = VariantTypeHandler()
        result = await handler._handle_standard(db, "CKD Stage 3+", ["HP:0012625"])

        # No groups have any members → empty groups list in response
        assert result["groups"] == []


# --------------------------------------------------------------------------
# _calculate_survival_curves + _calculate_statistical_tests via _build_result
# (covers base.py:225, 238-242)
# --------------------------------------------------------------------------


class TestBuildResultCalculations:
    """Exercise the Kaplan-Meier and log-rank-test branches inside
    ``_build_result``, via a real handler instance.

    Most of the body is already covered by the _handle_* tests above,
    but the non-empty-group branches of ``_calculate_survival_curves``
    and the pairwise loop in ``_calculate_statistical_tests`` only run
    when there are ≥2 non-empty groups.
    """

    def test_build_result_with_two_non_empty_groups_runs_log_rank(self) -> None:
        """Two non-empty groups triggers one pairwise log-rank test
        (covers the inner j-loop).
        """
        handler = PathogenicityHandler()
        groups: Dict[str, List[tuple]] = {
            "P/LP": [(20.0, True), (30.0, False), (40.0, True)],
            "VUS": [(25.0, True), (35.0, False)],
        }
        metadata: Dict[str, Any] = {"event_definition": "test"}

        result = handler._build_result("Any CKD", groups, metadata)

        assert result["comparison_type"] == "pathogenicity"
        assert {g["name"] for g in result["groups"]} == {"P/LP", "VUS"}
        # One pairwise test
        assert len(result["statistical_tests"]) == 1
        test = result["statistical_tests"][0]
        assert {test["group1"], test["group2"]} == {"P/LP", "VUS"}

    def test_build_result_with_three_non_empty_groups_runs_three_tests(self) -> None:
        """Three non-empty groups → C(3,2) = 3 pairwise tests. After
        Bonferroni correction the tests list still has 3 entries.
        """
        handler = VariantTypeHandler()
        groups: Dict[str, List[tuple]] = {
            "CNV": [(20.0, True), (30.0, False)],
            "Truncating": [(25.0, True), (35.0, True)],
            "Non-truncating": [(40.0, False), (45.0, True)],
        }
        metadata: Dict[str, Any] = {"event_definition": "test"}

        result = handler._build_result("Any CKD", groups, metadata)
        assert len(result["statistical_tests"]) == 3

    def test_build_result_with_empty_group_returns_empty_survival_data(
        self,
    ) -> None:
        """An empty group is filtered out of the groups response but the
        curve calculation still runs (returns empty list).
        """
        handler = VariantTypeHandler()
        groups: Dict[str, List[tuple]] = {
            "CNV": [(20.0, True)],
            "Truncating": [],  # empty — skipped in response
            "Non-truncating": [],
        }
        metadata: Dict[str, Any] = {"event_definition": "test"}

        result = handler._build_result("Any CKD", groups, metadata)
        # Only CNV has members
        assert {g["name"] for g in result["groups"]} == {"CNV"}
        # No pairs → no tests
        assert result["statistical_tests"] == []


# --------------------------------------------------------------------------
# DiseaseSubtypeHandler — _handle_*_with_params (covers disease_subtype.py
# lines 227-278)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDiseaseSubtypeHandlerWithParams:
    """Exercise the ``_handle_current_age_with_params`` and
    ``_handle_standard_with_params`` methods that ``DiseaseSubtypeHandler``
    overrides on top of the base class.
    """

    async def test_handle_routes_to_current_age_when_no_endpoint_hpo_terms(
        self,
    ) -> None:
        """``handle(endpoint_hpo_terms=None)`` → ``_handle_current_age_with_params``."""
        rows = [
            SimpleNamespace(
                disease_group="CAKUT",
                current_age="P30Y",
                has_kidney_failure=True,
            ),
            SimpleNamespace(
                disease_group="MODY",
                current_age="P25Y",
                has_kidney_failure=False,
            ),
            SimpleNamespace(
                disease_group="CAKUT/MODY",
                current_age="P40Y",
                has_kidney_failure=True,
            ),
        ]
        db = _make_async_session([rows])

        handler = DiseaseSubtypeHandler()
        result = await handler.handle(db, "Any CKD", None)

        assert result["comparison_type"] == "disease_subtype"
        group_names = {g["name"] for g in result["groups"]}
        assert {"CAKUT", "MODY", "CAKUT/MODY"}.issubset(group_names)

    async def test_handle_routes_to_standard_when_endpoint_hpo_terms_provided(
        self,
    ) -> None:
        """``handle(endpoint_hpo_terms=[...])`` →
        ``_handle_standard_with_params``; the event query + censored query
        both fire.
        """
        event_rows = [
            SimpleNamespace(
                disease_group="CAKUT",
                current_age=None,
                onset_age="P20Y",
                onset=None,
            ),
            SimpleNamespace(
                disease_group="MODY",
                current_age=None,
                onset_age="P30Y",
                onset=None,
            ),
        ]
        censored_rows = [
            SimpleNamespace(
                disease_group="Other",
                current_age="P50Y",
                onset_age=None,
                onset=None,
            ),
        ]
        db = _make_async_session([event_rows, censored_rows])

        handler = DiseaseSubtypeHandler()
        result = await handler.handle(db, "CKD Stage 3+", ["HP:0012625"])

        assert result["comparison_type"] == "disease_subtype"
        cakut = next(g for g in result["groups"] if g["name"] == "CAKUT")
        assert cakut["n"] == 1
        assert cakut["events"] == 1
        other = next(g for g in result["groups"] if g["name"] == "Other")
        assert other["n"] == 1
        assert other["events"] == 0  # censored

    async def test_handle_standard_drops_unparseable_onset_rows(self) -> None:
        """Event rows with no parseable onset (both onset_age and onset
        are None) are silently dropped, matching base-class behaviour.
        """
        event_rows = [
            SimpleNamespace(
                disease_group="CAKUT",
                current_age=None,
                onset_age=None,
                onset=None,
            ),
        ]
        db = _make_async_session([event_rows, []])

        handler = DiseaseSubtypeHandler()
        result = await handler.handle(db, "CKD Stage 3+", ["HP:0012625"])

        # No groups have members → empty groups list
        assert result["groups"] == []

    async def test_handle_standard_falls_back_to_onset_label_when_age_missing(
        self,
    ) -> None:
        """``_handle_standard_with_params`` falls back to ``row.onset``
        when ``row.onset_age`` is None. Covers the ``elif row.onset:``
        branch in disease_subtype.py (parity with the base-class
        ``_handle_standard`` fallback exercised by the VariantTypeHandler
        test above).
        """
        event_rows = [
            SimpleNamespace(
                disease_group="MODY",
                current_age=None,
                onset_age=None,
                onset="P20Y6M",  # only this is set — forces the elif branch
            ),
        ]
        db = _make_async_session([event_rows, []])

        handler = DiseaseSubtypeHandler()
        result = await handler.handle(db, "CKD Stage 3+", ["HP:0012625"])

        mody = next(g for g in result["groups"] if g["name"] == "MODY")
        assert mody["n"] == 1
        assert mody["events"] == 1


# --------------------------------------------------------------------------
# DiseaseSubtypeHandler params dict — Copilot fix verification
# --------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDiseaseSubtypeParamsDict:
    """Verify the ``params`` dict that ``DiseaseSubtypeHandler.handle``
    builds only carries keys that are actually bound in the generated
    SQL. The unused ``any_kidney_hpo_terms`` key was removed in the
    Wave 3 Copilot-comment fix.
    """

    async def test_params_dict_has_only_bound_keys(self) -> None:
        """``cakut_hpo_terms``, ``genital_hpo``, ``mody_hpo`` only."""
        captured_params: Dict[str, Any] = {}

        db = AsyncMock()

        def _execute_side_effect(*args: Any, **_kwargs: Any) -> MagicMock:
            # The second positional argument is the params dict on both
            # _handle_current_age_with_params and _handle_standard_with_params.
            if len(args) >= 2 and isinstance(args[1], dict):
                captured_params.update(args[1])
            result = MagicMock()
            result.fetchall.return_value = []
            return result

        db.execute.side_effect = _execute_side_effect

        handler = DiseaseSubtypeHandler()
        await handler.handle(db, "Any CKD", None)

        # Unused key must not be present (removed in the Copilot-comment fix)
        assert "any_kidney_hpo_terms" not in captured_params
        # These three ARE bound in _build_disease_classification_sql
        assert "cakut_hpo_terms" in captured_params
        assert "genital_hpo" in captured_params
        assert "mody_hpo" in captured_params


# --------------------------------------------------------------------------
# SurvivalHandlerFactory — dispatch + error handling
# --------------------------------------------------------------------------


class TestSurvivalHandlerFactoryDispatch:
    """The factory maps comparison-type strings to handler classes.
    Already exercised by the endpoint smoke tests, but add direct unit
    tests for completeness and error-path coverage.
    """

    @pytest.mark.parametrize(
        "comparison_type,expected_class",
        [
            ("variant_type", VariantTypeHandler),
            ("pathogenicity", PathogenicityHandler),
            ("disease_subtype", DiseaseSubtypeHandler),
        ],
    )
    def test_factory_returns_expected_handler(
        self, comparison_type: str, expected_class: type
    ) -> None:
        """Every registered comparison type returns a fresh handler instance."""
        handler = SurvivalHandlerFactory.get_handler(comparison_type)
        assert isinstance(handler, expected_class)
        assert handler.comparison_type == comparison_type

    def test_factory_raises_value_error_for_unknown_type(self) -> None:
        """Unknown comparison types raise ``ValueError`` — this is what
        the endpoint then catches and converts to ``HTTPException(400)``.
        """
        with pytest.raises(ValueError, match="Unknown comparison type"):
            SurvivalHandlerFactory.get_handler("not_a_real_type")

    def test_factory_get_valid_comparison_types_lists_all_four(self) -> None:
        """The factory exposes a list of supported comparison types."""
        types = SurvivalHandlerFactory.get_valid_comparison_types()
        assert set(types) == {
            "variant_type",
            "pathogenicity",
            "disease_subtype",
            "protein_domain",
        }
