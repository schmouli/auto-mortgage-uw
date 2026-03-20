Here is the documentation for the **Authentication & User Management** module, structured according to the project conventions.

---

### 1. API Documentation

**File:** `docs/api/authentication.md`

```markdown
# Authentication & User Management API

## POST /api/v1/auth/register

Register a new user in the system.

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
  "id": 1,
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
- 400: Password does not meet complexity requirements (min 10 chars, 1 uppercase, 1 number, 1 special char).
- 409: User with this email already exists.
- 422: Validation error (see error_code).

---

## POST /api/v1/auth/login

Authenticate a user and issue JWT tokens.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- 401: Incorrect email or password.
- 422: Validation error.

---

## POST /api/v1/auth/refresh

Refresh an expired access token using a valid refresh token.

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
  "token_type": "bearer"
}
```

**Errors:**
- 401: Invalid or expired refresh token.
- 422: Validation error.

---

## POST /api/v1/auth/logout

Invalidate the current refresh token (logout).

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
- 422: Validation error.

---

## GET /api/v1/users/me

Retrieve the currently authenticated user's profile.

**Response (200):**
```json
{
  "id": 1,
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

**Request:**
```json
{
  "full_name": "John Smith",
  "phone": "+1-555-0200"
}
```

**Response (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "role": "broker",
  "full_name": "John Smith",
  "phone": "+1-555-0200",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 422: Validation error.
```

---

### 2. Module README

**File:** `docs/modules/authentication.md`

```markdown
# Authentication & User Management Module

## Overview
This module handles user registration, authentication, and profile management within the Canadian Mortgage Underwriting System. It utilizes JSON Web Tokens (JWT) for stateless authentication and Role-Based Access Control (RBAC) to enforce permissions across different user types.

## Key Features
- **Secure Registration:** Enforces strong password complexity (10+ chars, mixed case, numbers, special chars).
- **JWT Authentication:** Issues short-lived access tokens (30 mins) and long-lived refresh tokens (7 days).
- **Role Management:** Supports roles for `broker`, `client`, `admin`, and `underwriter`.
- **PIPEDA Compliance:** Passwords are hashed using bcrypt; PII (phone, name) is handled securely.

## User Roles
1. **broker**: Initiates mortgage applications on behalf of clients.
2. **client**: The applicant seeking a mortgage.
3. **underwriter**: Internal staff responsible for reviewing and approving applications.
4. **admin**: System administrator with full access.

## Usage Example

### 1. Register a new user
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane.broker@example.com",
    "password": "ComplexPass123!",
    "role": "broker",
    "full_name": "Jane Broker",
    "phone": "+1-604-555-0123"
  }'
```

### 2. Login to receive tokens
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "jane.broker@example.com",
    "password": "ComplexPass123!"
  }'
```
*Save the `access_token` from the response for subsequent requests.*

### 3. Access protected endpoint
```bash
curl -X GET "https://api.mortgage-system.com/api/v1/users/me" \
  -H "Authorization: Bearer <your_access_token>"
```

## Security Notes
- All passwords are salted and hashed before storage.
- Failed login attempts are logged for audit trails (FINTRAC compliance).
- Tokens must be transmitted over HTTPS.
```

---

### 3. Configuration Notes

**File:** `.env.example` (Append these lines)

```bash
# Authentication & User Management Configuration
# Secret key used to sign JWT tokens. Generate a strong random string in production.
SECRET_KEY=change_me_to_a_secure_random_string
ALGORITHM=HS256

# Token Expiration Times (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Complexity
# Minimum length for user passwords
PASSWORD_MIN_LENGTH=10
```

---

### 4. Changelog Update

**File:** `CHANGELOG.md` (Append to end)

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New module for user registration, login, and profile management.
- JWT Token handling: Access token (30m) and Refresh token (7d) implementation.
- RBAC: Support for roles (broker, client, admin, underwriter).
- Endpoints: POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout, GET /users/me, PUT /users/me.

### Changed
- Updated common/security.py to include password hashing utilities (bcrypt).

### Fixed
- N/A
```