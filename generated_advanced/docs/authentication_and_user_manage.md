# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**Module ID:** AUTH  
**Design Document:** `docs/design/authentication-user-management.md`  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Authentication:** Public  
**Rate Limit:** 5 requests/minute/IP  

**Request Body Schema:**
```json
{
  "email": "user@example.com",           // string, email format, required
  "password": "Str0ng!Passw0rd",         // string, min 10 chars, required
  "full_name": "John Doe",               // string, max 255 chars, required
  "phone": "+14165551234",               // string, E.164 format, required
  "role": "broker"                       // enum: broker, client, admin, underwriter, required
}
```

**Response Schema (201 Created):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone": "+14165551234",
  "role": "broker",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 422 | `AUTH_002` | "Password must contain uppercase, number, and special character" |
| 422 | `AUTH_002` | "Email format invalid" |
| 409 | `AUTH_003` | "User with this email already exists" |
| 400 | `AUTH_002` | "Invalid role specified" |

---

### `POST /api/v1/auth/login`
**Authentication:** Public  
**Rate Limit:** 10 requests/minute/IP  

**Request Body Schema:**
```json
{
  "email": "user@example.com",           // string, required
  "password": "Str0ng!Passw0rd"          // string, required
}
```

**Response Schema (200 OK):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "v2.local.eyJzdWI...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "broker"
  }
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | `AUTH_004` | "Invalid email or password" |
| 403 | `AUTH_005` | "Account is deactivated" |
| 422 | `AUTH_002` | "Email format invalid" |

---

### `POST /api/v1/auth/refresh`
**Authentication:** Public (valid refresh token required)  
**Rate Limit:** 30 requests/hour/IP  

**Request Body Schema:**
```json
{
  "refresh_token": "v2.local.eyJzdWI..."  // string, required
}
```

**Response Schema (200 OK):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "v2.local.eyJzdWI...",  // Rotated token
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | `AUTH_006` | "Refresh token expired or revoked" |
| 401 | `AUTH_007` | "Invalid refresh token signature" |
| 422 | `AUTH_002` | "Refresh token required" |

---

### `POST /api/v1/auth/logout`
**Authentication:** Authenticated (access token required)  
**Rate Limit:** 20 requests/minute/user  

**Request Body Schema:**
```json
{
  "refresh_token": "v2.local.eyJzdWI..."  // string, required
}
```

**Response Schema (200 OK):**
```json
{
  "detail": "Successfully logged out"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | `AUTH_008` | "Invalid or expired access token" |
| 422 | `AUTH_002` | "Refresh token required" |

---

### `GET /api/v1/users/me`
**Authentication:** Authenticated  

**Response Schema (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone": "+14165551234",
  "role": "broker",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | `AUTH_008` | "Invalid or expired access token" |
| 404 | `AUTH_001` | "User not found" |

---

### `PUT /api/v1/users/me`
**Authentication:** Authenticated  

**Request Body Schema:**
```json
{
  "full_name": "John Smith",             // string, optional
  "phone": "+14165559876"                // string, E.164 format, optional
}
```

**Response Schema (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Smith",
  "phone": "+14165559876",
  "role": "broker",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | `AUTH_008` | "Invalid or expired access token" |
| 422 | `AUTH_002` | "Phone number format invalid" |
| 404 | `AUTH_001` | "User not found" |

---

## 2. Models & Database

### `users` Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_encrypted BYTEA NOT NULL,  -- AES-256 encrypted email for PIPEDA
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('broker', 'client', 'admin', 'underwriter')),
    full_name VARCHAR(255) NOT NULL,
    full_name_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    phone VARCHAR(20),
    phone_encrypted BYTEA,  -- AES-256 encrypted
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),  -- FINTRAC audit trail
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for common query patterns
CREATE INDEX idx_users_email_active ON users (email, is_active);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_is_active ON users (is_active);
CREATE INDEX idx_users_created_at ON users (created_at);
```

### `refresh_tokens` Table
```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,  -- SHA-256 hash of token for storage
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,  -- FINTRAC: track source of auth events
    user_agent TEXT
);

-- Performance indexes
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens (expires_at);
CREATE INDEX idx_refresh_tokens_active ON refresh_tokens (user_id, is_revoked, expires_at) 
    WHERE is_revoked = false;
```

### `audit_logs` Table (Common Module)
```sql
-- Located in common module but referenced for FINTRAC compliance
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,  -- CREATE, UPDATE, DELETE, LOGIN, LOGOUT
    user_id UUID,  -- Who performed the action
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,
    changes JSONB,
    correlation_id VARCHAR(100)
);
CREATE INDEX idx_audit_logs_table_record ON audit_logs (table_name, record_id);
CREATE INDEX idx_audit_logs_user_timestamp ON audit_logs (user_id, timestamp);
```

---

## 3. Business Logic

### Password Validation Algorithm
```python
def validate_password(password: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message)
    Rules: min 10 chars, 1 uppercase, 1 number, 1 special char
    """
    if len(password) < 10:
        return False, "Password must be at least 10 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain number"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain special character"
    return True, ""
```

### Token Generation & Rotation
```python
# Access Token: JWT (HS256), 30 min expiry
access_payload = {
    "sub": str(user.id),
    "email": user.email,
    "role": user.role,
    "exp": datetime.utcnow() + timedelta(minutes=30),
    "iat": datetime.utcnow(),
    "type": "access"
}

# Refresh Token: PASETO v2.local (symmetric encryption), 7 days expiry
refresh_payload = {
    "sub": str(user.id),
    "jti": str(uuid.uuid4()),
    "exp": datetime.utcnow() + timedelta(days=7),
    "iat": datetime.utcnow(),
    "type": "refresh"
}

# On refresh: revoke old token, create new token pair
```

### User State Machine
```
[INACTIVE] ←→ [ACTIVE]
    ↑              |
    |              v
    └──────── [LOCKED] (after 5 failed login attempts)
```

**Transitions:**
- Registration → ACTIVE (is_active=true)
- Admin deactivation → INACTIVE
- Failed login counter ≥ 5 → LOCKED (requires admin unlock)

### FINTRAC Audit Logging
Every authentication event must be logged with:
- `user_id` (if available)
- `ip_address`
- `timestamp`
- `action`: `LOGIN`, `LOGOUT`, `REGISTER`, `REFRESH`
- `correlation_id` (from request headers)
- Retention: 5 years (enforced at database level via partition retention policy)

---

## 4. Migrations

### Alembic Revision: `001_create_users_table`
```python
def upgrade():
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('email_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('full_name_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('phone_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('idx_users_email_active', 'users', ['email', 'is_active'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
```

### Alembic Revision: `002_create_refresh_tokens_table`
```python
def upgrade():
    op.create_table('refresh_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])
    op.create_index('idx_refresh_tokens_expires', 'refresh_tokens', ['expires_at'])
    op.create_index('idx_refresh_tokens_active', 'refresh_tokens', 
                    ['user_id', 'is_revoked', 'expires_at'],
                    postgresql_where=sa.text('is_revoked = false'))
```

### Data Migration: Encrypt Existing PII
```python
# For initial seeding only - run once in production
def encrypt_existing_users():
    for user in session.execute(select(User)):
        user.email_encrypted = encrypt_aes256(user.email)
        user.full_name_encrypted = encrypt_aes256(user.full_name)
        user.phone_encrypted = encrypt_aes256(user.phone) if user.phone else None
```

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** All PII fields (`email`, `full_name`, `phone`) encrypted using AES-256-GCM via SQLAlchemy `TypeDecorator`
- **Data Minimization:** Only collect fields required for underwriting identity verification
- **No Logging:** PII never appears in logs; log only `user_id` and `correlation_id`
- **Key Management:** Encryption keys stored in HashiCorp Vault, rotated every 90 days

### FINTRAC Requirements
- **Immutable Audit Trail:** All auth events logged to `audit_logs` table with `created_at` timestamp
- **5-Year Retention:** PostgreSQL partition table `audit_logs_yyyy_mm` with automatic retention policy
- **Transaction Threshold:** Login events from IP addresses with >$10,000 in pending applications flagged for review
- **Identity Verification Logging:** `REGISTER` events include `ip_address` and `user_agent`

### OSFI B-20 Implications
- **Audit Logging:** All authentication events must include `correlation_id` for end-to-end traceability of mortgage calculations
- **Stress Test Access:** Only `underwriter` and `admin` roles can modify stress test parameters
- **Non-Repudiation:** JWT tokens include `iat` claim; refresh token rotation prevents token replay

### Role Permissions Matrix (RBAC)
| Endpoint | broker | client | underwriter | admin |
|----------|--------|--------|-------------|-------|
| `POST /auth/register` | ✓ | ✓ | ✓ | ✓ |
| `POST /auth/login` | ✓ | ✓ | ✓ | ✓ |
| `GET /users/me` | ✓ | ✓ | ✓ | ✓ |
| `PUT /users/me` | ✓ | ✓ | ✓ | ✓ |
| `POST /auth/logout` | ✓ | ✓ | ✓ | ✓ |
| **Other Modules** | | | | |
| Create Application | ✓ | ✗ | ✗ | ✓ |
| View Own Application | ✓ | ✓ | ✓ | ✓ |
| Approve Mortgage | ✗ | ✗ | ✓ | ✓ |
| Modify System Config | ✗ | ✗ | ✗ | ✓ |

### Security Controls
- **Password Hashing:** bcrypt with cost factor 12
- **JWT Secret:** 256-bit key from environment, rotated every 30 days
- **Rate Limiting:** Redis-backed sliding window counter per IP/user
- **CORS:** Strict origin whitelist from `config.ALLOWED_ORIGINS`
- **mTLS:** Optional for inter-service auth (future enhancement)

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In modules/auth/exceptions.py
class AuthException(AppException):
    """Base exception for auth module"""
    module_code = "AUTH"

class UserNotFoundError(AuthException):
    http_status = 404
    error_code = "AUTH_001"
    message_template = "User {identifier} not found"

class AuthValidationError(AuthException):
    http_status = 422
    error_code = "AUTH_002"
    message_template = "{field}: {reason}"

class AuthBusinessRuleError(AuthException):
    http_status = 409
    error_code = "AUTH_003"
    message_template = "Business rule violated: {rule}"

class AuthCredentialError(AuthException):
    http_status = 401
    error_code = "AUTH_004"
    message_template = "Invalid credentials provided"

class AccountInactiveError(AuthException):
    http_status = 403
    error_code = "AUTH_005"
    message_template = "Account is deactivated or locked"

class RefreshTokenError(AuthException):
    http_status = 401
    error_code = "AUTH_006"
    message_template = "Refresh token expired or revoked"

class InvalidTokenSignatureError(AuthException):
    http_status = 401
    error_code = "AUTH_007"
    message_template = "Token signature validation failed"

class UnauthorizedAccessError(AuthException):
    http_status = 401
    error_code = "AUTH_008"
    message_template = "Invalid or expired access token"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "User user@example.com not found",
  "error_code": "AUTH_001",
  "module": "authentication",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-12345"
}
```

### Edge Cases & Error Handling
- **Duplicate Registration:** Return 409 on email conflict; do not reveal if email exists
- **Account Lockout:** After 5 failed attempts, set `is_active=false`; require admin unlock
- **Token Replay Attack:** Refresh token rotation ensures one-time use; revoked tokens stored indefinitely
- **Concurrent Logins:** Multiple valid refresh tokens allowed per user; logout revokes only specified token
- **PII Update:** `PUT /users/me` triggers re-encryption of changed fields; logs old values to `audit_logs` for 5-year retention

---

## Future Enhancements (Out of Scope)
- Email verification workflow with OTP
- Password reset via secure token (valid 15 min)
- OAuth2 integration with Equifax identity verification
- MFA (TOTP/SMS) for underwriter/admin roles
- Session management UI for admin to revoke active tokens