# Issue #58: docs(frontend): document test user credentials for development

## Overview

No documentation for test login credentials in frontend documentation.

**Current:** Test users exist in backend but not documented in frontend
**Target:** Document test credentials in `frontend/CLAUDE.md` or `frontend/README.md`

## Why This Matters

### Problem

**Current State:**
- Backend has default test users (defined in `backend/app/auth_endpoints.py`)
- Admin: `admin` / `admin123`
- Researcher: `researcher` / `research123`
- **No documentation in frontend README or CLAUDE.md**
- Developers must read backend code to find credentials
- New developers waste time searching for login info
- Poor developer experience

**Impact:**
- ❌ Developers can't test authentication flows
- ❌ Frontend demos require backend code diving
- ❌ Onboarding friction for new contributors
- ❌ Inconsistent developer experience
- ❌ Time wasted searching for credentials

### Solution

**Add test credentials to frontend documentation:**
- Document in `frontend/CLAUDE.md` (for Claude Code)
- Add to `frontend/README.md` (for developers)
- Include security warning (development only)
- Link to backend auth documentation

## Current State

### Backend Test Users

**File:** `backend/app/auth_endpoints.py`

**Default Users Created:**
```python
# Admin user
{
    "username": "admin",
    "password": "admin123",  # Hashed with bcrypt in database
    "role": "admin"
}

# Researcher user
{
    "username": "researcher",
    "password": "research123",  # Hashed with bcrypt in database
    "role": "researcher"
}
```

**Note:** These are created automatically on first backend startup if database is empty.

### Frontend Documentation Gap

**Current frontend documentation does NOT mention:**
- Test user credentials
- How to log in for development
- Available roles and permissions
- Authentication flow testing

**Developers must:**
1. Read backend code to find credentials
2. Ask other developers
3. Trial and error with common usernames/passwords

## Implementation

### Option 1: Add to frontend/CLAUDE.md (Recommended)

**File:** `frontend/CLAUDE.md`

**Add new section:**
```markdown
## Authentication & Test Users

### Test Credentials (Development Only)

**⚠️ WARNING: These credentials are for development/testing only. Never use in production.**

The backend creates default test users on first startup:

**Admin User:**
- **Username:** `admin`
- **Password:** `admin123`
- **Role:** Administrator (full access)
- **Use for:** Testing admin features, user management

**Researcher User:**
- **Username:** `researcher`
- **Password:** `research123`
- **Role:** Researcher (standard access)
- **Use for:** Testing standard user features, data access

### Login Flow

1. Navigate to `/login` page
2. Enter username and password
3. Click "Login" button
4. JWT token stored in `localStorage.token`
5. Redirected to `/phenopackets` (authenticated home)

### Authentication State

**Check if authenticated:**
```javascript
import { isAuthenticated } from '@/utils/auth';

if (isAuthenticated()) {
  // User is logged in
  const token = localStorage.getItem('token');
}
```

**Logout:**
```javascript
localStorage.removeItem('token');
this.$router.push('/login');
```

### Protected Routes

Routes that require authentication:
- `/phenopackets` - List of phenopackets
- `/phenopackets/:id` - Phenopacket detail
- `/variants` - Variants list
- `/variants/:id` - Variant detail
- `/publications` - Publications list
- `/publications/:pmid` - Publication detail
- `/aggregations` - Aggregation charts

Public routes (no auth required):
- `/` - Home page
- `/login` - Login page

### Backend Reference

See `backend/app/auth_endpoints.py` for:
- User creation logic
- Password hashing (bcrypt)
- JWT token generation
- Role-based access control

### Production Deployment

**⚠️ CRITICAL: Before production deployment:**

1. **Delete default test users:**
   ```sql
   DELETE FROM users WHERE username IN ('admin', 'researcher');
   ```

2. **Create production admin:**
   ```bash
   # Use secure password generator
   openssl rand -base64 32
   ```

3. **Update backend to disable default user creation:**
   ```python
   # backend/app/auth_endpoints.py
   CREATE_DEFAULT_USERS = os.getenv("CREATE_DEFAULT_USERS", "false").lower() == "true"
   ```

4. **Document real user creation process:**
   - See `backend/docs/USER_MANAGEMENT.md`

### Security Notes

- Passwords are hashed with bcrypt (never stored in plaintext)
- JWT tokens expire after 24 hours (configurable)
- No password reset flow in development (use SQL to reset)
- HTTPS required in production (token security)
```

### Option 2: Add to frontend/README.md

**File:** `frontend/README.md`

**Add new section under "Development":**
```markdown
## Test Users

For development and testing, the backend creates default users:

| Username | Password | Role | Access Level |
|----------|----------|------|--------------|
| `admin` | `admin123` | Admin | Full access |
| `researcher` | `research123` | Researcher | Standard access |

**⚠️ Development only - never use these credentials in production!**

### Quick Start

1. Start backend: `cd backend && uv run uvicorn app.main:app`
2. Start frontend: `npm run dev`
3. Navigate to http://localhost:5173/login
4. Login with `admin` / `admin123`
5. Access authenticated routes

See `CLAUDE.md` for detailed authentication documentation.
```

### Option 3: Both (Recommended)

- **frontend/CLAUDE.md**: Detailed documentation (for Claude Code and developers)
- **frontend/README.md**: Quick reference (for fast onboarding)

## Implementation Steps

### Step 1: Update frontend/CLAUDE.md (10 min)

Add comprehensive authentication section with:
- Test user credentials
- Login flow explanation
- Authentication utilities
- Protected routes list
- Production security warnings

### Step 2: Update frontend/README.md (5 min)

Add quick reference table with:
- Test user credentials
- Link to detailed documentation
- Security warning

### Step 3: Add Backend Reference (Optional) (5 min)

**File:** `backend/CLAUDE.md`

Add cross-reference:
```markdown
## Test Users

See `frontend/CLAUDE.md` for test user credentials used in development.

Default users created on first startup (if database empty):
- Admin: `admin` / `admin123`
- Researcher: `researcher` / `research123`

**Production:** Set `CREATE_DEFAULT_USERS=false` environment variable.
```

### Step 4: Update .env.example (Optional) (2 min)

**File:** `backend/.env.example`

Add:
```bash
# Development: Create default test users on startup
# Production: Set to false and create users manually
CREATE_DEFAULT_USERS=true
```

## Acceptance Criteria

### Documentation
- [ ] Test credentials documented in `frontend/CLAUDE.md`
- [ ] Quick reference added to `frontend/README.md`
- [ ] Security warning included (development only)
- [ ] Login flow explained
- [ ] Protected routes listed
- [ ] Production deployment warnings added

### Clarity
- [ ] Credentials easily findable (first search result)
- [ ] No ambiguity about which username/password to use
- [ ] Clear distinction between dev and production

### Cross-References
- [ ] Backend documentation references frontend docs
- [ ] Frontend documentation references backend auth code
- [ ] Links between related documentation sections

### Security
- [ ] Warning that credentials are for development only
- [ ] Production deployment checklist included
- [ ] Instructions to delete default users before production
- [ ] Password security best practices mentioned

## Files Modified

### Primary Changes
- `frontend/CLAUDE.md` (~50 lines added)
  - New "Authentication & Test Users" section
  - Test credentials table
  - Login flow explanation
  - Protected routes list
  - Production security warnings

- `frontend/README.md` (~15 lines added)
  - Quick reference table
  - Link to detailed docs
  - Security warning

### Optional Changes
- `backend/CLAUDE.md` (~10 lines added)
  - Cross-reference to frontend docs
  - Production environment variable

- `backend/.env.example` (~3 lines added)
  - CREATE_DEFAULT_USERS variable

**Total changes:** ~65-80 lines across 2-4 files

## Dependencies

**Blocked by:** None - documentation only

**Blocks:** None

**Requires:**
- Knowledge of backend test users (already exist)
- Understanding of authentication flow

## Timeline

**Estimated:** 30 minutes

**Breakdown:**
- Step 1 (frontend/CLAUDE.md): 10 minutes
- Step 2 (frontend/README.md): 5 minutes
- Step 3 (backend reference): 5 minutes
- Step 4 (.env.example): 2 minutes
- Review and polish: 8 minutes

**Total:** ~30 minutes

## Priority

**P2 (Medium)** - Developer experience

**Rationale:**
- Improves developer onboarding
- Quick fix (30 minutes)
- No code changes required
- Low priority (workaround: ask other developers or read backend code)
- Nice-to-have but not blocking

**Recommended Timeline:** After Issue #37 Phase 2 complete

## Labels

`frontend`, `backend`, `documentation`, `developer-experience`, `authentication`, `p2`

## Testing Verification

### Test 1: Documentation Findability
1. Open `frontend/CLAUDE.md`
2. Search for "login" or "credentials" or "password"
3. Verify test user section found in <10 seconds
4. Credentials clearly visible

### Test 2: Login Flow
1. Follow documented instructions
2. Start backend and frontend
3. Login with `admin` / `admin123`
4. Verify successful authentication
5. Verify JWT token in localStorage
6. Access protected route (e.g., `/phenopackets`)

### Test 3: Cross-References
1. Check links between frontend and backend docs
2. Verify links work (no 404s)
3. Verify consistent information across docs

### Test 4: Security Warnings
1. Verify prominent warning in documentation
2. Check production deployment checklist present
3. Verify instructions to delete default users

## Known Limitations

### Limitation 1: No Password Reset Flow
**Issue:** Test users cannot reset passwords in development
**Workaround:** Restart backend or update database directly
**Future:** Add password reset flow (not in scope)

### Limitation 2: Single Role per User
**Issue:** Test users have fixed roles (admin or researcher)
**Workaround:** Create additional test users in database
**Future:** Add user management UI (not in scope)

### Limitation 3: No Email Verification
**Issue:** Test users don't require email verification
**Impact:** Doesn't match production flow
**Workaround:** Document difference between dev and prod
**Future:** Add email verification in production (not in scope)

## Future Enhancements (Not in Scope)

- [ ] Add test user creation script (`create-test-user.sh`)
- [ ] Document user management UI (if implemented)
- [ ] Add password reset flow documentation
- [ ] Document role-based access control (RBAC)
- [ ] Add authentication troubleshooting guide
- [ ] Document JWT token structure and claims
- [ ] Add security best practices guide
- [ ] Document OAuth/SSO integration (future)

## Security Considerations

### Development
- Test credentials only active in development mode
- Passwords hashed with bcrypt (never plaintext)
- JWT tokens used for authentication
- HTTPS not required in development (localhost)

### Production
- **MUST delete default test users before production**
- **MUST use strong passwords (32+ chars, random)**
- **MUST enable HTTPS (TLS 1.3+)**
- **MUST rotate JWT secret regularly**
- **MUST implement rate limiting on login endpoint**
- **MUST enable password complexity requirements**
- **MUST implement account lockout after failed attempts**

### Documentation Security
- No production credentials in documentation
- No real user data in examples
- Clear warnings about test-only credentials

## Related Issues

- Issue #X: User management UI (if exists)
- Issue #X: Role-based access control (RBAC)
- Issue #X: Production deployment guide

## Example Documentation Preview

### frontend/CLAUDE.md Preview

```markdown
# Frontend Development Guide

## Authentication & Test Users

### Quick Reference: Test Credentials

**⚠️ Development Only - Never use in production**

| Username | Password | Role | Use Case |
|----------|----------|------|----------|
| `admin` | `admin123` | Administrator | Testing admin features |
| `researcher` | `research123` | Researcher | Testing standard features |

### Login Instructions

1. Start backend: `cd backend && make backend`
2. Start frontend: `npm run dev`
3. Navigate to http://localhost:5173/login
4. Enter credentials:
   - Username: `admin`
   - Password: `admin123`
5. Click "Login"
6. Redirected to `/phenopackets` (authenticated)

### Verification

Check if login worked:
```bash
# Open browser DevTools console
localStorage.getItem('token')
// Should return JWT token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Protected Routes

These routes require authentication (redirect to `/login` if not logged in):
- `/phenopackets` - Phenopacket list
- `/phenopackets/:id` - Phenopacket detail
- `/publications` - Publications list
- `/aggregations` - Charts and statistics

### Production Warning

**⚠️ BEFORE PRODUCTION:**
1. Delete test users from database
2. Create real admin with strong password
3. Set `CREATE_DEFAULT_USERS=false` in backend
4. Enable HTTPS/TLS
5. Rotate JWT secret

See `backend/docs/PRODUCTION_DEPLOYMENT.md` for full checklist.
```

### frontend/README.md Preview

```markdown
# HNF1B Database - Frontend

## Development

### Test Users

Default test users for development:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Administrator |
| `researcher` | `research123` | Researcher |

**⚠️ Development only!** See [CLAUDE.md](./CLAUDE.md#authentication--test-users) for details.

### Quick Start

```bash
npm install
npm run dev
```

Navigate to http://localhost:5173/login and use test credentials above.
```

## Rollback Strategy

**No rollback needed** - documentation changes only.

If needed:
```bash
git revert <commit-hash>
```

**Impact:** Zero - documentation only.
