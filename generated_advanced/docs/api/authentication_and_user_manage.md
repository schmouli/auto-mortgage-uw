Here is the documentation for the Authentication & User Management module.

### 1. API Documentation
**File Path:** `docs/api/authentication_user_management.md`

```markdown
# Authentication & User Management API

This module handles user registration, authentication (JWT), and profile management. It enforces role-based access control and secure password policies compliant with financial regulations.

---

## POST /api/v1/auth/register

Register a new user (Broker or Client). Admins and Underwriters are typically created via database seeding or internal tools.

**Request:**
```json
{
  "email": "john.doe@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "phone": "+15145550199",
  "role": "broker"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "email": "john.doe@example.com",
  "full_name": "John Doe",
  "phone": "+15145550199",
  "role": "broker",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Password does not meet complexity requirements (min 10 chars, 1 uppercase, 1 number, 1 special char).
- 409: User with this email already exists.
- 422: Validation error (e.g., invalid email format).

---

## POST /api/v1/auth/login

Authenticate a user and return JWT tokens.

**Request:**
```json
{
  "email": "john.doe@example.com",
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
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:**
- 401: Invalid or expired refresh token.

---

## POST /api/v1/auth/logout

Invalidate the refresh token (add to blacklist).

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204):**
No Content.

**Errors:**
- 401: Invalid token.

---

## GET /api/v1/users/me

Retrieve the currently authenticated user's profile.

**Permissions:** Authenticated User (Any Role).

**Response (200):**
```json
{
  "id": "uuid-v4",
  "email": "john.doe@example.com",
  "full_name": "John Doe",
  "phone": "+15145550199",
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

Update the currently authenticated user's profile.

**Permissions:** Authenticated User (Any Role).

**Request:**
```json
{
  "full_name": "Johnathan Doe",
  "phone": "+15145550200"
}
```

**Response (200):**
```json
{
  "id": "uuid-v4",
  "email": "john.doe@example.com",
  "full_name": "Johnathan Doe",
  "phone": "+15145550200",
  "role": "broker",
  "is_active": true,
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 401: Not authenticated.
- 422: Validation error.
```

### 2. Module README
**File Path:** `docs/modules/authentication_user_management.md`

```markdown
# Authentication & User Management Module

## Overview
This module is responsible for identity and access management within the Canadian Mortgage Underwriting System. It handles user registration, secure authentication using JSON Web Tokens (JWT), and profile management. It ensures that all access is logged and that sensitive data (passwords) is handled according to security best practices (bcrypt hashing).

## Key Functions

### `AuthService`
- `register_user`: Validates password complexity and creates a new user record.
- `authenticate_user`: Verifies credentials and returns user data if valid.
- `create_tokens`: Generates access (30 min expiry) and refresh (7 days expiry) tokens.
- `refresh_access_token`: Validates a refresh token and issues a new access token.

### `UserService`
- `get_profile`: Fetches the current user's details from the database.
- `update_profile`: Updates allowed fields (full_name, phone) for the current user.

## Security & Compliance
- **Passwords**: Must be 10+ characters, containing uppercase, numbers, and special characters. Stored using bcrypt.
- **Tokens**: Access tokens are short-lived. Refresh tokens must be stored securely by the client.
- **PIPEDA**: PII (email, phone, name) is accessible only to the user and admins. Audit logs track profile changes.
```

### 3. Configuration Notes
**Update `.env.example`:**

```bash
# Authentication & User Management Configuration
# Secret key for encoding JWT tokens (generate via `openssl rand -hex 32`)
SECRET_KEY=change_me_to_a_random_string
# Algorithm for encoding
ALGORITHM=HS256
# Access token expiration time in minutes (30 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30
# Refresh token expiration time in days (7 days)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 4. Changelog Update
**Append to `CHANGELOG.md`:**

```markdown
## [2026-03-02]
### Added
- Authentication & User Management: New endpoints for user registration, login, logout, and token refresh.
- User Profile: Endpoints to retrieve and update user details.
- JWT Implementation: Secure access and refresh token flow with configurable expiry.
- Password Validation: Enforced complexity requirements (min 10 chars, uppercase, number, special char).

### Changed
- N/A

### Fixed
- N/A
```

### 5. Docstrings for Complex Logic
**To be added to `modules/authentication_user_management/services.py`:**

```python
async def register_user(self, user_data: UserCreate) -> User:
    """
    Register a new user with password complexity validation.
    
    Rules:
    - Min length 10 chars.
    - At least 1 uppercase.
    - At least 1 number.
    - At least 1 special character.
    
    Args:
        user_data: Pydantic schema containing email, password, role, etc.
        
    Returns:
        User: The created user object (without password).
        
    Raises:
        AppException: If password is weak or email already exists.
    """
    pass

async def authenticate_user(self, email: str, password: str) -> User:
    """
    Verify user credentials and return user entity if valid.
    
    Args:
        email: User's email address.
        password: Plain text password to verify against hash.
        
    Returns:
        User: The authenticated user object.
        
    Raises:
        AppException: If credentials are invalid or user is inactive.
    """
    pass
```