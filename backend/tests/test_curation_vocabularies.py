"""Reference tables backing the curation vocabularies (spec §4.6)."""

import pytest
from sqlalchemy import text

VOCAB_TABLES = [
    "cohort_values",
    "detection_method_values",
    "segregation_values",
    "family_history_values",
]

EXPECTED_VALUES = {
    "cohort_values": {"born", "fetus"},
    "detection_method_values": {
        "sanger",
        "ngs",
        "cma",
        "mlpa",
        "qpcr",
        "fish",
        "other",
        "not_reported",
    },
    "segregation_values": {
        "de_novo",
        "inherited_maternal",
        "inherited_paternal",
        "inherited_unspecified",
        "not_reported",
    },
    "family_history_values": {"positive", "negative", "not_reported"},
}


@pytest.mark.parametrize("table", VOCAB_TABLES)
@pytest.mark.asyncio
async def test_table_exists_with_expected_columns(db_session, table):
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t ORDER BY column_name"
        ),
        {"t": table},
    )
    columns = {row[0] for row in result.fetchall()}
    assert {"value", "label", "description", "sort_order"} <= columns


@pytest.mark.parametrize("table", VOCAB_TABLES)
@pytest.mark.asyncio
async def test_seeded_with_expected_values(db_session, table):
    result = await db_session.execute(text(f"SELECT value FROM {table}"))  # noqa: S608
    assert {row[0] for row in result.fetchall()} == EXPECTED_VALUES[table]


@pytest.mark.parametrize("table", VOCAB_TABLES)
@pytest.mark.asyncio
async def test_sort_order_is_dense_and_unique(db_session, table):
    result = await db_session.execute(
        text(f"SELECT sort_order FROM {table} ORDER BY sort_order")  # noqa: S608
    )
    orders = [row[0] for row in result.fetchall()]
    assert orders == list(range(1, len(orders) + 1))


@pytest.mark.asyncio
async def test_not_reported_present_where_the_source_records_silence(db_session):
    """`not_reported` means the curator read the source and it was silent.

    Cohort is excluded on purpose: the spreadsheet states it for all 939 rows,
    so absence of the key means 'not yet curated' instead.
    """
    for table in (
        "detection_method_values",
        "segregation_values",
        "family_history_values",
    ):
        result = await db_session.execute(
            text(f"SELECT 1 FROM {table} WHERE value = 'not_reported'")  # noqa: S608
        )
        assert result.first() is not None, table

    result = await db_session.execute(
        text("SELECT 1 FROM cohort_values WHERE value = 'not_reported'")
    )
    assert result.first() is None
