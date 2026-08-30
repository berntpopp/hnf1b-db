"""Shared HTTP response models that mirror the application's error handlers."""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel
from typing_extensions import TypeAliasType

ApiJsonValue = TypeAliasType(  # type: ignore[misc]
    "ApiJsonValue",
    Union[
        list["ApiJsonValue"],  # type: ignore[misc]
        dict[str, "ApiJsonValue"],  # type: ignore[misc]
        str,
        int,
        float,
        bool,
        None,
    ],
)


class ApiErrorEnvelope(BaseModel):
    """Runtime-accurate envelope emitted by the global exception handlers."""

    detail: ApiJsonValue
    error_code: str
    request_id: str | None = None
