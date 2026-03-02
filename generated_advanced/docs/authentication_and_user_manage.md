# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**Feature Slug:** `auth-user-management`  
**Module Path:** `modules/auth/`

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Authentication:** Public (rate-limited: 10 requests/minute per IP)

**Request Body Schema:**
```python
class RegisterRequest(BaseModel):
    email: EmailStr  # Validated email format
    password: str  # Min 10 chars, 1 uppercase, 1 number, 1 special char
    role: Literal["broker", "client", "admin", "underwriter"]
    full_name: str  # Min 2 chars, max 100 chars
    phone: str | None = None  # E.164 format validation
```

**Response Schema (201 Created):**
```python
class RegisterResponse(BaseModel):
    id: UUID
    email: str  # Encrypted in DB, decrypted for response
    role: str
    full_name: str  # Encrypted in DB, decrypted for response
    phone: str | None  # Encrypted in DB, decrypted for response
    is_active: bool
    created_at: datetime
```

**Error Responses:**
- `409 Conflict` → `AUTH_001`: "User with email {email} already exists"
- `422 Unprocessable Entity` → `AUTH_006`: "Password does not meet requirements: {detail}"
- `422 Unprocessable Entity` → `AUTH_007`: "Invalid role specified"
- `422 Unprocessable Entity` → `AUTH_008`: "Invalid phone format (E.164 required)"

---

### `POST /api/v1/auth/login`
**Authentication:** Public (rate-limited: 5 requests/minute per IP)

**Request Body Schema:**
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

**Response Schema (200 OK):**
```python
class LoginResponse(BaseModel):
    access_token: str  # JWT, 30 min expiry
    refresh_token: str  # JWT, 7 days expiry
    token_type: str = "bearer"
    expires_in: int = 1800  # seconds
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_002`: "Invalid email or password" (generic message for security)
- `403 Forbidden` → `AUTH_009`: "Account is inactive or locked"
- `429 Too Many Requests` → `AUTH_010`: "Too many login attempts, account locked for 15 minutes"

---

### `POST /api/v1/auth/refresh`
**Authentication:** Public (requires valid refresh token)

**Request Body Schema:**
```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

**Response Schema (200 OK):**
```python
class RefreshResponse(BaseModel):
    access_token: str  # New JWT
    refresh_token: str  # Rotated refresh token
    token_type: str = "bearer"
    expires_in: int = 1800
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_004`: "Invalid or expired token"
- `401 Unauthorized` → `AUTH_005`: "Token has expired"
- `401 Unauthorized` → `AUTH_011`: "Token has been revoked"

---

### `POST /api/v1/auth/logout`
**Authentication:** Authenticated (requires valid access token)

**Request Body Schema:**
```python
class LogoutRequest(BaseModel):
    refresh_token: str  # Required for revocation
```

**Response Schema (200 OK):**
```python
class LogoutResponse(BaseModel):
    message: str = "Successfully logged out"
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_004`: "Invalid or expired token"
- `401 Unauthorized` → `AUTH_011`: "Token has been revoked"

---

### `GET /api/v1/users/me`
**Authentication:** Authenticated (any active role)

**Request:** None (JWT in Authorization header)

**Response Schema (200 OK):**
```python
class UserProfileResponse(BaseModel):
    id: UUID
    email: str
    role: str
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_004`: "Invalid or expired token"
- `404 Not Found` → `AUTH_003`: "User not found"

---

### `PUT /api/v1/users/me`
**Authentication:** Authenticated (any active role)

**Request Body Schema:**
```python
class UpdateProfileRequest(BaseModel):
    full_name: str | None = None  # Min 2 chars if provided
    phone: str | None = None  # E.164 format if provided
```

**Response Schema (200 OK):**
```python
class UpdateProfileResponse(BaseModel):
    id: UUID
    email: str
    role: str
    full_name: str
    phone: str | None
    is_active: bool
    updated_at: datetime
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_004`: "Invalid or expired token"
- `404 Not Found` → `AUTH_003`: "User not found"
- `422 Unprocessable Entity` → `AUTH_012`: "Invalid field format: {field}"

---

## 2. Models & Database

### `users` Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,  -- AES-256 encrypted, base64 encoded
    hashed_password TEXT NOT NULL,  -- Argon2id hash
    role VARCHAR(20) NOT NULL CHECK (role IN ('broker', 'client', 'admin', 'underwriter')),
    full_name TEXT,  -- AES-256 encrypted, base64 encoded
    phone TEXT,  -- AES-256 encrypted, base64 encoded (E.164 format)
    is_active BOOLEAN NOT NULL DEFAULT true,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    account_locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active) WHERE is_active = true;
CREATE INDEX idx_users_created_at ON users(created_at DESC);
```

### `refresh_tokens` Table
```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,  -- SHA256 hash of token for lookup
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT refresh_tokens_token_hash_unique UNIQUE (token_hash)
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX idx_refresh_tokens_is_revoked ON refresh_tokens(is_revoked) WHERE is_revoked = false;
```

**Encryption Configuration:**
- **PIPEDA Compliance:** `email`, `full_name`, `phone` encrypted at rest using AES-256-GCM
- Encryption key managed via `common/config.py` from environment variable `PIPEDA_ENCRYPTION_KEY`
- Fernet (symmetric encryption) from `cryptography.fernet` for implementation
- Decryption only in service layer, never in logs or error messages

---

## 3. Business Logic

### Password Validation Algorithm
```python
def validate_password(password: str) -> None:
    """
    Rules:
    - Minimum length: 10 characters
    - At least 1 uppercase letter: [A-Z]
    - At least 1 digit: [0-9]
    - At least 1 special character: [!@#$%^&*()_+{}|:"<>?`~[\];',./]
    """
    if len(password) < 10:
        raise PasswordValidationError("Password must be at least 10 characters")
    
    if not re.search(r"[A-Z]", password):
        raise PasswordValidationError("Password must contain uppercase letter")
    
    if not re.search(r"\d", password):
        raise PasswordValidationError("Password must contain number")
    
    if not re.search(r'[!@#$%^&*()_+{}|:"<>?`~\[\];\',./]', password):
        raise PasswordValidationError("Password must contain special character")
    
    # Additional entropy check (optional but recommended)
    if len(set(password)) < 6:
        raise PasswordValidationError("Password must contain more unique characters")
```

### JWT Token Generation
```python
def create_access_token(user_id: UUID, email: str, role: str) -> str:
    """
    Claims:
    - sub: user_id (UUID)
    - email: user email (hashed in logs)
    - role: user role
    - iat: issued at timestamp
    - exp: expiry (30 minutes from iat)
    - jti: unique token ID for audit
    """
    payload = {
        "sub": str(user_id),
        "email_hash": hashlib.sha256(email.encode()).hexdigest()[:16],  # For logging
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "jti": str(uuid4()),
        "type": "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """
    Returns: (token_plaintext, token_hash)
    Plaintext returned to user, hash stored in DB
    Expiry: 7 days
    """
    token_plaintext = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token_plaintext.encode()).hexdigest()
    
    payload = {
        "sub": str(user_id),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=7),
        "jti": str(uuid4()),
        "type": "refresh"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256"), token_hash
```

### Refresh Token Rotation Strategy
1. On `/refresh`: Validate incoming refresh token (JWT signature + DB hash check)
2. Mark old token as `is_revoked = true` in DB
3. Generate new token pair (access + refresh)
4. Store new refresh token hash in DB with `expires_at`
5. Return new tokens to client

### Account Lockout Logic
```python
def record_failed_login(user_id: UUID):
    """
    After 5 failed attempts: lock account for 15 minutes
    Resets on successful login
    """
    UPDATE users 
    SET failed_login_attempts = failed_login_attempts + 1,
        account_locked_until = CASE 
            WHEN failed_login_attempts >= 4 
            THEN NOW() + INTERVAL '15 minutes' 
            ELSE account_locked_until 
        END
    WHERE id = user_id;
```

### Role-Based Access Control (RBAC) Matrix
| Endpoint | broker | client | underwriter | admin |
|----------|--------|--------|-------------|-------|
| `/auth/register` | ❌ | ❌ | ❌ | ✅ |
| `/auth/login` | ✅ | ✅ | ✅ | ✅ |
| `/auth/refresh` | ✅ | ✅ | ✅ | ✅ |
| `/auth/logout` | ✅ | ✅ | ✅ | ✅ |
| `/users/me GET` | ✅ | ✅ | ✅ | ✅ |
| `/users/me PUT` | ✅ | ✅ | ✅ | ✅ |

*Note: Admin registration should be bootstrapped; other roles register via admin invitation flow (future enhancement)*

---

## 4. Migrations

### Alembic Revision: `create_auth_tables`
```python
revision = '001_create_auth_tables'
down_revision = None

def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('hashed_password', sa.Text(), nullable=False),
        sa.Column('role', sa.VARCHAR(20), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('account_locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_is_active', 'users', ['is_active'], 
                    postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_users_created_at', 'users', ['created_at'], 
                    postgresql_using='btree', postgresql_desc='true')
    
    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])
    op.create_index('idx_refresh_tokens_is_revoked', 'refresh_tokens', ['is_revoked'], 
                    postgresql_where=sa.text('is_revoked = false'))

def downgrade():
    op.drop_index('idx_refresh_tokens_is_revoked')
    op.drop_index('idx_refresh_tokens_expires_at')
    op.drop_index('idx_refresh_tokens_user_id')
    op.drop_table('refresh_tokens')
    op.drop_index('idx_users_created_at')
    op.drop_index('idx_users_is_active')
    op.drop_index('idx_users_role')
    op.drop_table('users')
```

### Data Migration Needs
- **Initial Admin User:** Bootstrap script required to create first admin via CLI (not via API)
- **Encryption Migration:** Existing plaintext data must be encrypted in-place using Alembic `execute()` with encryption service

---

## 5. Security & Compliance

### PIPEDA Data Handling
- **Encrypted Fields:** `email`, `full_name`, `phone` encrypted using AES-256-GCM via `cryptography.fernet`
- **Key Management:** `PIPEDA_ENCRYPTION_KEY` loaded from AWS Secrets Manager or environment variable (never committed)
- **Data Minimization:** Only collect required fields; `phone` is optional
- **Logging:** Never log decrypted values; log `email_hash` (SHA256 first 16 chars) for correlation
- **PII Access:** Only decrypt in service layer; schemas return decrypted data but logs contain only hashes

### FINTRAC Audit Trail
```python
# In services.py - log all auth events
structlog.bind(
    correlation_id=correlation_id,
    user_id_hash=hashlib.sha256(str(user.id).encode()).hexdigest()[:16],
    action="login",
    ip_address=client_ip,
    user_agent=user_agent
).info("auth_event")

# Required retention: 5 years (handled by PostgreSQL partitioning)
```
**Triggers:**
- Successful/failed login attempts
- Token refresh events
- Logout events
- Account lockouts
- Role changes (future admin endpoint)

### OSFI B-20 Applicability
- **Not Applicable** for auth module directly
- **Indirect Requirement:** Authentication **must** be enforced on all GDS/TDS calculation endpoints via dependency injection (`get_current_user`)
- **Audit:** All underwriting actions must include `user_id` from JWT in calculation logs

### JWT Security
- **Algorithm:** HS256 (HMAC with SHA-256)
- **Secret Source:** `JWT_SECRET` from environment variable, 32+ bytes cryptographically random
- **Token Storage:** Refresh token hashes stored in DB; never store plaintext tokens
- **Rotation:** Mandatory on each refresh to prevent token reuse attacks
- **Blacklist:** `is_revoked` flag enables instant invalidation

### Password Security
- **Hashing:** Argon2id (memory-hard, recommended by OWASP)
- **Cost Parameters:** `time_cost=3`, `memory_cost=65536`, `parallelism=4`
- **Salt:** Automatically handled by Argon2id implementation
- **Never:** Store, log, or transmit plaintext passwords

### Rate Limiting & Account Lockout
- **Login:** 5 attempts/minute per IP; 5 failed attempts per account → 15-minute lockout
- **Register:** 10 attempts/minute per IP
- **Implementation:** Redis-backed rate limiter with `common/security.py` middleware

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In modules/auth/exceptions.py
class AuthException(AppException):
    """Base exception for auth module"""
    module_code = "AUTH"

class UserAlreadyExistsError(AuthException):
    """Raised when email already registered"""
    http_status = 409
    error_code = "AUTH_001"
    message_template = "User with email {email} already exists"

class InvalidCredentialsError(AuthException):
    """Raised on failed authentication"""
    http_status = 401
    error_code = "AUTH_002"
    message_template = "Invalid email or password"  # Generic for security

class UserNotFoundError(AuthException):
    """Raised when user lookup fails"""
    http_status = 404
    error_code = "AUTH_003"
    message_template = "User not found"

class InvalidTokenError(AuthException):
    """Raised when JWT validation fails"""
    http_status = 401
    error_code = "AUTH_004"
    message_template = "Invalid or expired token"

class TokenExpiredError(AuthException):
    """Raised when token expiry detected"""
    http_status = 401
    error_code = "AUTH_005"
    message_template = "Token has expired"

class PasswordValidationError(AuthException):
    """Raised when password doesn't meet policy"""
    http_status = 422
    error_code = "AUTH_006"
    message_template = "Password does not meet requirements: {detail}"

class InvalidRoleError(AuthException):
    """Raised when invalid role provided"""
    http_status = 422
    error_code = "AUTH_007"
    message_template = "Invalid role: {role}"

class InactiveAccountError(AuthException):
    """Raised when account is locked or deactivated"""
    http_status = 403
    error_code = "AUTH_009"
    message_template = "Account is inactive or locked"

class RateLimitExceededError(AuthException):
    """Raised when rate limit exceeded"""
    http_status = 429
    error_code = "AUTH_010"
    message_template = "Rate limit exceeded: {limit} attempts per {period}"

class TokenRevokedError(AuthException):
    """Raised when refresh token has been revoked"""
    http_status = 401
    error_code = "AUTH_011"
    message_template = "Token has been revoked"

class FieldValidationError(AuthException):
    """Raised when profile update validation fails"""
    http_status = 422
    error_code = "AUTH_012"
    message_template = "Invalid field format: {field}"
```

### Error Response Format
All errors return consistent JSON structure:
```json
{
  "detail": "Invalid email or password",
  "error_code": "AUTH_002",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Edge Cases & Special Handling
- **Token Leakage:** If refresh token used twice (detected via hash lookup), revoke all user tokens and require re-login
- **Concurrent Requests:** Use database row-level locking on `users` table during login attempt updates
- **Time Sync:** All JWT validation uses UTC; servers must be NTP synchronized
- **Graceful Degradation:** If encryption service unavailable, fail closed (deny all access)

---

## 7. Additional Design Considerations

### Future Enhancements (Not in Current Scope)
1. **Email Verification:** Add `email_verified: bool` field and `/auth/verify-email` endpoint
2. **Password Reset:** Implement `/auth/request-reset` and `/auth/confirm-reset` with OTP
3. **OAuth2 Integration:** Support Google/Microsoft SSO for brokers (FINTRAC identity verification logging required)
4. **MFA:** TOTP/HOTP for underwriter/admin roles (regulatory requirement for high-risk operations)
5. **Role Permissions Matrix:** Fine-grained permissions via `permissions` table (e.g., `underwriting:approve`, `applications:view_all`)

### Testing Requirements
```python
# pytest markers
@pytest.mark.unit  # Password validation, JWT encoding/decoding
@pytest.mark.integration  # Database operations, token rotation
@pytest.mark.security  # Rate limiting, encryption, timing attacks

# Critical test cases:
# - Timing attack resistance (constant-time password comparison)
# - Token reuse detection
# - Encryption/decryption roundtrip accuracy
# - Concurrent login attempts
# - Account lockout reset on successful login
```

### Deployment Checklist
- [ ] `JWT_SECRET` generated and stored in secrets manager (32+ random bytes)
- [ ] `PIPEDA_ENCRYPTION_KEY` generated and stored (Fernet key format)
- [ ] Rate limiting Redis cluster provisioned
- [ ] Initial admin user created via secure CLI tool
- [ ] Database indexes created and analyzed
- [ ] OpenTelemetry tracing configured for auth events
- [ ] Prometheus metrics exposed: `auth_login_total`, `auth_login_failed_total`, `auth_token_revoked_total`
- [ ] `pip-audit` run and vulnerabilities remediated

---