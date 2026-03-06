```markdown
# Authentication & User Management

## Overview
This module handles user registration, authentication, and profile management within the Canadian Mortgage Underwriting System. It supports role-based access control (RBAC) for Brokers, Clients, Admins, and Underwriters. The module ensures compliance with PIPEDA by securing Personally Identifiable Information (PII) and enforcing strict password policies.

### Key Features
- **Registration:** Self-service registration with email validation and strong password enforcement.
- **Authentication:** JWT-based stateless authentication with short-lived access tokens and long-lived refresh tokens.
- **Profile Management:** Users can update their own contact details.
- **Security:** Passwords are hashed using bcrypt; sensitive fields are encrypted at rest.

### Configuration
The following environment variables must be set in `.env` to configure the authentication module.

```bash
# Authentication & User Management Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## API Documentation

### POST /api/v1/auth/register

Register a new user. The default role is typically assigned as 'client' unless otherwise configured by an administrator.

**Request:**
```json
{
  "email": "broker@example.com",
  "password": "SecurePass123!",
  "full_name": "Jane Doe",
  "phone": "+1-416-555-0199"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "email": "broker@example.com",
  "role": "client",
  "full_name": "Jane Doe",
  "phone": "+1-416-555-0199",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400 Bad Request`: Password does not meet complexity requirements (Min 10 chars, 1 uppercase, 1 number, 1 special char).
- `409 Conflict`: Email already registered.
- `422 Unprocessable Entity`: Validation error on input fields.

---

### POST /api/v1/auth/login

Authenticate a user and return JWT tokens.

**Request:**
```json
{
  "email": "broker@example.com",
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
- `422 Unprocessable Entity`: Validation error on input fields.

---

### POST /api/v1/auth/refresh

Refresh an access token using a valid refresh token.

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
- `422 Unprocessable Entity`: Validation error on input fields.

---

### POST /api/v1/auth/logout

Invalidate the current session (refresh token).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204 No Content)**

**Errors:**
- `401 Unauthorized`: Invalid token.
- `422 Unprocessable Entity`: Validation error on input fields.

---

### GET /api/v1/users/me

Retrieve the currently authenticated user's profile.

**Headers:**
`Authorization: Bearer <access_token>`

**Response (200 OK):**
```json
{
  "id": 1,
  "email": "broker@example.com",
  "role": "broker",
  "full_name": "Jane Doe",
  "phone": "+1-416-555-0199",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `401 Unauthorized`: Token missing or invalid.

---

### PUT /api/v1/users/me

Update the currently authenticated user's profile information.

**Headers:**
`Authorization: Bearer <access_token>`

**Request:**
```json
{
  "full_name": "Jane Smith",
  "phone": "+1-416-555-0200",
  "password": "NewSecurePass456!"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "email": "broker@example.com",
  "role": "broker",
  "full_name": "Jane Smith",
  "phone": "+1-416-555-0200",
  "is_active": true,
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- `400 Bad Request`: Password does not meet complexity requirements.
- `401 Unauthorized`: Token missing or invalid.
- `422 Unprocessable Entity`: Validation error on input fields.
```