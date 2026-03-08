# Authentication & User Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

**docs/design/auth.md**

## 1. Endpoints

| Method | Path | Auth | Request Body (Pydantic) | Response Body | Status Codes & Error Codes |
|--------|------|------|--------------------------|---------------|----------------------------|
| **POST** | `/api/v1/auth/register` | Public | `RegisterRequest`<br>- email: str<br>- password: str<br>- full_name: str<br>- phone: str<br>- role: Literal["broker","client","admin","underwriter"] (optional, default="client") | `UserResponse`<br>- id: UUID<br>- email: str<br>- full_name: str<br>- phone: str<br>- role: str<br>- is_active: bool<br>- created_at: datetime | 201 Created<br>400 Bad Request (`AUTH_002`)<br>409 Conflict (`AUTH_003`) |
| **POST** | `/api/v1/auth/login` | Public | `LoginRequest`<br>- email: str<br>- password: str | `LoginResponse`<br>- access_token: str<br>- refresh_token: str<br>- token_type: "bearer"<br>- expires_in: int (seconds) | 200 OK<br>401 Unauthorized (`AUTH_001`)<br>422 Validation Error (`AUTH_002`) |
| **POST** | `/api/v1/auth/refresh` | Public (refresh token) | `RefreshRequest`<br>- refresh_token: str | `LoginResponse` (new access token) | 200 OK<br>401 Unauthorized (`AUTH_004`)<br>422 Validation Error (`AUTH_002`) |
| **POST** | `/api/v1/auth/logout` | Authenticated | `LogoutRequest`<br>- refresh_token: str | `None` | 204 No Content<br>401 Unauthorized (`AUTH_001`)<br>404 Not Found (`AUTH_005`) |
| **GET** | `/api/v1/users/me` | Authenticated | `None` | `UserResponse` (same as register) | 200 OK<br>401 Unauthorized (`AUTH_001`) |
| **PUT** | `/api/v1/users/me` | Authenticated | `UserUpdateRequest`<br>- full_name: str (optional)<br>- phone: str (optional) | `UserResponse` (updated) | 200 OK<br>401 Unauthorized (`AUTH_001`)<br>422 Validation Error (`AUTH_002`) |

**Notes**
- `phone` is stored AES‑256 encrypted at rest (PIPEDA).
- `password` is hashed with `bcrypt` (never persisted plain).
- `role` defaults to `client` for self‑registration; only an `admin` can create `broker`, `underwriter`, or `admin` accounts (see “Business Logic”).
- All endpoints return structured error bodies: `{"detail": "...", "error_code": "AUTH_xxx"}`.

---

## 2. Models & Database

### 2.1 `users` table

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | `UUID` | PrimaryKey | – | – |
| `email` | `String(255)` | Unique, NotNull | Unique (`idx_users_email`) | – |
| `hashed_password` | `String(255)` | NotNull | – | – |
| `role` | `Enum("broker","client","admin","underwriter")` | NotNull | (`idx_users_role`) | – |
| `full_name` | `String(255)` | NotNull | – | – |
| `phone` | `String(50)` | NotNull | – | **AES‑256** |
| `is_active` | `Boolean` | NotNull, default=True | (`idx_users_is_active`) | – |
| `created_at` | `DateTime(timezone=True)` | NotNull, default=now() | – | – |
| `updated_at` | `DateTime(timezone=True)` | NotNull, default=now(), onupdate=now() | – | – |

**Relationships** – None (standalone user entity).

**Audit** – `created_at`, `updated_at` mandatory.

**Encryption** – `phone` encrypted via `common/security.encrypt_pii()` / `decrypt_pii()`.

### 2.2 `refresh_tokens` table

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | PrimaryKey | – |
| `user_id` | `UUID` | ForeignKey(`users.id`, ondelete=CASCADE) | (`idx_refresh_tokens_user_id`) |
| `token_jti` | `String(255)` | Unique, NotNull | Unique (`idx_refresh_tokens_jti`) |
| `expires_at` | `DateTime(timezone=True)` | NotNull | (`idx_refresh_tokens_expires`) |
| `created_at` | `DateTime(timezone=True)` | NotNull, default=now() | – |

**Purpose** – Store refresh tokens for revocation; `token_jti` is the JWT `jti` claim.

---

## 3. Business Logic

### 3.1 Registration (`/auth/register`)

1. **Input Validation** – Enforce password policy (≥10 chars, ≥1 uppercase, ≥1 digit, ≥1 special char). Use `pydantic` validators.
2. **Email Uniqueness** – Query `users` by email; if exists → raise `AuthConflictError`.
3. **Role Assignment** – If caller is anonymous, default role = `client`. If caller is `admin`, allow explicit role (broker/underwriter/admin).
4. **PII Encryption** – Encrypt `phone` with AES‑256 (key from `common/config.py`).
5. **Password Hashing** – `bcrypt.hashpw()`; store only `hashed_password`.
6. **Audit Logging** – Log `user.id`, `role`, `created_at` with `structlog` (correlation_id). **FINTRAC** identity‑verification event.
7. **Token Generation** – On successful registration, optionally auto‑login: issue access (30 min) & refresh (7 days) tokens, persist refresh token in `refresh_tokens`.
8. **Response** – Return `UserResponse` (no `hashed_password`).

### 3.2 Login (`/auth/login`)

1. **Credential Lookup** – Fetch user by email; if not found → `AuthInvalidCredentialsError`.
2. **Password Verification** – `bcrypt.checkpw()`; if mismatch → `AuthInvalidCredentialsError`.
3. **Account Status** – If `is_active=False` → `AuthAccountDisabledError`.
4. **Token Creation** – Generate JWT access token (`exp`=now+30 min) with claims `sub=user.id`, `role=user.role`, `jti=random`. Generate refresh token (`exp`=now+7 days, `jti` stored in DB).
5. **Audit Logging** – Log login event (FINTRAC identity verification).
6. **Response** – Return `LoginResponse`.

### 3.3 Refresh (`/auth/refresh`)

1. **Token Extraction** – Decode refresh token (verify signature, `exp`, `jti`).
2. **DB Check** – Query `refresh_tokens` by `token_jti`; if missing or `expires_at`<now → `AuthTokenRevokedError`.
3. **User Validation** – Ensure user still exists and `is_active=True`.
4. **New Access Token** – Issue new access token (same 30 min policy) with fresh `jti`.
5. **Response** – Return `LoginResponse` (same shape, new access token only; refresh token remains unchanged).

### 3.4 Logout (`/auth/logout`)

1. **Token Extraction** – Extract refresh token from request body.
2. **Revocation** – Delete the corresponding row from `refresh_tokens` (or mark revoked if soft‑delete preferred).
3. **Audit Logging** – Log logout event.

### 3.5 User Profile (`/users/me`)

- **GET** – Return authenticated user’s own record (no sensitive fields).
- **PUT** – Allow updating `full_name` and `phone` only; re‑encrypt `phone` if changed; update `updated_at`.

### 3.6 Role Permissions Matrix (to be enforced in `services.py` & `dependencies.py`)

| Role | Can Create (via register) | Can Self‑Update | Can View Others | Can Manage Users |
|------|---------------------------|----------------|-----------------|------------------|
| `client` | No (self‑register only) | Yes (`/users/me`) | No | No |
| `broker` | No | Yes (`/users/me`) | No | No |
| `underwriter` | No | Yes (`/users/me`) | No | No |
| `admin` | Yes (any role) | Yes (`/users/me`) | Yes (future admin endpoints) | Yes (future admin endpoints) |

**Implementation** – Use FastAPI `dependencies` that inspect `token["role"]` and raise `AuthPermissionError` if operation not allowed.

---

## 4. Migrations

### Alembic Revision `auth_001`

**Create Tables**

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('broker','client','admin','underwriter')),
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_is_active ON users (is_active);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_jti ON refresh_tokens (token_jti);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens (expires_at);
```

**Data Migration** – None required (new module).

---

## 5. Security & Compliance

### 5.1 OSFI B‑20
- *Not directly applicable* – No GDS/TDS calculations in auth module. Ensure that any downstream underwriting logic that uses `user.role` to fetch income data will apply the stress‑test rule (see Underwriting module design).

### 5.2 FINTRAC
- **Identity Verification Logging** – On successful `login` and `register`, emit a structured log:
  ```json
  {
    "event": "identity_verified",
    "user_id": "<UUID>",
    "role": "<role>",
    "timestamp": "<ISO8601>",
    "correlation_id": "<uuid>"
  }
  ```
  Retain logs for 5 years (log aggregation policy).
- **Transaction >$10 000** – Not triggered in auth; however, when a mortgage application is created (Application module), the `created_by` audit trail must reference the authenticated user.

### 5.3 CMHC
- *Not applicable* – No LTV/premium logic in auth.

### 5.4 PIPEDA
- **Encryption at Rest** – `phone` column encrypted with AES‑256 (key from `COMMON_ENCRYPTION_KEY` env var, loaded via `common/config.py`).
- **Data Minimization** – Only `email`, `full_name`, `phone` are collected. No SIN/DOB stored in this module.
- **No PII in Logs/Errors** – Ensure `phone` is never logged; log only `user_id` and `role`.
- **Lookup Hashes** – If SIN is needed later, store SHA‑256 hash in a separate table, never plain.

### 5.5 JWT & Token Security
- **Secret Management** – `JWT_SECRET` and `REFRESH_TOKEN_SECRET` loaded from environment via `common/config.py`; never hardcoded.
- **Signature Algorithm** – `HS256` (or `RS256` if asymmetric keys are configured).
- **Token Claims** – `sub` (user_id), `role`, `jti`, `iat`, `exp`.
- **Refresh Token Rotation** – Optional (can be implemented later); for now, a refresh token is valid until expiry or explicit logout.
- **Token Revocation** – Deleting the row from `refresh_tokens` instantly invalidates the token.

### 5.6 Password Policy
- **Validation** – Regex: `^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{10,}$`.
- **Hashing** – `bcrypt` with cost factor 12 (configurable via `common/config.py`).

### 5.7 API Security
- **Rate Limiting** – Apply `slowapi` or similar on `/auth/login` and `/auth/register` (e.g., 5 requests/min per IP).
- **CORS** – Configure `CORSMiddleware` in FastAPI; allow only trusted origins (from `common/config.py`).
- **mTLS** – If required, terminate TLS at the load balancer and forward client certificate info via headers; validation logic in `common/security.py`.

---

## 6. Error Codes & HTTP Responses

| Exception Class (module‑specific) | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------------------------|-------------|------------|-----------------|-----------------|
| `AuthInvalidCredentialsError` | 401 | `AUTH_001` | "Invalid email or password." | Login with wrong password |
| `AuthValidationError` | 422 | `AUTH_002` | "{field}: {reason}" | Password too short |
| `AuthConflictError` | 409 | `AUTH_003` | "User with this email already exists." | Duplicate registration |
| `AuthTokenRevokedError` | 401 | `AUTH_004` | "Refresh token has been revoked or expired." | Stolen refresh token |
| `AuthUserNotFoundError` | 404 | `AUTH_005` | "User not found." | Logout with non‑existent token |
| `AuthPermissionError` | 403 | `AUTH_006` | "Insufficient permissions for this operation." | Client tries to create broker |
| `AuthAccountDisabledError` | 403 | `AUTH_007` | "Account is deactivated." | Login on disabled user |
| `AuthTokenExpiredError` | 401 | `AUTH_008` | "Access token has expired." | Expired JWT |

**Base Exception** – All inherit from `common.exceptions.AppException` to guarantee structured JSON responses and consistent logging.

**Implementation Notes**
- Use FastAPI `HTTPException` subclasses that return `{"detail": "...", "error_code": "AUTH_xxx"}`.
- Log each exception with `structlog` including `correlation_id`, `user_id` (if available), `error_code`.

---

## 7. Module Layout (Reference)

```
modules/auth/
├── __init__.py
├── models.py          # SQLAlchemy User, RefreshToken
├── schemas.py         # Pydantic request/response DTOs
├── services.py        # Registration, login, token logic
├── routes.py          # FastAPI router with dependencies
├── exceptions.py      # Auth*Error definitions
└── dependencies.py    # get_current_user(), require_role()
```

**Dependencies**
- `common/config.py` – JWT secrets, encryption key, bcrypt cost.
- `common/database.py` – `get_async_session()`.
- `common/security.py` – `encrypt_pii()`, `decrypt_pii()`, `create_access_token()`, `create_refresh_token()`, `verify_token()`.
- `common/exceptions.py` – `AppException`.

**Testing**
- `tests/unit/test_auth.py` – Unit tests for services (mocked DB, token generation).
- `tests/integration/test_auth_integration.py` – End‑to‑end flow with real PostgreSQL, verifying token lifecycle, revocation, PII encryption.
- Use `pytest.mark.unit` / `pytest.mark.integration` markers.

**Observability**
- `structlog` JSON logs on each endpoint entry/exit with `correlation_id`.
- OpenTelemetry spans for `register`, `login`, `refresh`, `logout`.
- Prometheus counter `auth_requests_total` labeled by `endpoint`, `status`.

**Security Scanning**
- Run `uv run pip-audit` before each deploy; ensure no known vulnerabilities in `bcrypt`, `pyjwt`, `cryptography`.

---

## 8. Future Considerations (Out of Scope for MVP)

- **Email Verification** – Add `email_verified: bool` column, send OTP via Notifications module.
- **Password Reset Flow** – `POST /auth/password‑reset‑request` + `POST /auth/password‑reset‑confirm` with short‑lived JWT.
- **OAuth2 / OIDC** – Integrate third‑party identity providers (e.g., Equifax) for broker/underwriter onboarding.
- **Role‑Based Access Control (RBAC) UI** – Admin panel to manage user roles (separate Admin module).
- **Multi‑Factor Authentication (MFA)** – TOTP/HOTP for high‑privilege roles.

--- 

**Design Version:** 1.0  
**Last Updated:** 2025‑06‑28  
**Compliance:** OSFI B‑20 (indirect), FINTRAC (identity audit), CMHC (N/A), PIPEDA (encryption, data minimization).