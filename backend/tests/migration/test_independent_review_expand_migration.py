"""Database behavior contract for the nullable independent-review expansion."""

from __future__ import annotations

import importlib.util
import re
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database import Base


def _migration_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/d0f422b00005_expand_independent_review_audit.py"
    )
    assert path.exists(), (
        "independent-review expand migration is missing; without it deployed "
        "databases cannot store review audit evidence"
    )
    spec = importlib.util.spec_from_file_location("independent_review_expand", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _normalize_sql(sql: str) -> str:
    without_reflection_casts = sql.replace("::text", "")
    return re.sub(r"[()\s]+", " ", without_reflection_casts).strip().lower()


def _assert_check_rejects(connection, statement: str, parameters: dict) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(text(statement), parameters)


def test_expand_migration_catches_wrong_revision_chain():
    """The additive migration must extend, never rewrite, the current head."""
    migration = _migration_module()

    assert migration.revision == "d0f422b00005"
    assert migration.down_revision == "c0f422b00004"


def test_expand_migration_catches_missing_database_guards_and_downgrade_cleanup():
    """Upgrade must enforce audit shape without activating workflow triggers."""
    migration = _migration_module()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    schema = f"review_expand_{uuid.uuid4().hex}"

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                connection.execute(text("CREATE TABLE users (id BIGINT PRIMARY KEY)"))
                connection.execute(
                    text("CREATE TABLE phenopackets (id UUID PRIMARY KEY)")
                )
                connection.execute(
                    text("CREATE TABLE phenopacket_revisions (id BIGINT PRIMARY KEY)")
                )
                connection.execute(
                    text(
                        """
                        CREATE FUNCTION prevent_revision_mutation()
                        RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                            RAISE EXCEPTION 'phenopacket revisions are immutable';
                        END;
                        $$
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TRIGGER phenopacket_revisions_immutable
                        BEFORE UPDATE OR DELETE ON phenopacket_revisions
                        FOR EACH ROW EXECUTE FUNCTION prevent_revision_mutation()
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE comments (
                            id BIGINT PRIMARY KEY,
                            record_type TEXT NOT NULL,
                            record_id UUID NOT NULL,
                            resolved_at TIMESTAMPTZ,
                            deleted_at TIMESTAMPTZ
                        )
                        """
                    )
                )
                connection.execute(text("INSERT INTO users (id) VALUES (1)"))
                connection.execute(
                    text("INSERT INTO phenopacket_revisions (id) VALUES (1)")
                )
                record_id = uuid.uuid4()
                connection.execute(
                    text(
                        "INSERT INTO comments (id, record_type, record_id) "
                        "VALUES (1, 'phenopacket', :record_id)"
                    ),
                    {"record_id": record_id},
                )

                migration.op = Operations(
                    MigrationContext.configure(
                        connection, opts={"target_metadata": Base.metadata}
                    )
                )
                migration.upgrade()

                inspector = inspect(connection)
                revision_columns = {
                    column["name"]: column
                    for column in inspector.get_columns(
                        "phenopacket_revisions", schema=schema
                    )
                }
                assert {
                    "actor_role",
                    "decision_metadata",
                    "content_sha256",
                    "ledger_version",
                } <= revision_columns.keys()
                assert all(
                    revision_columns[name]["nullable"]
                    for name in (
                        "actor_role",
                        "decision_metadata",
                        "content_sha256",
                        "ledger_version",
                    )
                )
                assert connection.execute(
                    text(
                        """
                        SELECT actor_role, decision_metadata,
                               content_sha256, ledger_version
                        FROM phenopacket_revisions
                        WHERE id = 1
                        """
                    )
                ).one() == (None, None, None, None)

                comment_columns = {
                    column["name"]: column
                    for column in inspector.get_columns("comments", schema=schema)
                }
                assert comment_columns["review_revision_id"]["nullable"]
                assert (
                    connection.execute(
                        text("SELECT review_revision_id FROM comments WHERE id = 1")
                    ).scalar_one_or_none()
                    is None
                )
                comment_fks = inspector.get_foreign_keys("comments", schema=schema)
                assert any(
                    fk["constrained_columns"] == ["review_revision_id"]
                    and fk["referred_table"] == "phenopacket_revisions"
                    and fk["options"].get("ondelete") == "RESTRICT"
                    for fk in comment_fks
                )

                event_columns = {
                    column["name"]: column
                    for column in inspector.get_columns(
                        "comment_resolution_events", schema=schema
                    )
                }
                assert event_columns.keys() >= {
                    "id",
                    "comment_id",
                    "action",
                    "disposition",
                    "rationale",
                    "actor_id",
                    "actor_role",
                    "created_at",
                }
                assert event_columns["disposition"]["nullable"]
                assert all(
                    not event_columns[name]["nullable"]
                    for name in (
                        "id",
                        "comment_id",
                        "action",
                        "rationale",
                        "actor_id",
                        "actor_role",
                        "created_at",
                    )
                )
                event_fks = inspector.get_foreign_keys(
                    "comment_resolution_events", schema=schema
                )
                assert {
                    (
                        tuple(fk["constrained_columns"]),
                        fk["referred_table"],
                        fk["options"].get("ondelete"),
                    )
                    for fk in event_fks
                } >= {
                    (("comment_id",), "comments", "RESTRICT"),
                    (("actor_id",), "users", "RESTRICT"),
                }

                revision_checks = {
                    check["name"]: _normalize_sql(check["sqltext"])
                    for check in inspector.get_check_constraints(
                        "phenopacket_revisions", schema=schema
                    )
                }
                assert revision_checks.keys() >= {
                    "ck_phenopacket_revisions_actor_role",
                    "ck_phenopacket_revisions_content_sha256",
                    "ck_phenopacket_revisions_ledger_version",
                    "ck_phenopacket_revisions_decision_metadata_ledger",
                }
                event_checks = {
                    check["name"]: _normalize_sql(check["sqltext"])
                    for check in inspector.get_check_constraints(
                        "comment_resolution_events", schema=schema
                    )
                }
                assert event_checks.keys() >= {
                    "ck_comment_resolution_event_action_disposition",
                    "ck_comment_resolution_event_rationale",
                    "ck_comment_resolution_event_actor_role",
                }

                indexes = {
                    index["name"]: index
                    for index in inspector.get_indexes("comments", schema=schema)
                }
                blocking_index = indexes[
                    "ix_comments_live_unresolved_phenopacket_review_issues"
                ]
                assert blocking_index["column_names"] == [
                    "record_id",
                    "review_revision_id",
                ]
                predicate = str(blocking_index["dialect_options"]["postgresql_where"])
                assert _normalize_sql(predicate) == _normalize_sql(
                    "record_type = 'phenopacket' AND "
                    "review_revision_id IS NOT NULL AND resolved_at IS NULL AND "
                    "deleted_at IS NULL"
                )

                trigger_enabled = connection.execute(
                    text(
                        """
                        SELECT t.tgenabled
                        FROM pg_trigger AS t
                        JOIN pg_class AS c ON c.oid = t.tgrelid
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = :schema
                          AND c.relname = 'phenopacket_revisions'
                          AND t.tgname = 'phenopacket_revisions_immutable'
                        """
                    ),
                    {"schema": schema},
                ).scalar_one()
                assert trigger_enabled == "O"
                assert (
                    connection.execute(
                        text(
                            """
                            SELECT count(*)
                            FROM pg_trigger AS t
                            JOIN pg_class AS c ON c.oid = t.tgrelid
                            JOIN pg_namespace AS n ON n.oid = c.relnamespace
                            WHERE n.nspname = :schema
                              AND c.relname IN (
                                  'comments', 'comment_resolution_events'
                              )
                              AND NOT t.tgisinternal
                            """
                        ),
                        {"schema": schema},
                    ).scalar_one()
                    == 0
                )

                valid_revisions = connection.begin_nested()
                connection.execute(
                    text(
                        """
                        INSERT INTO phenopacket_revisions
                            (id, actor_role, decision_metadata,
                             content_sha256, ledger_version)
                        VALUES
                            (2, 'viewer', NULL, NULL, 2),
                            (3, 'curator', '{}'::jsonb,
                             :digest, 2),
                            (4, 'admin', NULL, NULL, NULL)
                        """
                    ),
                    {"digest": f"sha256:{'a' * 64}"},
                )
                valid_revisions.rollback()

                _assert_check_rejects(
                    connection,
                    "INSERT INTO phenopacket_revisions "
                    "(id, content_sha256) VALUES (2, 'sha256:not-a-digest')",
                    {},
                )
                _assert_check_rejects(
                    connection,
                    "INSERT INTO phenopacket_revisions "
                    "(id, ledger_version) VALUES (2, 1)",
                    {},
                )
                _assert_check_rejects(
                    connection,
                    "INSERT INTO phenopacket_revisions "
                    "(id, decision_metadata, ledger_version) "
                    "VALUES (2, '{}'::jsonb, 1)",
                    {},
                )
                _assert_check_rejects(
                    connection,
                    "INSERT INTO phenopacket_revisions "
                    "(id, actor_role) VALUES (2, 'superuser')",
                    {},
                )
                _assert_check_rejects(
                    connection,
                    """
                    INSERT INTO comment_resolution_events
                        (comment_id, action, disposition, rationale, actor_id, actor_role)
                    VALUES (1, 'reopened', 'addressed', 'reopened', 1, 'curator')
                    """,
                    {},
                )
                _assert_check_rejects(
                    connection,
                    """
                    INSERT INTO comment_resolution_events
                        (comment_id, action, disposition, rationale, actor_id, actor_role)
                    VALUES (1, 'resolved', 'addressed', '   ', 1, 'curator')
                    """,
                    {},
                )
                _assert_check_rejects(
                    connection,
                    """
                    INSERT INTO comment_resolution_events
                        (comment_id, action, disposition, rationale, actor_id, actor_role)
                    VALUES (1, 'resolved', 'addressed', :rationale, 1, 'curator')
                    """,
                    {"rationale": "x" * 501},
                )
                _assert_check_rejects(
                    connection,
                    """
                    INSERT INTO comment_resolution_events
                        (comment_id, action, disposition, rationale, actor_id, actor_role)
                    VALUES (1, 'resolved', 'addressed', 'valid', 1, 'viewer')
                    """,
                    {},
                )
                _assert_check_rejects(
                    connection,
                    """
                    INSERT INTO comment_resolution_events
                        (comment_id, action, disposition, rationale, actor_id, actor_role)
                    VALUES (1, 'deleted', NULL, 'valid', 1, 'curator')
                    """,
                    {},
                )
                _assert_check_rejects(
                    connection,
                    """
                    INSERT INTO comment_resolution_events
                        (comment_id, action, disposition, rationale, actor_id, actor_role)
                    VALUES (1, 'resolved', 'ignored', 'valid', 1, 'curator')
                    """,
                    {},
                )
                for disposition in (
                    "addressed",
                    "accepted_with_rationale",
                    "retracted",
                    "superseded",
                ):
                    connection.execute(
                        text(
                            """
                            INSERT INTO comment_resolution_events
                                (comment_id, action, disposition, rationale,
                                 actor_id, actor_role)
                            VALUES
                                (1, 'resolved', :disposition, 'valid', 1, 'curator')
                            """
                        ),
                        {"disposition": disposition},
                    )
                connection.execute(
                    text(
                        """
                        INSERT INTO comment_resolution_events
                            (comment_id, action, disposition, rationale,
                             actor_id, actor_role)
                        VALUES (1, 'reopened', NULL, 'valid', 1, 'admin')
                        """
                    )
                )
                connection.execute(text("DELETE FROM comment_resolution_events"))
                assert (
                    connection.execute(
                        text("SELECT count(*) FROM comment_resolution_events")
                    ).scalar_one()
                    == 0
                )
                assert (
                    connection.execute(
                        text(
                            """
                            SELECT count(*) FROM phenopacket_revisions
                            WHERE actor_role IS NOT NULL
                               OR decision_metadata IS NOT NULL
                               OR content_sha256 IS NOT NULL
                               OR ledger_version IS NOT NULL
                            """
                        )
                    ).scalar_one()
                    == 0
                )

                migration.downgrade()
                inspector = inspect(connection)
                assert not inspector.has_table(
                    "comment_resolution_events", schema=schema
                )
                assert {
                    column["name"]
                    for column in inspector.get_columns(
                        "phenopacket_revisions", schema=schema
                    )
                } == {"id"}
                assert {
                    column["name"]
                    for column in inspector.get_columns("comments", schema=schema)
                } == {
                    "id",
                    "record_type",
                    "record_id",
                    "resolved_at",
                    "deleted_at",
                }
                assert (
                    connection.execute(
                        text(
                            """
                        SELECT t.tgenabled
                        FROM pg_trigger AS t
                        JOIN pg_class AS c ON c.oid = t.tgrelid
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = :schema
                          AND c.relname = 'phenopacket_revisions'
                          AND t.tgname = 'phenopacket_revisions_immutable'
                        """
                        ),
                        {"schema": schema},
                    ).scalar_one()
                    == "O"
                )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
