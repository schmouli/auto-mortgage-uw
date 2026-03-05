# Design: Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

**docs/design/authentication-user-management.md**

---

## 1. Endpoints

| Method | Path | Auth | Request Body (Pydantic) | Response Body (Pydantic) | Error Codes (HTTP) |
|--------|------|------|--------------------------|--------------------------|--------------------|
| **POST** | `/api/v1/auth/register` | Public | `RegisterRequest`<br>- `email`: EmailStr (required)<br>- `password`: str (required, ≥10 chars, 1 upper, 1 lower, 1 digit, 1 special)<br>- `full_name`: str (required, max 100)<br>- `phone`: str (optional, E.164 format) | `RegisterResponse`<br>- `user_id`: UUID<br>- `email`: EmailStr<br>- `role`: Literal["client"]<br>- `full_name`: str<br>- `phone`: str \| None<br>- `is_active`: bool<br>- `created_at`: datetime | `AUTH_002` (409) – User already exists<br>`AUTH_003` (422) – Weak password<br>`AUTH_004` (422) – Invalid email format<br>`AUTH_005` (422) – Invalid phone format |
| **POST** | `/api/v1/auth/login` | Public | `LoginRequest`<br>- `email`: EmailStr (required)<br>- `password`: str (required) | `LoginResponse`<br>- `access_token`: str (JWT, 30 min)<br>- `refresh_token`: str (random, 7 days)<br>- `token_type`: str = "bearer" | `AUTH_001` (401) – Invalid credentials<br>`AUTH_009` (403) – Account inactive |
| **POST** | `/api/v1/auth/refresh` | Public (refresh token) | `RefreshRequest`<br>- `refresh_token`: str (required) | `RefreshResponse`<br>- `access_token`: str (new JWT, 30 min)<br>- `token_type`: str = "bearer" | `AUTH_004` (401) – Refresh token expired<br>`AUTH_005` (401) – Refresh token invalid<br>`AUTH_006` (404) – Refresh token not found |
| **POST** | `/api/v1/auth/logout` | Authenticated (any role) | `LogoutRequest`<br>- `refresh_token`: str (required) | `LogoutResponse`<br>- `detail`: str = "Logged out" | `AUTH_006` (404) – Refresh token not found |
| **GET** | `/api/v1/users/me` | Authenticated (any role) | – | `UserProfileResponse`<br>- `id`: UUID<br>- `email`: EmailStr<br>- `role`: str<br>- `full_name`: str<br>- `phone`: str \| None<br>- `is_active`: bool<br>- `created_at`: datetime<br>- `updated_at`: datetime | `AUTH_007` (404) – User not found |
| **PUT** | `/api/v1/users/me` | Authenticated (any role) | `UpdateProfileRequest`<br>- `full_name`: str (optional, max 100)<br>- `phone`: str (optional, E.164) | `UserProfileResponse` (same as above) | `AUTH_007` (404) – User not found<br>`AUTH_003` (422) – Invalid phone format |
| **POST** | `/api/v1/auth/request‑verify‑email` | Authenticated (any role) | – | `DetailResponse`<br>- `detail`: str = "Verification email sent" | `AUTH_010` (403) – Email already verified |
| **POST** | `/api/v1/auth/verify‑email` | Public (token) | `VerifyEmailRequest`<br>- `token`: str (required, URL‑safe) | `DetailResponse`<br>- `detail`: str = "Email verified" | `AUTH_005` (401) – Token invalid/expired |
| **POST** | `/api/v1/auth/request‑password‑reset` | Public | `PasswordResetRequest`<br>- `email`: EmailStr (required) | `DetailResponse`<br>- `detail`: str = "Reset email sent" | `AUTH_007` (404) – User not found (do not reveal) |
| **POST** | `/api/v1/auth/reset‑password` | Public (token) | `ResetPasswordRequest`<br>- `token`: str (required)<br>- `new_password`: str (required, ≥10 chars, 1 upper, 1 lower, 1 digit, 1 special) | `DetailResponse`<br>- `detail`: str = "Password reset successful" | `AUTH_005` (401) – Token invalid/expired<br>`AUTH_003` (422) – Weak password |

*Authentication scheme*: OAuth2 Password Bearer (`Authorization: Bearer <access_token>`).  
*Rate limiting*: 5 req/min on `/login`, `/register`, `/request‑password‑reset`.  
*CORS*: Strict origin whitelist (`origins` from `common/config.py`).  
*mTLS*: Optional (configurable via `common/config.py`).

---

## 2. Models & Database

### 2.1 `users` Table

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | `UUID` | PrimaryKey, default `gen_random_uuid()` | – | – |
| `email` | `VARCHAR(255)` | Unique, NotNull | `idx_users_email` (unique) | PII – never logged |
| `hashed_password` | `VARCHAR(255)` | NotNull | – | Bcrypt hash – never returned |
| `role` | `VARCHAR(20)` | NotNull, Check(`role` IN (`broker`,`client`,`admin`,`underwriter`)) | `idx_users_role` | – |
| `full_name` | `VARCHAR(100)` | NotNull | – | PII – avoid logging |
| `phone` | `VARCHAR(20)` | Nullable | – | E.164 format; PII |
| `is_active` | `BOOLEAN` | NotNull, Default `False` | `idx_users_active` | Active only after email verification (if enforced) |
| `email_verified` | `BOOLEAN` | NotNull, Default `False` | – | Optional – see “Email Verification” |
| `verification_token` | `VARCHAR(255)` | Nullable, Unique | `idx_users_verify_token` | Optional – one‑time token |
| `verification_token_expires_at` | `TIMESTAMP` | Nullable | – | – |
| `created_at` | `TIMESTAMP` | NotNull, Default `now()` | – | Audit field |
| `updated_at` | `TIMESTAMP` | NotNull, Default `now()`, OnUpdate `now()` | – | Audit field |

**Relationships**: One‑to‑many with `refresh_tokens` (see below).  

**Encryption**: No AES‑256 required for `full_name`/`phone` per current PIPEDA scope, but field‑level encryption can be added later if needed.

### 2.2 `refresh_tokens` Table

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | `UUID` | PrimaryKey, default `gen_random_uuid()` | – | – |
| `user_id` | `UUID` | ForeignKey(`users.id`, ondelete=`CASCADE`), NotNull | `idx_refresh_tokens_user_id` | – |
| `token_hash` | `VARCHAR(64)` | NotNull, Unique | `idx_refresh_tokens_hash` | SHA‑256 of the raw token |
| `expires_at` | `TIMESTAMP` | NotNull | `idx_refresh_tokens_expires` | TTL 7 days |
| `created_at` | `TIMESTAMP` | NotNull, Default `now()` | – | Audit field |
| `used_at` | `TIMESTAMP` | Nullable | – | Set when token is rotated or invalidated |

**Purpose**: Enables immediate invalidation of refresh tokens on logout or compromise.

### 2.3 Indexes (Composite)

- `idx_users_email_active` on `users(email, is_active)` for fast lookup during login.
- `idx_refresh_tokens_user_expires` on `refresh_tokens(user_id, expires_at)` for pruning expired tokens.

---

## 3. Business Logic

### 3.1 Password Policy

- **Minimum length**: 10 characters.  
- **Complexity**: At least one uppercase letter, one lowercase letter, one digit, one special character (`!@#$%^&*()`).  
- **Validation**: Performed in the service layer (`services.py`) using a regular expression.  
- **Storage**: Bcrypt hash with cost factor 12 (configurable via `common/config.py`).  
- **Never** log or return the raw password.

### 3.2 JWT & Refresh Token Lifecycle

1. **Access Token** (JWT)
   - **Payload**: `sub` (user_id), `role`, `exp` (30 min from issuance), `iat`, `iss` (issuer), `aud` (audience).  
   - **Signature**: HMAC‑SHA256 using a secret key (rotated via `common/config.py`).  
   - **Transport**: Sent as `Authorization: Bearer <token>` header.

2. **Refresh Token** (Opaque)
   - **Generation**: 32‑byte cryptographically random string, base64‑url‑safe.  
   - **Storage**: SHA‑256 hash stored in `refresh_tokens.token_hash`; raw token returned only once to the client.  
   - **Expiry**: 7 days (configurable).  
   - **Rotation**: Optional (new refresh token issued on each refresh, old token marked `used_at`).

3. **Token Validation**
   - Access token: Verify signature, expiry, audience, issuer.  
   - Refresh token: Verify expiry, existence in DB (by hash), and that `used_at` is `NULL`.  
   - User must be `is_active=True` and `email_verified=True` (if verification enforced).

### 3.3 Registration Flow

1. Validate `email` uniqueness (case‑insensitive).  
2. Validate password against policy.  
3. Hash password with bcrypt.  
4. Create `users` record with `role="client"` (default; other roles require admin creation).  
5. If email verification is enabled: generate a one‑time `verification_token` (UUID), set `verification_token_expires_at` (24 h), send token via secure email (link to `/auth/verify‑email?token=…`).  
6. Return public user profile (excluding `hashed_password`).

### 3.4 Login Flow

1. Fetch user by email (case‑insensitive).  
2. Verify bcrypt hash of provided password.  
3. Check `is_active=True` and `email_verified=True` (if enforced).  
4. Generate access and refresh tokens.  
5. Store refresh token hash in DB with `expires_at`.  
6. Log authentication event (success/failure) with `structlog` (exclude PII).  
7. Return tokens.

### 3.5 Logout & Token Invalidation

1. Receive `refresh_token` from client.  
2. Compute SHA‑256 hash and delete the corresponding DB row (or set `used_at`).  
3. Return success.

### 3.6 Token Refresh

1. Validate refresh token (signature, expiry, DB existence).  
2. If valid, issue new access token.  
3. Optionally rotate refresh token: generate new raw token, store new hash, mark old token `used_at`.  
4. Return new tokens.

### 3.7 Profile Management

- **GET /users/me**: Extract `user_id` from JWT, fetch user record, return public fields.  
- **PUT /users/me**: Validate input (phone format), update `full_name`/`phone`, set `updated_at = now()`.  
- **Email change**: Not allowed via this endpoint; requires separate verification flow to avoid account takeover.

### 3.8 Role‑Based Access Control (RBAC) Matrix (Proposed)

| Endpoint | broker | client | admin | underwriter |
|----------|--------|--------|-------|-------------|
| `POST /auth/register` | – | ✅ (self) | – | – |
| `POST /auth/login` | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/refresh` | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/logout` | ✅ | ✅ | ✅ | ✅ |
| `GET /users/me` | ✅ | ✅ | ✅ | ✅ |
| `PUT /users/me` | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/verify‑email` | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/request‑password‑reset` | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/reset‑password` | ✅ | ✅ | ✅ | ✅ |
| **Admin‑only** (future) | | | | |
| `GET /users` | ❌ | ❌ | ✅ | ❌ |
| `POST /users` | ❌ | ❌ | ✅ | ❌ |
| `PUT /users/{id}` | ❌ | ❌ | ✅ | ❌ |
| `DELETE /users/{id}` | ❌ | ❌ | ✅ | ❌ |

*Implementation*: FastAPI `Depends()` with role check (`get_current_active_user`, `require_role("admin")`).

### 3.9 Audit & Observability

- **Login/Logout**: `structlog` entry with `event="auth.login|logout"`, `user_id`, `ip_address`, `user_agent`, `success`.  
- **Token refresh**: `event="auth.refresh"`, `user_id`, `success`.  
- **Password reset**: `event="auth.password_reset"`, `user_id`, `success`.  
- **Metrics**: Prometheus counters `auth_login_attempts_total`, `auth_login_failures_total`, `auth_token_refresh_total`.  
- **Tracing**: OpenTelemetry spans for each auth operation (exclude PII attributes).  
- **Retention**: Logs retained 5 years (FINTRAC) – shipped to a tamper‑proof store (e.g., AWS CloudTrail Logs).

---

## 4. Migrations

### 4.1 New Tables

```sql
-- alembic/versions/xxxx_create_users_and_refresh_tokens.py
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('broker','client','admin','underwriter')),
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT false,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    verification_token VARCHAR(255) UNIQUE,
    verification_token_expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_active ON users (is_active);
CREATE INDEX idx_users_email_active ON users (email, is_active);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    used_at TIMESTAMP
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens (expires_at);
CREATE INDEX idx_refresh_tokens_user_expires ON refresh_tokens (user_id, expires_at);
```

### 4.2 Follow‑up Migrations (Optional)

- Add `last_login_at` to `users` for activity tracking.  
- Add `password_changed_at` for password age policy.  
- Add `mfa_enabled` and `mfa_secret` for future MFA support.

---

## 5. Security & Compliance

### 5.1 PIPEDA (Personal Information Protection)

- **Data Minimization**: Only `email`, `full_name`, `phone` are collected; `hashed_password` is stored securely.  
- **Encryption at Rest**: Not mandated for name/phone per current scope, but AES‑256 can be added later if classified as sensitive.  
- **Logging**: **Never** log `email`, `full_name`, `phone`, or `hashed_password`. Use `user_id` for correlation.  
- **PII in Responses**: `full_name` and `phone` are returned only to the authenticated user; never expose other users’ PII.

### 5.2 FINTRAC (Anti‑Money Laundering)

- **Immutable Audit Trail**: All authentication events (login, logout, token refresh, password reset) are appended to a tamper‑proof log store (e.g., immutable S3 bucket).  
- **5‑Year Retention**: Logs retained for 5 years; automated lifecycle policy ensures no early deletion.  
- **Transaction Reporting**: Not applicable to auth module (no financial transactions > CAD 10 000).

### 5.3 OSFI B‑20 (Mortgage Underwriting)

- **Not Directly Applicable**: No GDS/TDS calculations in this module. If auth module ever touches rates, ensure `Decimal` is used.

### 5.4 CMHC (Mortgage Insurance)

- **Not Applicable**: No LTV or premium logic.

### 5.5 Authentication & Authorization

- **OAuth2**: Password Bearer flow for access tokens; refresh tokens are opaque.  
- **Token Storage**: Refresh token hashes stored in DB; raw tokens never persisted.  
- **Token Expiry**: Short‑lived access (30 min) + long‑lived refresh (7 days) balances security and UX.  
- **Invalidation**: Instant revocation via DB deletion on logout; periodic cleanup of expired tokens.  
- **Rate Limiting**: 5 attempts per minute on login/register; lockout after 10 failed attempts (optional).  
- **CORS**: Whitelist‑only origins; credentials not allowed from untrusted domains.  
- **mTLS**: Optional client certificate validation for high‑privilege roles (`admin`, `underwriter`).

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | When Raised |
|-----------------|-------------|------------|-----------------|-------------|
| `AuthInvalidCredentialsError` | 401 | `AUTH_001` | "Invalid email or password" | Login fails (password mismatch or user not found) |
| `AuthUserExistsError` | 409 | `AUTH_002` | "User with this email already exists" | Registration with duplicate email |
| `AuthWeakPasswordError` | 422 | `AUTH_003` | "Password must be ≥10 chars, include uppercase, lowercase, digit, special character" | Password policy violation |
| `AuthTokenExpiredError` | 401 | `AUTH_004` | "Token has expired" | Access or refresh token expiry |
| `AuthTokenInvalidError` | 401 | `AUTH_005` | "Token is invalid or malformed" | Signature verification failure |
| `AuthRefreshTokenNotFoundError` | 404 | `AUTH_006` | "Refresh token not found" | Logout/refresh with non‑existent token |
| `AuthUserNotFoundError` | 404 | `AUTH_007` | "User not found" | `GET /users/me` for deleted user |
| `AuthPermissionDeniedError` | 403 | `AUTH_008` | "Insufficient permissions" | Role‑based access denied |
| `AuthAccountInactiveError` | 403 | `AUTH_009` | "Account is inactive" | Login/refresh for `is_active=False` |
| `AuthEmailVerificationRequiredError` | 403 | `AUTH_010` | "Email verification required" | Accessing protected resource before verification |

**Implementation Notes**:
- All exceptions inherit from `common.exceptions.AppException`.  
- FastAPI exception handlers map these to the structured JSON response:  
  ```json
  {
    "detail": "<message>",
    "error_code": "AUTH_XXX"
  }
  ```
- Use `Depends(get_current_active_user)` to inject user and enforce `is_active=True`.  
- Use `Depends(require_role("admin"))` for admin‑only endpoints.

---

## 7. Future Considerations (Out of Scope for MVP)

| Feature | Description | Impact on Design |
|---------|-------------|------------------|
| **Role Permissions Matrix UI** | Admin dashboard to assign roles & permissions. | New endpoints under `/admin/permissions` (RBAC management). |
| **Email Verification** | Send signed URL with token; verify within 24 h. | Add `verification_token` columns, email service integration. |
| **Password Reset Flow** | Request → email with signed token → reset form. | New tables `password_reset_tokens` (hashed, expiry). |
| **OAuth2 Third‑Party** | Google, Microsoft login; link external accounts. | Add `external_accounts` table (provider, external_id, access_token). |
| **Multi‑Factor Authentication (MFA)** | TOTP or SMS; enforce for `admin`/`underwriter`. | Add `mfa_secret`, `mfa_enabled` to `users`; extra `/auth/mfa` endpoints. |
| **Account Lockout** | After N failed attempts, lock account for M minutes. | Add `failed_login_count`, `locked_until` to `users`; background job to prune. |
| **Session Management** | List active sessions, revoke individual tokens. | Add `session_id` to `refresh_tokens`; new `/auth/sessions` endpoints. |

---

**Document Version**: 1.0  
**Last Updated**: 2025‑06‑27  
**Maintained By**: Architecture Team  
**Compliance Review**: PIPEDA, FINTRAC, OSFI B‑20, CMHC (where applicable).