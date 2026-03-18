# Design: Admin Panel
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Admin Panel Module Design Plan

**Module Identifier:** `admin_panel`  
**Design Document:** `docs/design/admin-panel.md`  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### 1.1 User Management

#### `GET /api/v1/admin/users`
List all users with pagination and filtering.

**Authentication:** `admin-only` (requires `admin` or `super_admin` role)  
**Request Query Parameters:**
```python
{
    "page": int = 1,           # optional, min 1
    "page_size": int = 50,     # optional, min 1, max 200
    "role": str | None,        # optional filter: "applicant", "underwriter", "admin"
    "is_active": bool | None,  # optional filter
    "search": str | None       # optional: email or name substring
}
```

**Response Schema (200):**
```python
{
    "items": [
        {
            "id": UUID,
            "email": str,
            "first_name": str,
            "last_name": str,
            "role": str,           # "applicant", "underwriter", "admin", "super_admin"
            "is_active": bool,
            "last_login_at": datetime | None,
            "created_at": datetime
        }
    ],
    "total": int,
    "page": int,
    "page_size": int
}
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid JWT token
- `403 Forbidden` - Insufficient privileges (error_code: `ADMIN_001`)
- `422 ValidationError` - Invalid query parameters (error_code: `ADMIN_002`)

---

#### `PUT /api/v1/admin/users/{id}/deactivate`
Deactivate a user account (soft delete).

**Authentication:** `admin-only` (requires `super_admin` role for deactivating other admins)  
**Path Parameter:** `id: UUID` - User ID to deactivate  
**Request Body:**
```python
{
    "reason": str,             # required, min_length=10, max_length=500
    "deactivate_after_hours": int = 24  # optional, grace period
}
```

**Response Schema (200):**
```python
{
    "id": UUID,
    "email": str,
    "is_active": false,
    "deactivated_at": datetime,
    "deactivated_by": UUID,    # Admin user ID performing action
    "deactivation_reason": str
}
```

**Error Responses:**
- `400 Bad Request` - Cannot deactivate self (error_code: `ADMIN_003`)
- `404 NotFoundError` - User not found (error_code: `ADMIN_004`)
- `409 Conflict` - User already deactivated (error_code: `ADMIN_005`)
- `403 Forbidden` - Attempting to deactivate super_admin without super_admin role (error_code: `ADMIN_006`)

---

#### `PUT /api/v1/admin/users/{id}/role`
Change user role with approval workflow for sensitive escalations.

**Authentication:** `admin-only` (requires `super_admin` for `admin` role assignments)  
**Path Parameter:** `id: UUID` - User ID  
**Request Body:**
```python
{
    "new_role": str,           # required: "applicant", "underwriter", "admin"
    "justification": str,      # required if new_role == "admin", min_length=20
    "require_approval": bool   # auto-set true if promoting to admin
}
```

**Response Schema (202 Accepted):**
```python
{
    "request_id": UUID,
    "status": "pending_approval" | "completed",
    "user_id": UUID,
    "new_role": str,
    "requires_approval": bool,
    "approved_by": UUID | None,
    "approved_at": datetime | None
}
```

**Error Responses:**
- `400 Bad Request` - Invalid role transition (error_code: `ADMIN_007`)
- `404 NotFoundError` - User not found (error_code: `ADMIN_004`)
- `422 ValidationError` - Missing justification (error_code: `ADMIN_002`)
- `403 Forbidden` - Insufficient privileges (error_code: `ADMIN_001`)

---

### 1.2 Lender Management

#### `POST /api/v1/admin/lenders`
Create a new lender institution.

**Authentication:** `admin-only` (requires `admin` role minimum)  
**Request Body:**
```python
{
    "legal_name": str,         # required, max_length=255
    "short_name": str,         # required, max_length=50
    "lender_code": str,        # required, unique, regex: ^[A-Z]{3,6}$
    "address": {
        "street": str,
        "city": str,
        "province": str,       # 2-letter code
        "postal_code": str,
        "country": str = "CA"
    },
    "contact_email": str,      # email format
    "is_active": bool = true
}
```

**Response Schema (201):**
```python
{
    "id": UUID,
    "legal_name": str,
    "short_name": str,
    "lender_code": str,
    "address": dict,
    "contact_email": str,
    "is_active": bool,
    "created_at": datetime,
    "created_by": UUID
}
```

**Error Responses:**
- `409 Conflict` - lender_code already exists (error_code: `ADMIN_008`)
- `422 ValidationError` - Invalid address format (error_code: `ADMIN_002`)

---

#### `PUT /api/v1/admin/lenders/{id}`
Update lender details.

**Authentication:** `admin-only`  
**Path Parameter:** `id: UUID` - Lender ID  
**Request Body:** Same as POST (all fields optional except lender_code immutable)

**Response Schema (200):** Same as POST response

**Error Responses:**
- `404 NotFoundError` - Lender not found (error_code: `ADMIN_009`)
- `400 Bad Request` - Attempting to modify lender_code (error_code: `ADMIN_010`)

---

#### `POST /api/v1/admin/lenders/{id}/products`
Add a mortgage product to a lender.

**Authentication:** `admin-only`  
**Path Parameter:** `id: UUID` - Lender ID  
**Request Body:**
```python
{
    "product_name": str,       # required
    "product_code": str,       # required, unique per lender
    "product_type": str,       # required: "fixed", "variable", "hybrid"
    "interest_rate": Decimal,  # required, precision=5, scale=4 (e.g., 5.2500)
    "rate_type": str,          # "annual_nominal"
    "amortization_max_years": int,  # required, max 30
    "loan_to_value_max": Decimal,   # required, precision=5, scale=2
    "debt_service_ratios": {
        "gds_max": Decimal = 0.39,    # OSFI B-20 compliance
        "tds_max": Decimal = 0.44
    },
    "insurance_required": bool,  # CMHC: auto-calculated if LTV > 80%
    "premium_tiers": [         # CMHC premium structure
        {
            "ltv_min": Decimal,
            "ltv_max": Decimal,
            "premium_rate": Decimal
        }
    ],
    "is_active": bool = true
}
```

**Response Schema (201):**
```python
{
    "id": UUID,
    "lender_id": UUID,
    "product_name": str,
    "product_code": str,
    "product_type": str,
    "interest_rate": Decimal,
    "amortization_max_years": int,
    "loan_to_value_max": Decimal,
    "debt_service_ratios": dict,
    "insurance_required": bool,
    "premium_tiers": list,
    "is_active": bool,
    "created_at": datetime,
    "created_by": UUID
}
```

**Error Responses:**
- `404 NotFoundError` - Lender not found (error_code: `ADMIN_009`)
- `409 Conflict` - product_code already exists for lender (error_code: `ADMIN_011`)
- `422 ValidationError` - insurance_required mismatch with LTV > 80% (error_code: `ADMIN_012`)

---

#### `PUT /api/v1/admin/lenders/{id}/products/{prod_id}`
Update mortgage product details.

**Authentication:** `admin-only`  
**Path Parameters:** `id: UUID`, `prod_id: UUID`  
**Request Body:** Same as POST (all fields optional, product_code immutable)

**Response Schema (200):** Same as POST response

**Error Responses:**
- `404 NotFoundError` - Lender or product not found (error_code: `ADMIN_013`)
- `400 Bad Request` - Rate change requires audit justification > $10,000 impact (error_code: `ADMIN_014`)

---

#### `DELETE /api/v1/admin/lenders/{id}/products/{prod_id}`
Deactivate a mortgage product (soft delete).

**Authentication:** `admin-only`  
**Path Parameters:** `id: UUID`, `prod_id: UUID`  
**Request Body:**
```python
{
    "deactivation_reason": str,  # required
    "effective_date": date       # optional, defaults to today
}
```

**Response Schema (200):**
```python
{
    "id": UUID,
    "product_code": str,
    "is_active": false,
    "deactivated_at": datetime,
    "deactivated_by": UUID
}
```

**Error Responses:**
- `404 NotFoundError` - Product not found (error_code: `ADMIN_013`)
- `409 Conflict` - Product already deactivated (error_code: `ADMIN_015`)

---

### 1.3 Audit & Compliance

#### `GET /api/v1/admin/audit-logs`
View audit logs with FINTRAC-compliant filtering.

**Authentication:** `admin-only`  
**Request Query Parameters:**
```python
{
    "page": int = 1,
    "page_size": int = 100,    # max 1000 for FINTRAC exports
    "entity_type": str | None,  # e.g., "application", "user", "lender_product"
    "entity_id": UUID | None,
    "action": str | None,      # e.g., "status_change", "rate_update"
    "user_id": UUID | None,
    "date_from": datetime | None,
    "date_to": datetime | None,
    "ip_address": str | None
}
```

**Response Schema (200):**
```python
{
    "items": [
        {
            "id": UUID,
            "user_id": UUID,
            "user_email": str,     # PIPEDA: only show to authorized admins
            "action": str,
            "entity_type": str,
            "entity_id": UUID,
            "old_value": dict | None,
            "new_value": dict | None,
            "ip_address": str,
            "user_agent": str,
            "created_at": datetime
        }
    ],
    "total": int,
    "retention_until": date    # FINTRAC: 5-year retention marker
}
```

**Error Responses:**
- `403 Forbidden` - Missing `audit_viewer` permission (error_code: `ADMIN_016`)
- `422 ValidationError` - Date range exceeds FINTRAC export limit (error_code: `ADMIN_017`)

---

#### `GET /api/v1/admin/fintrac/reports`
Generate FINTRAC compliance reports for large transactions.

**Authentication:** `admin-only` (requires `compliance_officer` role)  
**Request Query Parameters:**
```python
{
    "report_type": str,        # required: "large_cash", "suspicious", "electronic_funds"
    "date_from": date,         # required
    "date_to": date,           # required, max 90-day range
    "format": str = "json"     # optional: "json", "csv", "fintrac_xml"
}
```

**Response Schema (200):**
```python
{
    "report_id": UUID,
    "report_type": str,
    "date_range": {
        "from": date,
        "to": date
    },
    "generated_at": datetime,
    "total_records": int,
    "total_amount": Decimal,   # FINTRAC: sum of all transactions > $10,000
    "records": [
        {
            "transaction_id": UUID,
            "applicant_hash": str,     # SHA256 of SIN for FINTRAC
            "transaction_date": datetime,
            "amount": Decimal,
            "transaction_type": str,
            "property_address": str    # PIPEDA: minimal data only
        }
    ]
}
```

**Error Responses:**
- `403 Forbidden` - Not a compliance officer (error_code: `ADMIN_018`)
- `400 Bad Request` - Date range > 90 days (error_code: `ADMIN_019`)
- `422 ValidationError` - Invalid report type (error_code: `ADMIN_002`)

---

## 2. Models & Database

### 2.1 Core Models

```python
# modules/admin_panel/models.py

from sqlalchemy import (
    Column, UUID, String, JSON, DateTime, Boolean, ForeignKey, Index, Numeric
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql import func
from common.database import Base

class AuditLog(Base):
    """Immutable audit trail for all admin and system actions."""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Action metadata
    action = Column(String(50), nullable=False, index=True)  # e.g., "user_deactivate", "product_rate_update"
    entity_type = Column(String(50), nullable=False, index=True)  # e.g., "application", "lender_product"
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Immutable data snapshots (FINTRAC compliance)
    old_value = Column(JSON, nullable=True)  # Before state
    new_value = Column(JSON, nullable=True)  # After state
    
    # Request metadata (PIPEDA: IP tracking)
    ip_address = Column(INET, nullable=False)
    user_agent = Column(String(500), nullable=True)
    
    # CMHC/OSFI: Track financial impact for rate changes
    financial_impact_amount = Column(Numeric(precision=12, scale=2), nullable=True)
    
    # Audit fields (FINTRAC 5-year retention)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Indexes for FINTRAC queries
    __table_args__ = (
        Index('idx_audit_logs_fintrac', 'entity_type', 'created_at', 
              postgresql_where=(Column('financial_impact_amount') >= 10000)),
        Index('idx_audit_logs_user_timeline', 'user_id', 'created_at'),
        Index('idx_audit_logs_entity_lookup', 'entity_type', 'entity_id', 'created_at'),
    )

class AdminApprovalRequest(Base):
    """Two-step approval workflow for sensitive admin actions."""
    __tablename__ = "admin_approval_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    action_type = Column(String(50), nullable=False)  # e.g., "user_promote_to_admin"
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    
    request_payload = Column(JSON, nullable=False)  # Stashed parameters
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index('idx_approval_pending', 'status', 'created_at', 
              postgresql_where=(Column('status') == 'pending')),
    )

# Existing models extended via migrations:
# - users: add column is_active (Boolean, default true)
# - users: add column deactivated_at (DateTime, nullable)
# - users: add column deactivated_by (UUID, ForeignKey, nullable)
# - lender_products: add column is_active (Boolean, default true)
# - lender_products: add column deactivated_at (DateTime, nullable)
```

### 2.2 Encryption & PIPEDA Compliance

- **AuditLog.user_agent**: Logged for security but truncated to 500 chars to minimize PII
- **IP addresses**: Stored as INET type for geolocation analysis; retained per FINTRAC 5-year policy
- **No SIN/DOB in logs**: `entity_id` uses UUID references; `old_value`/`new_value` must be scrubbed of PII before insertion
- **AdminApprovalRequest.request_payload**: Must be sanitized by service layer to exclude PII

---

## 3. Business Logic

### 3.1 Approval Workflow Engine

**Sensitive Actions Requiring Approval:**
```python
APPROVAL_REQUIRED_ACTIONS = {
    "user_promote_to_admin": {
        "min_approver_role": "super_admin",
        "auto_approve_if": lambda user: user.role != "admin",
        "notification_channels": ["email", "slack_security_channel"]
    },
    "lender_product_rate_update": {
        "min_approver_role": "admin",
        "requires_justification": True,
        "financial_threshold": Decimal("10000.00"),  # FINTRAC trigger
        "notification_channels": ["email", "audit_log"]
    },
    "uw_decision_override": {
        "min_approver_role": "admin",
        "requires_application_lock": True,
        "notification_recipients": ["compliance_team", "original_underwriter"]
    }
}
```

**Workflow Steps:**
1. **Request Phase**: Admin submits action; system creates `AdminApprovalRequest` with `status='pending'`
2. **Validation Phase**: Service layer checks `APPROVAL_REQUIRED_ACTIONS` rules
3. **Notification Phase**: If threshold met, send real-time alert to security team
4. **Approval Phase**: Approver reviews in Admin UI; on approval, execute action and log to `audit_logs`
5. **Rejection Phase**: Log rejection reason; notify requester
6. **Auto-Expiration**: Pending requests > 7 days auto-reject via background job

### 3.2 Audit Log Retention Policy

```python
# FINTRAC 5-year retention with tiered storage
RETENTION_POLICY = {
    "fintrac_related": {
        "hot_storage_days": 365,      # PostgreSQL
        "warm_storage_days": 1460,    # S3 Glacier Instant
        "cold_storage_years": 5,      # S3 Glacier Deep Archive
        "deletion_after_years": 5     # Permanent deletion post-FINTRAC
    },
    "standard_admin": {
        "hot_storage_days": 90,
        "warm_storage_days": 365,
        "deletion_after_days": 365    # Non-regulatory logs
    }
}

# Automatic archival job runs monthly:
# - Moves logs > 1 year old to S3 (encrypted with AES-256)
# - Updates audit_logs.archived_at timestamp
# - Maintains searchable metadata in PostgreSQL
```

### 3.3 Rate Change Impact Calculation

**OSFI B-20 & CMHC Compliance Check:**
```python
async def calculate_rate_change_impact(
    product_id: UUID, 
    new_rate: Decimal
) -> Decimal:
    """
    Calculate financial impact of rate change across all active applications.
    Triggers FINTRAC reporting if aggregate impact > $10,000.
    """
    # 1. Fetch all applications using this product (not closed)
    # 2. For each application, recalculate:
    #    - Monthly payment difference: ΔP = P_new - P_old
    #    - GDS/TDS stress test: qualifying_rate = max(new_rate + 2%, 5.25%)
    #    - Insurance premium if LTV > 80% (CMHC tiers)
    # 3. Sum absolute impact across all applications
    # 4. If total_impact >= 10000, set AuditLog.financial_impact_amount
    
    # Returns total impact for audit logging
    pass
```

### 3.4 User Activity Dashboard Metrics

**Real-time Metrics Cache (Redis TTL: 5 min):**
- Active admin sessions in last 15 minutes
- Pending approval requests count
- Rate changes today with >$10k impact
- FINTRAC reportable transactions (last 24h)
- Failed admin login attempts by IP

**Aggregated Metrics (PostgreSQL materialized view, refreshed hourly):**
```sql
CREATE MATERIALIZED VIEW admin_dashboard_metrics AS
SELECT 
    date_trunc('hour', created_at) as hour,
    entity_type,
    action,
    COUNT(*) as action_count,
    SUM(CASE WHEN financial_impact_amount >= 10000 THEN 1 ELSE 0 END) as fintrac_triggers
FROM audit_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY hour, entity_type, action;
```

---

## 4. Migrations

### 4.1 New Tables

```python
# migrations/versions/2024_01_15_add_admin_panel.py

def upgrade():
    # audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', UUID(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', UUID(), nullable=False),
        sa.Column('old_value', JSONB(), nullable=True),
        sa.Column('new_value', JSONB(), nullable=True),
        sa.Column('ip_address', INET(), nullable=False),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('financial_impact_amount', Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Composite indexes for FINTRAC queries
    op.create_index('idx_audit_logs_fintrac', 'audit_logs', 
                    ['entity_type', 'created_at'], 
                    postgresql_where=sa.text('financial_impact_amount >= 10000'))
    op.create_index('idx_audit_logs_user_timeline', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('idx_audit_logs_entity_lookup', 'audit_logs', ['entity_type', 'entity_id', 'created_at'])
    
    # admin_approval_requests table
    op.create_table(
        'admin_approval_requests',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('requester_id', UUID(), nullable=False),
        sa.Column('approver_id', UUID(), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', UUID(), nullable=False),
        sa.Column('request_payload', JSONB(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('approved_at', DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_approval_pending', 'admin_approval_requests', 
                    ['status', 'created_at'], 
                    postgresql_where=sa.text("status = 'pending'"))

def downgrade():
    op.drop_table('admin_approval_requests')
    op.drop_table('audit_logs')
```

### 4.2 Existing Table Modifications

```python
# Add soft-delete and audit fields to users table
op.add_column('users', sa.Column('is_active', Boolean(), server_default='true', nullable=False))
op.add_column('users', sa.Column('deactivated_at', DateTime(timezone=True), nullable=True))
op.add_column('users', sa.Column('deactivated_by', UUID(), nullable=True))
op.create_foreign_key('fk_users_deactivated_by', 'users', 'users', ['deactivated_by'], ['id'])

# Add soft-delete to lender_products table
op.add_column('lender_products', sa.Column('is_active', Boolean(), server_default='true', nullable=False))
op.add_column('lender_products', sa.Column('deactivated_at', DateTime(timezone=True), nullable=True))
op.add_column('lender_products', sa.Column('deactivated_by', UUID(), nullable=True))
op.create_foreign_key('fk_lender_products_deactivated_by', 'lender_products', 'users', ['deactivated_by'], ['id'])

# Add rate history tracking
op.add_column('lender_products', sa.Column('rate_last_changed_at', DateTime(timezone=True), nullable=True))
op.add_column('lender_products', sa.Column('rate_last_changed_by', UUID(), nullable=True))
```

---

## 5. Security & Compliance

### 5.1 Authentication & Authorization

**JWT Claims Required:**
```json
{
  "sub": "user_uuid",
  "role": "admin",
  "mfa_verified": true,
  "ip_whitelisted": true,
  "permissions": ["admin:read", "admin:write", "audit:view", "fintrac:report"]
}
```

**Role Hierarchy:**
- `super_admin`: Full access, can manage other admins, override any approval
- `admin`: Standard admin access, can manage users/products, requires approval for sensitive actions
- `compliance_officer`: Read-only access to audit logs and FINTRAC reports
- `auditor_viewer`: Read-only access to audit logs (no FINTRAC)

**IP Whitelisting:** Admin endpoints check `common/config.py` `ADMIN_IP_WHITELIST` (CIDR blocks). Enforced at middleware level.

**MFA Enforcement:** All `/admin/*` endpoints require `mfa_verified: true` claim. Middleware returns `403` if missing.

### 5.2 OSFI B-20 Requirements

- **Rate Update Logging**: All `lender_product` rate changes must calculate stress test impact using `qualifying_rate = max(new_rate + 2%, 5.25%)` and validate GDS/TDS ≤ limits
- **GDS/TDS Recalculation**: When rates change, system enqueues background job to flag applications that would exceed 39%/44% ratios
- **Audit Trail**: `AuditLog.action = "lender_rate_update"` must include `old_value` and `new_value` with full rate structure for examiner review

### 5.3 FINTRAC Compliance

- **Large Transaction Flagging**: `AuditLog.financial_impact_amount` populated for any action affecting > CAD $10,000 in aggregate
- **Immutable Records**: `audit_logs` table has no UPDATE or DELETE operations allowed. Row-level security policy:
  ```sql
  CREATE POLICY audit_immutable ON audit_logs FOR UPDATE USING (false);
  CREATE POLICY audit_no_delete ON audit_logs FOR DELETE USING (false);
  ```
- **5-Year Retention**: Materialized view `fintrac_retention_schedule` tracks deletion eligibility. Monthly job archives to S3 with tamper-evident signatures.
- **Report Generation**: `/admin/fintrac/reports` endpoint produces XML in FINTRAC F2R format for direct submission

### 5.4 PIPEDA Data Handling

- **Data Minimization**: `AuditLog.user_agent` truncated; IP addresses anonymized after 30 days (last octet zeroed) unless FINTRAC-related
- **PII Scrubbing**: Service layer sanitizes `old_value`/`new_value` to remove:
  - `sin`, `dob`, `bank_account`, `income` fields
  - Replaces with `sha256_hash` for correlation only
- **Access Logging**: Every access to `/admin/audit-logs` is itself audited with `action = "audit_log_viewed"`

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```python
# modules/admin_panel/exceptions.py

class AdminPanelException(AppException):
    """Base exception for admin panel module."""
    module_code = "ADMIN"

class AdminAuthorizationError(AdminPanelException):
    """Insufficient privileges or MFA not verified."""
    http_status = 403
    error_code = "ADMIN_001"
    message_template = "Admin access denied: {detail}"

class AdminValidationError(AdminPanelException):
    """Invalid input parameters."""
    http_status = 422
    error_code = "ADMIN_002"
    message_template = "Validation failed: {field} - {reason}"

class AdminSelfActionError(AdminPanelException):
    """Prevent admins from modifying own account."""
    http_status = 400
    error_code = "ADMIN_003"
    message_template = "Cannot perform {action} on your own account"

class UserNotFoundError(AdminPanelException):
    """Target user does not exist."""
    http_status = 404
    error_code = "ADMIN_004"
    message_template = "User {user_id} not found"

class UserAlreadyInactiveError(AdminPanelException):
    """User already deactivated."""
    http_status = 409
    error_code = "ADMIN_005"
    message_template = "User {user_id} already deactivated"

class RoleAssignmentForbiddenError(AdminPanelException):
    """Insufficient role to assign target role."""
    http_status = 403
    error_code = "ADMIN_006"
    message_template = "Cannot assign role {target_role} with current privileges"

class InvalidRoleTransitionError(AdminPanelException):
    """Illegal role state change."""
    http_status = 400
    error_code = "ADMIN_007"
    message_template = "Invalid role transition: {from_role} → {to_role}"

class LenderCodeConflictError(AdminPanelException):
    """Lender code already exists."""
    http_status = 409
    error_code = "ADMIN_008"
    message_template = "Lender code '{code}' already in use"

class LenderNotFoundError(AdminPanelException):
    """Lender institution not found."""
    http_status = 404
    error_code = "ADMIN_009"
    message_template = "Lender {lender_id} not found"

class LenderCodeImmutableError(AdminPanelException):
    """Attempting to change immutable lender_code."""
    http_status = 400
    error_code = "ADMIN_010"
    message_template = "lender_code cannot be modified after creation"

class ProductCodeConflictError(AdminPanelException):
    """Product code already exists for lender."""
    http_status = 409
    error_code = "ADMIN_011"
    message_template = "Product code '{code}' already exists for lender {lender_id}"

class InsuranceRequirementMismatchError(AdminPanelException):
    """CMHC: insurance_required flag inconsistent with LTV."""
    http_status = 422
    error_code = "ADMIN_012"
    message_template = "LTV > 80% requires insurance_required=True per CMHC guidelines"

class ProductNotFoundError(AdminPanelException):
    """Lender product not found."""
    http_status = 404
    error_code = "ADMIN_013"
    message_template = "Product {product_id} not found for lender {lender_id}"

class RateChangeJustificationRequiredError(AdminPanelException):
    """FINTRAC: Rate change impact exceeds threshold."""
    http_status = 400
    error_code = "ADMIN_014"
    message_template = "Rate change impact ${impact} exceeds $10,000 threshold. Provide detailed justification."

class ProductAlreadyDeactivatedError(AdminPanelException):
    """Product already inactive."""
    http_status = 409
    error_code = "ADMIN_015"
    message_template = "Product {product_id} already deactivated"

class AuditAccessDeniedError(AdminPanelException):
    """Missing audit viewer permission."""
    http_status = 403
    error_code = "ADMIN_016"
    message_template = "Missing audit:view permission"

class FintracDateRangeExceededError(AdminPanelException):
    """FINTRAC export range too large."""
    http_status = 422
    error_code = "ADMIN_017"
    message_template = "FINTRAC report date range cannot exceed 90 days"

class ComplianceRoleRequiredError(AdminPanelException):
    """FINTRAC report requires compliance officer role."""
    http_status = 403
    error_code = "ADMIN_018"
    message_template = "FINTRAC reports require compliance_officer role"

class InvalidFintracReportTypeError(AdminPanelException):
    """Invalid FINTRAC report type."""
    http_status = 400
    error_code = "ADMIN_019"
    message_template = "Invalid FINTRAC report type: {report_type}"
```

### 6.2 Error Response Format

All errors return structured JSON:
```json
{
  "detail": "User 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "ADMIN_004",
  "module": "admin_panel",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req_abc123def456",
  "request_id": "req_abc123def456"
}
```

---

## 7. Missing Details Resolution

### 7.1 Admin Authorization Scope Definition
**Resolution:** Implement RBAC with permissions matrix stored in `common/config.py`. Scope definitions:
- `admin:read` - View users, lenders, products
- `admin:write` - Modify users, lenders, products
- `admin:super` - Manage admins, bypass approvals
- `audit:view` - View audit logs
- `fintrac:report` - Generate FINTRAC reports

### 7.2 Audit Log Retention Policy
**Resolution:** See Section 3.2. Implement `AdminRetentionService` with methods:
- `archive_to_s3(cutoff_date)` - Moves cold logs
- `generate_retention_report()` - For OSFI examinations
- `delete_expired()` - Post-5-year cleanup

### 7.3 Admin Action Approval Workflow
**Resolution:** See Section 3.1. UI will show pending requests in admin dashboard with approve/reject buttons. Email notifications use `common/security.py:send_admin_alert()`.

### 7.4 User Activity Dashboard Design
**Resolution:** Endpoint `GET /api/v1/admin/dashboard/metrics` returns:
```python
{
    "active_sessions": int,
    "pending_approvals": int,
    "fintrac_triggers_24h": int,
    "rate_changes_today": int,
    "failed_logins_15m": int,
    "system_health": {
        "db_latency_ms": float,
        "last_backup_hours_ago": float
    }
}
```

### 7.5 System Health Monitoring Integration
**Resolution:** Admin panel integrates with Prometheus metrics:
- `admin_actions_total{action, status}` counter
- `admin_approval_pending_gauge` current pending count
- `audit_log_insert_errors_total` counter
- `fintrac_report_generation_duration_seconds` histogram

### 7.6 Sensitive Action Notification Recipients
**Resolution:** Configurable in `common/config.py`:
```python
ADMIN_NOTIFICATIONS = {
    "rate_change_over_10k": ["compliance@lender.ca", "risk-team@lender.ca"],
    "user_promote_to_admin": ["security@lender.ca"],
    "uw_override": ["compliance_officer", "audit_team"],
    "failed_admin_login": ["security@lender.ca", "soc@lender.ca"]
}
```

---

**Next Steps:** Implementation tickets to be created for each service layer method and endpoint handler. Priority: FINTRAC compliance and audit log immutability first.