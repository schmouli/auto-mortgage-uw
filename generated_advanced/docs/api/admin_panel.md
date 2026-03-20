# Admin Panel API

## Overview
The Admin Panel module provides endpoints for system administration, including user management and lender/product configuration. All actions performed through these endpoints are logged to the `audit_logs` table to satisfy FINTRAC regulatory requirements for immutable audit trails.

---

## GET /admin/users

List all users in the system with pagination support.

**Request:**
```http
GET /api/v1/admin/users?page=1&limit=50
```

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
  "page": 1,
  "limit": 50
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions (Admin role required)

---

## PUT /admin/users/{id}/deactivate

Deactivate a specific user account. This action prevents the user from logging in but preserves their data for audit purposes.

**Request:**
```http
PUT /api/v1/admin/users/42/deactivate
```

**Response (200):**
```json
{
  "id": 42,
  "is_active": false,
  "updated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions
- 404: User not found

---

## PUT /admin/users/{id}/role

Change the role of a specific user.

**Request:**
```json
{
  "role": "admin"
}
```

**Response (200):**
```json
{
  "id": 42,
  "role": "admin",
  "updated_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions
- 422: Invalid role value

---

## POST /admin/lenders

Create a new lender institution.

**Request:**
```json
{
  "name": "First National Bank",
  "code": "FNB001",
  "is_active": true
}
```

**Response (201):**
```json
{
  "id": 101,
  "name": "First National Bank",
  "code": "FNB001",
  "is_active": true,
  "created_at": "2026-03-02T09:00:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 409: Lender code already exists
- 422: Validation error

---

## PUT /admin/lenders/{id}

Update details for an existing lender.

**Request:**
```json
{
  "name": "First National Bank Updated",
  "is_active": false
}
```

**Response (200):**
```json
{
  "id": 101,
  "name": "First National Bank Updated",
  "code": "FNB001",
  "is_active": false,
  "updated_at": "2026-03-02T09:15:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 404: Lender not found

---

## POST /admin/lenders/{id}/products

Add a new mortgage product to a lender's portfolio.

**Request:**
```json
{
  "name": "5-Year Fixed",
  "type": "fixed",
  "rate": "5.49",
  "max_ltv": "80.00",
  "term_months": 60
}
```

**Response (201):**
```json
{
  "id": 501,
  "lender_id": 101,
  "name": "5-Year Fixed",
  "type": "fixed",
  "rate": "5.49",
  "max_ltv": "80.00",
  "term_months": 60,
  "created_at": "2026-03-02T09:30:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 404: Lender not found
- 422: Validation error (e.g., rate must be Decimal)

---

## PUT /admin/lenders/{id}/products/{prod_id}

Update an existing mortgage product.

**Request:**
```json
{
  "rate": "5.75",
  "max_ltv": "95.00"
}
```

**Response (200):**
```json
{
  "id": 501,
  "lender_id": 101,
  "name": "5-Year Fixed",
  "rate": "5.75",
  "max_ltv": "95.00",
  "updated_at": "2026-03-02T09:45:00Z"
}
```

**Errors:**
- 401: Not authenticated
- 404: Product or Lender not found
- 422: Validation error

---

# Admin Panel Module

## Overview
The Admin Panel module is responsible for the configuration and maintenance of the mortgage underwriting system's core entities. It facilitates the management of system users and the definition of lending institutions and their respective financial products.

### Key Functions

1.  **User Management:**
    *   Listing all system users.
    *   Deactivating users (soft delete).
    *   Role assignment (e.g., `admin`, `underwriter`, `agent`).

2.  **Lender Management:**
    *   CRUD operations for lending institutions.
    *   Managing mortgage products associated with lenders (rates, terms, LTV limits).

3.  **Audit Logging:**
    *   Automatically records every administrative action to the `audit_logs` table.
    *   Tracks `user_id`, `action`, `entity_type`, `old_value`, `new_value`, `ip_address`, and `user_agent`.

## Regulatory Compliance
*   **FINTRAC:** This module is critical for compliance. All modifications to user roles, lender status, and product rates create an immutable record in the `audit_logs` table. This ensures a 5-year retention of configuration changes and identity verification of administrators.
*   **PIPEDA:** User data returned by the API is minimized. Sensitive fields (SIN, DOB) are never exposed via the list endpoints.

## Usage Example

To create a new lender product via the Python client:

```python
import httpx

async def create_product():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.mortgage-system.com/api/v1/admin/lenders/101/products",
            headers={"Authorization": "Bearer <token>"},
            json={
                "name": "3-Year Variable",
                "type": "variable",
                "rate": "5.10",
                "max_ltv": "80.00",
                "term_months": 36
            }
        )
        response.raise_for_status()
        return response.json()
```

## CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Admin Panel: New endpoints for User Management (list, deactivate, role change)
- Admin Panel: New endpoints for Lender and Product Management (CRUD)
- Audit Log Model: Implemented immutable audit trail for all admin actions
- Documentation: API usage guide for Admin Panel

### Changed
- N/A

### Fixed
- N/A
```

## .env.example

```bash
# Admin Panel Configuration
# Default role assigned to the first provisioned system user
DEFAULT_ADMIN_ROLE=admin

# IP Whitelist for Admin Endpoints (Optional, comma-separated)
# ADMIN_IP_WHITELIST=127.0.0.1,10.0.0.1
```