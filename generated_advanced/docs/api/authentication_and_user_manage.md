Here is the documentation for the **Authentication & User Management** module.

### 1. API Documentation

**File:** `docs/api/authentication_user_management.md`

```markdown
# Authentication & User Management API

## Overview
This module handles user registration, authentication, and profile management. It supports role-based access control (RBAC) for brokers, clients, admins, and underwriters. All passwords are hashed using Argon2, and sessions are managed via JWT tokens.

---

## POST /api/v1/auth/register

Registers a new user in the system.

**Request:**
```json
{
  "email": "broker@example.com",
  "password": "SecurePass123!",
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
  "phone": "+1-416-555-0123",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Password does not meet complexity requirements (min 10 chars, uppercase, number, special char).
- 409: User with this email already exists.
- 422: Validation error on input fields.

---

## POST /api/v1/auth/login

Authenticates a user and returns JWT tokens.

**Request:**
```json
{
  "email": "broker@example.com",
  "password": "SecurePass123!"
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
- 401: Invalid credentials or account inactive.

---

## POST /api/v1/auth/refresh

Refreshes an access token using a valid refresh token.

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

---

## POST /api/v1/auth/logout

Invalidates the refresh token (revokes session).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):**
*No Content*

**Errors:**
- 401: Invalid token.

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

Updates the currently authenticated user's profile.

**Headers:**
`Authorization: Bearer <access_token>`

**Request:**
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0999",
  "password": "NewSecurePass456!"
}
```
*(Note: `password` is optional. If provided, it must meet complexity requirements.)*

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
- 400: Validation error or weak password.
- 401: Not authenticated.
```

### 2. CHANGELOG Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New module for user registration and login.
- Endpoints: POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout.
- User Profile Management: GET /users/me, PUT /users/me.
- RBAC Support: Implemented roles (broker, client, admin, underwriter) with strict password policies (min 10 chars, complexity enforced).
- JWT Security: Implemented Access Token (30m expiry) and Refresh Token (7d expiry) logic.

### Changed
- Updated common/security.py to support password hashing (Argon2) and JWT encoding/decoding.
```

### 3. Configuration Notes

**File:** `.env.example`

```bash
# ... existing config ...

# Authentication & User Management Configuration
# Secret key for encoding JWT tokens (Generate via: openssl rand -hex 32)
SECRET_KEY=change_me_to_a_secure_random_string
ALGORITHM=HS256

# Token Expiry Settings
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Policy
# Min length is enforced in code, complexity (upper, num, special) is enforced in code.
```