"""Independent phenopacket review policy."""

from typing import Any

from app.phenopackets.review.schemas import (
    ActionCapability,
    ReviewBlockCode,
    ReviewCapabilities,
)

__all__ = [
    "ActionCapability",
    "ReviewBlockCode",
    "ReviewCapabilities",
    "ReviewPolicy",
    "ReviewPolicyError",
]


def __getattr__(name: str) -> Any:
    """Load database-backed policy exports without coupling schema imports."""
    if name in {"ReviewPolicy", "ReviewPolicyError"}:
        from app.phenopackets.review.policy import (  # noqa: PLC0415
            ReviewPolicy,
            ReviewPolicyError,
        )

        return {
            "ReviewPolicy": ReviewPolicy,
            "ReviewPolicyError": ReviewPolicyError,
        }[name]
    raise AttributeError(name)
