# Admin Panel API

## GET /api/v1/admin/users

List all users in the system.

**Request:**
```json
// No body required
// Query params: ?limit=50&offset=0&active=true
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
  "limit": 50,
  "offset": 0
}
```

**Errors:**
- 401: Not authenticated
- 403: Insufficient permissions (Admin role required)

---

## PUT /api/v1/admin/users/{id}/deactivate

Deactivate a specific user account. This action is irreversible via this endpoint and logs an audit trail.

**Request:**
```json
{
  "reason": "Violation of security policy"
}
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
- 400: Invalid reason provided
- 401: Not authenticated
- 403: Insufficient permissions
- 404: User not found

---

## PUT /api/v1/admin/users/{id}/role

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
  "id": 1,
  "role": "admin",
  "updated_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 400: Invalid role value
- 401: Not authenticated
- 403: Insufficient permissions
- 404: User not found

---

## POST /api/v1/admin/lenders

Create a new lending institution.

**Request:**
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
- 400: Invalid input data
- 401: Not authenticated
- 409: Lender code already exists

---

## PUT /api/v1/admin/lenders/{id}

Update details for an existing lender.

**Request:**
```json
{
  "contact_email": "updated@fnb.com"
}
```

**Response (200):**
```json
{
  "id": 10,
  "name": "First National Bank",
  "code": "FNB001",
  "contact_email": "updated@fnb.com",
  "updated_at": "2026-03-02T09:15:00Z"
}
```

**Errors:**
- 400: Invalid input data
- 401: Not authenticated
- 404: Lender not found

---

## POST /api/v1/admin/lenders/{id}/products

Add a new mortgage product to a lender's portfolio.

**Request:**
```json
{
  "name": "5-Year Fixed",
  "type": "fixed",
  "interest_rate": "5.24",
  "max_ltv": "80.00",
  "max_amortization_months": 300
}
```

**Response (201):**
```json
{
  "id": 55,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "type": "fixed",
  "interest_rate": "5.24",
  "max_ltv": "80.00",
  "max_amortization_months": 300,
  "created_at": "2026-03-02T09:30:00Z"
}
```

**Errors:**
- 400: Invalid financial values (must be Decimal)
- 401: Not authenticated
- 404: Lender not found

---

## PUT /api/v1/admin/lenders/{id}/products/{product_id}

Update an existing mortgage product.

**Request:**
```json
{
  "interest_rate": "5.15",
  "max_ltv": "85.00"
}
```

**Response (200):**
```json
{
  "id": 55,
  "lender_id": 10,
  "name": "5-Year Fixed",
  "interest_rate": "5.15",
  "max_ltv": "85.00",
  "updated_at": "2026-03-02T09:45:00Z"
}
```

**Errors:**
- 400: Invalid financial values (must be Decimal)
- 401: Not authenticated
- 404: Lender or Product not found

---

# Admin Panel Module

## Overview
The Admin Panel module provides the necessary interfaces for system administrators to manage users, roles, lenders, and mortgage products. It serves as the central control point for configuration and access control within the Canadian Mortgage Underwriting System.

## Key Functions

### User Management
- **Listing Users:** Retrieve paginated lists of users with filtering capabilities.
- **Deactivation:** Securely disable user accounts. This action prevents login but preserves data for audit purposes.
- **Role Assignment:** Modify user permissions (e.g., promoting a user to `admin` or `underwriter`).

### Lender & Product Management
- **Lender CRUD:** Create and update lending institution profiles.
- **Product Configuration:** Define mortgage products including interest rates (stored as `Decimal`), LTV limits, and amortization periods.

### Audit & Compliance
All actions performed through the Admin Panel are logged to the `audit_logs` table to satisfy **FINTRAC** regulatory requirements.
- **Immutable Trail:** Records include `user_id`, `action`, `entity_type`, `old_value`, `new_value`, `ip_address`, and `user_agent`.
- **Retention:** Logs are retained for 5 years.

## Usage Example

To update a mortgage product rate via the API:

```python
import httpx

async def update_product_rate():
    async with httpx.AsyncClient() as client:
        response = await client.put(
            "http://api/v1/admin/lenders/10/products/55",
            json={"interest_rate": "5.49"},
            headers={"Authorization": "Bearer <admin_token>"}
        )
        response.raise_for_status()
        return response.json()
```

## Configuration Notes

Ensure the following environment variables are configured in `.env`:

```bash
# Admin Panel Configuration
# The email address of the initial super admin (created on first run)
DEFAULT_ADMIN_EMAIL=admin@mortgage-system.ca

# Audit Log Retention (Days) - FINTRAC Compliance
# Minimum 1825 days (5 years)
AUDIT_LOG_RETENTION_DAYS=1825
```