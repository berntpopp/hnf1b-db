"""Single source of truth for application and schema version strings.

The application version is declared in exactly one place — ``pyproject.toml``
``[project].version`` — and resolved at runtime here, so it is never hardcoded
in application code. The project is currently still in beta (``0.X.Y``).

Resolution order (first hit wins, cached for the process lifetime):

1. Installed distribution metadata (``importlib.metadata``), in case the
   package is ever built and installed as a wheel.
2. ``pyproject.toml`` parsed at runtime. The project runs from source today,
   and ``pyproject.toml`` ships in the production image (see
   ``Dockerfile.prod``), so this is the load-bearing path.
3. A fail-soft sentinel so version resolution never raises and never takes the
   API down — the worst case is a clearly-bogus version string.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

# Distribution name as declared in ``pyproject.toml`` ``[project].name``.
_DISTRIBUTION_NAME = "hnf1b-api"

# Returned only if every resolution strategy fails. Intentionally invalid-looking
# so a misconfiguration is obvious rather than silently reporting a real version.
_SENTINEL = "0.0.0+unknown"

# GA4GH Phenopackets schema version the API conforms to. This is a domain
# standard version (GA4GH Phenopackets v2.0.0), distinct from — and unrelated
# to — the application version. Declared once here so it is not scattered.
PHENOPACKET_SCHEMA_VERSION = "2.0.0"

# Major version of the REST API URL contract (the ``/api/v2`` prefix).
API_PATH_VERSION = "v2"


def _read_version_from_pyproject() -> str | None:
    """Return ``[project].version`` from the nearest ``pyproject.toml``.

    Walks up from this module so it works regardless of the working directory
    and whether the code runs from source or a copied image layout.
    """
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - Python 3.10 fallback
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            return None

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            try:
                with candidate.open("rb") as fh:
                    data = tomllib.load(fh)
            except (OSError, ValueError):
                return None
            version = data.get("project", {}).get("version")
            return version if isinstance(version, str) and version else None
    return None


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Resolve the application version from the single source of truth."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version(_DISTRIBUTION_NAME)
        except PackageNotFoundError:
            pass
    except ImportError:  # pragma: no cover - importlib.metadata is stdlib
        pass

    from_pyproject = _read_version_from_pyproject()
    if from_pyproject:
        return from_pyproject

    return _SENTINEL


#: Application version, resolved once at import time.
APP_VERSION = get_app_version()
