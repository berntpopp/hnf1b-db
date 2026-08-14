"""ORM contracts for independent-review persistence."""

from sqlalchemy import CheckConstraint

from app.comments import models as comments_models
from app.phenopackets.models import PhenopacketRevision


def _check_names(table) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def _check_sql(table, name: str) -> str:
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == name:
            return str(constraint.sqltext)
    raise AssertionError(f"missing check constraint {name}")


def test_revision_model_catches_missing_nullable_v2_audit_storage():
    """A revision must expose nullable storage for every v2 audit component."""
    columns = PhenopacketRevision.__table__.c

    assert {
        "actor_role",
        "decision_metadata",
        "content_sha256",
        "ledger_version",
    } <= set(columns.keys())
    assert all(
        columns[name].nullable
        for name in (
            "actor_role",
            "decision_metadata",
            "content_sha256",
            "ledger_version",
        )
    )
    assert {
        "ck_phenopacket_revisions_actor_role",
        "ck_phenopacket_revisions_content_sha256",
        "ck_phenopacket_revisions_ledger_version",
        "ck_phenopacket_revisions_decision_metadata_ledger",
    } <= _check_names(PhenopacketRevision.__table__)


def test_revision_model_catches_decision_metadata_with_null_ledger_version():
    """ORM metadata must require an explicit v2 ledger for decision metadata."""
    check_sql = _check_sql(
        PhenopacketRevision.__table__,
        "ck_phenopacket_revisions_decision_metadata_ledger",
    )

    assert "ledger_version IS NOT NULL" in check_sql


def test_review_issue_model_catches_missing_restrictive_revision_link():
    """Blocking issues must reference the reviewed immutable revision."""
    comment = comments_models.Comment
    column = comment.__table__.c.review_revision_id

    assert column.nullable
    foreign_key = next(iter(column.foreign_keys))
    assert foreign_key.target_fullname == "phenopacket_revisions.id"
    assert foreign_key.ondelete == "RESTRICT"
    assert comment.review_revision.property.mapper.class_ is PhenopacketRevision


def test_resolution_event_model_catches_missing_append_only_audit_links():
    """Resolution history must retain restrictive comment and actor links."""
    event = getattr(comments_models, "CommentResolutionEvent")
    columns = event.__table__.c

    assert {
        "comment_id",
        "action",
        "disposition",
        "rationale",
        "actor_id",
        "actor_role",
        "created_at",
    } <= set(columns.keys())
    assert next(iter(columns.comment_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(columns.actor_id.foreign_keys)).ondelete == "RESTRICT"
    assert {
        "ck_comment_resolution_event_action_disposition",
        "ck_comment_resolution_event_rationale",
        "ck_comment_resolution_event_actor_role",
    } <= _check_names(event.__table__)


def test_resolution_event_model_catches_resolved_event_with_null_disposition():
    """ORM metadata must require a disposition for every resolved event."""
    event = getattr(comments_models, "CommentResolutionEvent")
    check_sql = _check_sql(
        event.__table__, "ck_comment_resolution_event_action_disposition"
    )

    assert "disposition IS NOT NULL" in check_sql
