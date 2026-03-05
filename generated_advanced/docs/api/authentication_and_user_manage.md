```markdown
# Authentication & User Management API

## Overview

This module handles user registration, authentication, and profile management within the Canadian Mortgage Underwriting System. It supports role-based access control (RBAC) for Brokers, Clients, Admins, and Underwriters.

### Key Features
- **Secure Registration:** Enforces strong password policies (min 10 chars, uppercase, number, special char).
- **JWT Authentication:** Issues short-lived access tokens (30 min) and long-lived refresh tokens (7 days).
- **Profile Management:** Allows users to update their own contact information.
- **Audit Compliance:** All user records include `created_at` and `updated_at` timestamps. Passwords are hashed using bcrypt and never logged.

### Roles
- `broker`: External agent submitting applications.
- `client`: Applicant accessing their own status.
- `admin`: System administrator.
- `underwriter`: Internal staff reviewing applications.

---

## Configuration

Ensure the following environment variables are set in `.env`:

```bash
# Authentication Configuration
SECRET_KEY=your_super_secret_key_change_this_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## API Endpoints

### POST /auth/register

Registers a new user in the system.

**Request:**
```json
{
  "email": "john.doe@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "broker"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "email": "john.doe@example.com",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400 Bad Request`: Password does not meet complexity requirements.
- `409 Conflict`: Email already registered.
- `422 Unprocessable Entity`: Invalid input data structure.

---

### POST /auth/login

Authenticates a user and returns JWT tokens.

**Request:**
```json
{
  "email": "john.doe@example.com",
  "password": "SecurePass123!"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401 Unauthorized`: Incorrect email or password.
- `403 Forbidden`: User account is inactive.

---

### POST /auth/refresh

Refreshes an access token using a valid refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401 Unauthorized`: Invalid or expired refresh token.

---

### POST /auth/logout

Invalidates the refresh token (logout).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204 No Content)**

**Errors:**
- `401 Unauthorized`: Invalid token.

---

### GET /users/me

Retrieves the currently authenticated user's profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": 1,
  "email": "john.doe@example.com",
  "full_name": "John Doe",
  "phone": "+1-416-555-0199",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `401 Unauthorized`: Missing, invalid, or expired access token.

---

### PUT /users/me

Updates the currently authenticated user's profile information. Email and role cannot be changed via this endpoint.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0200"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "email": "john.doe@example.com",
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0200",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid phone number format.
- `401 Unauthorized`: Missing, invalid, or expired access token.
- `422 Unprocessable Entity`: Invalid input data structure.
```