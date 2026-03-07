Here is the documentation for the Authentication & User Management module.

### 1. API Documentation

**File:** `docs/api/authentication_user_management.md`

```markdown
# Authentication & User Management API

## Overview
This module handles user registration, authentication (JWT), and user profile management. It supports role-based access control for brokers, clients, admins, and underwriters.

**Compliance Notes:**
- **PIPEDA:** All passwords are hashed using Argon2. PII (email, phone, name) is encrypted at rest (AES-256).
- **FINTRAC:** All login and registration events are logged with immutable audit trails.

---

## POST /api/v1/auth/register

Registers a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecureP@ssw0rd",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "broker"
}
```

**Constraints:**
- `password`: Minimum 10 characters. Must contain at least one uppercase letter, one number, and one special character.
- `role`: Must be one of `broker`, `client`, `admin`, `underwriter`. Defaults to `client` if omitted.

**Response (201):**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Password does not meet complexity requirements.
- 409: User with this email already exists.
- 422: Validation error (invalid email format, missing fields).

---

## POST /api/v1/auth/login

Authenticates a user and returns JWT tokens.

**Request:**
```json
{
  "email": "user@example.com",
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
- 401: Invalid credentials (email or password incorrect).
- 403: Account is inactive.

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

Invalidates the current refresh token (adds to blacklist).

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
  "id": "uuid-string",
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated or token expired.

---

## PUT /api/v1/users/me

Updates the currently authenticated user's profile.

**Headers:**
`Authorization: Bearer <access_token>`

**Request:**
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0200"
}
```

**Response (200):**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0200",
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

**File:** `docs/modules/authentication_user_management.md`

```markdown
# Authentication & User Management Module

## Overview
This module is responsible for identity and access management within the Canadian Mortgage Underwriting System. It provides secure endpoints for user registration, login, token management, and profile updates.

## Key Features
- **Secure Password Storage:** Uses Argon2id for password hashing.
- **JWT Authentication:** Implements stateless authentication using short-lived access tokens (30 mins) and long-lived refresh tokens (7 days).
- **Role-Based Access Control (RBAC):** Supports roles for `broker`, `client`, `admin`, and `underwriter`.
- **PIPEDA Compliance:** Encrypts PII at rest (AES-256) and ensures sensitive data is never logged.
- **Audit Trail:** Tracks creation and update timestamps for all user records.

## Service Logic (`services.py`)

### `AuthService`
- `register_user(data)`: Validates password complexity, checks for existing emails, hashes passwords, and creates a user record.
- `authenticate_user(email, password)`: Verifies credentials and returns user entity if valid.
- `create_tokens(user)`: Generates access and refresh JWTs with appropriate expiry times.
- `refresh_access_token(refresh_token)`: Validates refresh token and issues a new access token.

### `UserService`
- `get_user_profile(user_id)`: Retrieves user details.
- `update_user_profile(user_id, update_data)`: Updates allowed fields (full_name, phone). Enforces data minimization (email/role cannot be changed via this endpoint).

## Usage Example

### 1. Register a Broker
```bash
curl -X POST "https://api.example.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "broker@example.com",
    "password": "ComplexP@ss123",
    "full_name": "Jane Smith",
    "role": "broker"
  }'
```

### 2. Login
```bash
curl -X POST "https://api.example.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "broker@example.com",
    "password": "ComplexP@ss123"
  }'
```

### 3. Access Protected Route
```bash
curl -X GET "https://api.example.com/api/v1/users/me" \
  -H "Authorization: Bearer <access_token_from_login>"
```

## Security Considerations
- **Password Policy:** Enforced strictly in `schemas.py`.
- **Token Storage:** Refresh tokens are stored securely in the database (hashed) to allow revocation/logout.
- **Encryption:** `common/security.py` is used to encrypt `email` and `phone` before database persistence.
```

### 3. Configuration Notes

**File:** `.env.example`

```bash
# ... existing config ...

# Authentication & User Management Configuration
# Secret key for signing JWTs (generate with: openssl rand -hex 32)
SECRET_KEY=change_me_to_a_secure_random_string
ALGORITHM=HS256

# Token Expiry
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Policy
# Minimum length for user passwords
PASSWORD_MIN_LENGTH=10
```

### 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New endpoints for user registration, login, token refresh, logout, and profile management.
- JWT implementation with 30-minute access token expiry and 7-day refresh token expiry.
- Role-based access control support (broker, client, admin, underwriter).
- PII encryption at rest for user emails and phone numbers.

### Changed
- Updated common/security.py to support AES-256 encryption for user profile fields.

### Fixed
- N/A
```