# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**File**: `docs/design/auth-user-management.md`

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Authentication**: Public

**Request Body Schema**:
```json
{
  "email": "string, required, email format",
  "password": "string, required, min 10 chars, uppercase, number, special char",
  "full_name": "string, required, max 100 chars",
  "phone": "string, optional, E.164 format (+1234567890)",
  "role": "enum, optional, default='client' [broker, client, admin, underwriter]"
}
```

**Response Schema (201 Created)**:
```json
{
  "user_id": "uuid",
  "email": "string",
  "full_name": "string",
  "phone": "string | null",
  "role": "string",
  "is_active": "boolean",
  "created_at": "iso8601 timestamp"
}
```

**Error Responses**:
- `422 AUTH_002`: Password fails complexity requirements or invalid email format
- `409 AUTH_004`: Email already registered
- `422 AUTH_002`: Invalid role value

---

### `POST /api/v1/auth/login`
**Authentication**: Public

**Request Body Schema**:
```json
{
  "email": "string, required",
  "password": "string, required"
}
```

**Response Schema (200 OK)**:
```json
{
  "access_token": "jwt_string",
  "refresh_token": "jwt_string",
  "token_type": "Bearer",
  "expires_in": 1800,
  "user": {
    "user_id": "uuid",
    "email": "string",
    "full_name": "string",
    "role": "string"
  }
}
```

**Error Responses**:
- `401 AUTH_005`: Invalid credentials
- `403 AUTH_006`: Account inactive or locked
- `429 AUTH_007`: Rate limit exceeded (after 5 failed attempts per IP/hour)

---

### `POST /api/v1/auth/refresh`
**Authentication**: Public (requires valid refresh token)

**Request Body Schema**:
```json
{
  "refresh_token": "string, required"
}
```

**Response Schema (200 OK)**:
```json
{
  "access_token": "jwt_string",
  "expires_in": 1800
}
```

**Error Responses**:
- `401 AUTH_008`: Refresh token expired or revoked
- `401 AUTH_009`: Refresh token invalid

---

### `POST /api/v1/auth/logout`
**Authentication**: Authenticated

**Request Body Schema**:
```json
{
  "refresh_token": "string, required"
}
```

**Response Schema (200 OK)**:
```json
{
  "detail": "Successfully logged out"
}
```

**Error Responses**:
- `401 AUTH_001`: Missing or invalid access token
- `404 AUTH_010`: Refresh token not found

---

### `GET /api/v1/users/me`
**Authentication**: Authenticated

**Request**: None (JWT from Authorization header)

**Response Schema (200 OK)**:
```json
{
  "user_id": "uuid",
  "email": "string",
  "full_name": "string",
  "phone": "string | null",
  "role": "string",
  "is_active": "boolean",
  "created_at": "iso8601 timestamp",
  "updated_at": "iso8601 timestamp"
}
```

**Error Responses**:
- `401 AUTH_001`: Invalid or expired access token
- `404 USER_001`: User not found (deleted account edge case)

---

### `PUT /api/v1/users/me`
**Authentication**: Authenticated

**Request Body Schema**:
```json
{
  "full_name": "string, optional, max 100 chars",
  "phone": "string, optional, E.164 format"
}
```

**Response Schema (200 OK)**:
```json
{
  "user_id": "uuid",
  "email": "string",
  "full_name": "string",
  "phone": "string | null",
  "role": "string",
  "is_active": "boolean",
  "created_at": "iso8601 timestamp",
  "updated_at": "iso8601 timestamp"
}
```

**Error Responses**:
- `422 USER_002`: Invalid phone format or full_name exceeds length
- `401 AUTH_001`: Invalid access token

---

## 2. Models & Database

### `users` Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,  -- bcrypt hash
    role VARCHAR(20) NOT NULL CHECK (role IN ('broker', 'client', 'admin', 'underwriter')),
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),  -- E.164 format
    is_active BOOLEAN DEFAULT true,
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE UNIQUE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_is_active ON users (is_active);
CREATE INDEX idx_users_created_at ON users (created_at);
```

**Encrypted Fields (PIPEDA Compliance)**:
- `email`: AES-256 encryption at rest (SQLAlchemy `EncryptedType`)
- `full_name`: AES-256 encryption at rest
- `phone`: AES-256 encryption at rest
- **Note**: Hashed password uses bcrypt (one-way hash, not encryption)

---

### `refresh_tokens` Table
```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,  -- SHA256 of token
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

-- Indexes for efficient lookup and cleanup
CREATE UNIQUE INDEX idx_refresh_tokens_hash ON refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens (expires_at) WHERE is_revoked = false;
CREATE INDEX idx_refresh_tokens_created_at ON refresh_tokens (created_at);
```

---

### `audit_logs` Table (FINTRAC Compliance)
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),  -- NULL for anonymous events
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('login', 'logout', 'register', 'password_change', 'account_lockout')),
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    details JSONB  -- Additional context (never include passwords)
);

-- Indexes for regulatory reporting queries
CREATE INDEX idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs (timestamp);
CREATE INDEX idx_audit_logs_event_type ON audit_logs (event_type);
CREATE INDEX idx_audit_logs_ip_address ON audit_logs (ip_address);
```

---

## 3. Business Logic

### Password Validation Algorithm
```python
import re

def validate_password(password: str) -> bool:
    """
    Rules:
    - Minimum 10 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character: !@#$%^&*()_+-=[]{}|;:,.<>?
    """
    if len(password) < 10:
        return False
    
    patterns = [
        r'[A-Z]',           # uppercase
        r'[a-z]',           # lowercase
        r'\d',              # digit
        r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]'  # special char
    ]
    
    return all(re.search(pattern, password) for pattern in patterns)
```

### JWT Token Generation
- **Access Token**: 
  - Expiry: 30 minutes (1800 seconds)
  - Payload: `sub` (user_id), `email`, `role`, `iat`, `exp`, `jti`
  - Algorithm: HS256 (or RS256 for better key rotation)
  
- **Refresh Token**:
  - Expiry: 7 days (604800 seconds)
  - Payload: `sub` (user_id), `token_type: refresh`, `iat`, `exp`, `jti`
  - Stored as SHA256 hash in database (never plaintext)

### Account Lockout Logic
- After 5 consecutive failed login attempts: lock account for 15 minutes
- Increment `failed_login_attempts` on each failure
- Reset counter on successful login
- Log all failed attempts to `audit_logs` (FINTRAC requirement)

### Role Permissions Matrix
```python
ROLE_PERMISSIONS = {
    "client": [
        "read:self",
        "update:self",
        "create:application",
        "read:application"  # only own
    ],
    "broker": [
        "read:self",
        "update:self",
        "create:application",
        "read:application",  # own and assigned
        "update:application",
        "read:client"  # own clients only
    ],
    "underwriter": [
        "read:self",
        "update:self",
        "read:application",  # all assigned
        "update:application",
        "read:appraisal",
        "create:decision"
    ],
    "admin": [
        "*"
    ]
}
```

---

## 4. Migrations

### Alembic Migration: `create_auth_tables`
```python
# migration script
def upgrade():
    # Create users table
    op.create_table('users', ...)
    
    # Create refresh_tokens table
    op.create_table('refresh_tokens', ...)
    
    # Create audit_logs table
    op.create_table('audit_logs', ...)
    
    # Create indexes
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_refresh_tokens_hash', 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index('idx_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    
    # Add updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Attach trigger to users table
    op.execute("""
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
```

---

## 5. Security & Compliance

### PIPEDA Requirements
- **Data Minimization**: Only collect email, full_name, phone required for underwriting workflow
- **Encryption at Rest**: All PII fields (`email`, `full_name`, `phone`) encrypted using AES-256 via SQLAlchemy `EncryptedType`
- **Secure Password Storage**: bcrypt with cost factor 12 (never reversible)
- **Data Retention**: User records retained for 5 years post-deactivation (soft delete only)
- **No PII in Logs**: All logging excludes `email`, `full_name`, `phone`; use `user_id` only

### FINTRAC Requirements
- **Immutable Audit Trail**: `audit_logs` table has no UPDATE/DELETE operations; append-only
- **Authentication Event Logging**: All login attempts (success/failure), logouts, registrations logged with IP and timestamp
- **5-Year Retention**: Audit logs retained for minimum 5 years; implement archival strategy to cold storage after 1 year
- **Access Logging**: All user actions that access financial data must be logged with correlation_id

### General Security Measures
- **Rate Limiting**: 5 requests/minute per IP on login/register; 100 requests/minute on authenticated endpoints
- **CORS**: Strict origin whitelist from `common/config.py`
- **JWT Security**: 
  - Use `python-jose[cryptography]` with RSA keys (RS256)
  - Key rotation every 90 days
  - Tokens stored in httpOnly, secure, SameSite=strict cookies + Authorization header
- **Password Reset**: Out of scope for v1; will use admin-initiated flow with secure token
- **Email Verification**: Out of scope for v1; flag `is_verified` added to model for future use

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `AuthenticationError` | 401 | AUTH_001 | "Invalid or missing authentication token" | JWT validation failure |
| `AuthValidationError` | 422 | AUTH_002 | "{field}: {reason}" | Password complexity fail |
| `EmailAlreadyExistsError` | 409 | AUTH_004 | "Email already registered" | Duplicate registration |
| `InvalidCredentialsError` | 401 | AUTH_005 | "Invalid email or password" | Login failure |
| `AccountInactiveError` | 403 | AUTH_006 | "Account is inactive or locked" | `is_active=false` or lockout |
| `RateLimitExceededError` | 429 | AUTH_007 | "Too many requests, try again later" | 5+ failed attempts |
| `RefreshTokenExpiredError` | 401 | AUTH_008 | "Refresh token expired" | Token past expiry |
| `RefreshTokenInvalidError` | 401 | AUTH_009 | "Refresh token invalid or revoked" | Token not found/revoked |
| `TokenNotFoundError` | 404 | AUTH_010 | "Refresh token not found" | Logout with bad token |
| `UserNotFoundError` | 404 | USER_001 | "User not found" | /users/me on deleted user |
| `UserValidationError` | 422 | USER_002 | "{field}: {reason}" | Invalid phone format |

### Error Response Format
```json
{
  "detail": "Error message here",
  "error_code": "AUTH_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "corr-12345-abcde"
}
```

---

## Future Considerations (Out of Scope)

1. **Email Verification Flow**: Add `is_verified` boolean to users table; send verification token via email
2. **Password Reset**: Implement `POST /auth/forgot-password` and `POST /auth/reset-password` with secure JWT tokens
3. **OAuth2 Integration**: Extend to support Google/Microsoft SSO for brokers/clients
4. **MFA**: TOTP-based multi-factor authentication for admin/underwriter roles
5. **Session Management**: Device tracking and remote logout capability

---

**Implementation Notes**:
- Use `asyncpg` with connection pooling via SQLAlchemy async engine
- Implement repository pattern in `services.py` for database operations
- All service methods must be async (`async def`)
- Use dependency injection for `get_current_user()` and `get_current_active_user()` in routes
- Add Prometheus metrics: `auth_login_attempts_total`, `auth_login_failures_total`, `auth_token_refreshes_total`