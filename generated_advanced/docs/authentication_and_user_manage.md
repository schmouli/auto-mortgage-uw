# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Module Design

**Module Path:** `modules/auth/`  
**Feature Slug:** `authentication-user-management`  
**Document Version:** 1.0

---

## 1. Endpoints

### 1.1 POST /api/v1/auth/register
**Authentication:** Public  
**Purpose:** Create new user account with role-based registration

**Request Schema:**
```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str  # Min 10 chars, 1 uppercase, 1 number, 1 special char
    role: Literal["broker", "client", "admin", "underwriter"]
    full_name: str  # Min 2 chars, max 100 chars
    phone: str | None = None  # E.164 format validation
```

**Response Schema (201 Created):**
```python
class RegisterResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: str
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    message: str = "Registration successful. Please verify your email."
```

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 422 | AUTH_002 | Password fails complexity requirements |
| 422 | AUTH_003 | Invalid email format or phone format |
| 409 | AUTH_004 | Email already registered |
| 422 | AUTH_005 | Invalid role specified |

---

### 1.2 POST /api/v1/auth/login
**Authentication:** Public  
**Purpose:** Authenticate user and issue JWT tokens

**Request Schema:**
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fingerprint: str | None = None  # For FINTRAC audit trail
```

**Response Schema (200 OK):**
```python
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes
    user: UserProfileResponse
```

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 401 | AUTH_006 | Invalid credentials |
| 403 | AUTH_007 | Account deactivated (is_active=False) |
| 422 | AUTH_008 | Email not verified (if enforcement enabled) |

---

### 1.3 POST /api/v1/auth/refresh
**Authentication:** Authenticated (refresh token)  
**Purpose:** Obtain new access token using valid refresh token

**Request Schema:**
```python
class RefreshRequest(BaseModel):
    refresh_token: str
    correlation_id: str  # From request headers for tracing
```

**Response Schema (200 OK):**
```python
class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int = 1800
    token_type: str = "bearer"
```

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 401 | AUTH_009 | Refresh token expired or invalid |
| 401 | AUTH_010 | Refresh token revoked (logged out) |

---

### 1.4 POST /api/v1/auth/logout
**Authentication:** Authenticated  
**Purpose:** Invalidate refresh token and log access for FINTRAC

**Request Schema:**
```python
class LogoutRequest(BaseModel):
    refresh_token: str
    reason: Literal["user_initiated", "security"] = "user_initiated"
```

**Response Schema (204 No Content):** Empty body

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 401 | AUTH_011 | Refresh token not found or already invalidated |

---

### 1.5 GET /api/v1/users/me
**Authentication:** Authenticated (any role)  
**Purpose:** Retrieve current user profile (PIPEDA compliance - no sensitive data)

**Response Schema (200 OK):**
```python
class UserProfileResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: str
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
```

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 401 | AUTH_012 | Access token expired or invalid |

---

### 1.6 PUT /api/v1/users/me
**Authentication:** Authenticated (any role)  
**Purpose:** Update current user profile with audit logging

**Request Schema:**
```python
class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    current_password: str | None = None  # Required if changing sensitive fields
```

**Response Schema (200 OK):** Same as `UserProfileResponse`

**Error Responses:**
| HTTP Status | Error Code | Scenario |
|-------------|------------|----------|
| 422 | AUTH_013 | Phone format invalid |
| 401 | AUTH_014 | Current password incorrect when required |
| 409 | AUTH_015 | Email change requires verification flow (if implemented) |

---

## 2. Models & Database

### 2.1 users Table
```python
class User(Base):
    __tablename__ = "users"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # PII (handled per PIPEDA - phone is not encrypted but access logged)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # FINTRAC Audit Trail (immutable)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(100))  # System or admin ID
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_ip: Mapped[str | None] = mapped_column(String(45))  # IPv6 support
    
    # PIPEDA compliance tracking
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
        Index("idx_users_role_active", "role", "is_active"),
        CheckConstraint("role IN ('broker', 'client', 'admin', 'underwriter')", name="valid_role"),
    )
```

### 2.2 refresh_tokens Table
```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # SHA256 of token
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # FINTRAC audit trail
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_ip: Mapped[str | None] = mapped_column(String(45))
    device_fingerprint: Mapped[str | None] = mapped_column(String(255))  # For tracking
    
    # PIPEDA compliance
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(50))
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
    
    # Indexes
    __table_args__ = (
        Index("idx_tokens_user_expires", "user_id", "expires_at"),
        Index("idx_tokens_hash_active", "token_hash", "is_revoked"),
    )
```

### 2.3 audit_logs Table (for FINTRAC compliance)
```python
class UserAuditLog(Base):
    __tablename__ = "user_audit_logs"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # login, logout, update, etc.
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    
    # PIPEDA: Data minimization - only log non-sensitive metadata
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    device_fingerprint: Mapped[str | None] = mapped_column(String(255))
    
    # FINTRAC: Immutable record
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_correlation", "correlation_id"),
    )
```

---

## 3. Business Logic

### 3.1 Password Validation Algorithm
```python
def validate_password(password: str) -> tuple[bool, list[str]]:
    """
    Enforces password complexity per security best practices
    Returns: (is_valid, list_of_error_messages)
    """
    errors = []
    if len(password) < 10:
        errors.append("Password must be at least 10 characters")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain uppercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain number")
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain special character")
    
    return len(errors) == 0, errors
```

### 3.2 JWT Token Generation
```python
def create_tokens(user: User, device_fingerprint: str | None) -> tuple[str, str]:
    """
    Generates access and refresh tokens with FINTRAC audit logging
    """
    # Access token: 30 minutes expiry
    access_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    
    # Refresh token: 7 days expiry
    refresh_payload = {
        "sub": str(user.id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),  # Unique token ID
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    
    # Generate tokens
    access_token = jwt.encode(access_payload, settings.JWT_SECRET, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET, algorithm="HS256")
    
    # Store refresh token hash in DB for invalidation
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=refresh_payload["exp"],
        created_by_ip=get_client_ip(),
        device_fingerprint=device_fingerprint
    )
    # ... save to DB ...
    
    # FINTRAC: Log authentication event
    audit_log = UserAuditLog(
        user_id=user.id,
        action="login",
        correlation_id=get_correlation_id(),
        ip_address=get_client_ip(),
        device_fingerprint=device_fingerprint
    )
    # ... save to DB ...
    
    return access_token, refresh_token
```

### 3.3 Role Permissions Matrix
| Role | Can Register Self | Can View Users | Can Manage Users | Can Underwrite | Can Submit Applications |
|------|-------------------|----------------|------------------|----------------|------------------------|
| broker | Yes | Own only | Own only | No | Yes |
| client | Yes | Own only | Own only | No | Yes (own) |
| admin | No | All | All | No | No |
| underwriter | No | All | No | Yes | No |

### 3.4 State Machine for User Account
```
[created] → [email_verified] → [active] → [suspended] → [reactivated]
     ↓              ↓                ↓            ↓            ↓
[deleted]      [rejected]       [inactive]   [inactive]   [active]
```

---

## 4. Migrations

### 4.1 New Tables

**migration_001_create_users_table.py**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('broker', 'client', 'admin', 'underwriter')),
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT true NOT NULL,
    is_email_verified BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    last_login_at TIMESTAMP,
    last_login_ip INET,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email_active ON users (email, is_active);
CREATE INDEX idx_users_role_active ON users (role, is_active);
CREATE INDEX idx_users_created_at ON users (created_at);
```

**migration_002_create_refresh_tokens_table.py**
```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by_ip INET,
    device_fingerprint VARCHAR(255),
    revoked_at TIMESTAMP,
    revoke_reason VARCHAR(50)
);

CREATE INDEX idx_tokens_user_expires ON refresh_tokens (user_id, expires_at);
CREATE INDEX idx_tokens_hash_active ON refresh_tokens (token_hash, is_revoked);
CREATE INDEX idx_tokens_expires_at ON refresh_tokens (expires_at) WHERE is_revoked = false;
```

**migration_003_create_user_audit_logs_table.py**
```sql
CREATE TABLE user_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    correlation_id VARCHAR(36),
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user_action ON user_audit_logs (user_id, action);
CREATE INDEX idx_audit_correlation ON user_audit_logs (correlation_id);
CREATE INDEX idx_audit_created_at ON user_audit_logs (created_at);
```

### 4.2 Data Migration Needs
- **None** for initial implementation
- Future migration for email verification: Add `email_verification_token` column if implementing verification flow

---

## 5. Security & Compliance

### 5.1 PIPEDA Compliance
- **Data Minimization:** Only collect `email`, `full_name`, `phone` - fields are necessary for mortgage underwriting workflow
- **Encryption at Rest:** `phone` field should be encrypted using `encrypt_pii()` from `common/security.py`
- **Logging:** NEVER log `email`, `full_name`, `phone` in plain text. Use user_id for correlation
- **Response Filtering:** `hashed_password` is never included in API responses
- **Access Control:** Users can only access `/users/me` endpoint; admin role required for accessing other user records

### 5.2 FINTRAC Requirements
- **Authentication Logging:** All login/logout events logged in `user_audit_logs` with:
  - `correlation_id` for request tracing
  - `ip_address` and `device_fingerprint` for device tracking
  - Immutable records (no updates/deletes allowed)
- **5-Year Retention:** `user_audit_logs` table must have retention policy configured at database level
- **Session Tracking:** `refresh_tokens` table tracks active sessions for suspicious activity monitoring

### 5.3 Password Security
- **Hashing Algorithm:** Use Argon2id (via `passlib`) with minimum configuration:
  - time_cost=3, memory_cost=65536, parallelism=1
- **Password Reset:** Future implementation must use secure token expiry (15 minutes) and one-time use
- **Rate Limiting:** Implement on all auth endpoints:
  - Register: 5 attempts per hour per IP
  - Login: 10 attempts per 15 minutes per account
  - Reset: 3 attempts per hour per email

### 5.4 JWT Security
- **Secret Management:** `JWT_SECRET` loaded from `common/config.py` (pydantic.BaseSettings)
- **Token Storage:** Refresh tokens stored as SHA256 hashes only
- **Token Validation:** Verify `jti` claim against `refresh_tokens` table on each use
- **Correlation ID:** All token operations must log with `correlation_id` for OpenTelemetry tracing

---

## 6. Error Codes & HTTP Responses

### 6.1 Authentication Exceptions
```
| Exception Class              | HTTP Status | Error Code | Message Pattern                              |
|------------------------------|-------------|------------|----------------------------------------------|
| InvalidCredentialsError      | 401         | AUTH_006   | "Invalid email or password"                  |
| AccountInactiveError         | 403         | AUTH_007   | "Account is deactivated"                     |
| EmailNotVerifiedError        | 422         | AUTH_008   | "Email verification required"                |
| TokenExpiredError            | 401         | AUTH_009   | "Token has expired"                          |
| TokenRevokedError            | 401         | AUTH_010   | "Token has been revoked"                     |
| TokenNotFoundError           | 401         | AUTH_011   | "Invalid token"                              |
| UnauthorizedAccessError      | 401         | AUTH_012   | "Access token invalid or missing"            |
| PasswordMismatchError        | 401         | AUTH_014   | "Current password is incorrect"              |
```

### 6.2 Validation Exceptions
```
| Exception Class              | HTTP Status | Error Code | Message Pattern                              |
|------------------------------|-------------|------------|----------------------------------------------|
| PasswordComplexityError      | 422         | AUTH_002   | "Password fails complexity: {details}"       |
| InvalidEmailFormatError      | 422         | AUTH_003   | "Invalid email format"                       |
| InvalidPhoneFormatError      | 422         | AUTH_013   | "Phone must be E.164 format"                 |
| DuplicateEmailError          | 409         | AUTH_004   | "Email already registered"                   |
| InvalidRoleError             | 422         | AUTH_005   | "Invalid role: {role}"                       |
```

### 6.3 User Management Exceptions
```
| Exception Class              | HTTP Status | Error Code | Message Pattern                              |
|------------------------------|-------------|------------|----------------------------------------------|
| UserNotFoundError            | 404         | USER_001   | "User {user_id} not found"                   |
| UserUpdateConflictError      | 409         | USER_002   | "Concurrent update detected"                 |
| RolePermissionError          | 403         | USER_003   | "Insufficient permissions for role {role}"   |
```

### 6.4 Rate Limiting Responses
```json
{
  "detail": "Rate limit exceeded",
  "error_code": "AUTH_016",
  "retry_after": 3600,
  "limit": "5 per hour"
}
```

---

## 7. Future Enhancements (Out of Scope)

1. **Email Verification Flow:** Add `POST /auth/verify-email` and `POST /auth/resend-verification`
2. **Password Reset:** Add `POST /auth/forgot-password` and `POST /auth/reset-password` with secure token
3. **OAuth2 Integration:** Support for Google/Microsoft SSO for broker/client roles
4. **MFA:** TOTP-based multi-factor authentication for admin and underwriter roles
5. **Session Management:** `GET /auth/sessions` and `DELETE /auth/sessions/{token_id}` for viewing/revoking active sessions

---

**Design Approval Required:** Security team review for FINTRAC audit trail completeness and PIPEDA encryption implementation.