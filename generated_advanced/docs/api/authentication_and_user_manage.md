Here is the documentation for the Authentication & User Management module.

### 1. API Documentation

**File:** `docs/api/Authentication & User Management.md`

```markdown
# Authentication & User Management API

## Overview
This module handles user registration, authentication (JWT), and profile management. It enforces role-based access control (RBAC) and strict password policies.

## POST /api/v1/auth/register

Registers a new user in the system.

**Request:**
```json
{
  "email": "broker@example.com",
  "password": "SecureP@ssw0rd",
  "full_name": "John Doe",
  "phone": "+1-416-555-0123",
  "role": "broker"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "email": "broker@example.com",
  "full_name": "John Doe",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Password does not meet complexity requirements (min 10 chars, uppercase, number, special char).
- 409: User with this email already exists.
- 422: Validation error (see error_code).

---

## POST /api/v1/auth/login

Authenticates a user and returns JWT tokens.

**Request:**
```json
{
  "email": "broker@example.com",
  "password": "SecureP@ssw0rd"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:**
- 401: Invalid credentials.
- 422: Validation error.

---

## POST /api/v1/auth/refresh

Refreshes an expired access token using a valid refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:**
- 401: Invalid or expired refresh token.
- 422: Validation error.

---

## POST /api/v1/auth/logout

Invalidates the refresh token (revocation).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):** No Content

**Errors:**
- 401: Invalid token.
- 422: Validation error.

---

## GET /api/v1/users/me

Retrieves the currently authenticated user's profile.

**Headers:**
`Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "id": "uuid-v4",
  "email": "broker@example.com",
  "full_name": "John Doe",
  "phone": "+1-416-555-0123",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated.

---

## PUT /api/v1/users/me

Updates the currently authenticated user's profile information.

**Headers:**
`Authorization: Bearer <access_token>`

**Request:**
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0999"
}
```

**Response (200):**
```json
{
  "id": "uuid-v4",
  "email": "broker@example.com",
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0999",
  "role": "broker",
  "is_active": true,
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 422: Validation error.
```

### 2. Module README

**File:** `docs/modules/Authentication & User Management.md`

```markdown
# Authentication & User Management Module

## Overview
This module is responsible for identity and access management within the Canadian Mortgage Underwriting System. It handles user registration, secure authentication via JSON Web Tokens (JWT), and profile management.

### Key Features
- **Secure Password Storage**: Passwords are hashed using bcrypt/argon2 before storage.
- **JWT Authentication**: Stateless authentication with short-lived access tokens and long-lived refresh tokens.
- **Role-Based Access Control (RBAC)**: Supports four distinct roles to enforce permissions across the application.
- **Audit Compliance**: Maintains `created_at` and `updated_at` timestamps for all user records to satisfy FINTRAC audit trail requirements.

## Data Model

### Users Table
| Column          | Type         | Description                              |
|-----------------|--------------|------------------------------------------|
| id              | UUID / PK    | Unique identifier                        |
| email           | String       | Unique login email                       |
| hashed_password | String       | Bcrypt hash of the password              |
| role            | Enum         | User role (broker, client, admin, underwriter) |
| full_name       | String       | User's full legal name                   |
| phone           | String       | Contact phone number                     |
| is_active       | Boolean      | Account status flag                      |
| created_at      | DateTime     | Audit timestamp (FINTRAC)                |
| updated_at      | DateTime     | Audit timestamp (FINTRAC)                |

## Roles
1. **broker**: External agents submitting mortgage applications.
2. **client**: Applicants viewing their own application status.
3. **underwriter**: Internal staff reviewing and approving applications.
4. **admin**: System administrators with full access.

## Security & Compliance
- **PIPEDA Compliance**: Email addresses are treated as PII. Passwords are never logged or returned in API responses.
- **Password Policy**:
  - Minimum length: 10 characters.
  - Must contain at least one uppercase letter.
  - Must contain at least one number.
  - Must contain at least one special character.
```

### 3. Configuration Notes

**File:** `.env.example` (Append these entries)

```bash
# Authentication & User Management Configuration
# Secret key for encoding JWT tokens (Generate via `openssl rand -hex 32`)
SECRET_KEY=change_me_to_a_secure_random_string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 4. Changelog Update

**File:** `CHANGELOG.md` (Append these entries)

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New endpoints for registration, login, token refresh, logout, and profile management.
- JWT implementation with role-based access control (RBAC).
- Password complexity validation (min 10 chars, uppercase, number, special).
- Support for roles: broker, client, admin, underwriter.

### Changed
- N/A

### Fixed
- N/A
```