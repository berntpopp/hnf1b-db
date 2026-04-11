# Refactor Tech Debt Register

Files intentionally exceeding the 500-LOC rule from `CLAUDE.md` after
the backend decomposition waves. Each entry has a justification and a
re-evaluation trigger.

## Backend

After Wave 4 (2026-04-11), every file in `backend/app/` is under 500 LOC:

```bash
$ find backend/app -name "*.py" -exec wc -l {} \; | awk '$1 > 500' | sort -rn
(no results)
```

The table below is therefore empty. If a future wave introduces a
justified exception, add a row with a concrete re-evaluation trigger —
not "too complex to split", which is a symptom, not a reason.

| File | Lines | Justification | Re-evaluate when |
|------|:-----:|---------------|------------------|
| _none_ | — | — | — |

## Frontend

Populated during Wave 5 if and when any Vue component stays over 500
LOC with a justified reason. Currently unpopulated.

| File | Lines | Justification | Re-evaluate when |
|------|:-----:|---------------|------------------|
| _none_ | — | — | — |
