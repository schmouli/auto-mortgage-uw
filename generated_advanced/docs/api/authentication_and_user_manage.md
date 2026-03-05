# Authentication & User Management API

## Overview

This module handles user registration, authentication (JWT), and profile management within the Canadian Mortgage Underwriting System. It enforces role-based access control (RBAC) and secure password storage.

## Base URL
`/api/v1`

---

## POST /auth/register

Registers a new user in the system. Passwords must meet complexity requirements (min 10 characters, uppercase, number, special character).

**Request:**
```json
{
  "email": "broker@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "phone": "+14155552671",
  "role": "broker"
}
```

**Response (201):**
```json
{
  "id": 1,
  "email": "broker@example.com",
  "full_name": "John Doe",
  "phone": "+14155552671",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400`: Password does not meet complexity requirements.
- `422`: Validation error (e.g., invalid email format).
- `409`: User with this email already exists.

**Valid Roles:** `broker`, `client`, `admin`, `underwriter`

---

## POST /auth/login

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
  "token_type": "bearer"
}
```

**Errors:**
- `401`: Invalid credentials or inactive account.

---

## POST /auth/refresh

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
- `401`: Invalid or expired refresh token.

---

## POST /auth/logout

Invalidates the refresh token (logout).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):**
No Content.

**Errors:**
- `401`: Invalid token.

---

## GET /users/me

Retrieves the profile of the currently authenticated user.

**Headers:**
`Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "id": 1,
  "email": "broker@example.com",
  "full_name": "John Doe",
  "phone": "+14155552671",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `401`: Not authenticated.

---

## PUT /users/me

Updates the profile of the currently authenticated user. Email and Role cannot be changed via this endpoint.

**Headers:**
`Authorization: Bearer <access_token>`

**Request:**
```json
{
  "full_name": "John Smith",
  "phone": "+14155552672"
}
```

**Response (200):**
```json
{
  "id": 1,
  "email": "broker@example.com",
  "full_name": "John Smith",
  "phone": "+14155552672",
  "role": "broker",
  "is_active": true,
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- `401`: Not authenticated.
- `422`: Validation error.

---

## Configuration Notes

Ensure the following environment variables are set in `.env` to support authentication flows:

```bash
# Authentication & User Management
# Secret key for JWT signing (generate a strong random key)
SECRET_KEY=your-super-secret-jwt-key-here

# Algorithm for encoding tokens
ALGORITHM=HS256

# Access token expiration time in minutes (Default: 30)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh token expiration time in days (Default: 7)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New endpoints for user registration, login, logout, and token refresh.
- User Profile: Endpoints to retrieve and update user profile (GET /users/me, PUT /users/me).
- Role-Based Access Control: Support for roles (broker, client, admin, underwriter) in user model.
- Security: Enforced password complexity (min 10 chars, uppercase, number, special char).
```