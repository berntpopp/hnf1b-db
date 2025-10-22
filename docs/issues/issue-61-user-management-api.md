# Issue #61: feat(backend): implement user management API endpoints

## Overview

No API endpoints for user management (create/update/delete users, roles, permissions).

**Current:** Only authentication endpoints exist (`/api/auth/token`, `/api/auth/me`)
**Target:** Complete user management API with CRUD operations, role management, and audit logging

## Why This Matters

### Problem

**Current State:**
- Only authentication endpoints exist
- No way to create users via API (must use SQL)
- No role management endpoints
- No user listing or search
- No audit trail for user changes
- Admin must manually run SQL commands

**Example: Creating a new user today:**
```sql
-- Manual SQL required (not ideal)
INSERT INTO users (username, hashed_password, role, created_at)
VALUES ('newuser', '$2b$12$...', 'researcher', NOW());
```

**Impact:**
- ❌ Cannot manage users programmatically
- ❌ No self-service user creation
- ❌ No audit trail for user changes
- ❌ Manual SQL errors risk security
- ❌ Poor admin experience
- ❌ Cannot integrate with external systems

### Solution

**Add comprehensive user management API:**
- User CRUD endpoints (create, read, update, delete)
- Role management endpoints
- Admin-only access control
- Password hashing with bcrypt
- Audit logging for all changes
- OpenAPI documentation

**After implementation:**
```bash
# Create user via API (secure, audited)
curl -X POST http://localhost:8000/api/v2/users/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "SecurePass123!",
    "role": "researcher",
    "email": "user@example.com"
  }'
```

**Benefits:**
- ✅ Programmatic user management
- ✅ Secure password hashing
- ✅ Audit trail for compliance
- ✅ Self-service user creation (with admin approval)
- ✅ Integration with external systems
- ✅ OpenAPI documentation

## Current State

### Existing Authentication Endpoints

**File:** `backend/app/auth_endpoints.py`

**Available Endpoints:**
```python
POST /api/auth/token
# Login - Returns JWT token
# Body: {"username": "admin", "password": "admin123"}
# Returns: {"access_token": "eyJ...", "token_type": "bearer"}

GET /api/auth/me
# Get current user info
# Headers: {"Authorization": "Bearer <token>"}
# Returns: {"username": "admin", "role": "admin"}
```

### Database Schema

**Table:** `users`

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,  -- 'admin' or 'researcher'
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Missing Functionality

- ❌ No user creation endpoint
- ❌ No user listing endpoint
- ❌ No user update endpoint
- ❌ No user deletion endpoint
- ❌ No role management
- ❌ No audit logging

## Implementation

### 1. User Management Endpoints

**File:** `backend/app/users/endpoints.py` (NEW)

```python
"""User management API endpoints."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_auth
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/users", tags=["users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Request/Response Models

class UserCreate(BaseModel):
    """Request model for creating a new user."""
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 chars)")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    role: str = Field(..., description="User role (admin or researcher)")
    email: Optional[EmailStr] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")

    @validator("username")
    def validate_username(cls, v):
        """Validate username format."""
        if not v.isalnum() and "_" not in v and "-" not in v:
            raise ValueError("Username must contain only letters, numbers, underscores, or hyphens")
        return v.lower()

    @validator("role")
    def validate_role(cls, v):
        """Validate role is one of allowed values."""
        allowed_roles = {"admin", "researcher"}
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {allowed_roles}")
        return v

    @validator("password")
    def validate_password_strength(cls, v):
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    """Request model for updating a user."""
    password: Optional[str] = Field(None, min_length=8, description="New password (optional)")
    role: Optional[str] = Field(None, description="New role (optional)")
    email: Optional[EmailStr] = Field(None, description="New email (optional)")
    full_name: Optional[str] = Field(None, max_length=255, description="New full name (optional)")
    is_active: Optional[bool] = Field(None, description="Active status (optional)")

    @validator("role")
    def validate_role(cls, v):
        """Validate role is one of allowed values."""
        if v is not None:
            allowed_roles = {"admin", "researcher"}
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of: {allowed_roles}")
        return v

    @validator("password")
    def validate_password_strength(cls, v):
        """Validate password meets security requirements."""
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
            if not any(c.isupper() for c in v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(c.islower() for c in v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    username: str
    role: str
    email: Optional[str]
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    """Response model for role data."""
    role: str
    description: str
    permissions: List[str]


# Helper Functions

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


async def log_user_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    performed_by: str,
    details: Optional[str] = None
):
    """Log user management action to audit table."""
    query = text("""
        INSERT INTO user_audit_log (user_id, action, performed_by, details, timestamp)
        VALUES (:user_id, :action, :performed_by, :details, NOW())
    """)
    await db.execute(query, {
        "user_id": user_id,
        "action": action,
        "performed_by": performed_by,
        "details": details
    })
    await db.commit()


# Endpoints

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create a new user (admin only).

    **Security:**
    - Requires admin role
    - Password is hashed with bcrypt
    - Action is logged in audit trail

    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit

    **Returns:**
    - 201: User created successfully
    - 400: Validation error (weak password, invalid role, etc.)
    - 409: Username already exists
    - 403: Not authorized (not admin)
    """
    # Check if username already exists
    check_query = text("SELECT id FROM users WHERE username = :username")
    result = await db.execute(check_query, {"username": user_data.username})
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{user_data.username}' already exists"
        )

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create user
    insert_query = text("""
        INSERT INTO users (username, hashed_password, role, email, full_name, created_at, updated_at)
        VALUES (:username, :hashed_password, :role, :email, :full_name, NOW(), NOW())
        RETURNING id, username, role, email, full_name, is_active, created_at, updated_at
    """)

    result = await db.execute(insert_query, {
        "username": user_data.username,
        "hashed_password": hashed_password,
        "role": user_data.role,
        "email": user_data.email,
        "full_name": user_data.full_name
    })
    await db.commit()

    user = result.fetchone()

    # Log action
    await log_user_action(
        db,
        user.id,  # type: ignore
        "USER_CREATED",
        current_user.username,
        f"Created user '{user_data.username}' with role '{user_data.role}'"
    )

    logger.info(f"User '{user_data.username}' created by '{current_user.username}'")

    return UserResponse(
        id=user.id,  # type: ignore
        username=user.username,  # type: ignore
        role=user.role,  # type: ignore
        email=user.email,  # type: ignore
        full_name=user.full_name,  # type: ignore
        is_active=user.is_active,  # type: ignore
        created_at=user.created_at,  # type: ignore
        updated_at=user.updated_at  # type: ignore
    )


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Max results (max: 500)"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    List all users (admin only).

    **Security:**
    - Requires admin role
    - Passwords are never returned

    **Returns:**
    - 200: List of users
    - 403: Not authorized (not admin)
    """
    query = "SELECT id, username, role, email, full_name, is_active, created_at, updated_at FROM users WHERE 1=1"
    params = {"skip": skip, "limit": limit}

    if role:
        query += " AND role = :role"
        params["role"] = role

    if is_active is not None:
        query += " AND is_active = :is_active"
        params["is_active"] = is_active

    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :skip"

    result = await db.execute(text(query), params)
    users = result.fetchall()

    return [
        UserResponse(
            id=user.id,  # type: ignore
            username=user.username,  # type: ignore
            role=user.role,  # type: ignore
            email=user.email,  # type: ignore
            full_name=user.full_name,  # type: ignore
            is_active=user.is_active,  # type: ignore
            created_at=user.created_at,  # type: ignore
            updated_at=user.updated_at  # type: ignore
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Get a single user by ID (admin only).

    **Security:**
    - Requires admin role
    - Password is never returned

    **Returns:**
    - 200: User data
    - 404: User not found
    - 403: Not authorized (not admin)
    """
    query = text("""
        SELECT id, username, role, email, full_name, is_active, created_at, updated_at
        FROM users
        WHERE id = :user_id
    """)

    result = await db.execute(query, {"user_id": user_id})
    user = result.fetchone()

    if user is None:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    return UserResponse(
        id=user.id,  # type: ignore
        username=user.username,  # type: ignore
        role=user.role,  # type: ignore
        email=user.email,  # type: ignore
        full_name=user.full_name,  # type: ignore
        is_active=user.is_active,  # type: ignore
        created_at=user.created_at,  # type: ignore
        updated_at=user.updated_at  # type: ignore
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Update a user (admin only).

    **Security:**
    - Requires admin role
    - Password is hashed if provided
    - Action is logged in audit trail

    **Returns:**
    - 200: User updated successfully
    - 404: User not found
    - 400: Validation error
    - 403: Not authorized (not admin)
    """
    # Check if user exists
    check_query = text("SELECT id FROM users WHERE id = :user_id")
    result = await db.execute(check_query, {"user_id": user_id})
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    # Build update query dynamically
    updates = []
    params = {"user_id": user_id}

    if user_data.password is not None:
        updates.append("hashed_password = :hashed_password")
        params["hashed_password"] = hash_password(user_data.password)

    if user_data.role is not None:
        updates.append("role = :role")
        params["role"] = user_data.role

    if user_data.email is not None:
        updates.append("email = :email")
        params["email"] = user_data.email

    if user_data.full_name is not None:
        updates.append("full_name = :full_name")
        params["full_name"] = user_data.full_name

    if user_data.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = user_data.is_active

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")

    update_query = text(f"""
        UPDATE users
        SET {", ".join(updates)}
        WHERE id = :user_id
        RETURNING id, username, role, email, full_name, is_active, created_at, updated_at
    """)

    result = await db.execute(update_query, params)
    await db.commit()

    user = result.fetchone()

    # Log action
    changes = ", ".join([k for k in user_data.dict(exclude_unset=True).keys()])
    await log_user_action(
        db,
        user_id,
        "USER_UPDATED",
        current_user.username,
        f"Updated fields: {changes}"
    )

    logger.info(f"User {user_id} updated by '{current_user.username}': {changes}")

    return UserResponse(
        id=user.id,  # type: ignore
        username=user.username,  # type: ignore
        role=user.role,  # type: ignore
        email=user.email,  # type: ignore
        full_name=user.full_name,  # type: ignore
        is_active=user.is_active,  # type: ignore
        created_at=user.created_at,  # type: ignore
        updated_at=user.updated_at  # type: ignore
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Delete a user (admin only).

    **Security:**
    - Requires admin role
    - Cannot delete yourself
    - Action is logged in audit trail

    **Returns:**
    - 204: User deleted successfully
    - 404: User not found
    - 400: Cannot delete yourself
    - 403: Not authorized (not admin)
    """
    # Check if user exists
    check_query = text("SELECT id, username FROM users WHERE id = :user_id")
    result = await db.execute(check_query, {"user_id": user_id})
    user = result.fetchone()

    if user is None:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    # Prevent self-deletion
    if user.username == current_user.username:  # type: ignore
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )

    # Log action before deletion
    await log_user_action(
        db,
        user_id,
        "USER_DELETED",
        current_user.username,
        f"Deleted user '{user.username}'"  # type: ignore
    )

    # Delete user
    delete_query = text("DELETE FROM users WHERE id = :user_id")
    await db.execute(delete_query, {"user_id": user_id})
    await db.commit()

    logger.warning(f"User {user_id} ('{user.username}') deleted by '{current_user.username}'")  # type: ignore


@router.get("/roles/", response_model=List[RoleResponse])
async def list_roles(
    current_user = Depends(require_auth)
):
    """
    List available roles and their permissions.

    **Security:**
    - Requires authentication (any role)

    **Returns:**
    - 200: List of roles
    """
    return [
        RoleResponse(
            role="admin",
            description="Administrator with full access",
            permissions=[
                "read:all",
                "write:all",
                "delete:all",
                "manage:users",
                "manage:roles"
            ]
        ),
        RoleResponse(
            role="researcher",
            description="Researcher with read access",
            permissions=[
                "read:phenopackets",
                "read:publications",
                "read:aggregations"
            ]
        )
    ]


@router.post("/{user_id}/roles", response_model=UserResponse)
async def assign_role(
    user_id: int,
    role: str = Query(..., description="Role to assign (admin or researcher)"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Assign a role to a user (admin only).

    **Security:**
    - Requires admin role
    - Action is logged in audit trail

    **Returns:**
    - 200: Role assigned successfully
    - 404: User not found
    - 400: Invalid role
    - 403: Not authorized (not admin)
    """
    # Validate role
    allowed_roles = {"admin", "researcher"}
    if role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role}'. Must be one of: {allowed_roles}"
        )

    # Update role
    update_query = text("""
        UPDATE users
        SET role = :role, updated_at = NOW()
        WHERE id = :user_id
        RETURNING id, username, role, email, full_name, is_active, created_at, updated_at
    """)

    result = await db.execute(update_query, {"user_id": user_id, "role": role})
    await db.commit()

    user = result.fetchone()

    if user is None:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    # Log action
    await log_user_action(
        db,
        user_id,
        "ROLE_ASSIGNED",
        current_user.username,
        f"Assigned role '{role}' to user '{user.username}'"  # type: ignore
    )

    logger.info(f"Role '{role}' assigned to user {user_id} by '{current_user.username}'")

    return UserResponse(
        id=user.id,  # type: ignore
        username=user.username,  # type: ignore
        role=user.role,  # type: ignore
        email=user.email,  # type: ignore
        full_name=user.full_name,  # type: ignore
        is_active=user.is_active,  # type: ignore
        created_at=user.created_at,  # type: ignore
        updated_at=user.updated_at  # type: ignore
    )
```

### 2. Database Migration for Audit Logging

**File:** `backend/alembic/versions/xxxx_add_user_audit_log.py`

```python
"""Add user audit log table

Revision ID: xxxx
Revises: yyyy
Create Date: 2025-01-XX XX:XX:XX
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'xxxx'
down_revision = 'yyyy'  # Previous migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_audit_log table for tracking user management actions."""
    op.execute("""
        CREATE TABLE user_audit_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action VARCHAR(50) NOT NULL,
            performed_by VARCHAR(100) NOT NULL,
            details TEXT,
            timestamp TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    # Index for efficient querying
    op.execute("""
        CREATE INDEX idx_user_audit_log_user_id ON user_audit_log (user_id);
        CREATE INDEX idx_user_audit_log_timestamp ON user_audit_log (timestamp DESC);
        CREATE INDEX idx_user_audit_log_action ON user_audit_log (action);
    """)

    # Add missing columns to users table
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS email VARCHAR(255),
        ADD COLUMN IF NOT EXISTS full_name VARCHAR(255),
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    """)


def downgrade() -> None:
    """Drop user_audit_log table."""
    op.execute("DROP TABLE IF EXISTS user_audit_log CASCADE;")
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS email,
        DROP COLUMN IF EXISTS full_name,
        DROP COLUMN IF EXISTS is_active;
    """)
```

### 3. Auth Dependency Updates

**File:** `backend/app/auth.py`

**Add `require_admin` dependency:**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Require admin role for endpoint access.

    Validates JWT token and checks if user has admin role.

    Raises:
        HTTPException: 403 if user is not admin
    """
    user = await require_auth(credentials)  # Validate token first

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return user
```

### 4. Register Router in Main App

**File:** `backend/app/main.py`

```python
from app.users import endpoints as user_endpoints

# Include routers
app.include_router(user_endpoints.router)
```

## Acceptance Criteria

### User CRUD Operations
- [ ] `POST /api/v2/users/` - Create user (admin only)
- [ ] `GET /api/v2/users/` - List users (admin only)
- [ ] `GET /api/v2/users/{id}` - Get user (admin only)
- [ ] `PUT /api/v2/users/{id}` - Update user (admin only)
- [ ] `DELETE /api/v2/users/{id}` - Delete user (admin only)

### Role Management
- [ ] `GET /api/v2/users/roles/` - List available roles
- [ ] `POST /api/v2/users/{id}/roles` - Assign role (admin only)

### Security
- [ ] Password hashing with bcrypt
- [ ] Password strength validation (8+ chars, uppercase, lowercase, digit)
- [ ] Admin-only access enforced
- [ ] Cannot delete own account
- [ ] JWT token validation

### Audit Logging
- [ ] `user_audit_log` table created
- [ ] All actions logged (create, update, delete, role assign)
- [ ] Logs include: user_id, action, performed_by, details, timestamp

### Documentation
- [ ] OpenAPI docs generated
- [ ] Request/response models documented
- [ ] Security requirements documented

## Files Created/Modified

### New Files (2 files, ~800 lines)
- `backend/app/users/endpoints.py` (~700 lines)
- `backend/alembic/versions/xxxx_add_user_audit_log.py` (~60 lines)

### Modified Files (2 files, ~40 lines)
- `backend/app/auth.py` (+20 lines for `require_admin`)
- `backend/app/main.py` (+2 lines to register router)

**Total changes:** ~860 lines across 4 files

## Dependencies

**Blocked by:** None

**Blocks:** None (optional feature)

**Requires:**
- `passlib[bcrypt]>=1.7.4` (already installed)
- `pydantic[email]` (for email validation)

## Timeline

**Estimated:** 6 hours

**Breakdown:**
- Step 1 (Endpoints): 3 hours
- Step 2 (Migration): 30 minutes
- Step 3 (Auth updates): 30 minutes
- Step 4 (Testing): 1.5 hours
- Step 5 (Documentation): 30 minutes

**Total:** ~6 hours

## Priority

**P3 (Low)** - Admin convenience feature

**Rationale:**
- Nice-to-have (not blocking any features)
- Admins can still manage users via SQL
- Improves admin experience
- Enables future features (self-service, integrations)

**Recommended Timeline:** After Issue #37 Phase 2 complete

## Labels

`backend`, `api`, `security`, `user-management`, `admin`, `p3`

## Testing Verification

### Test 1: Create User

```bash
# Login as admin
TOKEN=$(curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | jq -r '.access_token')

# Create new user
curl -X POST http://localhost:8000/api/v2/users/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "TestPass123!",
    "role": "researcher",
    "email": "test@example.com",
    "full_name": "Test User"
  }'

# Expected: 201 Created with user data
```

### Test 2: List Users

```bash
curl -X GET http://localhost:8000/api/v2/users/ \
  -H "Authorization: Bearer $TOKEN"

# Expected: Array of users (admin + testuser)
```

### Test 3: Update User

```bash
curl -X PUT http://localhost:8000/api/v2/users/2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "admin",
    "email": "newemail@example.com"
  }'

# Expected: 200 OK with updated user data
```

### Test 4: Assign Role

```bash
curl -X POST "http://localhost:8000/api/v2/users/2/roles?role=admin" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 200 OK with user data showing new role
```

### Test 5: Delete User

```bash
curl -X DELETE http://localhost:8000/api/v2/users/2 \
  -H "Authorization: Bearer $TOKEN"

# Expected: 204 No Content
```

### Test 6: Non-Admin Access (Should Fail)

```bash
# Login as researcher
RESEARCHER_TOKEN=$(curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=researcher&password=research123" | jq -r '.access_token')

# Try to list users (should fail)
curl -X GET http://localhost:8000/api/v2/users/ \
  -H "Authorization: Bearer $RESEARCHER_TOKEN"

# Expected: 403 Forbidden
```

### Test 7: Audit Log

```sql
-- Check audit log entries
SELECT * FROM user_audit_log ORDER BY timestamp DESC LIMIT 10;

-- Expected: All actions logged with user_id, action, performed_by, timestamp
```

## Security Considerations

### Password Security
- Bcrypt hashing with salt (OWASP recommended)
- Password strength validation enforced
- Passwords never returned in responses
- Password history not tracked (can be added in future)

### Access Control
- All endpoints require admin role
- JWT token validation on every request
- Cannot delete own account (prevents lockout)
- Role validation on assignment

### Audit Trail
- All actions logged to `user_audit_log`
- Immutable audit records (no updates/deletes)
- Includes: who, what, when, details
- Compliant with HIPAA audit requirements

### Rate Limiting (Future)
- Not implemented in this issue
- Recommend adding rate limiting for user creation (prevent abuse)
- Example: 10 users per hour per admin

## Performance Considerations

### Database Queries
- All queries use indexes (username, id, role)
- Pagination enforced (max 500 users)
- No N+1 queries

### Password Hashing
- Bcrypt is CPU-intensive (~100ms per hash)
- Acceptable for user creation/update (infrequent)
- Does not affect read operations

### Audit Logging
- Async insert (doesn't block response)
- Indexed for efficient querying
- Minimal storage impact (~100 bytes per log entry)

## Rollback Strategy

If issues arise:

```bash
# 1. Revert code
git revert <commit-hash>
systemctl restart hnf1b-backend

# 2. Drop audit log table (optional)
psql $DATABASE_URL -c "DROP TABLE IF EXISTS user_audit_log CASCADE;"

# 3. Revert database migration
cd backend
uv run alembic downgrade -1
```

**Impact:** Minimal - existing auth endpoints still work

## Future Enhancements (Not in Scope)

- [ ] Self-service user registration (with approval workflow)
- [ ] Password reset via email
- [ ] Two-factor authentication (2FA)
- [ ] OAuth/SSO integration (Google, GitHub)
- [ ] User groups/teams
- [ ] Fine-grained permissions (beyond admin/researcher)
- [ ] User activity dashboard
- [ ] Password expiration policy
- [ ] Account lockout after failed login attempts
- [ ] API key management for programmatic access

## Related Issues

- Issue #58: Document test user credentials (admin/admin123, researcher/research123)
- Future: User management UI in frontend

## Reference Documentation

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Passlib Bcrypt](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html)
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
