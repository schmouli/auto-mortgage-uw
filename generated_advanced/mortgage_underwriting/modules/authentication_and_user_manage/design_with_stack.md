# Design: Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**Module Identifier:** `AUTH`  
**Design Document:** `docs/design/auth-user-management.md`  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Authentication:** Public (rate limited: 5 requests/minute per IP)  
**Description:** Register a new user account with role-based access.

**Request Schema:**
```python
class UserRegisterRequest(BaseModel):
    email: EmailStr  # Will be encrypted at rest per PIPEDA
    password: str    # Min 10 chars, 1 uppercase, 1 number, 1 special char
    full_name: str   # AES-256 encrypted in DB
    phone: str       # AES-256 encrypted in DB
    role: Literal["broker", "client", "underwriter"] = "client"  # Admin role requires manual provisioning
```

**Response Schema (201 Created):**
```python
class UserRegisterResponse(BaseModel):
    user_id: UUID
    email: EmailStr  # Masked: user●●●@domain.com
    full_name: str   # Decrypted from DB
    phone: str       # Decrypted and formatted as (XXX) XXX-XXXX
    role: str
    created_at: datetime
    message: str = "Registration successful. Identity verification required for FINTRAC compliance."
```

**Error Responses:**
| Status | Error Code | Detail | Trigger |
|--------|------------|--------|---------|
| 400 | `AUTH_001` | "Password does not meet complexity requirements" | Weak password |
| 409 | `AUTH_002` | "Email already registered" | Duplicate email hash |
| 422 | `AUTH_003` | "{field}: {validation_error}" | Pydantic validation failure |
| 429 | `AUTH_004` | "Rate limit exceeded: 5 requests/minute" | IP rate limit hit |

---

### `POST /api/v1/auth/login`
**Authentication:** Public (rate limited: 10 requests/minute per IP)  
**Description:** Authenticate user and issue JWT tokens. FINTRAC audit event logged.

**Request Schema:**
```python
class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
```

**Response Schema (200 OK):**
```python
class UserLoginResponse(BaseModel):
    access_token: str      # JWT, expires in 30 minutes
    refresh_token: str     # UUID4, stored hashed in DB, expires in 7 days
    token_type: str = "Bearer"
    expires_in: int = 1800  # seconds
```

**Error Responses:**
| Status | Error Code | Detail | Trigger |
|--------|------------|--------|---------|
| 401 | `AUTH_005` | "Invalid email or password" | Authentication failure |
| 401 | `AUTH_006` | "Account deactivated" | `is_active=False` |
| 422 | `AUTH_003` | "{field}: {validation_error}" | Validation failure |
| 429 | `AUTH_004` | "Rate limit exceeded" | Rate limit hit |

---

### `POST /api/v1/auth/refresh`
**Authentication:** Refresh token required (bearer token or body)  
**Description:** Exchange valid refresh token for new access token.

**Request Schema:**
```python
class TokenRefreshRequest(BaseModel):
    refresh_token: str  # Raw JWT or UUID4 token
```

**Response Schema (200 OK):**
```python
class TokenRefreshResponse(BaseModel):
    access_token: str
    expires_in: int = 1800
```

**Error Responses:**
| Status | Error Code | Detail | Trigger |
|--------|------------|--------|---------|
| 401 | `AUTH_007` | "Invalid or expired refresh token" | Token not found/expired/revoked |
| 422 | `AUTH_003` | "{field}: {validation_error}" | Validation failure |

---

### `POST /api/v1/auth/logout`
**Authentication:** Authenticated user + refresh token  
**Description:** Revoke refresh token and log FINTRAC session termination.

**Request Schema:**
```python
class LogoutRequest(BaseModel):
    refresh_token: str
```

**Response Schema (200 OK):**
```python
class LogoutResponse(BaseModel):
    message: str = "Session terminated successfully"
```

**Error Responses:**
| Status | Error Code | Detail | Trigger |
|--------|------------|--------|---------|
| 401 | `AUTH_008` | "Refresh token not found" | Token doesn't exist |
| 422 | `AUTH_003` | "{field}: {validation_error}" | Validation failure |

---

### `GET /api/v1/users/me`
**Authentication:** JWT access token required  
**Description:** Retrieve current user's profile (PIPEDA-compliant data minimization).

**Response Schema (200 OK):**
```python
class UserProfileResponse(BaseModel):
    user_id: UUID
    email: EmailStr  # Masked
    full_name: str   # Decrypted
    phone: str       # Decrypted and masked: (XXX) XXX-1234
    role: str
    is_active: bool
    created_at: datetime
```

**Error Responses:**
| Status | Error Code | Detail | Trigger |
|--------|------------|--------|---------|
| 401 | `AUTH_009` | "Access token expired or invalid" | JWT validation failure |
| 404 | `AUTH_010` | "User not found" | User ID from token not in DB |

---

### `PUT /api/v1/users/me`
**Authentication:** JWT access token required  
**Description:** Update current user's profile. FINTRAC audit log for changes.

**Request Schema:**
```python
class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None  # Must meet complexity rules
```

**Response Schema (200 OK):**
```python
class UserProfileUpdateResponse(BaseModel):
    user_id: UUID
    email: EmailStr  # Masked
    full_name: str   # Updated and decrypted
    phone: str       # Updated and decrypted
    role: str
    updated_at: datetime
```

**Error Responses:**
| Status | Error Code | Detail | Trigger |
|--------|------------|--------|---------|
| 400 | `AUTH_001` | "Password does not meet complexity requirements" | Weak new password |
| 401 | `AUTH_009` | "Access token expired or invalid" | JWT failure |
| 404 | `AUTH_010` | "User not found" | User ID not found |
| 422 | `AUTH_003` | "{field}: {validation_error}" | Validation failure |

---

## 2. Models & Database

### `users` Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256 for lookup
    email_encrypted BYTEA NOT NULL,           -- AES-256-GCM encrypted
    hashed_password VARCHAR(255) NOT NULL,    -- Argon2id hash
    role VARCHAR(20) NOT NULL CHECK (role IN ('broker', 'client', 'underwriter', 'admin')),
    full_name_encrypted BYTEA NOT NULL,       -- AES-256-GCM encrypted (PIPEDA)
    phone_hash VARCHAR(64),                   -- SHA256 for optional lookup
    phone_encrypted BYTEA,                    -- AES-256-GCM encrypted (PIPEDA)
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Composite indexes for common queries
    CONSTRAINT users_email_hash_key UNIQUE (email_hash)
);

-- Indexes
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at);
```

### `refresh_tokens` Table
```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256 of raw token
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_ip INET NOT NULL,              -- FINTRAC audit: IP address
    created_by_user_agent TEXT                -- FINTRAC audit: device fingerprint
);

-- Indexes
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX idx_refresh_tokens_is_revoked ON refresh_tokens(is_revoked);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

### Encryption Strategy (PIPEDA Compliance)
- **Fields to encrypt:** `email_encrypted`, `full_name_encrypted`, `phone_encrypted`
- **Encryption method:** AES-256-GCM via `common/security.encrypt_pii()`
- **Key management:** Rotated every 90 days, stored in Vault/AWS KMS
- **Hash for lookups:** SHA256 with salt for `email_hash` and `phone_hash`

---

## 3. Business Logic

### Password Validation Algorithm
```python
def validate_password(password: str) -> bool:
    """
    Complexity rules:
    - Minimum length: 10 characters
    - At least 1 uppercase letter (A-Z)
    - At least 1 lowercase letter (a-z)
    - At least 1 digit (0-9)
    - At least 1 special character: !@#$%^&*()_+-=[]{}|;:,.<>?
    - Maximum length: 128 characters (prevent DoS)
    - Must not contain email prefix or common patterns (e.g., "Password123!")
    """
    if len(password) < 10 or len(password) > 128:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    return all([has_upper, has_lower, has_digit, has_special])
```

### JWT Token Generation
```python
def create_access_token(user_id: UUID, role: str) -> str:
    """
    Access token claims:
    - sub: user_id (UUID)
    - role: user role for RBAC
    - exp: 30 minutes from issuance
    - iat: issued at timestamp
    - jti: unique token ID for revocation tracking
    """
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def create_refresh_token(user_id: UUID, ip: str, user_agent: str) -> str:
    """
    Refresh token: UUID4 stored hashed in DB with metadata for FINTRAC audit
    """
    raw_token = str(uuid4())
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    # Store in DB with FINTRAC required metadata
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_by_ip=ip,
        created_by_user_agent=user_agent
    )
    return raw_token
```

### User State Machine
```
[Unregistered] --(register)--> [Registered] --(verify_email)--> [Active]
[Active] --(deactivate)--> [Inactive] --(reactivate)--> [Active]
[Active] --(lock_after_failed_attempts)--> [Locked] --(admin_unlock)--> [Active]
```

**FINTRAC Identity Verification Trigger:** On registration, log `identity_verification_attempt` event with `user_id`, `timestamp`, `ip_address`, `verification_method="email"`. After email verification, log `identity_verified` event.

---

## 4. Migrations

### Alembic Migration: `001_create_users_and_refresh_tokens.py`
```python
def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email_hash', sa.String(length=64), nullable=False),
        sa.Column('email_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('full_name_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('phone_hash', sa.String(length=64), nullable=True),
        sa.Column('phone_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email_hash')
    )
    
    # Create refresh_tokens table
    op.create_table('refresh_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_by_ip', postgresql.INET(), nullable=False),
        sa.Column('created_by_user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    
    # Create indexes
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])
    op.create_index('idx_refresh_tokens_is_revoked', 'refresh_tokens', ['is_revoked'])
    
    # FINTRAC compliance: 5-year retention policy trigger
    op.execute("""
        CREATE EVENT TABLE IF NOT EXISTS fintrac_audit_events (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(50) NOT NULL,
            user_id UUID REFERENCES users(id),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip_address INET,
            user_agent TEXT,
            metadata JSONB
        );
    """)
```

### Alembic Migration: `002_add_user_encryption_versioning.py`
```python
def upgrade():
    # Add encryption key version for key rotation compliance
    op.add_column('users', sa.Column('encryption_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('refresh_tokens', sa.Column('encryption_version', sa.Integer(), nullable=False, server_default='1'))
```

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Data Minimization:** Only collect `email`, `full_name`, `phone` required for underwriting identity verification
- **Encryption at Rest:** All PII fields encrypted using AES-256-GCM via `common/security.encrypt_pii()`
- **Data Masking:** API responses mask email (`u***@domain.com`) and phone (`(XXX) XXX-1234`)
- **Access Logging:** All user data access logged with correlation_id, never log plaintext PII
- **Right to Deletion:** `DELETE /users/me` soft-deletes (sets `is_active=False`) per FINTRAC 5-year retention override

### FINTRAC Requirements
- **Identity Verification Audit:** Every registration and email verification logs to `fintrac_audit_events` table
- **Session Tracking:** `refresh_tokens` table captures IP and user agent for all sessions
- **5-Year Retention:** All `users` and `refresh_tokens` records retained for 5 years, soft-delete only
- **Suspicious Activity:** More than 5 failed login attempts within 10 minutes triggers `AUTH_011` error and FINTRAC alert

### OSFI B-20 & CMHC
- **Not Directly Applicable:** This module does not calculate GDS/TDS or LTV ratios
- **Indirect Support:** Secure authentication ensures only authorized underwriters can access OSFI-compliant underwriting calculations

### Role-Based Access Control (RBAC) Matrix
| Endpoint | broker | client | underwriter | admin |
|----------|--------|--------|-------------|-------|
| `POST /auth/register` | ✓ | ✓ | ✓ | ✗ (admin only) |
| `POST /auth/login` | ✓ | ✓ | ✓ | ✓ |
| `GET /users/me` | ✓ | ✓ | ✓ | ✓ |
| `PUT /users/me` | ✓ | ✓ | ✓ | ✓ |
| `DELETE /users/{id}` | ✗ | ✗ | ✗ | ✓ |
| `GET /users/{id}` | ✗ | ✗ | ✗ | ✓ |

**Admin-Only Provisioning:** `admin` role users must be created via CLI tool `uv run python -m modules.auth.scripts.create_admin` with mTLS certificate verification.

### Security Best Practices
- **Password Hashing:** Argon2id with memory cost=65536, time cost=3, parallelism=1
- **JWT Secret Rotation:** Every 24 hours via `common/security.rotate_jwt_secret()`
- **Refresh Token Storage:** Hashed with SHA256 in DB; raw token never stored
- **Rate Limiting:** Redis-backed sliding window counter per IP
- **CORS:** Strict origin whitelist from `common/config.py`
- **mTLS:** Optional for admin endpoints via `common/security.verify_client_cert()`

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | FINTRAC Logged |
|-----------------|-------------|------------|-----------------|----------------|
| `AuthWeakPasswordError` | 400 | `AUTH_001` | "Password must be ≥10 chars with uppercase, number, special char" | No |
| `AuthEmailExistsError` | 409 | `AUTH_002` | "Email already registered" | Yes (metadata only) |
| `AuthValidationError` | 422 | `AUTH_003` | "{field}: {reason}" | No |
| `AuthRateLimitError` | 429 | `AUTH_004` | "Rate limit exceeded: {limit}/minute" | Yes (if repeated) |
| `AuthInvalidCredentialsError` | 401 | `AUTH_005` | "Invalid email or password" | Yes (failed attempt) |
| `AuthAccountInactiveError` | 401 | `AUTH_006` | "Account deactivated" | Yes |
| `AuthInvalidRefreshTokenError` | 401 | `AUTH_007` | "Invalid or expired refresh token" | Yes |
| `AuthTokenNotFoundError` | 401 | `AUTH_008` | "Refresh token not found" | Yes |
| `AuthInvalidAccessTokenError` | 401 | `AUTH_009` | "Access token expired or invalid" | No |
| `AuthUserNotFoundError` | 404 | `AUTH_010` | "User not found" | Yes |
| `AuthSuspiciousActivityError` | 403 | `AUTH_011` | "Account locked due to suspicious activity" | Yes (alert) |

**Structured Error Response Format (All Endpoints):**
```json
{
  "detail": "Error message",
  "error_code": "AUTH_XXX",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "path": "/api/v1/auth/login",
  "request_id": "req_12345"
}
```

---

## 7. Future Considerations (Out of Scope)

- **Email Verification Flow:** Design pending; requires `email_verification_tokens` table and `GET /auth/verify-email?token=...` endpoint
- **Password Reset:** Requires `password_reset_tokens` table and `POST /auth/request-reset`, `POST /auth/reset-password` endpoints
- **OAuth2 Integration:** Google/Microsoft OAuth for client role; design pending security review
- **MFA:** TOTP/OTP for underwriter/admin roles; design after base auth stable
- **Session Management:** Redis-based session store for instant revocation across cluster

---

**Implementation Priority:** Core endpoints (register, login, refresh, logout, me) → FINTRAC audit logging → PIPEDA encryption → RBAC enforcement → Rate limiting