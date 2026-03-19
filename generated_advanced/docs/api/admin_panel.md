# Admin Panel Documentation

## 1. API Documentation

**File:** `docs/api/admin_panel.md`

```markdown
# Admin Panel API

## Overview
Administrative endpoints for managing users, lenders, and lending products. All actions performed through these endpoints are logged to the `audit_logs` table to satisfy FINTRAC immutable audit trail requirements.

---

## GET /api/v1/admin/users

List all users in the system.

**Query Parameters:**
- `skip`: int (default 0) - Pagination offset
- `limit`: int (default 100) - Pagination limit

**Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "username": "jdoe",
      "email": "jdoe@example.com",
      "role": "underwriter",
      "is_active": true,
      "created_at": "2026-03-01T12:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Admin role required)

---

## PUT /api/v1/admin/users/{id}/deactivate

Deactivate a specific user account. This action prevents the user from logging in but preserves data for audit purposes.

**Path Parameters:**
- `id`: int - The User ID

**Request Body:**
```json
{}
```

**Response (200):**
```json
{
  "id": 1,
  "is_active": false,
  "updated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Admin role required)
- 404: User not found

---

## PUT /api/v1/admin/users/{id}/role

Change the role of a user.

**Path Parameters:**
- `id`: int - The User ID

**Request:**
```json
{
  "role": "admin"
}
```

**Response (200):**
```json
{
  "id": 1,
  "role": "admin",
  "updated_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Admin role required)
- 404: User not found
- 422: Invalid role value

---

## POST /api/v1/admin/lenders

Create a new lending institution.

**Request:**
```json
{
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "admin@fnb.com",
  "is_active": true
}
```

**Response (201):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "admin@fnb.com",
  "is_active": true,
  "created_at": "2026-03-02T09:00:00Z"
}
```

**Errors:**
- 400: Invalid input
- 401: Not authenticated
- 403: Forbidden (Admin role required)
- 422: Validation error

---

## PUT /api/v1/admin/lenders/{id}

Update details for an existing lender.

**Path Parameters:**
- `id`: int - The Lender ID

**Request:**
```json
{
  "name": "First National Bank",
  "contact_email": "new-contact@fnb.com"
}
```

**Response (200):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "new-contact@fnb.com",
  "is_active": true,
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Admin role required)
- 404: Lender not found

---

## POST /api/v1/admin/lenders/{id}/products

Add a new mortgage product to a lender's portfolio.

**Path Parameters:**
- `id`: int - The Lender ID

**Request:**
```json
{
  "name": "5-Year Fixed",
  "type": "fixed",
  "rate_min": "4.50",
  "rate_max": "5.00",
  "max_ltv": "80.00",
  "max_amortization_months": 300,
  "insurance_required": false
}
```

**Response (201):**
```json
{
  "id": 55,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "rate_min": "4.50",
  "rate_max": "5.00",
  "max_ltv": "80.00",
  "max_amortization_months": 300,
  "insurance_required": false,
  "created_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 400: Invalid financial value (must be Decimal)
- 401: Not authenticated
- 403: Forbidden (Admin role required)
- 404: Lender not found

---

## PUT /api/v1/admin/lenders/{id}/products/{prod_id}

Update an existing mortgage product.

**Path Parameters:**
- `id`: int - The Lender ID
- `prod_id`: int - The Product ID

**Request:**
```json
{
  "rate_min": "4.60",
  "rate_max": "5.10"
}
```

**Response (200):**
```json
{
  "id": 55,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "rate_min": "4.60",
  "rate_max": "5.10",
  "max_ltv": "80.00",
  "max_amortization_months": 300,
  "insurance_required": false,
  "updated_at": "2026-03-02T11:30:00Z"
}
```

**Errors:**
- 400: Invalid financial value (must be Decimal)
- 401: Not authenticated
- 403: Forbidden (Admin role required)
- 404: Lender or Product not found
```

## 2. Module README

**File:** `docs/modules/admin_panel.md`

```markdown
# Admin Panel Module

## Overview
The Admin Panel module provides the necessary interfaces for system administrators to manage the operational entities of the mortgage underwriting system. This includes user management (role-based access control), lender management, and the configuration of lending products.

## Key Features

### User Management
- **Listing:** Retrieve paginated lists of all system users.
- **Deactivation:** Soft-delete users to revoke access without destroying historical data (essential for audit trails).
- **Role Assignment:** Modify user roles (e.g., promoting an underwriter to an admin).

### Lender & Product Management
- **Lender CRUD:** Create and update lending institution profiles.
- **Product Configuration:** Define mortgage products with specific financial parameters (rates, LTV, amortization).
- **Financial Precision:** All rate and LTV calculations use Python `Decimal` types to prevent floating-point errors.

## Regulatory Compliance

### FINTRAC Audit Trail
Every state-changing action (create, update, deactivate) performed via the Admin Panel automatically generates an entry in the `audit_logs` table.
- **Immutable:** Records are inserted with `created_at` and are never updated or deleted.
- **Scope:** Logs capture `user_id`, `action`, `entity_type`, `entity_id`, and the full state diff (`old_value`, `new_value`).
- **Metadata:** IP address and User Agent are captured for security forensics.

### PIPEDA & Data Minimization
- Admin endpoints do not expose PII (SIN/DOB) in list views.
- Audit logs store state changes as JSON, but sensitive fields (like SIN) are hashed before storage in `old_value`/`new_value` if present.

## Dependencies
- **FastAPI:** Router endpoints.
- **SQLAlchemy:** ORM for `User`, `Lender`, `LenderProduct`, and `AuditLog` models.
- **Common/Security:** Role verification logic (e.g., `verify_admin_role`).
```

## 3. Configuration Notes

**File:** `.env.example` (Append or update)

```bash
# ... existing config ...

# Admin Panel Configuration
# Default email for the initial system admin user (created on first run if DB is empty)
DEFAULT_ADMIN_EMAIL=admin@mortgage-system.local
DEFAULT_ADMIN_PASSWORD=change_me_immediately

# Admin Session Settings
ADMIN_SESSION_TIMEOUT_MINUTES=60
```

## 4. CHANGELOG Update

**File:** `CHANGELOG.md` (Append)

```markdown
## [2026-03-02]
### Added
- Admin Panel: New endpoints for user management (list, deactivate, role change).
- Admin Panel: New endpoints for lender and product management (CRUD operations).
- Audit Log: Implemented automatic logging of admin actions to satisfy FINTRAC requirements.
- Models: Added `AuditLog` model for tracking entity changes with IP/User Agent metadata.

### Changed
- Updated User schema to support role updates and soft deactivation.
- Updated Lender and Product schemas to enforce Decimal types for all financial fields.
```

## 5. Docstring Additions (For Source Code)

*Note: These should be added to the corresponding service files in `modules/admin_panel/services.py`.*

```python
async def log_audit_entry(
    self,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    old_value: dict | None,
    new_value: dict | None,
    request: Request
) -> None:
    """
    Record an immutable audit entry for administrative actions.
    Complies with FINTRAC 5-year retention and immutable trail requirements.
    """
```