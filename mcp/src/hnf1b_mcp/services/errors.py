"""Typed tool-result error taxonomy for the MCP server."""

from __future__ import annotations

from typing import Any

ERROR_CODES = {
    "invalid_input",
    "not_found",
    "ambiguous_query",
    "temporarily_unavailable",
}


class McpToolError(Exception):
    """A recoverable tool error surfaced as an isError tool result."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        """Initialize with a known error code, message, and optional details.

        Args:
            code: One of the known ERROR_CODES values.
            message: Human-readable error description.
            **details: Optional extra fields merged into the error envelope.

        Raises:
            ValueError: If *code* is not in ERROR_CODES.
        """
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = {k: v for k, v in details.items() if v is not None}

    def to_envelope(self) -> dict[str, Any]:
        """Return the JSON error envelope embedded in the tool result."""
        return {
            "schema_version": "1.0",
            "error": {
                "code": self.code,
                "message": self.message,
                **self.details,
            },
        }
