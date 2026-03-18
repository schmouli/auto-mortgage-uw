# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**Module Path:** `mortgage_underwriting/modules/auth/`

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Purpose:** Register a new user account with role-based access.

**Request Body (JSON):**
```json
{
  "email": "user@example.com",           // string, required, valid email format
  "password": "SecureP@ssw0rd",          // string, required, min 10 chars, 1 uppercase, 1 digit, 1 special
  "role": "client",                      // enum: broker|client|admin|underwriter, optional (default: client)
  "full_name": "John Doe",               // string, required, max 100 chars
  "phone": "+14165551234"                // string, required, E.164 format
}
```

**Response (201 Created):**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "client",
  "full_name": "John Doe",
  "phone": "+14165551234",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
| HTTP Status | error_code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 409 Conflict | AUTH_001 | "Email already registered" | Duplicate email address |
| 422 Unprocessable | AUTH_002 | "Password: must contain uppercase, digit, special character" | Weak password validation fails |
| 422 Unprocessable | AUTH_003 | "phone: invalid E.164 format" | Phone number format invalid |

**Access:** Public (no authentication required)

---

### `POST /api/v1/auth/login`
**Purpose:** Authenticate user and issue JWT tokens.

**Request Body (JSON):**
```json
{
  "email": "user@example.com",           // string, required
  "password": "SecureP@ssw0rd"           // string, required
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "v2.local.eyJzdWIiOiIxMjM0NTY3ODkwIn0...",
  "token_type": "Bearer",
  "expires_in": 1800                     // seconds (30 minutes)
}
```

**Error Responses:**
| HTTP Status | error_code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 Unauthorized | AUTH_004 | "Invalid credentials" | Email/password mismatch |
| 403 Forbidden | AUTH_005 | "Account deactivated" | is_active = false |
| 422 Unprocessable | AUTH_006 | "Invalid request format" | Missing required fields |

**Access:** Public

---

### `POST /api/v1/auth/refresh`
**Purpose:** Obtain a new access token using a valid refresh token.

**Request Body (JSON):**
```json
{
  "refresh_token": "v2.local.eyJzdWIiOiIxMjM0NTY3ODkwIn0..."  // string, required
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

**Error Responses:**
| HTTP Status | error_code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 Unauthorized | AUTH_007 | "Invalid or expired refresh token" | Token validation fails |
| 403 Forbidden | AUTH_008 | "Token revoked" | Refresh token marked as revoked |

**Access:** Public (token-based authentication)

---

### `POST /api/v1/auth/logout`
**Purpose:** Invalidate refresh token and log out user.

**Request Body (JSON):**
```json
{
  "refresh_token": "v2.local.eyJzdWIiOiIxMjM0NTY3ODkwIn0..."  // string, required
}
```

**Response (204 No Content)**

**Error Responses:**
| HTTP Status | error_code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 400 Bad Request | AUTH_009 | "Refresh token required" | Missing token in request |

**Access:** Authenticated (requires valid access token in header)

---

### `GET /api/v1/users/me`
**Purpose:** Retrieve current authenticated user's profile.

**Response (200 OK):**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "client",
  "full_name": "John Doe",
  "phone": "+14165551234",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Error Responses:**
| HTTP Status | error_code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 Unauthorized | AUTH_010 | "Authentication required" | Missing or invalid access token |

**Access:** Authenticated (any active role)

---

### `PUT /api/v1/users/me`
**Purpose:** Update current user's profile (full_name, phone only).

**Request Body (JSON):**
```json
{
  "full_name": "Johnathan Doe",          // string, optional, max 100 chars
  "phone": "+14165559876"                // string, optional, E.164 format
}
```

**Response (200 OK):** Same schema as GET /users/me

**Error Responses:**
| HTTP Status | error_code | Detail Message | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 Unauthorized | AUTH_010 | "Authentication required" | Missing or invalid access token |
| 422 Unprocessable | AUTH_011 | "phone: invalid E.164 format" | Phone validation fails |

**Access:** Authenticated (any active role)

---

## 2. Models & Database

### `User` ORM Model
**Table Name:** `users`

| Column Name | Type | Constraints | Index | Description |
|-------------|------|-------------|-------|-------------|
| `id` | `UUID` | PrimaryKey, default=uuid4 | Primary | Unique user identifier |
| `email` | `String(255)` | Unique, Not Null | `idx_users_email` | User email address (PII) |
| `hashed_password` | `String(255)` | Not Null | - | Bcrypt hash (never exposed) |
| `role` | `Enum('broker','client','admin','underwriter')` | Not Null, Default='client' | `idx_users_role` | Role-based access level |
| `full_name` | `String(100)` | Not Null | - | Full legal name (PII) |
| `phone` | `String(20)` | Not Null | - | E.164 formatted phone (PII) |
| `is_active` | `Boolean` | Not Null, Default=True | `idx_users_active` | Account status flag |
| `created_at` | `DateTime` | Not Null, default=utcnow | - | Audit timestamp |
| `updated_at` | `DateTime` | Not Null, default=utcnow, onupdate=utcnow | - | Audit timestamp |

**Relationships:**
- One-to-Many: `User.refresh_tokens` → `RefreshToken.user_id`

---

### `RefreshToken` ORM Model
**Table Name:** `refresh_tokens`

| Column Name | Type | Constraints | Index | Description |
|-------------|------|-------------|-------|-------------|
| `id` | `UUID` | PrimaryKey, default=uuid4 | Primary | Token record identifier |
| `user_id` | `UUID` | ForeignKey('users.id'), Not Null | `idx_refresh_tokens_user_id` | Parent user reference |
| `token_hash` | `String(64)` | Unique, Not Null | `idx_refresh_tokens_hash` | SHA256 hash of token |
| `expires_at` | `DateTime` | Not Null | `idx_refresh_tokens_expiry` | Token expiration timestamp |
| `is_revoked` | `Boolean` | Not Null, Default=False | `idx_refresh_tokens_revoked` | Revocation status flag |
| `created_at` | `DateTime` | Not Null, default=utcnow | - | Audit timestamp |

**Indexes for Cleanup:**
```sql
CREATE INDEX idx_refresh_tokens_expired ON refresh_tokens (expires_at) WHERE is_revoked = false;
```

---

## 3. Business Logic

### Password Validation Algorithm
```python
import re

def validate_password(password: str) -> bool:
    """
    Rules:
    - Minimum length: 10 characters
    - At least 1 uppercase letter [A-Z]
    - At least 1 digit [0-9]
    - At least 1 special character from set: !@#$%^&*()_+-=[]{}|;':",./<>?
    """
    if len(password) < 10:
        return False
    
    patterns = [
        r'[A-Z]',           # uppercase
        r'[0-9]',           # digit
        r'[!@#$%^&*()_+\-=\[\]{}|;\':\",./<>?]'  # special char
    ]
    
    return all(re.search(pattern, password) for pattern in patterns)
```

### JWT Token Generation
**Access Token Payload:**
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "client",
  "iat": 1705321800,
  "exp": 1705323600,  // +30 minutes
  "iss": "mortgage-underwriter",
  "type": "access"
}
```

**Refresh Token Payload:**
```json
{
  "sub": "user-uuid",
  "jti": "token-uuid",
  "iat": 1705321800,
  "exp": 1705926600,  // +7 days
  "iss": "mortgage-underwriter",
  "type": "refresh"
}
```

**Token Storage:** Refresh token plaintext stored client-side; only SHA256 hash stored in `refresh_tokens.token_hash` for lookup.

### Token Invalidation Flow
1. **Logout:** Set `is_revoked = true` on the specific refresh token
2. **Password Change:** Revoke ALL refresh tokens for user (`UPDATE refresh_tokens SET is_revoked = true WHERE user_id = ?`)
3. **Account Deactivation:** Same as password change
4. **Scheduled Cleanup:** Daily cron job deletes expired tokens older than 7 days

### Role Permissions Matrix (Initial)
| Role | Applications | Underwriting | Appraisal | Admin | Users |
|------|--------------|--------------|-----------|-------|-------|
| **client** | read:own, create | - | - | - | read:own, update:own |
| **broker** | read:own, create, update:own | - | - | - | read:own, update:own |
| **underwriter** | read:all, approve/reject | full access | read:all | - | read:own, update:own |
| **admin** | full access | full access | full access | full access | full access |

---

## 4. Migrations

### Alembic Revision: `create_auth_tables`
```python
# New Tables
- users
- refresh_tokens

# Indexes
- idx_users_email (unique)
- idx_users_role
- idx_users_active
- idx_refresh_tokens_user_id
- idx_refresh_tokens_hash (unique)
- idx_refresh_tokens_expiry
- idx_refresh_tokens_revoked

# No data migration required for initial creation
```

**Post-deployment:** Schedule PostgreSQL cleanup job:
```sql
-- Daily cleanup of expired revoked tokens
DELETE FROM refresh_tokens WHERE expires_at < NOW() - INTERVAL '7 days';
```

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Data Minimization:** Only collect email, full_name, phone required for underwriting workflow
- **PII Encryption:** 
  - `email`, `full_name`, `phone` encrypted at rest using PostgreSQL `pgcrypto` extension
  - AES-256-CBC encryption with key from `common/security.py`
- **No Logging:** Never log `email`, `full_name`, `phone`, `hashed_password`
- **Secure Deletion:** User data hard-deleted after 5-year retention period (admin-only endpoint, future scope)

### Authentication Security
- **Password Hashing:** Bcrypt with cost factor 12 (via `passlib`)
- **Token Security:** 
  - Access tokens: Signed JWT (HS256) with 30-min expiry
  - Refresh tokens: Encrypted JWT (JWE) with 7-day expiry
  - Token rotation on refresh recommended (future enhancement)
- **Rate Limiting:** 
  - `/auth/register`: 5 requests/hour per IP
  - `/auth/login`: 10 requests/minute per IP
  - `/auth/*`: 100 requests/minute per IP
- **CORS:** Strict origin whitelist from `common/config.py`

### FINTRAC Considerations
- **User Identity Logging:** When user performs transaction > CAD $10,000, log `user_id` (not email) for audit trail
- **5-Year Retention:** User records retained for 5 years post-deactivation (soft-delete not implemented; admin must archive)

### OSFI B-20 / CMHC
- **Not Applicable:** This module does not perform financial calculations or insurance logic.

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In modules/auth/exceptions.py
class AuthException(AppException):
    """Base exception for auth module"""
    module_code = "AUTH"

class EmailAlreadyExistsError(AuthException):
    http_status = 409
    error_code = "AUTH_001"
    message_template = "Email {email} already registered"

class WeakPasswordError(AuthException):
    http_status = 422
    error_code = "AUTH_002"
    message_template = "Password: {validation_error}"

class InvalidPhoneError(AuthException):
    http_status = 422
    error_code = "AUTH_003"
    message_template = "phone: {reason}"

class InvalidCredentialsError(AuthException):
    http_status = 401
    error_code = "AUTH_004"
    message_template = "Invalid credentials"

class InactiveAccountError(AuthException):
    http_status = 403
    error_code = "AUTH_005"
    message_template = "Account deactivated"

class TokenValidationError(AuthException):
    http_status = 401
    error_code = "AUTH_007"
    message_template = "Invalid or expired token"

class TokenRevokedError(AuthException):
    http_status = 403
    error_code = "AUTH_008"
    message_template = "Token revoked"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "Email user@example.com already registered",
  "error_code": "AUTH_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-1234567890"
}
```

### Edge Cases & Handling
| Scenario | HTTP Status | Error Code | Log Level | Notes |
|----------|-------------|------------|-----------|-------|
| Concurrent registration of same email | 409 | AUTH_001 | WARNING | DB unique constraint handles race condition |
| Token replay attack | 403 | AUTH_008 | CRITICAL | Log correlation_id for FINTRAC audit |
| Refresh token expired | 401 | AUTH_007 | INFO | User must re-login |
| User role escalation attempt | 403 | AUTH_012 | CRITICAL | Admin-only role change endpoint (future) |
| Missing Authorization header | 401 | AUTH_010 | INFO | Standard FastAPI exception handler |

---

## Future Considerations (Out of Current Scope)

1. **Email Verification:** Add `email_verified: Boolean` column and `/auth/verify-email` endpoint with token expiry
2. **Password Reset:** Implement `/auth/forgot-password` and `/auth/reset-password` with secure token flow
3. **OAuth2 Integration:** Support for Google/Microsoft SSO for broker/client roles
4. **MFA:** TOTP-based multi-factor authentication for admin/underwriter roles
5. **Role Management:** Admin endpoints for creating/updating users with role-based access
6. **PII Encryption at Rest:** Implement column-level encryption using SQLAlchemy hybrid properties

---

**Design Document Location:** `docs/design/auth-user-management.md`