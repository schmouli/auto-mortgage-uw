# Design: Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Authentication & User Management Design Plan

**Feature Slug:** `auth-user-management`  
**Module Path:** `mortgage_underwriting/modules/auth/`  
**Design Document:** `docs/design/auth-user-management.md`

---

## 1. Endpoints

### `POST /api/v1/auth/register`
**Purpose:** Register new user with role-based access

**Request Schema:**
```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str  # Min 10 chars, 1 uppercase, 1 number, 1 special char
    role: Literal["broker", "client", "admin", "underwriter"]
    full_name: str  # Max 100 chars
    phone: str | None = None  # E.164 format validated
```

**Response Schema (201 Created):**
```python
class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
```

**Error Responses:**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| 409 | AUTH_001 | "Email already registered" |
| 422 | AUTH_002 | "Password must contain uppercase, number, and special character" |
| 422 | AUTH_003 | "Invalid phone format" |

**Auth Requirement:** Public (rate-limited: 5 requests/minute per IP)

---

### `POST /api/v1/auth/login`
**Purpose:** Authenticate user and return JWT tokens

**Request Schema:**
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

**Response Schema (200 OK):**
```python
class TokenResponse(BaseModel):
    access_token: str  # JWT, expires in 30 min
    refresh_token: str  # JWT, expires in 7 days
    token_type: str = "bearer"
    expires_in: int = 1800  # seconds
```

**Error Responses:**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| 401 | AUTH_004 | "Invalid credentials" |
| 403 | AUTH_005 | "Account deactivated" |
| 423 | AUTH_006 | "Too many failed attempts" (after 5 tries) |

**Auth Requirement:** Public (rate-limited: 10 requests/minute per IP)

---

### `POST /api/v1/auth/refresh`
**Purpose:** Refresh access token using valid refresh token

**Request Schema:**
```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

**Response Schema (200 OK):** Same as `TokenResponse`

**Error Responses:**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| 401 | AUTH_007 | "Invalid or expired refresh token" |
| 403 | AUTH_008 | "Refresh token revoked" |

**Auth Requirement:** Public (token-based validation)

---

### `POST /api/v1/auth/logout`
**Purpose:** Invalidate refresh token and log audit event

**Request Schema:**
```python
class LogoutRequest(BaseModel):
    refresh_token: str
```

**Response Schema (204 No Content):** Empty body

**Error Responses:**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| 400 | AUTH_009 | "Refresh token required" |

**Auth Requirement:** Authenticated (any role)

---

### `GET /api/v1/users/me`
**Purpose:** Retrieve current user profile

**Response Schema (200 OK):** `UserResponse`

**Error Responses:**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| 401 | AUTH_010 | "Not authenticated" |

**Auth Requirement:** Authenticated (any role)

---

### `PUT /api/v1/users/me`
**Purpose:** Update current user profile (data minimization)

**Request Schema:**
```python
class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
```

**Response Schema (200 OK):** `UserResponse`

**Error Responses:**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| 422 | AUTH_011 | "Cannot update email or role" |

**Auth Requirement:** Authenticated (any role)

---

## 2. Models & Database

### `models.py` - User Model
```python
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # Enum: broker, client, admin, underwriter
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    
    # PIPEDA: Audit trail for FINTRAC compliance
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
        Index("idx_users_role_active", "role", "is_active"),
    )
```

### `models.py` - RefreshToken Model
```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # SHA256 of JWT
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(default=False, index=True)
    
    # FINTRAC: Immutable audit trail
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    created_by_ip: Mapped[str | None] = mapped_column(String(45))  # For IPv6 support
    
    # Relationship
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
    
    __table_args__ = (
        Index("idx_tokens_user_expires", "user_id", "expires_at"),
    )
```

**Encryption Requirements (PIPEDA):**
- `full_name` and `phone` must be encrypted at rest using `encrypt_pii()` from `common/security.py`
- `email` is used for lookups and must remain in plaintext for indexing
- `hashed_password` uses bcrypt (never encrypted, only hashed)

---

## 3. Business Logic

### Password Validation Algorithm
```python
def validate_password(password: str) -> bool:
    """
    Rules: Min 10 chars, 1 uppercase, 1 digit, 1 special char
    Returns: True if valid, raises ValidationError otherwise
    """
    if len(password) < 10:
        raise AuthValidationError("Password minimum 10 characters")
    if not re.search(r"[A-Z]", password):
        raise AuthValidationError("Password must contain uppercase letter")
    if not re.search(r"\d", password):
        raise AuthValidationError("Password must contain number")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise AuthValidationError("Password must contain special character")
    return True
```

### JWT Token Generation
```python
def create_access_token(user_id: UUID, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4())  # For token tracking
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def create_refresh_token(user_id: UUID) -> tuple[str, str]:
    """
    Returns: (jwt_token, token_hash)
    """
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
        "jti": jti
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash
```

### Role Permissions Matrix
```python
ROLE_PERMISSIONS = {
    "client": ["read:own_profile", "write:own_profile"],
    "broker": ["read:own_profile", "write:own_profile", "create:application", "read:own_applications"],
    "underwriter": ["read:own_profile", "write:own_profile", "read:all_applications", "update:application_status"],
    "admin": ["*"]  # Full access
}
```

### Token Invalidation Flow
1. On logout: Set `RefreshToken.is_revoked = True`
2. On refresh: Check `is_revoked` and `expires_at` before issuing new token
3. On password change: Revoke all refresh tokens for user
4. FINTRAC audit: Log token creation/revocation events with `created_by_ip`

---

## 4. Migrations

### New Tables
```sql
-- Create users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create refresh_tokens table
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_ip INET
);

-- Indexes
CREATE INDEX idx_users_email_active ON users(email, is_active);
CREATE INDEX idx_users_role_active ON users(role, is_active);
CREATE INDEX idx_tokens_user_expires ON refresh_tokens(user_id, expires_at);
CREATE INDEX idx_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_tokens_expires ON refresh_tokens(expires_at) WHERE is_revoked = false;
```

### Data Migration
- None required (new module)

---

## 5. Security & Compliance

### FINTRAC Requirements
- **Audit Trail:** All auth events (login, logout, token refresh) logged with `correlation_id` and `created_by_ip`
- **Identity Verification:** Log successful login events with timestamp and user_id
- **5-Year Retention:** `refresh_tokens` table retains records for 5 years (soft delete via `is_revoked`)
- **Transaction Flagging:** N/A for auth module directly, but user roles determine who can flag >$10K transactions

### PIPEDA Requirements
- **Data Encryption:** `full_name` and `phone` encrypted using AES-256-GCM via `encrypt_pii()`
- **Data Minimization:** `phone` is optional; no SIN/DOB collected in this module
- **No Logging:** Never log passwords, tokens, or PII fields
- **Secure Storage:** `hashed_password` uses bcrypt with cost factor 12

### OSFI B-20 Requirements
- **N/A for auth module** (no GDS/TDS calculations)

### CMHC Requirements
- **N/A for auth module** (no insurance calculations)

### Security Controls
- **Rate Limiting:** 5 req/min (register), 10 req/min (login) per IP
- **Token Security:** JWT signed with HS256, secret from environment
- **Password Policy:** Enforced at API and service layer
- **CORS:** Configured in `common/config.py` with strict origins
- **mTLS:** Optional for internal service communication (documented in `common/security.py`)

---

## 6. Error Codes & HTTP Responses

### Exception Classes (`modules/auth/exceptions.py`)
```python
class AuthException(AppException):
    """Base auth exception"""
    pass

class EmailExistsError(AuthException):
    http_status = 409
    error_code = "AUTH_001"

class PasswordValidationError(AuthException):
    http_status = 422
    error_code = "AUTH_002"

class InvalidCredentialsError(AuthException):
    http_status = 401
    error_code = "AUTH_004"

class AccountDeactivatedError(AuthException):
    http_status = 403
    error_code = "AUTH_005"

class TooManyAttemptsError(AuthException):
    http_status = 423
    error_code = "AUTH_006"

class InvalidTokenError(AuthException):
    http_status = 401
    error_code = "AUTH_007"

class TokenRevokedError(AuthException):
    http_status = 403
    error_code = "AUTH_008"
```

### Error Response Structure
All errors return:
```json
{
    "detail": "Human-readable message",
    "error_code": "AUTH_XXX",
    "correlation_id": "uuid",
    "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## 7. Implementation Notes

### Files to Create
```
modules/auth/
├── __init__.py
├── models.py          # User, RefreshToken
├── schemas.py         # All request/response DTOs
├── services.py        # AuthService class with async methods
├── routes.py          # FastAPI router with 6 endpoints
└── exceptions.py      # Auth exception hierarchy

common/security.py     # Add: create_token, verify_token, encrypt_pii
common/config.py       # Add: JWT_SECRET, JWT_ALGORITHM, TOKEN_EXPIRY
```

### Environment Variables
```env
# .env.example
JWT_SECRET="your-256-bit-secret-here"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRY_MINUTES=30
REFRESH_TOKEN_EXPIRY_DAYS=7
BCRYPT_ROUNDS=12
ENCRYPTION_KEY="your-32-byte-aes-key"
```

### Testing Strategy
- **Unit Tests:** Password validation, token generation, role permissions
- **Integration Tests:** Full auth flow, token refresh, logout invalidation
- **Security Tests:** Rate limiting, SQL injection attempts, XSS in full_name

### Future Enhancements (Out of Scope)
- Email verification via OTP
- Password reset flow with secure token
- OAuth2 integration with third-party identity providers
- MFA support for admin/underwriter roles