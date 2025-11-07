"""Role and permission definitions - Single source of truth."""

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """User roles enum."""

    ADMIN = "admin"
    CURATOR = "curator"
    VIEWER = "viewer"


@dataclass(frozen=True)
class RoleDefinition:
    """Role definition with description and permissions."""

    name: str
    description: str
    permissions: tuple[str, ...]  # Immutable


# Single source of truth for role permissions
ROLE_DEFINITIONS: dict[Role, RoleDefinition] = {
    Role.ADMIN: RoleDefinition(
        name="admin",
        description="Administrator with full system access",
        permissions=(
            "users:read",
            "users:write",
            "users:delete",
            "phenopackets:read",
            "phenopackets:write",
            "phenopackets:delete",
            "variants:read",
            "variants:write",
            "variants:delete",
            "ingestion:run",
            "system:manage",
            "logs:read",
        ),
    ),
    Role.CURATOR: RoleDefinition(
        name="curator",
        description="Data curator with editing permissions",
        permissions=(
            "phenopackets:read",
            "phenopackets:write",
            "variants:read",
            "variants:write",
            "ingestion:run",
        ),
    ),
    Role.VIEWER: RoleDefinition(
        name="viewer",
        description="Public read-only access (default)",
        permissions=("phenopackets:read", "variants:read", "publications:read"),
    ),
}


def get_role_permissions(role: str) -> list[str]:
    """Get permissions for a role.

    Args:
        role: Role name string

    Returns:
        List of permission strings

    Raises:
        KeyError: If role is invalid
    """
    return list(ROLE_DEFINITIONS[Role(role)].permissions)


def get_all_roles() -> list[dict[str, str | list[str]]]:
    """Get all role definitions for API responses.

    Returns:
        List of role definitions with name, description, permissions
    """
    return [
        {
            "role": definition.name,
            "description": definition.description,
            "permissions": list(definition.permissions),
        }
        for definition in ROLE_DEFINITIONS.values()
    ]
