# Design: Admin Panel
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Admin Panel Module Design Plan

**Module Identifier:** `admin`  
**Design Document:** `docs/design/admin-panel.md`

---

## 1. Endpoints

### 1.1 User Management

#### `GET /api/v1/admin/users`
- **Auth:** Admin-only (`admin:read` scope)
- **Query Params:**
  - `page` (int, optional, default=1)
  - `limit` (int, optional, default=50, max=200)
  - `status` (enum: active, inactive, pending, optional)
  - `role` (str, optional)
  - `search` (str, optional) - searches email, name
- **Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "first_name": "Jane",
      "last_name": "Doe",
      "role": "underwriter",
      "status": "active",
      "last_login_at": "2024-01-15T10:30:00Z",
      "created_at": "2023-06-01T08:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 50
}
```
- **Errors:**
  - `401 Unauthorized` - Missing/invalid token
  - `403 Forbidden` - Insufficient permissions
  - `422 ValidationError` - Invalid query parameters

#### `PUT /api/v1/admin/users/{id}/deactivate`
- **Auth:** Admin-only (`admin:write` scope)
- **Path Param:** `id` (uuid, required)
- **Request Body:**
```json
{
  "reason": "string (max 500 chars, required)",
  "notify_user": "bool (default=true)"
}
```
- **Response 200:**
```json
{
  "id": "uuid",
  "status": "inactive",
  "deactivated_at": "2024-01-15T10:30:00Z",
  "deactivated_by": "admin_uuid"
}
```
- **Errors:**
  - `404 AdminUserNotFoundError` - User not found
  - `409 AdminBusinessRuleError` - Cannot deactivate self or last admin
  - `422 ValidationError` - Invalid reason length

#### `PUT /api/v1/admin/users/{id}/role`
- **Auth:** Admin-only (`admin:write` scope)
- **Path Param:** `id` (uuid, required)
- **Request Body:**
```json
{
  "new_role": "enum[admin, underwriter, read_only]",
  "justification": "string (max 500 chars, required)"
}
```
- **Response 200:**
```json
{
  "id": "uuid",
  "previous_role": "underwriter",
  "new_role": "admin",
  "changed_at": "2024-01-15T10:30:00Z",
  "changed_by": "admin_uuid"
}
```
- **Errors:**
  - `404 AdminUserNotFoundError` - User not found
  - `409 AdminBusinessRuleError` - Insufficient privileges to grant role
  - `422 ValidationError` - Invalid role or justification

### 1.2 Lender Management

#### `POST /api/v1/admin/lenders`
- **Auth:** Admin-only (`admin:write` scope)
- **Request Body:**
```json
{
  "legal_name": "string (required, max 255)",
  "operating_name": "string (optional, max 255)",
  "lender_code": "string (required, unique, max 50)",
  "contact_email": "email (required)",
  "contact_phone": "string (max 20)",
  "address": {
    "street": "string (required)",
    "city": "string (required)",
    "province": "enum[AB, BC, MB, ...] (required)",
    "postal_code": "string (required)",
    "country": "string (default=CA)"
  },
  "is_active": "bool (default=true)"
}
```
- **Response 201:**
```json
{
  "id": "uuid",
  "legal_name": "ABC Lending Corp",
  "lender_code": "ABC123",
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z"
}
```
- **Errors:**
  - `409 AdminBusinessRuleError` - Lender code already exists
  - `422 ValidationError` - Invalid address format or lender code

#### `PUT /api/v1/admin/lenders/{id}`
- **Auth:** Admin-only (`admin:write` scope)
- **Path Param:** `id` (uuid, required)
- **Request Body:** Same as POST, all fields optional
- **Response 200:** Updated lender object
- **Errors:**
  - `404 AdminLenderNotFoundError` - Lender not found
  - `409 AdminBusinessRuleError` - Cannot modify inactive lender

### 1.3 Product Management

#### `POST /api/v1/admin/lenders/{id}/products`
- **Auth:** Admin-only (`admin:write` scope)
- **Path Param:** `id` (lender_id, uuid)
- **Request Body:**
```json
{
  "product_name": "string (required, max 255)",
  "product_code": "string (required, max 50)",
  "product_type": "enum[fixed, variable, hybrid] (required)",
  "min_rate": "Decimal (string, required, >= 0)",
  "max_rate": "Decimal (string, required, >= min_rate)",
  "default_rate": "Decimal (string, required)",
  "min_amortization_months": "int (required, >= 12)",
  "max_amortization_months": "int (required, <= 480)",
  "min_loan_amount": "Decimal (string, required, >= 0)",
  "max_loan_amount": "Decimal (string, required)",
  "max_ltv": "Decimal (string, required, <= 1.0)",
  "insurance_required": "bool (required)",
  "stress_test_rate": "Decimal (string, optional)",
  "is_active": "bool (default=true)"
}
```
- **Response 201:**
```json
{
  "id": "uuid",
  "product_name": "5-Year Fixed",
  "product_code": "5YF-2024",
  "lender_id": "uuid",
  "created_at": "2024-01-15T10:30:00Z"
}
```
- **Errors:**
  - `404 AdminLenderNotFoundError` - Lender not found
  - `409 AdminBusinessRuleError` - Product code already exists for lender
  - `422 ValidationError` - Rate/amount validations

#### `PUT /api/v1/admin/lenders/{id}/products/{prod_id}`
- **Auth:** Admin-only (`admin:write` scope)
- **Path Params:** `id` (lender_id), `prod_id` (product_id)
- **Request Body:** Partial product fields
- **Response 200:** Updated product object
- **Errors:**
  - `404 AdminProductNotFoundError` - Product not found
  - `409 AdminBusinessRuleError` - Rate change exceeds daily threshold

#### `DELETE /api/v1/admin/lenders/{id}/products/{prod_id}`
- **Auth:** Admin-only (`admin:write` scope)
- **Path Params:** `id` (lender_id), `prod_id` (product_id)
- **Response 204:** No content (soft delete)
- **Errors:**
  - `404 AdminProductNotFoundError` - Product not found
  - `409 AdminBusinessRuleError` - Product has active applications

### 1.4 Audit & Compliance

#### `GET /api/v1/admin/audit-logs`
- **Auth:** Admin-only (`admin:audit` scope)
- **Query Params:**
  - `page`, `limit` (pagination)
  - `user_id` (uuid, optional)
  - `action` (enum, optional)
  - `entity_type` (string, optional)
  - `entity_id` (uuid, optional)
  - `date_from`, `date_to` (ISO dates, optional)
- **Response 200:** Paginated audit log entries
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "user_email": "admin@example.com",
      "action": "user_role_changed",
      "entity_type": "user",
      "entity_id": "uuid",
      "old_value": {"role": "underwriter"},
      "new_value": {"role": "admin"},
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1250,
  "page": 1,
  "limit": 100
}
```

#### `GET /api/v1/admin/fintrac/reports`
- **Auth:** Admin-only (`admin:compliance` scope)
- **Query Params:**
  - `report_type` (enum: large_cash, suspicious, monthly_summary, required)
  - `start_date`, `end_date` (ISO dates, required)
  - `format` (enum: json, csv, xml, default=json)
- **Response 200:**
```json
{
  "report_id": "uuid",
  "report_type": "large_cash",
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "generated_at": "2024-01-15T10:30:00Z",
  "total_records": 45,
  "total_amount_cad": "1250000.00",
  "records": [
    {
      "transaction_id": "uuid",
      "transaction_date": "2024-01-10",
      "amount_cad": "15000.00",
      "transaction_type": "purchase",
      "applicant_name": "[ENCRYPTED]",
      "applicant_sin_hash": "sha256_hash",
      "property_address": "[REDACTED]"
    }
  ]
}
```
- **Errors:**
  - `400 AdminValidationError` - Date range exceeds 1 year
  - `422 ValidationError` - Invalid report type

---

## 2. Models & Database

### 2.1 Core Audit Log Model

**Table:** `audit_logs`
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    
    # JSONB for structured data comparison
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    # Client metadata
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True, index=True)  # IPv6 support
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, 
                                                  default=lambda: datetime.now(timezone.utc),
                                                  index=True)
    
    # Indexes
    __table_args__ = (
        # Composite index for entity lookup
        Index("idx_audit_entity_lookup", "entity_type", "entity_id"),
        # Composite index for time-range queries
        Index("idx_audit_user_time", "user_id", "created_at"),
        # Composite index for action filtering
        Index("idx_audit_action_time", "action", "created_at"),
    )
```

### 2.2 Related Models (Existing Tables - Reference)

**Table:** `users`
- Must have `role` (enum: admin, underwriter, read_only) and `status` (enum: active, inactive, pending)
- Must include `last_login_at`, `created_at`, `updated_at`

**Table:** `lenders`
```python
class Lender(Base):
    __tablename__ = "lenders"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operating_name: Mapped[str] = mapped_column(String(255), nullable=True)
    lender_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=...)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=..., onupdate=...)
```

**Table:** `lender_products`
```python
class LenderProduct(Base):
    __tablename__ = "lender_products"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    lender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lenders.id"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Financial fields - ALL Decimal
    min_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    max_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    default_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    stress_test_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)
    
    min_amortization_months: Mapped[int] = mapped_column(nullable=False)
    max_amortization_months: Mapped[int] = mapped_column(nullable=False)
    min_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    
    insurance_required: Mapped[bool] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=...)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=..., onupdate=...)
    
    __table_args__ = (
        UniqueConstraint("lender_id", "product_code", name="uq_lender_product_code"),
        Index("idx_product_lender_active", "lender_id", "is_active"),
    )
```

---

## 3. Business Logic

### 3.1 User Deactivation Service
```python
# Pseudo-code for business logic
async def deactivate_user(
    admin_user_id: UUID,
    target_user_id: UUID,
    reason: str,
    notify_user: bool = True
) -> User:
    
    # Rule: Cannot deactivate self
    if admin_user_id == target_user_id:
        raise AdminBusinessRuleError("Cannot deactivate your own account")
    
    # Rule: Must have at least one active admin
    active_admin_count = await get_active_admin_count()
    target_user = await get_user(target_user_id)
    
    if target_user.role == "admin" and active_admin_count <= 1:
        raise AdminBusinessRuleError("Cannot deactivate last remaining admin")
    
    # Rule: Cannot deactivate if user has pending applications
    pending_apps = await get_pending_applications(target_user_id)
    if pending_apps:
        raise AdminBusinessRuleError(
            f"User has {len(pending_apps)} pending applications"
        )
    
    # Perform deactivation
    user.status = "inactive"
    user.deactivated_at = utcnow()
    user.deactivated_by = admin_user_id
    
    # Audit log
    await audit_log_service.log(
        user_id=admin_user_id,
        action="user_deactivated",
        entity_type="user",
        entity_id=target_user_id,
        old_value={"status": "active"},
        new_value={"status": "inactive", "reason": reason},
        ip_address=client_ip,
        user_agent=client_ua
    )
    
    # Send notification (async task)
    if notify_user:
        await enqueue_notification(
            "account_deactivated",
            user_email=target_user.email,
            reason=reason
        )
    
    return user
```

### 3.2 Role Change Approval Workflow
**Sensitive Action:** User role changes require two-person approval if:
- Granting `admin` role
- Changing role of existing admin

**Workflow:**
1. Initial admin requests role change → Status: `pending_approval`
2. Second admin must approve within 24 hours
3. After approval → Status: `approved` → Execute change
4. If no approval in 24h → Status: `expired` → Reject change
5. Audit log created at each step

### 3.3 Lender Product Rate Change Constraints
- **Daily Rate Change Limit:** Max 0.50% per product per day
- **Stress Test Auto-Calculation:** If not provided, calculate as `max(rate + 2%, 5.25%)` per OSFI B-20
- **Rate Change Notification:** Log audit entry and notify all underwriters via email

### 3.4 Audit Log Generation
**Tracked Actions Mapping:**
```python
AUDIT_ACTIONS = {
    "application_status_changed": "applications",
    "uw_decision_override": "applications",
    "document_verified": "documents",
    "document_rejected": "documents",
    "fintrac_record_created": "fintrac_records",
    "fintrac_record_updated": "fintrac_records",
    "user_role_changed": "users",
    "lender_product_rate_changed": "lender_products",
    "lender_product_deactivated": "lender_products"
}
```

**Audit Log Service:**
- Automatically capture `ip_address` and `user_agent` from request headers
- Hash `ip_address` with HMAC-SHA256 before logging for PIPEDA compliance (store raw for 72h only)
- Never log PII in `old_value`/`new_value` - reference entity IDs only

### 3.5 FINTRAC Report Generation
**Large Cash Transaction Report (LCTR):**
- Trigger: Transactions > CAD $10,000.00
- Fields: transaction_id, date, amount, type, applicant_sin_hash, property_id
- Format: FINTRAC XML schema v.17
- Retention: 5 years (immutable)
- Generation: Async Celery task, email to compliance team

**Monthly Summary Report:**
- Aggregate counts by transaction type
- Include total amounts per type
- Submit by 15th of following month

---

## 4. Migrations

### 4.1 New Table: audit_logs
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    old_value JSONB,
    new_value JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_audit_lookup UNIQUE (entity_type, entity_id, created_at)
);

CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_entity_lookup ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_user_time ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_ip ON audit_logs(ip_address) WHERE ip_address IS NOT NULL;

-- Partitioning for 5-year retention (monthly partitions)
CREATE TABLE audit_logs_y2024m01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 4.2 Existing Tables Modifications

**Table:** `users`
```sql
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active' NOT NULL,
ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS deactivated_by UUID REFERENCES users(id),
ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_role_status ON users(role, status);
```

**Table:** `lenders`
```sql
ALTER TABLE lenders
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true NOT NULL,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE TRIGGER update_lenders_updated_at 
    BEFORE UPDATE ON lenders 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Table:** `lender_products`
```sql
ALTER TABLE lender_products
ADD COLUMN IF NOT EXISTS stress_test_rate NUMERIC(5, 4),
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true NOT NULL,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX idx_lender_products_active ON lender_products(lender_id, is_active) 
    WHERE is_active = true;
```

### 4.3 Data Migration
- **Seed initial admin user** from environment variables (only in development)
- **Migrate existing lender data** to include `is_active=true` and timestamps
- **Backfill audit logs** for existing users/lenders with "system_migration" action

---

## 5. Security & Compliance

### 5.1 Authentication & Authorization
- **JWT Claims Required:** `scope: "admin:*"` or specific scopes:
  - `admin:read` - View users, lenders, audit logs
  - `admin:write` - Modify users, lenders, products
  - `admin:audit` - Access audit logs
  - `admin:compliance` - Access FINTRAC reports
- **mTLS:** Required for admin endpoints in production
- **IP Whitelisting:** Admin endpoints only accessible from corporate VPN ranges
- **Session Timeout:** 30 minutes idle timeout for admin sessions

### 5.2 OSFI B-20 Compliance
- **Stress Test Enforcement:** Admin cannot set product `stress_test_rate` below `max(product_rate + 2%, 5.25%)`
- **Validation Rule:** 
```python
min_stress_rate = max(product.default_rate + Decimal('0.02'), Decimal('0.0525'))
if product.stress_test_rate < min_stress_rate:
    raise AdminBusinessRuleError(
        f"Stress test rate must be ≥ {min_stress_rate} per OSFI B-20"
    )
```

### 5.3 FINTRAC Compliance
- **Immutable Records:** `audit_logs` table has no UPDATE/DELETE operations
- **5-Year Retention:** Automatic partition archiving after 5 years to cold storage
- **Large Transaction Flagging:** Any product rate change affecting loans >$10K must be logged with `fintrac_record_updated` action
- **Report Generation:** All FINTRAC reports include hash of applicant SIN (SHA256) never plain SIN

### 5.4 PIPEDA Compliance
- **No PII in Logs:** Audit logs never contain names, SIN, DOB, income, or banking data
- **IP Address Hashing:** Raw IP stored in `audit_logs.ip_address` for 72h only, then hashed
- **Data Minimization:** Admin API responses exclude unnecessary fields (e.g., user passwords, encrypted SIN)
- **Access Logging:** Every admin data access logged with `data_accessed` action

### 5.5 Sensitive Action Notifications
**Trigger Matrix:**
| Action | Notification Recipients | Delay |
|--------|------------------------|-------|
| User role → admin | All existing admins + security@ | Immediate |
| Lender product rate change >0.25% | Compliance team + underwriter leads | Immediate |
| User deactivation | Security team | Immediate |
| Failed admin login (3 attempts) | Security team + user | Immediate |
| FINTRAC report generation | Compliance officer | Upon completion |

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
class AdminException(AppException):
    """Base exception for admin module"""
    module_code = "ADMIN"

class AdminUserNotFoundError(AdminException):
    http_status = 404
    error_code = "ADMIN_001"
    message_template = "User {entity_id} not found"

class AdminLenderNotFoundError(AdminException):
    http_status = 404
    error_code = "ADMIN_002"
    message_template = "Lender {entity_id} not found"

class AdminProductNotFoundError(AdminException):
    http_status = 404
    error_code = "ADMIN_003"
    message_template = "Product {entity_id} not found"

class AdminValidationError(AdminException):
    http_status = 422
    error_code = "ADMIN_004"
    message_template = "Validation failed: {detail}"

class AdminBusinessRuleError(AdminException):
    http_status = 409
    error_code = "ADMIN_005"
    message_template = "Business rule violation: {rule}"

class AdminUnauthorizedError(AdminException):
    http_status = 403
    error_code = "ADMIN_006"
    message_template = "Admin privilege required: {required_scope}"

class AdminAuditLogRetentionError(AdminException):
    http_status = 400
    error_code = "ADMIN_007"
    message_template = "Audit log query exceeds maximum 90-day window"
```

### 6.2 Error Response Format
```json
{
  "detail": "Business rule violation: Cannot deactivate last remaining admin",
  "error_code": "ADMIN_005",
  "module": "admin",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "corr-12345-abc",
  "context": {
    "target_user_id": "uuid",
    "active_admin_count": 1
  }
}
```

### 6.3 Edge Cases & Error Handling
- **Race Condition:** Concurrent product updates → Use `SELECT FOR UPDATE` with row-level locking
- **Stale Data:** Update lender with outdated version → Return `409 Conflict` with `ADMIN_005`
- **Invalid UUID Format:** Return `422 ValidationError` with malformed field details
- **Missing Scope:** JWT without `admin:*` → `403 Forbidden` with `ADMIN_006`
- **Audit Log Query Too Broad:** >90 days → `400 Bad Request` with `ADMIN_007`

---

## 7. Missing Details Resolution

### 7.1 Admin Authorization Scope Definition
```python
# In common/security.py
ADMIN_SCOPES = {
    "admin:read": "View admin resources",
    "admin:write": "Modify admin resources", 
    "admin:audit": "Access audit logs",
    "admin:compliance": "Access FINTRAC reports",
    "admin:super": "All admin privileges (implicitly grants all above)"
}
```

### 7.2 Audit Log Retention Policy
- **Hot Storage:** 90 days in PostgreSQL (primary partitions)
- **Warm Storage:** 90 days - 2 years in S3 (JSONL format)
- **Cold Storage:** 2-5 years in Glacier (FINTRAC compliance)
- **Purge:** After 5 years, secure deletion with certificate

### 7.3 Admin Action Approval Workflow
**Tables Required:**
- `admin_action_approvals`: id, action_type, requester_id, approver_id, status, expires_at, created_at
- Sensitive actions require two-person rule within 24h window

### 7.4 User Activity Dashboard Metrics
**New Endpoint:** `GET /api/v1/admin/metrics/activity`
- Returns: Login counts, application volumes, decision overrides, document processing times
- Auth: `admin:audit` scope
- Cache: 5-minute TTL

### 7.5 System Health Monitoring
**Integration:** Prometheus metrics endpoint
- `admin_login_attempts_total{status="success|failure"}`
- `audit_log_inserts_total`
- `fintrac_reports_generated_total`
- Alert: `admin_login_attempts_total{status="failure"} > 3` in 5m → PagerDuty

### 7.6 Sensitive Action Notification Recipients
**Configuration:** `common/config.py`
```python
class AdminConfig(BaseSettings):
    admin_notification_email: EmailStr
    compliance_team_email: EmailStr
    security_team_email: EmailStr
    rate_change_threshold: Decimal = Decimal("0.0025")  # 0.25%
```

---

**Design Approval:** This plan must be reviewed by Security, Compliance, and DevOps teams before implementation.