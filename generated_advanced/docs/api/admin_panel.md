# docs/api/Admin Panel.md

# Admin Panel API

The Admin Panel module provides endpoints for system administration, including user management, lender configuration, and product management. All actions performed through this module are logged to the `audit_logs` table for FINTRAC compliance.

---

## GET /api/v1/admin/users

List all users in the system with pagination.

**Query Parameters:**
- `skip` (int, optional): Number of records to skip. Default: 0.
- `limit` (int, optional): Maximum number of records to return. Default: 100.

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
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)

---

## PUT /api/v1/admin/users/{id}/deactivate

Deactivate a specific user account. This action prevents the user from logging in but preserves their data for audit purposes.

**Path Parameters:**
- `id` (int): The user ID.

**Request Body:**
```json
{
  "reason": "Account closure request"
}
```

**Response (200):**
```json
{
  "id": 1,
  "username": "jdoe",
  "is_active": false,
  "updated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)
- 404: User not found

---

## PUT /api/v1/admin/users/{id}/role

Change the role of a specific user.

**Path Parameters:**
- `id` (int): The user ID.

**Request Body:**
```json
{
  "role": "admin"
}
```

**Response (200):**
```json
{
  "id": 1,
  "username": "jdoe",
  "role": "admin",
  "updated_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)
- 404: User not found
- 422: Validation error (Invalid role provided)

---

## POST /api/v1/admin/lenders

Create a new lending institution.

**Request Body:**
```json
{
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "lending@fnb.com",
  "is_active": true
}
```

**Response (201):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "lending@fnb.com",
  "is_active": true,
  "created_at": "2026-03-02T09:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)
- 422: Validation error (Duplicate code, invalid email)

---

## PUT /api/v1/admin/lenders/{id}

Update details for an existing lender.

**Path Parameters:**
- `id` (int): The lender ID.

**Request Body:**
```json
{
  "contact_email": "new-contact@fnb.com",
  "is_active": false
}
```

**Response (200):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "new-contact@fnb.com",
  "is_active": false,
  "updated_at": "2026-03-02T09:15:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)
- 404: Lender not found

---

## POST /api/v1/admin/lenders/{id}/products

Add a new mortgage product to a specific lender.

**Path Parameters:**
- `id` (int): The lender ID.

**Request Body:**
```json
{
  "name": "5-Year Fixed",
  "type": "fixed",
  "term_months": 60,
  "min_rate": "5.00",
  "max_rate": "6.50",
  "max_ltv": "80.00",
  "insurable": true
}
```

**Response (201):**
```json
{
  "id": 105,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "type": "fixed",
  "term_months": 60,
  "min_rate": "5.00",
  "max_rate": "6.50",
  "max_ltv": "80.00",
  "insurable": true,
  "created_at": "2026-03-02T09:20:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)
- 404: Lender not found
- 422: Validation error (Financial fields must be Decimal)

---

## PUT /api/v1/admin/lenders/{id}/products/{prod_id}

Update an existing mortgage product.

**Path Parameters:**
- `id` (int): The lender ID.
- `prod_id` (int): The product ID.

**Request Body:**
```json
{
  "max_rate": "6.75",
  "insurable": false
}
```

**Response (200):**
```json
{
  "id": 105,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "max_rate": "6.75",
  "insurable": false,
  "updated_at": "2026-03-02T09:25:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (Requires `admin` role)
- 404: Lender or Product not found
- 422: Validation error

---

# docs/modules/admin_panel.md

# Admin Panel Module

## Overview
The Admin Panel module is responsible for system configuration and administrative tasks. It enables the management of user accounts, lender institutions, and mortgage products. This module enforces role-based access control (RBAC), ensuring only users with `admin` privileges can perform destructive or configuration changes.

## Key Features

### Audit Logging (FINTRAC Compliance)
Every administrative action that modifies data (User deactivation, Role changes, Lender/Product CRUD) automatically generates an entry in the `audit_logs` table. This ensures an immutable trail of who changed what and when.

**Audit Log Structure:**
- `user_id`: ID of the admin performing the action.
- `action`: The type of action (e.g., `DEACTIVATE_USER`, `UPDATE_LENDER`).
- `entity_type`: The type of object affected (e.g., `User`, `Lender`).
- `entity_id`: The ID of the affected object.
- `old_value` / `new_value`: JSON snapshots of the state before and after the change.
- `ip_address` & `user_agent`: Request metadata for traceability.

### User Management
- **Listing:** Retrieve all users with pagination.
- **Deactivation:** Soft-deactivate users (sets `is_active` to false) without deleting data.
- **Role Assignment:** Update user roles (e.g., promoting an underwriter to admin).

### Lender & Product Management
- **Lenders:** Create and update lending institution details.
- **Products:** Define mortgage parameters (rates, terms, LTV limits) associated with lenders. All financial values use the `Decimal` type to prevent floating-point errors.

## Usage Examples

### Deactivating a User via Python Client
```python
import httpx

async def deactivate_user(admin_token: str, user_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"https://api.mortgage-system.com/api/v1/admin/users/{user_id}/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Employee termination"}
        )
        response.raise_for_status()
        return response.json()
```

### Creating a Lender Product
```python
import httpx
from decimal import Decimal

async def create_product(admin_token: str, lender_id: int):
    payload = {
        "name": "3-Year Variable",
        "type": "variable",
        "term_months": 36,
        "min_rate": str(Decimal("5.25")),
        "max_rate": str(Decimal("6.00")),
        "max_ltv": str(Decimal("95.00")),
        "insurable": True
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.mortgage-system.com/api/v1/admin/lenders/{lender_id}/products",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=payload
        )
        response.raise_for_status()
        return response.json()
```

---

# CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Admin Panel: New module for system administration.
  - User management endpoints (List, Deactivate, Change Role).
  - Lender management endpoints (Create, Update).
  - Product management endpoints (Add, Update).
- Audit logging for all Admin actions (FINTRAC compliance).

### Changed
- N/A

### Fixed
- N/A
```

---

# .env.example

```bash
# ... existing config ...

# Admin Panel Configuration
# Minimum required role to access admin endpoints
ADMIN_ACCESS_ROLE=admin

# Audit Log Configuration
# Retention period for audit logs in days (FINTRAC 5-year requirement)
AUDIT_LOG_RETENTION_DAYS=1825
```