Here is the documentation for the Authentication & User Management module.

### 1. API Documentation

**File:** `docs/api/authentication_user_management.md`

```markdown
# Authentication & User Management API

## Overview
This module handles user registration, authentication (JWT), and profile management. It supports role-based access control for Brokers, Clients, Admins, and Underwriters.

---

## POST /api/v1/auth/register

Registers a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "client"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "client",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Password does not meet complexity requirements (min 10 chars, uppercase, number, special char).
- 409: User with this email already exists.
- 422: Validation error (e.g., invalid email format).

---

## POST /api/v1/auth/login

Authenticates a user and returns JWT tokens.

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
  "token_type": "bearer"
}
```

**Errors:**
- 401: Invalid credentials or account inactive.
- 422: Validation error.

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
  "token_type": "bearer"
}
```

**Errors:**
- 401: Invalid or expired refresh token.
- 422: Validation error.

---

## POST /api/v1/auth/logout

Invalidates the refresh token (logs the user out).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):**
*No Content*

**Errors:**
- 401: Invalid token or user not authenticated.
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
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "client",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated (missing or invalid token).

---

## PUT /api/v1/users/me

Updates the currently authenticated user's profile information.

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
  "id": "uuid-v4",
  "email": "user@example.com",
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0200",
  "role": "client",
  "is_active": true,
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 400: Invalid phone number format.
- 422: Validation error.
```

---

### 2. Module README

**File:** `docs/modules/authentication_user_management.md`

```markdown
# Authentication & User Management Module

## Overview
The Authentication & User Management module is responsible for identity lifecycle management within the Canadian Mortgage Underwriting System. It provides secure endpoints for registration, login, token management, and profile updates. The module enforces strict password policies and utilizes JSON Web Tokens (JWT) for stateless authentication.

## Key Features

1.  **Role-Based Access Control (RBAC):**
    *   Supports four distinct roles: `broker`, `client`, `admin`, and `underwriter`.
    *   Roles are embedded in the JWT payload for easy authorization checks in downstream services.

2.  **Security Standards:**
    *   **Password Storage:** Passwords are hashed using a strong algorithm (e.g., Argon2 or bcrypt) before storage. Plain text passwords are never persisted.
    *   **Password Complexity:** Enforces a minimum length of 10 characters, requiring at least one uppercase letter, one number, and one special character.
    *   **PIPEDA Compliance:** Access logs are maintained without logging sensitive credentials or PII.

3.  **JWT Token Management:**
    *   **Access Tokens:** Short-lived tokens (30-minute expiry) used to access protected API endpoints.
    *   **Refresh Tokens:** Long-lived tokens (7-day expiry) used to obtain new access tokens without requiring re-authentication.
    *   **Logout:** Refresh tokens are blacklisted/invalidated upon logout to prevent reuse.

## Usage Example

### 1. Register a new User
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/register" \
-H "Content-Type: application/json" \
-d '{
  "email": "broker@example.com",
  "password": "Mortgage@2026",
  "full_name": "Sarah Smith",
  "phone": "6045550123",
  "role": "broker"
}'
```

### 2. Login and Retrieve Token
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{
  "email": "broker@example.com",
  "password": "Mortgage@2026"
}'
```
*Save the `access_token` from the response.*

### 3. Access Protected Endpoint
```bash
curl -X GET "https://api.mortgage-system.com/api/v1/users/me" \
-H "Authorization: Bearer <access_token>"
```

## Dependencies
- `fastapi`: Web framework.
- `sqlalchemy`: ORM for user persistence.
- `pydantic`: Data validation.
- `python-jose`: JWT token creation and verification.
- `passlib`: Password hashing utilities.
```

---

### 3. Configuration Notes

**File:** `.env.example`

```bash
# ... existing config ...

# Authentication & User Management Configuration
# Algorithm used for signing JWT tokens (e.g., HS256)
JWT_ALGORITHM=HS256

# Secret key used to sign JWT tokens (Generate a strong random string)
# WARNING: Keep this secret in production
JWT_SECRET_KEY=change_me_in_production_to_a_secure_random_string

# Access Token Expiry (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh Token Expiry (days)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

### 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New endpoints for user registration, login, logout, and token refresh.
- User Profile: Endpoints to retrieve and update current user profile (`/users/me`).
- Role Support: Implementation of RBAC with roles (broker, client, admin, underwriter).
- Security: Enforced password complexity requirements (min 10 chars, mixed case, numbers, symbols).

### Changed
- Updated project dependencies to include `python-jose` and `passlib` for JWT and password handling.

### Fixed
- N/A
```