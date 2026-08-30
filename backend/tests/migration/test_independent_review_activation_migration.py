"""Real PostgreSQL behavior for independent-review invariant activation."""

from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import settings
from app.database import Base


def _migration_module(
    name: str = "e0f422b00006_activate_independent_review_invariants",
):
    path = Path(__file__).resolve().parents[2] / f"alembic/versions/{name}.py"
    assert path.exists(), f"activation migration is missing: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


class _GuardResult:
    def __init__(self, state: dict[str, int]) -> None:
        self.state = state

    def mappings(self):
        return self

    def one(self) -> dict[str, int]:
        return self.state


class _GuardBind:
    def __init__(self, state: dict[str, int]) -> None:
        self.state = state

    def execute(self, _statement):
        return _GuardResult(self.state)


_EMPTY_GUARD = {
    "blocking_issues": 0,
    "resolution_events": 0,
    "v2_revisions": 0,
    "decision_metadata": 0,
    "actor_roles": 0,
    "content_digests": 0,
}


def test_activation_revision_extends_exact_expansion_head() -> None:
    migration = _migration_module()
    assert migration.revision == "e0f422b00006"
    assert migration.down_revision == "d0f422b00005"


def test_forward_reconciliation_revision_extends_activation_head() -> None:
    migration = _migration_module(
        "f0f422b00007_reconcile_independent_review_activation"
    )
    assert migration.revision == "f0f422b00007"
    assert migration.down_revision == "e0f422b00006"


@pytest.mark.parametrize(
    "migration_name",
    [
        "d0f422b00005_expand_independent_review_audit",
        "e0f422b00006_activate_independent_review_invariants",
    ],
)
@pytest.mark.parametrize("evidence_key", list(_EMPTY_GUARD))
def test_both_downgrades_refuse_each_audit_evidence_class(
    migration_name: str, evidence_key: str
) -> None:
    migration = _migration_module(migration_name)
    state = {**_EMPTY_GUARD, evidence_key: 1}
    with pytest.raises(RuntimeError, match=evidence_key):
        migration.assert_independent_review_downgrade_safe(_GuardBind(state))


@contextmanager
def _isolated_schema():
    migration = _migration_module()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    schema = f"review_activation_{uuid.uuid4().hex}"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                connection.execute(
                    text(
                        """
                        CREATE TABLE users (
                            id BIGINT PRIMARY KEY,
                            role TEXT NOT NULL,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE
                        );
                        CREATE TABLE phenopackets (
                            id UUID PRIMARY KEY, state TEXT NOT NULL,
                            revision INTEGER NOT NULL, editing_revision_id BIGINT,
                            head_published_revision_id BIGINT, draft_owner_id BIGINT
                        );
                        CREATE TABLE phenopacket_revisions (
                            id BIGSERIAL PRIMARY KEY, record_id UUID NOT NULL,
                            parent_revision_id BIGINT, revision_number INTEGER NOT NULL,
                            state TEXT NOT NULL, event_type TEXT, actor_id BIGINT,
                            actor_role TEXT, decision_metadata JSONB,
                            content_sha256 TEXT, ledger_version INTEGER
                        );
                        CREATE TABLE comments (
                            id BIGSERIAL PRIMARY KEY, record_type TEXT NOT NULL,
                            record_id UUID NOT NULL, author_id BIGINT NOT NULL,
                            body_markdown TEXT NOT NULL, resolved_at TIMESTAMPTZ,
                            resolved_by_id BIGINT, deleted_at TIMESTAMPTZ,
                            deleted_by_id BIGINT, review_revision_id BIGINT,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        );
                        CREATE TABLE comment_resolution_events (
                            id BIGSERIAL PRIMARY KEY, comment_id BIGINT NOT NULL,
                            action TEXT NOT NULL, disposition TEXT, rationale TEXT NOT NULL,
                            actor_id BIGINT NOT NULL, actor_role TEXT NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        );
                        """
                    )
                )
                yield connection, schema, migration
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _install_existing_triggers(connection) -> None:
    connection.execute(
        text(
            """
            CREATE FUNCTION validate_phenopacket_revision_pointer()
            RETURNS trigger AS $$
            DECLARE packet phenopackets%ROWTYPE;
            BEGIN
                SELECT * INTO packet FROM phenopackets WHERE id = NEW.id;
                IF packet.head_published_revision_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM phenopacket_revisions revision
                    WHERE revision.id = packet.head_published_revision_id
                      AND revision.record_id = packet.id AND revision.state = 'published'
                ) THEN RAISE EXCEPTION 'invalid published pointer'; END IF;
                IF packet.state = 'published' AND packet.head_published_revision_id IS NULL
                THEN RAISE EXCEPTION 'published phenopacket requires head'; END IF;
                IF packet.editing_revision_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM phenopacket_revisions revision
                    WHERE revision.id = packet.editing_revision_id
                      AND revision.record_id = packet.id
                      AND revision.state IN ('draft','in_review','changes_requested','approved')
                ) THEN RAISE EXCEPTION 'invalid editing pointer'; END IF;
                IF packet.state = 'archived' AND packet.editing_revision_id IS NOT NULL
                THEN RAISE EXCEPTION 'archived pointer'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE CONSTRAINT TRIGGER phenopackets_revision_pointer_owner
            AFTER INSERT OR UPDATE OF head_published_revision_id, editing_revision_id, state
            ON phenopackets DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION validate_phenopacket_revision_pointer();

            CREATE FUNCTION validate_phenopacket_revision_parent()
            RETURNS trigger AS $$ BEGIN
                IF NEW.parent_revision_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM phenopacket_revisions parent
                    WHERE parent.id = NEW.parent_revision_id
                      AND parent.record_id = NEW.record_id
                ) THEN RAISE EXCEPTION 'parent revision must belong to its record'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER phenopacket_revisions_parent_owner
            BEFORE INSERT ON phenopacket_revisions
            FOR EACH ROW EXECUTE FUNCTION validate_phenopacket_revision_parent();

            CREATE FUNCTION reject_phenopacket_revision_mutation()
            RETURNS trigger AS $$ BEGIN
                RAISE EXCEPTION 'phenopacket revisions are append-only';
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER phenopacket_revisions_immutable
            BEFORE UPDATE OR DELETE ON phenopacket_revisions
            FOR EACH ROW EXECUTE FUNCTION reject_phenopacket_revision_mutation();
            """
        )
    )


def _bind(connection, migration) -> None:
    migration.op = Operations(
        MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
    )


def _seed_active_review(connection, record_id: uuid.UUID, owner: int | None) -> None:
    connection.execute(
        text("INSERT INTO users VALUES (1, 'curator', TRUE), (2, 'curator', TRUE)")
    )
    connection.execute(
        text(
            """
            INSERT INTO phenopacket_revisions
                (id, record_id, parent_revision_id, revision_number, state,
                 event_type, actor_id)
            VALUES
                (1, :id, NULL, 1, 'draft', 'created', 1),
                (2, :id, 1, 2, 'in_review', 'state_transition', 1)
            """
        ),
        {"id": record_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO phenopackets
                (id, state, revision, editing_revision_id,
                 head_published_revision_id, draft_owner_id)
            VALUES (:id, 'in_review', 2, 2, NULL, :owner)
            """
        ),
        {"id": record_id, "owner": owner},
    )


def _seed_actor_eligibility_review(connection, record_id: uuid.UUID) -> None:
    """Seed literal reviewer roles and one never-published candidate ancestry."""
    connection.execute(
        text(
            """INSERT INTO users (id,role,is_active) VALUES
            (1,'admin',TRUE),
            (2,'curator',TRUE),
            (3,'admin',TRUE),
            (4,'curator',FALSE),
            (5,'viewer',TRUE),
            (6,'curator',TRUE),
            (7,'admin',TRUE)"""
        )
    )
    connection.execute(
        text(
            """INSERT INTO phenopacket_revisions
            (id,record_id,parent_revision_id,revision_number,state,event_type,actor_id)
            VALUES
            (1,:id,NULL,1,'draft','created',1),
            (2,:id,1,2,'draft','draft_saved',3),
            (3,:id,2,3,'in_review','state_transition',2)"""
        ),
        {"id": record_id},
    )
    connection.execute(
        text(
            """INSERT INTO phenopackets
            (id,state,revision,editing_revision_id,draft_owner_id)
            VALUES (:id,'in_review',3,3,1)"""
        ),
        {"id": record_id},
    )


def _pointer_trigger(connection, schema):
    return connection.execute(
        text(
            """
            SELECT t.oid, t.tgdeferrable, t.tginitdeferred
            FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema AND c.relname = 'phenopackets'
              AND t.tgname = 'phenopackets_revision_pointer_owner'
            """
        ),
        {"schema": schema},
    ).one()


def test_upgrade_backfills_owner_and_preserves_pointer_trigger_identity() -> None:
    with _isolated_schema() as (connection, schema, migration):
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, None)
        _install_existing_triggers(connection)
        before = _pointer_trigger(connection, schema)
        _bind(connection, migration)
        migration.upgrade()

        assert (
            connection.execute(
                text("SELECT draft_owner_id FROM phenopackets WHERE id=:id"),
                {"id": record_id},
            ).scalar_one()
            == 1
        )
        assert _pointer_trigger(connection, schema) == before
        triggers = connection.execute(
            text(
                """
                SELECT c.relname, t.tgname, t.tgdeferrable, t.tginitdeferred
                FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND NOT t.tgisinternal
                ORDER BY c.relname, t.tgname
                """
            ),
            {"schema": schema},
        ).all()
        names = {(row[0], row[1]) for row in triggers}
        assert {
            ("phenopacket_revisions", "phenopacket_revisions_00_lock_record"),
            ("comments", "comments_review_issue_guard"),
            ("comments", "comments_review_issue_final_state"),
            ("comment_resolution_events", "comment_resolution_events_lock_record"),
            (
                "comment_resolution_events",
                "comment_resolution_events_projection_final_state",
            ),
            (
                "comment_resolution_events",
                "comment_resolution_events_project_comment",
            ),
            ("comment_resolution_events", "comment_resolution_events_immutable"),
        } <= names
        final_trigger = next(
            row for row in triggers if row[1] == "comments_review_issue_final_state"
        )
        assert final_trigger[2:] == (True, True)
        event_final_trigger = next(
            row
            for row in triggers
            if row[1] == "comment_resolution_events_projection_final_state"
        )
        assert event_final_trigger[2:] == (True, True)

        with pytest.raises(IntegrityError, match="active_edit_owner"):
            with connection.begin_nested():
                connection.execute(
                    text("INSERT INTO phenopackets VALUES (:id,'draft',1,2,NULL,NULL)"),
                    {"id": uuid.uuid4()},
                )

        migration.downgrade()
        assert (
            connection.execute(
                text("SELECT draft_owner_id FROM phenopackets WHERE id=:id"),
                {"id": record_id},
            ).scalar_one()
            == 1
        )
        assert _pointer_trigger(connection, schema) == before


def test_database_event_atomically_projects_resolution_and_rejects_issue_erasure() -> (
    None
):
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )
        with pytest.raises(DBAPIError, match="review_issue_resolution_event_required"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        "UPDATE comments SET resolved_at=now(), resolved_by_id=2 WHERE id=1"
                    )
                )

        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','fixed',2,'curator')"""
            )
        )
        assert connection.execute(
            text(
                "SELECT resolved_at IS NOT NULL, resolved_by_id FROM comments WHERE id=1"
            )
        ).one() == (True, 2)
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        for statement in (
            "UPDATE comments SET review_revision_id=NULL WHERE id=1",
            "UPDATE comments SET author_id=1 WHERE id=1",
            "UPDATE comments SET deleted_at=now() WHERE id=1",
            "DELETE FROM comments WHERE id=1",
        ):
            with pytest.raises(DBAPIError, match="review_issue_mutation_forbidden"):
                with connection.begin_nested():
                    connection.execute(text(statement))
        for statement in (
            "UPDATE comment_resolution_events SET rationale='tampered' WHERE id=1",
            "DELETE FROM comment_resolution_events WHERE id=1",
        ):
            with pytest.raises(DBAPIError, match="resolution events are append-only"):
                with connection.begin_nested():
                    connection.execute(text(statement))


def test_database_rejects_duplicate_event_after_atomic_projection() -> None:
    """An event projects immediately, so a duplicate action is rejected."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','first',2,'curator')"""
            )
        )

        with pytest.raises(DBAPIError, match="review_issue_already_resolved"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """INSERT INTO comment_resolution_events
                        (comment_id,action,disposition,rationale,actor_id,actor_role)
                        VALUES (1,'resolved','addressed','duplicate',2,'curator')"""
                    )
                )

        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'reopened',NULL,'supported reopen',2,'curator')"""
            )
        )
        assert connection.execute(
            text("SELECT resolved_at, resolved_by_id FROM comments WHERE id=1")
        ).one() == (None, None)
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_database_enforces_issue_author_independence_and_role() -> None:
    """Raw issue insertion applies owner/submitter/contributor/account policy."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        _seed_actor_eligibility_review(connection, record_id)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        denied = (
            (1, "self_review_forbidden"),
            (2, "reviewer_submitted"),
            (3, "reviewer_contributed"),
            (4, "reviewer_not_eligible"),
            (5, "reviewer_not_eligible"),
        )
        for author_id, error in denied:
            with pytest.raises(DBAPIError, match=error):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """INSERT INTO comments
                            (record_type,record_id,author_id,body_markdown,
                             review_revision_id)
                            VALUES ('phenopacket',:id,:author_id,'denied',3)"""
                        ),
                        {"id": record_id, "author_id": author_id},
                    )

        for author_id in (6, 7):
            connection.execute(
                text(
                    """INSERT INTO comments
                    (record_type,record_id,author_id,body_markdown,review_revision_id)
                    VALUES ('phenopacket',:id,:author_id,'eligible',3)"""
                ),
                {"id": record_id, "author_id": author_id},
            )
        assert (
            connection.execute(text("SELECT count(*) FROM comments")).scalar_one() == 2
        )


def test_database_enforces_resolution_event_actor_independence_and_role() -> None:
    """Raw issue events verify the stored user, role claim, and independence."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        _seed_actor_eligibility_review(connection, record_id)
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES
                (1,'phenopacket',:id,6,'curator path',3),
                (2,'phenopacket',:id,7,'admin path',3)"""
            ),
            {"id": record_id},
        )
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        denied = (
            (1, "admin", "self_review_forbidden"),
            (2, "curator", "reviewer_submitted"),
            (3, "admin", "reviewer_contributed"),
            (4, "curator", "reviewer_not_eligible"),
            (5, "viewer", "reviewer_not_eligible"),
            (7, "curator", "reviewer_actor_role_mismatch"),
        )
        for actor_id, actor_role, error in denied:
            with pytest.raises(DBAPIError, match=error):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            """INSERT INTO comment_resolution_events
                            (comment_id,action,disposition,rationale,actor_id,actor_role)
                            VALUES
                            (1,'resolved','addressed','denied',:actor_id,:actor_role)"""
                        ),
                        {"actor_id": actor_id, "actor_role": actor_role},
                    )

        for comment_id, actor_id, actor_role in (
            (1, 6, "curator"),
            (2, 7, "admin"),
        ):
            connection.execute(
                text(
                    """INSERT INTO comment_resolution_events
                    (comment_id,action,disposition,rationale,actor_id,actor_role)
                    VALUES
                    (:comment_id,'resolved','addressed','eligible',:actor_id,:actor_role)"""
                ),
                {
                    "comment_id": comment_id,
                    "actor_id": actor_id,
                    "actor_role": actor_role,
                },
            )
        assert (
            connection.execute(
                text("SELECT count(*) FROM comment_resolution_events")
            ).scalar_one()
            == 2
        )


def _drop_projection_trigger_for_old_e0(connection) -> None:
    connection.execute(
        text(
            """
            DROP TRIGGER comment_resolution_events_project_comment
                ON comment_resolution_events;
            DROP FUNCTION project_comment_resolution_event();
            """
        )
    )


def test_forward_reconciliation_repairs_old_e0_missing_projection_trigger() -> None:
    """Already-stamped e0 schemas converge without losing audit rows."""
    with _isolated_schema() as (connection, schema, migration):
        forward = _migration_module(
            "f0f422b00007_reconcile_independent_review_activation"
        )
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()
        _drop_projection_trigger_for_old_e0(connection)
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','project after repair',2,'curator')"""
            )
        )

        _bind(connection, forward)
        forward.upgrade()

        assert connection.execute(
            text(
                "SELECT resolved_at IS NOT NULL, resolved_by_id FROM comments WHERE id=1"
            )
        ).one() == (True, 2)
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'reopened',NULL,'reopen after repair',2,'curator')"""
            )
        )
        assert connection.execute(
            text("SELECT resolved_at, resolved_by_id FROM comments WHERE id=1")
        ).one() == (None, None)
        with pytest.raises(DBAPIError, match="review_issue_mutation_forbidden"):
            with connection.begin_nested():
                connection.execute(text("UPDATE comments SET author_id=1 WHERE id=1"))

        forward.downgrade()
        assert (
            connection.execute(
                text("SELECT count(*) FROM comment_resolution_events")
            ).scalar_one()
            == 2
        )
        assert connection.execute(
            text(
                """
                SELECT count(*) FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema
                  AND c.relname = 'comment_resolution_events'
                  AND t.tgname = 'comment_resolution_events_project_comment'
                """
            ),
            {"schema": schema},
        ).scalar_one() == 1


def test_forward_reconciliation_repairs_same_actor_resolved_timestamp_drift() -> None:
    """Resolved projections converge exactly to the latest event timestamp."""
    with _isolated_schema() as (connection, _schema, migration):
        forward = _migration_module(
            "f0f422b00007_reconcile_independent_review_activation"
        )
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','project after repair',2,'curator')"""
            )
        )
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        event_timestamp = connection.execute(
            text("SELECT created_at FROM comment_resolution_events WHERE id=1")
        ).scalar_one()
        connection.execute(
            text("DROP TRIGGER comments_review_issue_mutation_guard ON comments")
        )
        connection.execute(
            text(
                "DROP TRIGGER comment_resolution_events_projection_final_state "
                "ON comment_resolution_events"
            )
        )
        connection.execute(
            text(
                """
                UPDATE comments
                   SET resolved_at = CAST(:event_timestamp AS timestamptz)
                       - interval '1 day',
                       resolved_by_id = 2
                 WHERE id = 1
                """
            ),
            {"event_timestamp": event_timestamp},
        )

        _bind(connection, forward)
        forward.upgrade()

        assert (
            connection.execute(
                text("SELECT resolved_at FROM comments WHERE id=1")
            ).scalar_one()
            == event_timestamp
        )
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_forward_projection_validator_rejects_null_resolved_projection() -> None:
    """A resolved event with no projected timestamp must fail closed."""
    with _isolated_schema() as (connection, _schema, migration):
        forward = _migration_module(
            "f0f422b00007_reconcile_independent_review_activation"
        )
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        _bind(connection, forward)
        forward.upgrade()
        connection.execute(
            text(
                "DROP TRIGGER comment_resolution_events_project_comment "
                "ON comment_resolution_events"
            )
        )
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )

        with pytest.raises(
            DBAPIError, match="review_issue_resolution_projection_mismatch"
        ):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """INSERT INTO comment_resolution_events
                        (comment_id,action,disposition,rationale,actor_id,actor_role)
                        VALUES (1,'resolved','addressed','missing projection',2,'curator')"""
                    )
                )
                connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_forward_reconciliation_is_idempotent_for_fresh_activation_schema() -> None:
    """Fresh e0 installs keep the same final projection and mutation guards."""
    with _isolated_schema() as (connection, _schema, migration):
        forward = _migration_module(
            "f0f422b00007_reconcile_independent_review_activation"
        )
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        _bind(connection, forward)
        forward.upgrade()
        forward.upgrade()

        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','fresh projection',2,'curator')"""
            )
        )
        assert connection.execute(
            text(
                "SELECT resolved_at IS NOT NULL, resolved_by_id FROM comments WHERE id=1"
            )
        ).one() == (True, 2)
        with pytest.raises(DBAPIError, match="review_issue_mutation_forbidden"):
            with connection.begin_nested():
                connection.execute(text("UPDATE comments SET author_id=1 WHERE id=1"))


def test_unresolved_current_cycle_issue_blocks_approved_revision_insert() -> None:
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()
        connection.execute(
            text(
                """INSERT INTO comments
                (record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES ('phenopacket',:id,2,'issue',2)"""
            ),
            {"id": record_id},
        )
        with pytest.raises(DBAPIError, match="unresolved_review_issues"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """INSERT INTO phenopacket_revisions
                        (record_id,parent_revision_id,revision_number,state,event_type,actor_id)
                        VALUES (:id,2,3,'approved','state_transition',2)"""
                    ),
                    {"id": record_id},
                )


def test_old_issue_in_never_published_active_ancestry_can_resolve() -> None:
    """An earlier candidate in the live ancestry remains an actionable issue."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        connection.execute(
            text("INSERT INTO users VALUES (1, 'curator', TRUE), (2, 'curator', TRUE)")
        )
        connection.execute(
            text(
                """
                INSERT INTO phenopacket_revisions
                    (id,record_id,parent_revision_id,revision_number,state,
                     event_type,actor_id)
                VALUES
                    (1,:id,NULL,1,'draft','created',1),
                    (2,:id,1,2,'in_review','state_transition',1),
                    (3,:id,2,3,'changes_requested','state_transition',2),
                    (4,:id,3,4,'draft','draft_saved',1),
                    (5,:id,4,5,'in_review','state_transition',1)
                """
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO phenopackets
                (id,state,revision,editing_revision_id,draft_owner_id)
                VALUES (:id,'in_review',5,5,1)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'old live-cycle issue',2)"""
            ),
            {"id": record_id},
        )
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','fixed on resubmit',2,'curator')"""
            )
        )
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'reopened',NULL,'verify old issue',2,'curator')"""
            )
        )
        connection.execute(
            text(
                """INSERT INTO comment_resolution_events
                (comment_id,action,disposition,rationale,actor_id,actor_role)
                VALUES (1,'resolved','addressed','verified',2,'curator')"""
            )
        )
        connection.execute(
            text(
                """INSERT INTO phenopacket_revisions
                (id,record_id,parent_revision_id,revision_number,state,event_type,actor_id)
                VALUES (6,:id,5,6,'approved','state_transition',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """UPDATE phenopackets
                SET state='approved',revision=6,editing_revision_id=6 WHERE id=:id"""
            ),
            {"id": record_id},
        )
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_resolution_event_rejects_candidate_before_broken_active_cycle_root() -> None:
    """The event guard must validate ancestry beyond the linked issue candidate."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        connection.execute(
            text("INSERT INTO users VALUES (1, 'curator', TRUE), (2, 'curator', TRUE)")
        )
        connection.execute(
            text(
                """
                INSERT INTO phenopacket_revisions
                    (id,record_id,parent_revision_id,revision_number,state,
                     event_type,actor_id)
                VALUES
                    (2,:id,99,2,'in_review','state_transition',1),
                    (5,:id,2,5,'in_review','state_transition',1)
                """
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO phenopackets
                (id,state,revision,editing_revision_id,draft_owner_id)
                VALUES (:id,'in_review',5,5,1)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comments
                (id,record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES (1,'phenopacket',:id,2,'issue before broken root',2)"""
            ),
            {"id": record_id},
        )
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        with pytest.raises(DBAPIError, match="review_revision_mismatch"):
            connection.execute(
                text(
                    """INSERT INTO comment_resolution_events
                    (comment_id,action,disposition,rationale,actor_id,actor_role)
                    VALUES (1,'resolved','addressed','invalid ancestry',2,'curator')"""
                )
            )


def test_historical_cycle_issue_does_not_block_current_approval() -> None:
    """Only review snapshots newer than the exact public head gate approval."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        connection.execute(
            text("INSERT INTO users VALUES (1, 'curator', TRUE), (2, 'curator', TRUE)")
        )
        connection.execute(
            text(
                """
                INSERT INTO phenopacket_revisions
                    (id, record_id, parent_revision_id, revision_number, state,
                     event_type, actor_id)
                VALUES
                    (1, :id, NULL, 1, 'in_review', 'state_transition', 1),
                    (2, :id, 1, 2, 'published', 'state_transition', 2),
                    (3, :id, 2, 3, 'draft', 'draft_created', 1),
                    (4, :id, 3, 4, 'in_review', 'state_transition', 1)
                """
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO phenopackets
                    (id, state, revision, editing_revision_id,
                     head_published_revision_id, draft_owner_id)
                VALUES (:id, 'in_review', 4, 4, 2, 1)
                """
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comments
                (record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES ('phenopacket',:id,2,'historical issue',1)"""
            ),
            {"id": record_id},
        )
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        with pytest.raises(DBAPIError, match="review_revision_mismatch"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """INSERT INTO comment_resolution_events
                        (comment_id,action,disposition,rationale,actor_id,actor_role)
                        VALUES (1,'resolved','addressed','historical',2,'curator')"""
                    )
                )

        connection.execute(
            text(
                """INSERT INTO phenopacket_revisions
                (id,record_id,parent_revision_id,revision_number,state,event_type,actor_id)
                VALUES (5,:id,4,5,'approved','state_transition',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """UPDATE phenopackets
                SET state='approved', revision=5, editing_revision_id=:approved_id
                WHERE id=:id"""
            ),
            {"approved_id": 5, "id": record_id},
        )
        connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_database_rejects_wrong_record_review_revision_link() -> None:
    """A client cannot attach another record's immutable review snapshot."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        other_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        connection.execute(
            text(
                """INSERT INTO phenopacket_revisions
                (id,record_id,parent_revision_id,revision_number,state,event_type,actor_id)
                VALUES (3,:other_id,NULL,1,'in_review','state_transition',2)"""
            ),
            {"other_id": other_id},
        )
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()

        with pytest.raises(DBAPIError, match="review_revision_mismatch"):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """INSERT INTO comments
                        (record_type,record_id,author_id,body_markdown,review_revision_id)
                        VALUES ('phenopacket',:id,2,'wrong record',3)"""
                    ),
                    {"id": record_id},
                )


def test_deferred_pointer_check_rejects_approved_with_live_issue() -> None:
    """The augmented final-state trigger catches pointer-only approval bypasses."""
    with _isolated_schema() as (connection, _schema, migration):
        record_id = uuid.uuid4()
        _seed_active_review(connection, record_id, 1)
        _install_existing_triggers(connection)
        _bind(connection, migration)
        migration.upgrade()
        connection.execute(
            text(
                """INSERT INTO phenopacket_revisions
                (id,record_id,parent_revision_id,revision_number,state,event_type,actor_id)
                VALUES (3,:id,2,3,'approved','state_transition',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """INSERT INTO comments
                (record_type,record_id,author_id,body_markdown,review_revision_id)
                VALUES ('phenopacket',:id,2,'live issue',2)"""
            ),
            {"id": record_id},
        )
        connection.execute(
            text(
                """UPDATE phenopackets
                SET state='approved', revision=3, editing_revision_id=:approved_id
                WHERE id=:id"""
            ),
            {"approved_id": 3, "id": record_id},
        )

        with pytest.raises(DBAPIError, match="unresolved_review_issues"):
            with connection.begin_nested():
                connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_parent",
        "cross_record",
        "cycle",
        "nondecreasing",
        "missing_boundary",
        "multiple_roots",
    ],
)
def test_owner_preflight_refuses_ambiguous_ancestry_before_backfill(
    corruption: str,
) -> None:
    with _isolated_schema() as (connection, _schema, migration):
        first = uuid.UUID("00000000-0000-0000-0000-000000000001")
        second = uuid.UUID("00000000-0000-0000-0000-000000000002")
        connection.execute(
            text("INSERT INTO users VALUES (1,'curator',TRUE),(2,'curator',TRUE)")
        )
        connection.execute(
            text(
                """INSERT INTO phenopacket_revisions
                (id,record_id,parent_revision_id,revision_number,state,event_type,actor_id)
                VALUES
                (1,:first,NULL,1,'draft','created',1),
                (2,:first,1,2,'in_review','state_transition',1),
                (3,:second,NULL,1,'draft','created',2),
                (4,:second,3,2,'in_review','state_transition',2)"""
            ),
            {"first": first, "second": second},
        )
        corrupt_sql = {
            "missing_parent": "UPDATE phenopacket_revisions SET parent_revision_id=99 WHERE id=2",
            "cross_record": "UPDATE phenopacket_revisions SET parent_revision_id=3 WHERE id=2",
            "cycle": "UPDATE phenopacket_revisions SET parent_revision_id=2 WHERE id=1",
            "nondecreasing": "UPDATE phenopacket_revisions SET revision_number=2 WHERE id=1",
            "missing_boundary": "UPDATE phenopacket_revisions SET event_type='draft_saved' WHERE id=1",
            "multiple_roots": "UPDATE phenopacket_revisions SET event_type='created' WHERE id=2",
        }[corruption]
        connection.execute(text(corrupt_sql))
        connection.execute(
            text(
                """INSERT INTO phenopackets
                (id,state,revision,editing_revision_id,draft_owner_id) VALUES
                (:second,'in_review',2,4,NULL),(:first,'in_review',2,2,NULL)"""
            ),
            {"first": first, "second": second},
        )
        _install_existing_triggers(connection)
        _bind(connection, migration)
        with pytest.raises(DBAPIError) as exc_info, connection.begin_nested():
            migration.upgrade()
        message = str(exc_info.value)
        assert str(first) in message
        assert str(second) not in message
        assert (
            connection.execute(
                text("SELECT draft_owner_id FROM phenopackets WHERE id=:id"),
                {"id": first},
            ).scalar_one()
            is None
        )
        assert (
            connection.execute(
                text("SELECT draft_owner_id FROM phenopackets WHERE id=:id"),
                {"id": second},
            ).scalar_one()
            is None
        )
