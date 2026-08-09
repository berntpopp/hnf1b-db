"""The legacy CLI must fail closed instead of importing reviewer accounts or rows."""

import inspect

from migration.direct_sheets_to_phenopackets import DirectSheetsToPhenopackets


def test_direct_orchestration_has_no_embedded_sheet_authority_or_user_import():
    source = inspect.getsource(DirectSheetsToPhenopackets)
    assert "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw" not in source
    assert "UserImportService" not in source


def test_direct_orchestration_refuses_legacy_raw_storage_apply():
    migration = DirectSheetsToPhenopackets(
        "postgresql+asyncpg://test:test@localhost/test_db"
    )
    assert migration.legacy_apply_is_disabled is True
