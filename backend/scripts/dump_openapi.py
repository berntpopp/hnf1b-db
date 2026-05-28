"""Dump the live OpenAPI schema as deterministic JSON to stdout.

Run with:

    uv run python scripts/dump_openapi.py

The output is sorted and indented so it can be committed as a stable snapshot
(``mcp/contract/openapi.snapshot.json``) and diffed meaningfully. The backend
contract test (``tests/test_openapi_contract.py``) compares the committed
snapshot against the live schema; refresh it by piping this script's stdout into
that file whenever the API surface intentionally changes.
"""

import json
import sys
from pathlib import Path

# Ensure the backend package root is importable when run as a standalone script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    """Print the deterministic JSON representation of the OpenAPI schema."""
    print(json.dumps(app.openapi(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
