# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**File Location:** `docs/design/auth-user-management.md`

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Authentication:** Public  
**Rate Limit:** 5 requests/minute per IP

**Request Body:**
```json
{
  "email": "user@example.com",           // string, required, valid email format
  "password": "Str0ng!Passw0rd",         // string, required, min 10 chars, 1 uppercase, 1 number, 1 special
  "full_name": "John Doe",               // string, required, min 2 chars, max 100 chars
  "phone": "+14165551234",               // string, optional, E.164 format validated
  "role": "client"                       // enum, optional, default "client", one of: broker, client, admin, underwriter
}
```

**Response (201 Created):**
```json
{
  "id": "018e8f9a-4f2c-7b3d-9e1a-5f6b8c2d4e7f",
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone": "+14165551234",
  "role": "client",
  "is_active": true,
  "created_at": "2024-01-15T14:30:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 422 | AUTH_002 | "email: invalid format" or "password: must contain uppercase, number, special character" |
| 409 | AUTH_004 | "Email already registered" |
| 429 | RATE_001 | "Too many requests" |

---

### `POST /api/v1/auth/login`
**Authentication:** Public  
**Rate Limit:** 10 requests/minute per IP

**Request Body:**
```json
{
  "email": "user@example.com",           // string, required
  "password": "Str0ng!Passw0rd"          // string, required
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI256K...",
  "refresh_token": "v2.local.eyJzdWIiOiIxOH44ZjlhLi4u",
  "token_type": "bearer",
  "expires_in": 1800,                    // seconds (30 minutes)
  "user": {
    "id": "018e8f9a-4f2c-7b3d-9e1a-5f6b8c2d4e7f",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "client",
    "is_active": true
  }
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_005 | "Invalid credentials" |
| 422 | AUTH_002 | "email: field required" |
| 429 | RATE_001 | "Too many requests" |

---

### `POST /api/v1/auth/refresh`
**Authentication:** Public (refresh token validation)  
**Rate Limit:** 30 requests/hour per IP

**Request Body:**
```json
{
  "refresh_token": "v2.local.eyJzdWIiOiIxOH44ZjlhLi4u"  // string, required
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI256K...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_006 | "Refresh token expired or revoked" |
| 422 | AUTH_002 | "refresh_token: field required" |

---

### `POST /api/v1/auth/logout`
**Authentication:** Authenticated (any role)  
**Rate Limit:** 60 requests/hour per user

**Request Body:**
```json
{
  "refresh_token": "v2.local.eyJzdWIiOiIxOH44ZjlhLi4u"  // string, required
}
```

**Response (200 OK):**
```json
{
  "detail": "Successfully logged out"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_007 | "Invalid or already revoked token" |
| 422 | AUTH_002 | "refresh_token: field required" |

---

### `GET /api/v1/users/me`
**Authentication:** Authenticated (any role)  
**Authorization:** Returns own data only

**Response (200 OK):**
```json
{
  "id": "018e8f9a-4f2c-7b3d-9e1a-5f6b8c2d4e7f",
  "email": "user@example.com",
  "full_name": "John Doe",
  "phone": "+14165551234",
  "role": "client",
  "is_active": true,
  "created_at": "2024-01-15T14:30:00Z",
  "updated_at": "2024-01-15T14:30:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_001 | "Not authenticated" |
| 404 | AUTH_008 | "User not found" |

---

### `PUT /api/v1/users/me`
**Authentication:** Authenticated (any role)  
**Authorization:** Update own data only

**Request Body:**
```json
{
  "full_name": "Jane Smith",             // string, optional, min 2 chars
  "phone": "+14165559876"                // string, optional, E.164 format
}
```

**Response (200 OK):**
```json
{
  "id": "018e8f9a-4f2c-7b3d-9e1a-5f6b8c2d4e7f",
  "email": "user@example.com",
  "full_name": "Jane Smith",
  "phone": "+14165559876",
  "role": "client",
  "is_active": true,
  "created_at": "2024-01-15T14:30:00Z",
  "updated_at": "2024-01-16T10:15:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 | AUTH_001 | "Not authenticated" |
| 422 | AUTH_002 | "full_name: must be at least 2 characters" |
| 404 | AUTH_008 | "User not found" |

---

## 2. Models & Database

### `users` Table
```python
class User(Base):
    __tablename__ = "users"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Authentication
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(128), nullable=False)  # bcrypt hash
    
    # Profile
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Authorization
    role = Column(
        Enum("broker", "client", "admin", "underwriter", name="user_role"),
        nullable=False,
        default="client",
        index=True
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Audit Fields (FINTRAC Compliance)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    
    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
        Index("idx_users_role_active", "role", "is_active"),
    )
```

**Data Protection (PIPEDA):**
- `email`, `full_name`, `phone` are PII and must be encrypted at rest using `pgcrypto` or SQLAlchemy encryption extension
- `hashed_password` uses bcrypt with cost factor 12
- No SIN/DOB collection in this module

---

### `refresh_tokens` Table
```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token hash for invalidation (store hash, never raw token)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256
    
    # Expiry and revocation
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, default=False, index=True)
    
    # Audit Fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="refresh_tokens")
    
    # Indexes
    __table_args__ = (
        Index("idx_refresh_tokens_expires", "expires_at"),
        Index("idx_refresh_tokens_user_revoked", "user_id", "revoked"),
    )
```

---

## 3. Business Logic

### Password Validation Algorithm
```python
def validate_password(password: str) -> tuple[bool, list[str]]:
    """
    Validates password against OSFI-equivalent strong authentication standards
    Returns: (is_valid, list_of_error_messages)
    """
    errors = []
    
    if len(password) < 10:
        errors.append("password: must be at least 10 characters")
    
    if not re.search(r"[A-Z]", password):
        errors.append("password: must contain uppercase letter")
    
    if not re.search(r"\d", password):
        errors.append("password: must contain number")
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("password: must contain special character")
    
    # Check against common passwords (FINTRAC guidance)
    common_passwords = {"Password123!", "Qwerty123!", "Mortgage2024!"}
    if password in common_passwords:
        errors.append("password: too common")
    
    return len(errors) == 0, errors
```

### JWT Token Generation
```python
def create_access_token(user_id: UUID, role: str) -> str:
    """
    Creates JWT access token with 30 minute expiry
    Payload: sub (user_id), role, exp, iat, jti
    """
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),  # For token tracking
        "type": "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """
    Creates refresh token with 7 day expiry
    Returns: (raw_token, token_hash)
    """
    token = f"v2.local.{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Store in DB
    expires_at = datetime.utcnow() + timedelta(days=7)
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    # ... save to DB
    
    return token, token_hash
```

### Role-Based Access Control Matrix
```python
# WARNING: This is a design placeholder. Full RBAC implementation requires separate permissions table
ROLE_PERMISSIONS = {
    "client": ["read:own_profile", "write:own_profile"],
    "broker": ["read:own_profile", "write:own_profile", "read:applications", "write:applications"],
    "underwriter": ["read:own_profile", "write:own_profile", "read:all_applications", "write:underwriting_decisions"],
    "admin": ["read:all_profiles", "write:all_profiles", "read:all_applications", "write:system_config"]
}
```

### State Machine for User Account
```
inactive (email unverified) → active (verified) → suspended (manual) → deactivated
```

---

## 4. Migrations

### Alembic Migration: `001_create_auth_tables.py`
```python
def upgrade():
    # Create user_role enum
    op.execute("CREATE TYPE user_role AS ENUM ('broker', 'client', 'admin', 'underwriter')")
    
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("role", postgresql.ENUM("broker", "client", "admin", "underwriter", name="user_role"), nullable=False, server_default="client"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )
    
    # Create indexes
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_role_active", "users", ["role", "is_active"])
    op.create_index("idx_users_email_active", "users", ["email", "is_active"])
    
    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    
    # Create indexes for token invalidation queries
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"])
    op.create_index("idx_refresh_tokens_expires", "refresh_tokens", ["expires_at"])
    op.create_index("idx_refresh_tokens_user_revoked", "refresh_tokens", ["user_id", "revoked"])
    
    # FINTRAC audit log table (separate module, referenced here for compliance)
    # op.create_table("audit_logs", ...)
```

---

## 5. Security & Compliance

### FINTRAC Compliance
- **Audit Trail:** Every authentication event (login, logout, register, token refresh) must log to `audit_logs` table with:
  - `created_at`, `created_by` (user_id or IP for public endpoints)
  - `event_type`: `USER_LOGIN`, `USER_LOGOUT`, `USER_REGISTER`, `TOKEN_REFRESH`
  - `metadata`: JSON blob with non-PII data (user_id, user_agent, IP, correlation_id)
  - **RETENTION:** 5 years (enforced via database policy)

- **Transaction Threshold:** While auth module doesn't handle financial transactions, user registration events that enable >$10K transactions must be flagged in audit log with `high_value_access: true`

### PIPEDA Compliance
- **Encryption at Rest:** 
  - `email`, `full_name`, `phone` encrypted using AES-256 via SQLAlchemy `EncryptedType`
  - Encryption key from `settings.PIPEDA_ENCRYPTION_KEY` (32-byte base64)
  
- **Data Minimization:** Only collect fields required for underwriting authentication
- **No Logging:** `full_name`, `email`, `phone` must never appear in logs (use user_id instead)
- **Response Filtering:** Hashed password never serialized in API responses

### OSFI B-20 & CMHC
- **Not Directly Applicable:** This module does not calculate GDS/TDS or insurance premiums
- **Integration Point:** User identity verified here is referenced by underwriting modules; ensure user_id is immutable audit foreign key

### Authentication Security
- **Password Hashing:** bcrypt with cost factor 12, salt auto-generated
- **JWT:** HS256 with 256-bit secret from `settings.JWT_SECRET`
- **Refresh Tokens:** Stored as SHA256 hashes, never plain text; 7-day expiry
- **Token Invalidation:** On logout, set `revoked=True`; on password change, revoke all tokens
- **Rate Limiting:** Applied per IP and per user (see endpoint specs)
- **CORS:** Strict origin whitelist from `settings.ALLOWED_ORIGINS`
- **Secure Cookies:** `HttpOnly`, `Secure`, `SameSite=Strict` for token transport option
- **mTLS:** Optional client certificate validation for internal service-to-service auth

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In common/exceptions.py
class AuthException(AppException):
    """Base exception for auth module"""
    module_code = "AUTH"

# In modules/auth/exceptions.py
class InvalidCredentialsError(AuthException):
    http_status = 401
    error_code = "AUTH_005"
    message = "Invalid credentials"

class EmailAlreadyExistsError(AuthException):
    http_status = 409
    error_code = "AUTH_004"
    message = "Email already registered"

class TokenExpiredError(AuthException):
    http_status = 401
    error_code = "AUTH_006"
    message = "Token expired or revoked"

class TokenInvalidError(AuthException):
    http_status = 401
    error_code = "AUTH_007"
    message = "Invalid token format"

class UserNotFoundError(AuthException):
    http_status = 404
    error_code = "AUTH_008"
    message = "User not found"

class AuthValidationError(AuthException):
    http_status = 422
    error_code = "AUTH_002"
    message = "Validation failed"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "Human-readable message",
  "error_code": "AUTH_005",
  "correlation_id": "018e8f9a-4f2c-7b3d-9e1a-5f6b8c2d4e7f",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## 7. Missing Details & Future Considerations

**WARNING:** The following features are NOT covered in this design but are required for production:

### Email Verification
- **Design Needed:** 
  - `email_verified` boolean field on users table
  - POST `/auth/verify-email` endpoint with token
  - Background worker to send verification emails
  - Temporary JWT claims for unverified users restricting access

### Password Reset Flow
- **Design Needed:**
  - POST `/auth/forgot-password` with email
  - POST `/auth/reset-password` with token + new password
  - Secure token generation (6-digit OTP or JWT)
  - Token expiry (15 minutes)
  - Rate limiting (3 attempts/hour)

### OAuth2 Third-Party Integration
- **Design Needed:**
  - Support for Google, Microsoft Entra ID
  - `oauth_providers` table linking external IDs
  - PKCE flow for mobile apps
  - Separate migration for OAuth tokens

### Role Permissions Matrix
- **Design Needed:**
  - Separate `permissions` and `role_permissions` tables
  - Fine-grained permissions: `applications:read:own`, `applications:write:all`
  - Middleware for permission enforcement
  - Admin UI for role management

### Multi-Factor Authentication
- **Design Needed:**
  - TOTP/HOTP support for underwriter/admin roles (OSFI guidance)
  - `mfa_secret` and `mfa_enabled` fields
  - POST `/auth/mfa/enable`, `/auth/mfa/verify` endpoints
  - Backup codes generation

**Recommendation:** Implement Phase 1 (this design) for MVP, then iterate on missing features based on security audit findings.