# Independent Phenopacket Review Spec — One-Pass Review

**Date:** 2026-08-14

**Reviewed commit:** `07d27c0`

**Reviewed artifact:** `.planning/specs/2026-08-14-independent-phenopacket-review-design.md`

**Reviewer:** independent `gpt-5.6-sol` reviewer at `xhigh` reasoning. Opus 5 was requested but is not available in this environment; this was the strongest available substitute disclosed to the user.

**Review mode:** One pass, report-only. No reviewer edits and no second review pass.

## Outcome

The reviewer reported four high-severity and one medium-severity actionable findings. All five were accepted and addressed by the primary agent before implementation planning.

## Findings and disposition

### 1. Exact approved snapshot lacked a full-content digest contract — High

The initial spec relied partly on the existing projection hash even though it excludes extension content, and current publication canonicalizes content after approval.

**Disposition:** Accepted.

The revised spec now:

- defines a versioned canonical full-`content_jsonb` SHA-256 digest;
- canonicalizes and validates before entering `in_review`;
- requires expected revision IDs and full-content digests for approval/publication;
- stores the reviewed digest in decision metadata;
- versions the ledger hash and includes full-content digest, role snapshot, and decision metadata;
- requires publication to copy approved content unchanged;
- adds extension-only and publish-time mutation regression tests.

### 2. Deferred constraint alone did not prevent direct-writer write skew — High

Two raw transactions could each pass a deferred cross-table check under `READ COMMITTED` without seeing the other's uncommitted change.

**Disposition:** Accepted.

The revised spec requires lock-taking triggers on both blocking-issue mutations and active revision/state changes. All supported application and direct SQL writers acquire the same phenopacket row lock before validation. The deferred trigger is only a final invariant check. Two-connection raw-SQL race tests are mandatory in both commit orders.

### 3. Existing comment endpoints remained policy bypasses — High

The initial spec did not fully define how generic resolve/unresolve/delete routes behave after a comment becomes a blocking review issue.

**Disposition:** Accepted.

The revised spec defines conditional request schemas and behavior for create, resolve, reopen, retract, and delete. Blocking issues require optimistic record context, reviewer eligibility, rationale/disposition, and phenopacket-first locking. DELETE is forbidden for blocking issues, including for admins; retraction is an audited resolution disposition. Every legacy mutation route receives policy tests.

### 4. Conventional downgrade could erase the sole sign-off audit — High

A reversible migration that drops decision metadata or resolution events would leave published records without their authoritative review audit.

**Disposition:** Accepted.

The revised spec uses expand/activate migrations. Code can roll back while the expanded schema remains. Schema downgrade refuses after any blocking issue, resolution event, v2 ledger revision, or decision metadata exists. Guarded downgrade behavior is tested.

### 5. Historical role backfill violated append-only history and implied false certainty — Medium

Updating old revision rows conflicts with the append-only trigger, while copying a user's current role would not prove their historical role.

**Disposition:** Accepted.

The revised spec leaves historical actor-role/full-digest/version fields unset. UI fallback is explicitly labelled as not recorded at decision time. Existing v1 ledger rows are never rewritten.

## Residual risks accepted by product design

- One independent sign-off is proportionate local quality control, not ClinGen panel consensus.
- Admins are curator-capable by HNF1B-DB policy; role snapshot and attestation make this explicit.
- Lock-taking database triggers add operational complexity but are required by the direct-writer invariant.
- Open queues do not solve workload balancing; assignment remains a future extension.

## Gate result

**Pass after primary-agent corrections.** The written spec is ready for user confirmation and implementation planning. This review intentionally concludes the requested single spec-review pass.
