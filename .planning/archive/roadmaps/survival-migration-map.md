# Survival Handler Migration Map

**Wave 3 reference document (2026-04-10).** Documents the relationship between the 6 legacy `_handle_*` functions in `backend/app/phenopackets/routers/aggregations/survival.py` and the canonical `SurvivalHandler` subclasses in `survival_handlers.py`, and records the zero-caller confirmation that makes the Task 3 deletion safe.

## Dead-code confirmation

Grep output from `grep -rn "_handle_variant_type\|_handle_pathogenicity\|_handle_disease_subtype" backend/app backend/tests --include="*.py"`:

```
app/phenopackets/routers/aggregations/survival.py:126:async def _handle_variant_type_current_age(
app/phenopackets/routers/aggregations/survival.py:230:async def _handle_variant_type_standard(
app/phenopackets/routers/aggregations/survival.py:375:async def _handle_pathogenicity_current_age(
app/phenopackets/routers/aggregations/survival.py:467:async def _handle_pathogenicity_standard(
app/phenopackets/routers/aggregations/survival.py:621:async def _handle_disease_subtype_current_age(
app/phenopackets/routers/aggregations/survival.py:748:async def _handle_disease_subtype_standard(
```

All 6 matches are function definitions inside `survival.py`. **Zero callers** in the live dispatcher, in any endpoint, in tests, or in any other module. The legacy functions are orphaned dead code.

Grep output from `grep -rn "_calculate_survival_curves\|_calculate_statistical_tests\|_build_response" backend/app backend/tests --include="*.py"`:

```
app/phenopackets/routers/aggregations/survival_handlers.py:185:        survival_curves = self._calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival_handlers.py:186:        statistical_tests = self._calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival_handlers.py:205:    def _calculate_survival_curves(
app/phenopackets/routers/aggregations/survival_handlers.py:217:    def _calculate_statistical_tests(
app/phenopackets/routers/aggregations/survival.py:56:def _calculate_survival_curves(
app/phenopackets/routers/aggregations/survival.py:71:def _calculate_statistical_tests(
app/phenopackets/routers/aggregations/survival.py:99:def _build_response(
app/phenopackets/routers/aggregations/survival.py:189:  survival_curves = _calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival.py:190:  statistical_tests = _calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival.py:220:  return _build_response(
app/phenopackets/routers/aggregations/survival.py:338:  survival_curves = _calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival.py:339:  statistical_tests = _calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival.py:365:  return _build_response(
app/phenopackets/routers/aggregations/survival.py:432:  survival_curves = _calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival.py:433:  statistical_tests = _calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival.py:457:  return _build_response(
app/phenopackets/routers/aggregations/survival.py:586:  survival_curves = _calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival.py:587:  statistical_tests = _calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival.py:611:  return _build_response(
app/phenopackets/routers/aggregations/survival.py:711:  survival_curves = _calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival.py:712:  statistical_tests = _calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival.py:738:  return _build_response(
app/phenopackets/routers/aggregations/survival.py:935:  survival_curves = _calculate_survival_curves(groups)
app/phenopackets/routers/aggregations/survival.py:936:  statistical_tests = _calculate_statistical_tests(groups)
app/phenopackets/routers/aggregations/survival.py:961:  return _build_response(
```

Every caller of the 3 module-private helpers in `survival.py` (`_calculate_survival_curves`, `_calculate_statistical_tests`, `_build_response`) is inside the line range 126–968 — the 6 dead `_handle_*` functions. The 3 helpers are therefore also orphaned and will be deleted alongside the handlers in Task 3.

The `survival_handlers.py:185-217` matches are **instance methods** of the `SurvivalHandler` ABC — they are live code in the canonical production path and must **not** be touched.

## Why no parity tests

The original Wave 3 plan proposed byte-identical parity tests as a deletion gate. That approach assumed the dispatcher was still calling the legacy functions and that the new handler classes were an untested parallel path. Both assumptions are wrong:

1. The dispatcher has already been migrated (see `backend/app/phenopackets/routers/aggregations/survival.py:1006-1025`):

```python
from .survival_handlers import SurvivalHandlerFactory

endpoint_config = _get_endpoint_config()
if endpoint not in endpoint_config:
    valid_options = ", ".join(endpoint_config.keys())
    raise ValueError(
        f"Unknown endpoint: {endpoint}. Valid options: {valid_options}"
    )

config = endpoint_config[endpoint]
endpoint_hpo_terms: Optional[List[str]] = config["hpo_terms"]
endpoint_label: str = config["label"]

try:
    handler = SurvivalHandlerFactory.get_handler(comparison)
except ValueError as e:
    raise ValueError(str(e)) from e

return await handler.handle(db, endpoint_label, endpoint_hpo_terms)
```

2. The handler classes are the only path the endpoint uses in production.
3. The legacy functions are unreachable from any caller.

Parity testing would compare dead code to live code — the result is either "identical" (wasted effort) or "different" (reveals the dead code drifted, which is informative but doesn't block deletion because the dead code is unreachable anyway).

The deletion safety story is instead:

1. **Zero callers** (this document, Task 1).
2. **Endpoint smoke test** added in Task 2 — exercises every comparison type through the live dispatcher and gives a regression signal for the handler classes themselves. Runs before and after the Task 3 deletion.
3. **Full `make check`** before and after deletion.

## Handler mapping

The legacy functions split by comparison type × age-mode (6 functions). The new handler classes split only by comparison type (4 classes, plus an ABC and a factory). Age mode is an internal branch inside `SurvivalHandler.handle()`:

```python
async def handle(self, db, endpoint_label, endpoint_hpo_terms=None):
    if endpoint_hpo_terms is None:
        return await self._handle_current_age(db, endpoint_label)
    return await self._handle_standard(db, endpoint_label, endpoint_hpo_terms)
```

| Legacy function | survival.py line | Canonical handler method | survival_handlers.py class line |
|-----------------|:----------------:|-------------------------|:------------------------------:|
| `_handle_variant_type_current_age`    | 126 | `VariantTypeHandler._handle_current_age`    | 273 |
| `_handle_variant_type_standard`       | 230 | `VariantTypeHandler._handle_standard`       | 273 |
| `_handle_pathogenicity_current_age`   | 375 | `PathogenicityHandler._handle_current_age`  | 415 |
| `_handle_pathogenicity_standard`      | 467 | `PathogenicityHandler._handle_standard`     | 415 |
| `_handle_disease_subtype_current_age` | 621 | `DiseaseSubtypeHandler._handle_current_age` | 560 |
| `_handle_disease_subtype_standard`    | 748 | `DiseaseSubtypeHandler._handle_standard`    | 560 |

The `_handle_current_age` and `_handle_standard` methods are defined once on the ABC at `survival_handlers.py:97` and `:123`; concrete subclasses supply the SQL via `build_current_age_query()` and `build_standard_query(endpoint_hpo_terms)`.

`ProteinDomainHandler` (`survival_handlers.py:826`) is a net-new comparison type added *after* the legacy functions. It has no legacy equivalent — nothing to migrate for it. It is carried through the Task 4 sub-package restructure unchanged.

`SurvivalHandlerFactory` (`survival_handlers.py:1020`) is the dispatch entry point the live endpoint uses.

## Orphaned helper functions

These module-private helpers in `survival.py` are only called from the dead `_handle_*` functions and will be deleted in Task 3 alongside the handlers:

| Helper | survival.py lines | Call sites (all inside dead handlers) |
|--------|:-----------------:|---------------------------------------|
| `_calculate_survival_curves` | 56–68 | 189, 338, 432, 586, 711, 935 |
| `_calculate_statistical_tests` | 71–96 | 190, 339, 433, 587, 712, 936 |
| `_build_response` | 99–123 | 220, 365, 457, 611, 738, 961 |

Each call site sits inside one of the dead `_handle_*` functions (line ranges 126–968). None sit in the live dispatcher at 971–1025 or anywhere else in the codebase.

`SurvivalHandler` in `survival_handlers.py` has its own `_calculate_survival_curves` (line 205) and `_calculate_statistical_tests` (line 217) as instance methods — these are in a different scope and are **not** affected by the Task 3 deletion.

`_get_endpoint_config` (`survival.py:30–53`) is **kept** — it is called by the live dispatcher at `survival.py:1008`.

## Outcome

Task 3 will delete 9 module-private symbols from `survival.py`:

- 6 `_handle_*` async functions
- 3 `_calculate_*` / `_build_response` helper functions

Expected file shrinkage: 1,025 LOC → ~140 LOC (the final file will contain only imports, `_get_endpoint_config`, and the `get_survival_data` router endpoint).
