# Delete Revision Required Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require optimistic-locking revision values on phenopacket delete requests end-to-end.

**Architecture:** Tighten the backend delete contract so request validation requires `revision`, then update the single frontend delete caller to send the current revision in the JSON body already consumed by the backend route. Verification stays focused on the delete slice and the frontend request helper.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy async, Vue 3, Axios, pytest, Vitest.

---

### Task 1: Backend Contract

**Files:**
- Modify: `backend/tests/test_phenopackets_delete_revision.py`
- Modify: `backend/app/phenopackets/models.py`
- Modify: `backend/app/phenopackets/services/phenopacket_service.py`

- [ ] **Step 1: Write the failing backend test for missing revision**

```python
@pytest.mark.asyncio
async def test_delete_without_revision_returns_422(
    async_client: AsyncClient, admin_headers: dict
):
    create_payload = _valid_payload("delete-revision-required")
    create_resp = await async_client.post(
        "/api/v2/phenopackets/", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 200, create_resp.text

    response = await async_client.request(
        "DELETE",
        "/api/v2/phenopackets/delete-revision-required",
        json={"change_reason": "missing revision"},
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_phenopackets_delete_revision.py::test_delete_without_revision_returns_422 -v`
Expected: FAIL because the current contract still accepts revision-less delete.

- [ ] **Step 3: Write minimal backend implementation**

```python
class PhenopacketDelete(BaseModel):
    change_reason: str = Field(
        ..., min_length=1, description="Reason for deletion (audit trail)"
    )
    revision: int = Field(
        ..., description="Required optimistic-locking revision for delete requests."
    )
```

```python
async def soft_delete(
    self,
    phenopacket_id: str,
    change_reason: str,
    *,
    actor_id: Optional[int],
    actor_username: Optional[str] = None,
    expected_revision: int,
) -> Dict[str, Optional[str]]:
```

```python
if phenopacket.revision != expected_revision:
    raise ServiceConflict(
        {
            "error": "Conflict detected",
            "message": (
                f"Phenopacket was modified by another user. "
                f"Expected revision {expected_revision}, "
                f"but current revision is {phenopacket.revision}"
            ),
            "current_revision": phenopacket.revision,
            "expected_revision": expected_revision,
        },
        code="revision_mismatch",
    )
```

- [ ] **Step 4: Run backend delete slice**

Run: `cd backend && uv run pytest tests/test_phenopackets_delete_revision.py -v`
Expected: PASS

### Task 2: Frontend Delete Caller

**Files:**
- Modify: `frontend/src/api/domain/phenopackets.js`
- Modify: `frontend/src/views/PagePhenopacket.vue`
- Test: `frontend/tests/unit/...` if a focused test target exists for delete request wiring

- [ ] **Step 1: Write the failing frontend test or targeted verification**

```javascript
await deletePhenopacket('PP-1', 7, 'cleanup');
expect(apiClient.delete).toHaveBeenCalledWith('/phenopackets/PP-1', {
  data: { revision: 7, change_reason: 'cleanup' },
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `cd frontend && npm test -- --runInBand <focused-test>`
Expected: FAIL because delete currently sends only `change_reason` as query params.

- [ ] **Step 3: Write minimal frontend implementation**

```javascript
export const deletePhenopacket = (id, revision, changeReason) =>
  apiClient.delete(`/phenopackets/${id}`, {
    data: {
      revision,
      change_reason: changeReason,
    },
  });
```

```javascript
await deletePhenopacket(
  this.phenopacket.id,
  this.phenopacketMeta.revision,
  deleteReason
);
```

- [ ] **Step 4: Run the focused frontend test**

Run: `cd frontend && npm test -- --runInBand <focused-test>`
Expected: PASS

### Task 3: Verification

**Files:**
- No additional edits expected

- [ ] **Step 1: Run targeted backend verification**

Run: `cd backend && uv run pytest tests/test_phenopackets_delete_revision.py tests/test_state_flows.py tests/test_api_transitions.py -v`
Expected: PASS

- [ ] **Step 2: Run targeted frontend verification**

Run: `cd frontend && npm test -- --runInBand <focused-test>`
Expected: PASS

- [ ] **Step 3: Run lint and type checks**

Run: `cd backend && make lint && make typecheck`
Expected: PASS

Run: `cd frontend && npm test -- --runInBand <focused-test>`
Expected: PASS
