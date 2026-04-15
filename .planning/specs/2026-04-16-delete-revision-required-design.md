# Delete Revision Required Design

## Goal

Remove the last blind-delete path from phenopacket mutations by requiring clients to send the current `revision` when issuing a delete.

## Scope

This slice only changes phenopacket delete behavior.

- Backend request validation must require `revision` on delete requests.
- Backend delete service must always compare the supplied revision to the locked row revision.
- Frontend phenopacket delete calls must send the current revision in the request body.
- Existing backward-compat behavior for revision-less delete must be removed.

## Non-Goals

- No change to update semantics, which remain optionally revision-guarded.
- No change to state transition semantics.
- No migration or compatibility shim for legacy callers.

## Architecture

The backend already uses optimistic locking for updates and transitions. Delete should follow the same pattern: the request carries the caller's last-seen revision, the service locks the row, and the mutation proceeds only if the current revision still matches.

The frontend already has the active phenopacket revision available on the detail page, so the UI change is limited to passing that revision through the domain API helper into the existing delete request.

## API Behavior

### Success

If the request body includes the current revision, delete succeeds as it does today.

### Validation Failure

If the request omits `revision`, FastAPI/Pydantic request validation rejects it before the service layer runs.

### Conflict

If the request supplies a stale revision, delete returns the existing `409` conflict payload with `current_revision` and `expected_revision`.

## Files

- Modify `backend/app/phenopackets/models.py`
- Modify `backend/app/phenopackets/services/phenopacket_service.py`
- Modify `frontend/src/api/domain/phenopackets.js`
- Modify `frontend/src/views/PagePhenopacket.vue`
- Modify `backend/tests/test_phenopackets_delete_revision.py`
- Add or modify focused frontend unit coverage if a stable test target exists for the domain helper or page delete flow

## Testing

- Backend request validation test for missing delete revision
- Backend success test for matching revision
- Backend conflict test for stale revision
- Existing concurrent delete race test remains green
- Frontend test or focused verification that delete sends `change_reason` and `revision` in the request body
