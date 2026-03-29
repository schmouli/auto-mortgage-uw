# Documentation for Admin Panel Module

## 1. API Documentation

**File:** `docs/api/Admin Panel.md`

```markdown
# Admin Panel API

This module provides endpoints for system administration, including user management, lender management, and product configuration. All actions performed through these endpoints are logged to the `audit_logs` table for FINTRAC compliance.

---

## GET /admin/users

List all users in the system.

**Permissions:** `admin:read`

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
      "created_at": "2026-01-15T09:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (requires admin role)

---

## PUT /admin/users/{id}/deactivate

Deactivate a specific user account. This action is reversible but prevents the user from logging in.

**Permissions:** `admin:write`

**Request:**
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
- 404: User not found
- 403: Forbidden

---

## PUT /admin/users/{id}/role

Change the role of a specific user.

**Permissions:** `admin:write`

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
- 400: Invalid role value
- 404: User not found

---

## POST /admin/lenders

Create a new lending institution.

**Permissions:** `admin:write`

**Request:**
```json
{
  "name": "First National Bank",
  "code": "FNB",
  "contact_email": "admin@fnb.ca",
  "is_active": true
}
```

**Response (201):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "code": "FNB",
  "contact_email": "admin@fnb.ca",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Validation error (e.g., duplicate code)
- 422: Unprocessable entity

---

## PUT /admin/lenders/{id}

Update details for an existing lender.

**Permissions:** `admin:write`

**Request:**
```json
{
  "contact_email": "new-contact@fnb.ca"
}
```

**Response (200):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "contact_email": "new-contact@fnb.ca",
  "updated_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- 404: Lender not found

---

## POST /admin/lenders/{id}/products

Add a new mortgage product to a lender's portfolio.

**Permissions:** `admin:write`

**Request:**
```json
{
  "name": "5-Year Fixed",
  "rate_type": "fixed",
  "term_months": 60,
  "interest_rate": "5.49",
  "max_ltv": "80.00",
  "min_credit_score": 680
}
```

**Response (201):**
```json
{
  "id": 55,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "interest_rate": "5.49",
  "max_ltv": "80.00",
  "created_at": "2026-03-02T12:00:00Z"
}
```

**Errors:**
- 404: Lender not found
- 422: Validation error (e.g., invalid interest rate format)

---

## PUT /admin/lenders/{id}/products/{product_id}

Update details of a specific mortgage product.

**Permissions:** `admin:write`

**Request:**
```json
{
  "interest_rate": "5.65",
  "max_ltv": "95.00"
}
```

**Response (200):**
```json
{
  "id": 55,
  "lender_id": 10,
  "interest_rate": "5.65",
  "max_ltv": "95.00",
  "updated_at": "2026-03-02T12:30:00Z"
}
```

**Errors:**
- 404: Lender or Product not found
- 422: Validation error
```

## 2. Module README

**File:** `docs/modules/Admin Panel.md`

```markdown
# Admin Panel Module

## Overview
The Admin Panel module provides the necessary interface for system administrators to manage users, lending institutions, and mortgage products. It serves as the configuration layer for the mortgage underwriting system, ensuring that valid lenders and products are available to the underwriting modules.

## Key Functions

### User Management
- **Listing Users:** Retrieve a paginated list of all system users.
- **Deactivation:** Soft-deactivate users to revoke access without deleting data (maintains referential integrity).
- **Role Management:** Assign or update user roles (e.g., `admin`, `underwriter`, `agent`).

### Lender & Product Management
- **Lender CRUD:** Create and update lender profiles.
- **Product Configuration:** Define mortgage products with specific terms, rates, and LTV limits. 
  - *Note:* All financial fields (rates, LTV) use `Decimal` to prevent floating-point errors.

### Audit & Compliance
The module automatically triggers audit log entries for all modification operations (Create, Update, Deactivate) to satisfy FINTRAC requirements.

**Audit Log Schema:**
- `user_id`: The admin performing the action.
- `action`: The type of action (e.g., `deactivate_user`, `update_product`).
- `entity_type`: The type of object affected (e.g., `User`, `Lender`).
- `entity_id`: The ID of the affected object.
- `old_value` / `new_value`: JSON snapshots of the state before and after the change.
- `ip_address` & `user_agent`: Request metadata for traceability.

## Usage Example

To add a new product for a lender:

```python
import httpx

async def add_product():
    async with httpx.AsyncClient() as client:
        payload = {
            "name": "3-Year Variable",
            "rate_type": "variable",
            "term_months": 36,
            "interest_rate": "5.15", # Must be string or Decimal
            "max_ltv": "80.00"
        }
        response = await client.post(
            "http://api/v1/admin/lenders/10/products",
            json=payload,
            headers={"Authorization": "Bearer <admin_token>"}
        )
    return response.json()
```

## Regulatory Notes
- **FINTRAC:** All configuration changes are immutable once written to the audit log (never deleted/modified). 5-year retention is enforced at the database level.
- **PIPEDA:** PII (user emails, names) in requests/responses is handled securely. Audit logs may contain PII in `old_value`/`new_value` and must be accessed strictly by authorized personnel.
```

## 3. Configuration Notes

**File:** `.env.example` (Append or update existing)

```bash
# ... existing config ...

# Admin Panel Configuration
# Default role required to access admin endpoints
ADMIN_ROLE_NAME=admin

# Audit Log Configuration
# Retention period for audit logs in days (FINTRAC requirement: 5 years = 1825 days)
AUDIT_LOG_RETENTION_DAYS=1825
```