"""The source column map is an explicit conservation contract."""

from migration.phenopackets.source_column_map import (
    SOURCE_COLUMNS,
    validate_source_headers,
)


def test_all_sixty_source_columns_have_exactly_one_owned_observation_path():
    assert len(SOURCE_COLUMNS) == 60
    assert len({entry.header for entry in SOURCE_COLUMNS}) == 60
    assert all(entry.observation_path for entry in SOURCE_COLUMNS)
    validate_source_headers([entry.header for entry in SOURCE_COLUMNS])
