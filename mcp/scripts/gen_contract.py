#!/usr/bin/env python3
"""Generate the MCP API contract package from the committed OpenAPI snapshot.

Reads ``contract/openapi.snapshot.json`` (relative to the ``mcp/`` package root)
and writes two deterministic, idempotent modules into
``src/hnf1b_mcp/contract/``:

- ``_generated_paths.py`` — named, ``/api/v2``-stripped path-template constants
  (UPPER_SNAKE) plus ``ALL_PATHS``.
- ``_generated_enums.py`` — every enum in ``components.schemas`` and every inline
  parameter enum, emitted as :class:`typing.Literal` aliases plus value tuples.

The script is deterministic (sorted keys) and idempotent: running it twice on the
same snapshot produces byte-identical output. Do NOT hand-edit the generated
files; regenerate via ``make contract`` instead.

Usage::

    uv run python scripts/gen_contract.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SNAPSHOT = _ROOT / "contract" / "openapi.snapshot.json"
_OUT_DIR = _ROOT / "src" / "hnf1b_mcp" / "contract"
_PATHS_OUT = _OUT_DIR / "_generated_paths.py"
_ENUMS_OUT = _OUT_DIR / "_generated_enums.py"

_API_PREFIX = "/api/v2"

# Paths that exist outside the /api/v2 router space and are not part of the MCP
# path space; exclude them from constant generation to keep the contract clean.
_EXCLUDE_PATHS = frozenset({"/", "/health", "/livez"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_prefix(path: str) -> str:
    """Return *path* with the ``/api/v2`` prefix removed.

    The root ``/api/v2`` collapses to ``/``. All other prefixed paths keep their
    suffix (e.g. ``/api/v2/phenopackets/`` -> ``/phenopackets/``).
    """
    if path == _API_PREFIX:
        return "/"
    if path.startswith(_API_PREFIX + "/"):
        return path[len(_API_PREFIX) :]
    return path


def _const_name(stripped: str) -> str:
    """Derive a stable UPPER_SNAKE constant name from a stripped path template.

    ``{param}`` placeholders become ``BY_PARAM`` segments; other non-alnum
    characters collapse to underscores. The leading slash is dropped.
    """
    name = stripped.lstrip("/")
    if not name:
        return "ROOT"
    # Replace {param} with by_param to keep names readable and unambiguous.
    name = re.sub(r"\{([^}]+)\}", r"by_\1", name)
    # Any run of non-alphanumeric chars -> single underscore.
    name = re.sub(r"[^0-9A-Za-z]+", "_", name)
    name = name.strip("_")
    return name.upper()


def _enum_alias_name(schema_name: str) -> str:
    """Return the Literal alias name for a component-schema enum (kept as-is)."""
    return schema_name


def _values_const_name(alias: str) -> str:
    """Return the UPPER_SNAKE ``*_VALUES`` tuple name for an enum *alias*."""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", alias).upper()
    return f"{snake}_VALUES"


def _param_alias_name(param_name: str) -> str:
    """Return a CamelCase Literal alias for an inline parameter enum."""
    parts = re.split(r"[^0-9A-Za-z]+", param_name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _collect_paths(spec: dict[str, Any]) -> list[tuple[str, str]]:
    """Return sorted ``(const_name, stripped_path)`` tuples for every spec path."""
    out: dict[str, str] = {}
    for raw_path in spec.get("paths", {}):
        if raw_path in _EXCLUDE_PATHS:
            continue
        stripped = _strip_prefix(raw_path)
        const = _const_name(stripped)
        if const in out and out[const] != stripped:
            raise ValueError(
                f"path constant collision: {const} -> {out[const]!r} vs {stripped!r}"
            )
        out[const] = stripped
    return sorted(out.items())


def _enum_from_schema(schema: dict[str, Any]) -> list[str] | None:
    """Return the enum value list from a schema node, looking through anyOf."""
    if "enum" in schema and isinstance(schema["enum"], list):
        return [str(v) for v in schema["enum"]]
    for sub in schema.get("anyOf", []) or []:
        if isinstance(sub, dict) and isinstance(sub.get("enum"), list):
            return [str(v) for v in sub["enum"]]
    return None


def _collect_schema_enums(spec: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """Return sorted ``(alias, values)`` for every enum in components.schemas."""
    out: list[tuple[str, list[str]]] = []
    schemas = spec.get("components", {}).get("schemas", {})
    for name in sorted(schemas):
        values = _enum_from_schema(schemas[name])
        if values:
            out.append((_enum_alias_name(name), values))
    return out


def _collect_param_enums(spec: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """Return sorted ``(alias, values)`` for every inline parameter enum.

    Deduplicated by (alias, values); collisions on the same alias with different
    values raise to force a manual rename rather than silently dropping one.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(spec.get("paths", {})):
        methods = spec["paths"][path]
        for method in sorted(methods):
            op = methods[method]
            if not isinstance(op, dict):
                continue
            for param in op.get("parameters", []) or []:
                schema = param.get("schema", {})
                values = _enum_from_schema(schema)
                if not values:
                    continue
                alias = _param_alias_name(param.get("name", ""))
                if alias in found and found[alias] != values:
                    raise ValueError(
                        f"param enum collision for alias {alias}: "
                        f"{found[alias]!r} vs {values!r}"
                    )
                found[alias] = values
    return sorted(found.items())


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_GEN_HEADER = (
    '"""{title}\n\n'
    "GENERATED FILE — do not hand-edit.\n"
    "Regenerate with ``scripts/gen_contract.py`` (``make contract``) from\n"
    "``contract/openapi.snapshot.json``.\n"
    '"""\n'
    "from __future__ import annotations\n"
)


def _render_paths(paths: list[tuple[str, str]]) -> str:
    title = "API path-template constants (``/api/v2`` stripped)."
    lines = [_GEN_HEADER.format(title=title)]
    lines.append("")
    for const, stripped in paths:
        lines.append(f'{const} = "{stripped}"')
    lines.append("")
    lines.append("ALL_PATHS: tuple[str, ...] = (")
    for const, _ in paths:
        lines.append(f"    {const},")
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def _render_enums(
    schema_enums: list[tuple[str, list[str]]],
    param_enums: list[tuple[str, list[str]]],
) -> str:
    lines = [
        _GEN_HEADER.format(
            title="API enum vocabularies as Literal aliases + value tuples."
        )
    ]
    lines.append("")
    lines.append("from typing import Literal")
    lines.append("")

    def _emit(alias: str, values: list[str]) -> None:
        literal_args = ", ".join(json.dumps(v) for v in values)
        lines.append(f"{alias} = Literal[{literal_args}]")
        values_name = _values_const_name(alias)
        tuple_args = ", ".join(json.dumps(v) for v in values)
        if len(values) == 1:
            tuple_args += ","
        lines.append(f"{values_name}: tuple[str, ...] = ({tuple_args})")
        lines.append("")

    if schema_enums:
        lines.append("# --- component schema enums ---")
        lines.append("")
        for alias, values in schema_enums:
            _emit(alias, values)

    if param_enums:
        lines.append("# --- inline parameter enums ---")
        lines.append("")
        for alias, values in param_enums:
            _emit(alias, values)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the contract modules from the snapshot."""
    spec = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))

    paths = _collect_paths(spec)
    schema_enums = _collect_schema_enums(spec)
    param_enums = _collect_param_enums(spec)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    _PATHS_OUT.write_text(_render_paths(paths), encoding="utf-8")
    _ENUMS_OUT.write_text(_render_enums(schema_enums, param_enums), encoding="utf-8")

    print(f"wrote {_PATHS_OUT.relative_to(_ROOT)} ({len(paths)} paths)")
    print(
        f"wrote {_ENUMS_OUT.relative_to(_ROOT)} "
        f"({len(schema_enums)} schema enums, {len(param_enums)} param enums)"
    )


if __name__ == "__main__":
    main()
