# Authentication & User Management Documentation

## 1. API Documentation

**File:** `docs/api/authentication.md`

```markdown
# Authentication & User Management API

## POST /api/v1/auth/register

Register a new user (Broker, Client, Underwriter, or Admin).

**Permissions:** Public

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "role": "broker",
  "full_name": "John Doe",
  "phone": "+1-555-0199"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "email": "user@example.com",
  "role": "broker",
  "full_name": "John Doe",
  "phone": "+1-555-0199",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Password does not meet complexity requirements (min 10 chars, uppercase, number, special char).
- 409: User with this email already exists.
- 422: Validation error (invalid email format or missing fields).

---

## POST /api/v1/auth/login

Authenticate a user and return JWT tokens.

**Permissions:** Public

**Request:**
```json
{
  "email": "user@example.com",
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
- 401: Invalid credentials (email or password incorrect).
- 422: Validation error.

---

## POST /api/v1/auth/refresh

Refresh an expired access token using a valid refresh token.

**Permissions:** Public (Requires valid refresh token)

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

Invalidate the current refresh token (add to blocklist).

**Permissions:** Authenticated User

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):**
*No Content*

**Errors:**
- 401: Unauthorized.
- 422: Validation error.

---

## GET /api/v1/users/me

Retrieve the currently authenticated user's profile.

**Permissions:** Authenticated User

**Headers:**
`Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "id": "uuid-v4",
  "email": "user@example.com",
  "role": "broker",
  "full_name": "John Doe",
  "phone": "+1-555-0199",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated.

---

## PUT /api/v1/users/me

Update the currently authenticated user's profile information.

**Permissions:** Authenticated User

**Headers:**
`Authorization: Bearer <access_token>`

**Request:**
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+1-555-0200"
}
```

**Response (200):**
```json
{
  "id": "uuid-v4",
  "email": "user@example.com",
  "role": "broker",
  "full_name": "Johnathan Doe",
  "phone": "+1-555-0200",
  "is_active": true,
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 422: Validation error.

---
```

## 2. Module README

**File:** `docs/modules/authentication.md`

```markdown
# Authentication & User Management Module

## Overview
This module handles user registration, authentication, and profile management for the Canadian Mortgage Underwriting System. It supports role-based access control (RBAC) for Brokers, Clients, Underwriters, and Admins.

## Key Features
- **Secure Registration:** Enforces strong password complexity (10+ chars, mixed case, numbers, symbols).
- **JWT Authentication:** Stateless authentication with short-lived access tokens (30 min) and long-lived refresh tokens (7 days).
- **Role Management:** Supports distinct roles (`broker`, `client`, `admin`, `underwriter`) to enforce permission boundaries in business logic.
- **Profile Management:** Users can update their contact details via `PUT /users/me`.
- **Audit Trail:** All user records include `created_at` and `updated_at` timestamps to satisfy FINTRAC requirements.

## Security & Compliance
- **Password Storage:** Passwords are hashed using bcrypt before storage.
- **PIPEDA Compliance:** Sensitive fields are handled according to data minimization principles. While email/phone are stored for contact, passwords are never logged or returned in responses.
- **FINTRAC Compliance:** Identity verification events (login/register) are logged with correlation IDs for auditability.

## Usage Example

### 1. Register a new Broker
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "broker@example.com",
    "password": "SecurePass123!",
    "role": "broker",
    "full_name": "Jane Smith",
    "phone": "+14165550123"
  }'
```

### 2. Login to receive Tokens
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "broker@example.com",
    "password": "SecurePass123!"
  }'
```

### 3. Access Protected Endpoint
Use the `access_token` returned from login in the Authorization header.
```bash
curl -X GET "https://api.mortgage-system.com/api/v1/users/me" \
  -H "Authorization: Bearer <access_token>"
```
```

## 3. Configuration Notes

**Update to `.env.example`:**

```bash
# Authentication & User Management Configuration

# Secret key for encoding JWT tokens (Generate strong random string)
SECRET_KEY=change_me_to_secure_random_string

# Algorithm for encoding JWT
ALGORITHM=HS256

# Access Token Expiry (Minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh Token Expiry (Days)
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Complexity Rules
PASSWORD_MIN_LENGTH=10
```

## 4. Changelog Update

**Update to `CHANGELOG.md`:**

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New endpoints for user registration, login, token refresh, logout, and profile management.
- JWT implementation for stateless authentication with configurable expiry times.
- Role-based access control support (broker, client, admin, underwriter).
- Password complexity validation (enforced at registration/update).

### Changed
- Updated common/security.py to support bcrypt hashing and JWT generation.
- Updated .env.example with authentication specific configuration variables.

### Fixed
- N/A
```