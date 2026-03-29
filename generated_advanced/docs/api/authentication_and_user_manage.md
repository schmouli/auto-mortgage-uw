Here is the documentation for the **Authentication & User Management** module.

### 1. API Documentation

**File:** `docs/api/authentication_and_user_management.md`

```markdown
# Authentication & User Management API

This module handles user registration, authentication (JWT), and profile management for the Canadian Mortgage Underwriting System.

---

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
  "id": "550e8400-e29b-41d4-a716-446655440000",
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

**Permissions:** Public (No authentication required).

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
- 401: Invalid email or password.
- 422: Validation error.

**Permissions:** Public (No authentication required).

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

**Permissions:** Public (Requires valid refresh token).

---

## POST /api/v1/auth/logout

Invalidates the current refresh token (revokes it).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):**
(No Content)

**Errors:**
- 401: Invalid token.
- 422: Validation error.

**Permissions:** Authenticated User.

---

## GET /api/v1/users/me

Retrieves the profile of the currently authenticated user.

**Request:**
Headers: `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
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
- 401: Not authenticated or token expired.

**Permissions:** Authenticated User (Any Role).

---

## PUT /api/v1/users/me

Updates the profile of the currently authenticated user. Email and role cannot be changed via this endpoint.

**Request:**
Headers: `Authorization: Bearer <access_token>`
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+1-416-555-0999"
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
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

**Permissions:** Authenticated User (Any Role).
```

### 2. Module README

**File:** `docs/modules/authentication_and_user_management.md`

```markdown
# Authentication & User Management Module

## Overview
This module provides the foundational security layer for the Canadian Mortgage Underwriting System. It manages user identities, role-based access control (RBAC), and secure session management via JSON Web Tokens (JWT).

### Key Features
- **User Registration:** Secure onboarding with password complexity enforcement.
- **JWT Authentication:** Stateless authentication with short-lived access tokens and long-lived refresh tokens.
- **Role Management:** Supports roles specific to the mortgage lifecycle (Broker, Client, Underwriter, Admin).
- **Profile Management:** Users can update their own contact information.
- **Audit Compliance:** All user records include immutable `created_at` timestamps to satisfy FINTRAC requirements.

### Security & Compliance
- **PIPEDA:** PII (email, phone, name) is stored in the database. Passwords are hashed using bcrypt. Sensitive fields are never logged in plain text.
- **Password Policy:** Enforces OSFI-recommended security standards:
  - Minimum 10 characters.
  - At least one uppercase letter.
  - At least one number.
  - At least one special character.
- **Audit Trails:** Every user creation and update triggers a structured log event (correlation_id included) for FINTRAC auditability.

### Data Models

#### User
- `id`: UUID (Primary Key)
- `email`: String (Unique, Indexed)
- `hashed_password`: String (Bcrypt)
- `role`: Enum (broker, client, admin, underwriter)
- `full_name`: String
- `phone`: String
- `is_active`: Boolean
- `created_at`: DateTime (Audit)
- `updated_at`: DateTime (Audit)

### Service Logic Docstrings

The `services.py` file contains the core business logic:

```python
async def register_user(
    self, 
    email: str, 
    password: str, 
    full_name: str, 
    phone: str, 
    role: str
) -> User:
    """
    Registers a new user after validating password complexity and email uniqueness.
    Hashes password using bcrypt and persists user to DB.
    Logs PII masked event for FINTRAC compliance.
    """

async def authenticate_user(self, email: str, password: str) -> User:
    """
    Verifies credentials against stored hash.
    Returns User object if valid, raises AuthenticationError otherwise.
    """

async def create_tokens(self, user_id: str, role: str) -> TokenResponse:
    """
    Generates Access Token (30m expiry) and Refresh Token (7d expiry).
    Encodes role claims into the JWT for RBAC validation downstream.
    """
```

### Usage Examples

#### 1. Register a new Underwriter
```bash
curl -X POST "https://api.mortgage-system.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "underwriter@bank.ca",
    "password": "Complex!Pass123",
    "full_name": "Sarah Connor",
    "phone": "+1-647-555-0199",
    "role": "underwriter"
  }'
```

#### 2. Login and Access Protected Endpoint
```bash
# 1. Login
TOKEN_RESPONSE=$(curl -X POST "https://api.mortgage-system.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "underwriter@bank.ca", "password": "Complex!Pass123"}')

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r '.access_token')

# 2. Get Profile
curl -X GET "https://api.mortgage-system.com/api/v1/users/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```
```

### 3. Changelog Updates

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: Initial module implementation.
  - POST /auth/register: User registration with password complexity validation.
  - POST /auth/login: JWT authentication logic.
  - POST /auth/refresh: Token refresh mechanism.
  - POST /auth/logout: Token invalidation.
  - GET /users/me: User profile retrieval.
  - PUT /users/me: User profile updates.
- Database: Added `users` table with audit fields (created_at, updated_at).
- Security: Implemented Bcrypt password hashing and JWT generation (HS256).

### Changed
- Updated common/security.py to include password hashing utilities.

### Fixed
- N/A
```

### 4. Environment Variables

**File:** `.env.example`

```bash
# ... (existing config)

# Authentication & User Management Configuration
# Algorithm used for signing JWTs (e.g., HS256)
JWT_ALGORITHM=HS256

# Secret key used to sign JWTs (Generate via `openssl rand -hex 32`)
# WARNING: Keep this secret in production.
JWT_SECRET_KEY=change_me_to_a_secure_random_string

# Access Token expiration time in minutes (Standard: 30)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh Token expiration time in days (Standard: 7)
REFRESH_TOKEN_EXPIRE_DAYS=7
```