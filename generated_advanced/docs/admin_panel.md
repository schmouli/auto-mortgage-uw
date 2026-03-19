# Admin Panel
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Admin Panel Module Design Plan

**Feature Slug:** `admin-panel`  
**Design Doc:** `docs/design/admin-panel.md`  
**Module Path:** `mortgage_underwriting/modules/admin/`

---

## 1. Endpoints

### 1.1 User Management

#### `GET /api/v1/admin/users`
- **Auth:** Admin-only (`role IN ['admin', 'super_admin', 'auditor']`)
- **Query Params:** `page[int]`, `limit[int]`, `role[str]`, `is_active[bool]`
- **Response:** `200 OK`
  ```json
  {
    "items": [
      {
        "id": "uuid",
        "email": "string",
        "first_name": "string",
        "last_name": "string",
        "role": "string",
        "is_active": "bool",
        "last_login_at": "datetime",
        "created_at": "datetime"
      }
    ],
    "total": "int",
    "page": "int",
    "limit": "int"
  }
  ```
- **PIPEDA Note:** SIN/DOB excluded; SIN hash available only for lookup verification
- **Errors:** `401 Unauthorized`, `403 Forbidden`, `ADMIN_004`

#### `PUT /api/v1/admin/users/{id}/deactivate`
- **Auth:** Admin-only (`role IN ['admin', 'super_admin']`)
- **Request:** 
  ```json
  {
    "reason": "string (required, min 10 chars)",
    "notify_user": "bool (default: true)"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "id": "uuid",
    "is_active": false,
    "deactivated_at": "datetime"
  }
  ```
- **Business Rule:** Cannot deactivate last active super_admin
- **Audit:** Logs `USER_DEACTIVATED` action with reason in `new_value`
- **Errors:** `400 Bad Request (ADMIN_003)`, `404 Not Found (ADMIN_001)`, `409 Conflict (ADMIN_005)`

#### `PUT /api/v1/admin/users/{id}/role`
- **Auth:** Super-admin only
- **Request:**
  ```json
  {
    "new_role": "enum['applicant', 'broker', 'underwriter', 'admin', 'super_admin', 'auditor', 'compliance_officer']",
    "justification": "string (required, min 20 chars)"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "id": "uuid",
    "previous_role": "string",
    "new_role": "string",
    "changed_at": "datetime",
    "changed_by": "uuid"
  }
  ```
- **Audit:** Logs `USER_ROLE_CHANGED` with old/new roles
- **Errors:** `422 ValidationError (ADMIN_002)`, `403 Forbidden (ADMIN_004)`

---

### 1.2 Lender & Product Management

#### `POST /api/v1/admin/lenders`
- **Auth:** Admin-only
- **Request:**
  ```json
  {
    "name": "string (required, max 255)",
    "code": "string (required, unique, max 20)",
    "is_active": "bool (default: true)"
  }
  ```
- **Response:** `201 Created`
  ```json
  {
    "id": "uuid",
    "name": "string",
    "code": "string",
    "is_active": "bool",
    "created_at": "datetime"
  }
  ```
- **Errors:** `409 Conflict (ADMIN_005)` for duplicate code

#### `PUT /api/v1/admin/lenders/{id}`
- **Auth:** Admin-only
- **Request:** Same as POST, all fields optional
- **Response:** `200 OK`
- **Audit:** Logs `LENDER_UPDATED` with old/new values JSON diff

#### `POST /api/v1/admin/lenders/{id}/products`
- **Auth:** Admin-only
- **Request:**
  ```json
  {
    "name": "string (required)",
    "rate": "Decimal (required, precision=5, scale=4)",
    "product_type": "enum['fixed', 'variable', 'hybrid']",
    "term_years": "int (required, min=1, max=30)",
    "amortization_max_years": "int (required, min=5, max=30)",
    "insurance_eligible": "bool (default: true)",
    "ltv_max": "Decimal (required, precision=5, scale=2, max=95.00)",
    "gds_max": "Decimal (default: 39.00, precision=5, scale=2)",
    "tds_max": "Decimal (default: 44.00, precision=5, scale=2)"
  }
  ```
- **Response:** `201 Created`
- **OSFI B-20 Note:** Validates gds_max ≤ 39%, tds_max ≤ 44%
- **Audit:** Logs `LENDER_PRODUCT_CREATED` with full payload

#### `PUT /api/v1/admin/lenders/{id}/products/{prod_id}`
- **Auth:** Admin-only
- **Request:** Same as POST, all fields optional
- **Response:** `200 OK`
- **Audit:** Logs `LENDER_PRODUCT_RATE_CHANGED` if rate modified (FINTRAC trigger)
- **CMHC Note:** If LTV > 80%, validates insurance_eligible=True

#### `DELETE /api/v1/admin/lenders/{id}/products/{prod_id}`
- **Auth:** Admin-only
- **Response:** `204 No Content` (soft delete)
- **Behavior:** Sets `is_active=false`, does not hard delete for FINTRAC retention
- **Audit:** Logs `LENDER_PRODUCT_DEACTIVATED`

---

### 1.3 Audit & Compliance

#### `GET /api/v1/admin/audit-logs`
- **Auth:** Auditor, compliance_officer, or super_admin only
- **Query Params:** `user_id[uuid]`, `entity_type[str]`, `entity_id[str]`, `action[str]`, `date_from[date]`, `date_to[date]`, `page`, `limit`
- **Response:** `200 OK`
  ```json
  {
    "items": [
      {
        "id": "uuid",
        "user_id": "uuid",
        "user_email": "string",
        "action": "string",
        "entity_type": "string",
        "entity_id": "string",
        "created_at": "datetime",
        "ip_address": "string"
      }
    ],
    "total": "int"
  }
  ```
- **PIPEDA Note:** old_value/new_value excluded from list view; available via `GET /audit-logs/{id}` for detail
- **FINTRAC:** Supports 5-year retention query range enforcement

#### `GET /api/v1/admin/fintrac/reports`
- **Auth:** Compliance_officer or super_admin only
- **Query Params:** `reporting_period[str] (YYYY-MM)`, `transaction_threshold[Decimal] (default: 10000.00)`
- **Response:** `200 OK`
  ```json
  {
    "reporting_period": "string",
    "generated_at": "datetime",
    "transactions": [
      {
        "transaction_id": "uuid",
        "transaction_type": "enum['purchase', 'refinance', 'renewal']",
        "amount": "Decimal",
        "date": "date",
        "applicant": {
          "id": "uuid",
          "name": "string",
          "sin_hash": "string (SHA256)"
        },
        "property_address": "string"
      }
    ],
    "total_count": "int",
    "total_amount": "Decimal"
  }
  ```
- **FINTRAC Compliance:** Only includes transactions ≥ $10,000; includes mandatory type flag; data immutable
- **Errors:** `422 Invalid reporting period (ADMIN_002)`

---

## 2. Models & Database

### 2.1 Audit Log Model (`modules/admin/models.py`)

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Action categorization for FINTRAC/OSFI reporting
    action = Column(String(100), nullable=False, index=True)  # e.g., USER_ROLE_CHANGED, LENDER_PRODUCT_RATE_CHANGED
    entity_type = Column(String(50), nullable=False, index=True)  # e.g., application, user, lender_product
    entity_id = Column(String(36), nullable=False, index=True)  # UUID as string for polymorphic reference
    
    # Immutable audit trail (FINTRAC requirement)
    old_value = Column(JSONB, nullable=True)  # PostgreSQL JSONB for queryability
    new_value = Column(JSONB, nullable=True)
    
    # Request metadata
    ip_address = Column(INET, nullable=True)  # PostgreSQL INET type
    user_agent = Column(Text, nullable=True)
    
    # Mandatory audit fields
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="audit_logs")
    
    # Indexes
    __table_args__ = (
        # Composite index for common query pattern: filter by entity + date range
        Index('ix_audit_logs_entity_type_created_at', 'entity_type', 'created_at'),
        # Composite index for user activity dashboard
        Index('ix_audit_logs_user_id_action_created_at', 'user_id', 'action', 'created_at'),
        # Partial index for FINTRAC-relevant actions (performance optimization)
        Index('ix_audit_logs_fintrac_actions', 'action', 'created_at', 
              postgresql_where=action.in_(['FINTRAC_RECORD_CREATED', 'FINTRAC_RECORD_UPDATED'])),
    )
```

### 2.2 Supporting Indexes on Existing Tables

```sql
-- modules/admin/migrations/versions/xxx_add_admin_indexes.py
# On existing users table
op.create_index('ix_users_role_is_active', 'users', ['role', 'is_active'])

# On existing lender_products table for rate change tracking
op.create_index('ix_lender_products_rate_history', 'lender_products', 
                ['id', 'rate', 'updated_at'])

# On existing applications table for status change audit
op.create_index('ix_applications_status_changed', 'applications', 
                ['id', 'status', 'updated_at'])
```

---

## 3. Business Logic

### 3.1 Audit Log Service (`modules/admin/services.py`)

```python
class AuditLogService:
    """
    Centralized audit logging for FINTRAC/OSFI compliance.
    Called synchronously after successful DB commits.
    """
    
    @staticmethod
    async def log_action(
        db: AsyncSession,
        user_id: UUID,
        action: str,
        entity_type: str,
        entity_id: str,
        old_value: dict | None,
        new_value: dict | None,
        ip_address: str | None,
        user_agent: str | None
    ) -> AuditLog:
        """
        FINTRAC Requirement: All financial transaction records must have immutable audit trail.
        Implementation: old_value/new_value stored as JSONB; no updates allowed to audit_logs table.
        """
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(log)
        await db.flush()
        
        # Observability: Log metadata only (no PII)
        logger.info("audit_log_created", action=action, entity_type=entity_type, 
                    entity_id=str(entity_id), user_id=str(user_id))
        return log
    
    @staticmethod
    async def get_fintrac_report(
        db: AsyncSession,
        reporting_period: str,  # YYYY-MM
        threshold: Decimal = Decimal("10000.00")
    ) -> list[dict]:
        """
        FINTRAC Requirement: Transactions > CAD $10,000 require explicit transaction type flag.
        Generates immutable report for regulatory submission.
        """
        start_date, end_date = parse_period(reporting_period)
        
        result = await db.execute(
            select(
                Transaction.id,
                Transaction.transaction_type,
                Transaction.amount,
                Transaction.created_at,
                User.id.label("applicant_id"),
                User.first_name,
                User.last_name,
                User.sin_hash,  # PIPEDA: Only hash exposed
                Property.address
            )
            .join(User, Transaction.user_id == User.id)
            .join(Property, Transaction.property_id == Property.id)
            .where(
                Transaction.amount >= threshold,
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
                Transaction.is_fintrac_reportable == True
            )
            .order_by(Transaction.created_at)
        )
        return result.all()
```

### 3.2 User Deactivation Logic

```python
async def deactivate_user(
    db: AsyncSession,
    user_id: UUID,
    deactivator_id: UUID,
    reason: str,
    ip_address: str | None
) -> User:
    # Business Rule: Cannot deactivate last super_admin
    super_admin_count = await db.scalar(
        select(func.count(User.id)).where(
            User.role == "super_admin",
            User.is_active == True,
            User.id != user_id
        )
    )
    if super_admin_count == 0:
        raise AdminBusinessRuleError("Cannot deactivate last super_admin")
    
    user = await db.get(User, user_id)
    old_value = {"is_active": user.is_active}
    user.is_active = False
    user.deactivated_at = datetime.utcnow()
    
    await AuditLogService.log_action(
        db=db,
        user_id=deactivator_id,
        action="USER_DEACTIVATED",
        entity_type="user",
        entity_id=str(user_id),
        old_value=old_value,
        new_value={"is_active": False, "reason": reason},
        ip_address=ip_address
    )
    return user
```

### 3.3 Lender Product Rate Change Workflow

```python
async def update_product_rate(
    db: AsyncSession,
    product_id: UUID,
    new_rate: Decimal,
    admin_id: UUID,
    justification: str
) -> LenderProduct:
    """
    FINTRAC & OSFI Trigger: Rate changes affect debt service calculations.
    Requires dual approval workflow for rates > 0.5% change.
    """
    product = await db.get(LenderProduct, product_id)
    old_rate = product.rate
    
    # Business Rule: Rate change > 0.5% requires approval
    if abs(old_rate - new_rate) > Decimal("0.005"):
        await create_approval_request(
            action="RATE_CHANGE",
            entity_id=product_id,
            requested_by=admin_id,
            payload={"old_rate": str(old_rate), "new_rate": str(new_rate)}
        )
        raise AdminApprovalRequiredError("Rate change requires secondary approval")
    
    product.rate = new_rate
    product.updated_at = datetime.utcnow()
    
    # Audit for FINTRAC compliance
    await AuditLogService.log_action(
        db=db,
        user_id=admin_id,
        action="LENDER_PRODUCT_RATE_CHANGED",
        entity_type="lender_product",
        entity_id=str(product_id),
        old_value={"rate": str(old_rate)},
        new_value={"rate": str(new_rate), "justification": justification}
    )
    
    # Notification trigger
    await notify_security_team(
        event="sensitive_rate_change",
        product_id=product_id,
        admin_id=admin_id
    )
    
    return product
```

---

## 4. Migrations

### 4.1 New Table: `audit_logs`
```python
# migrations/versions/xxx_create_audit_logs.py
def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('old_value', postgresql.JSONB, nullable=True),
        sa.Column('new_value', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # FINTRAC 5-year retention query optimization
    op.create_index('ix_audit_logs_created_at_desc', 'audit_logs', [sa.desc('created_at')])
    op.create_index('ix_audit_logs_entity_composite', 'audit_logs', ['entity_type', 'entity_id', 'created_at'])
    op.create_index('ix_audit_logs_action_period', 'audit_logs', ['action', 'created_at'])
```

### 4.2 Existing Table Modifications
```python
# On users table
op.add_column('users', sa.Column('deactivated_at', TIMESTAMP(timezone=True), nullable=True))
op.add_column('users', sa.Column('last_login_ip', postgresql.INET, nullable=True))

# On lender_products table (add soft delete flag)
op.add_column('lender_products', sa.Column('is_active', sa.Boolean, default=True, nullable=False))
op.create_index('ix_lender_products_active_rate', 'lender_products', ['is_active', 'rate'])
```

---

## 5. Security & Compliance

### 5.1 Authorization Scope Definition

```python
# common/security.py - Admin RBAC mapping
ADMIN_PERMISSIONS = {
    "auditor": ["audit-logs:read", "fintrac-reports:read"],
    "compliance_officer": ["audit-logs:read", "fintrac-reports:read", "fintrac-reports:export"],
    "admin": [
        "users:read", "users:deactivate", "lenders:write", "lenders:products:write",
        "audit-logs:read"
    ],
    "super_admin": ["*"]  # All permissions including role management
}

# MFA requirement for sensitive actions
SENSITIVE_ACTIONS = [
    "USER_ROLE_CHANGED",
    "LENDER_PRODUCT_RATE_CHANGED",
    "USER_DEACTIVATED"
]
```

### 5.2 FINTRAC Compliance
- **Retention:** Audit logs retained for 5 years (FINTRAC requirement). Implemented via PostgreSQL partitioning by year-month.
- **Immutability:** `audit_logs` table has no UPDATE/DELETE endpoints; DBA policy denies modifications.
- **Transaction Flagging:** All transactions ≥ $10,000 automatically flagged `is_fintrac_reportable=True` at creation; audit log entry created synchronously.
- **Reporting:** `/admin/fintrac/reports` generates immutable snapshots; report ID hashed and stored in audit log.

### 5.3 PIPEDA Compliance
- **Admin PII Access:** Every admin view of user PII logs `USER_PII_ACCESSED` audit event with justification.
- **Encryption:** SIN/DOB fields remain encrypted; admin panel displays only SHA256 hashes for lookups.
- **Data Minimization:** Admin endpoints exclude banking data unless explicitly required for fraud investigation (requires secondary approval).

### 5.4 OSFI B-20 Compliance
- **Product Validation:** Lender product creation/editing enforces GDS ≤ 39%, TDS ≤ 44%.
- **Stress Test Audit:** Any override of qualifying_rate logs `OSFI_STRESS_TEST_OVERRIDE` with justification.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `AdminNotFoundError` | 404 | ADMIN_001 | "{resource} not found" | User ID does not exist |
| `AdminValidationError` | 422 | ADMIN_002 | "{field}: {reason}" | Invalid role enum value |
| `AdminBusinessRuleError` | 409 | ADMIN_003 | "{rule} violated: {detail}" | Deactivating last super_admin |
| `AdminPermissionError` | 403 | ADMIN_004 | "Insufficient permissions for {action}" | Auditor trying to deactivate user |
| `AdminConflictError` | 409 | ADMIN_005 | "{resource} already exists" | Duplicate lender code |
| `AdminApprovalRequiredError` | 202 | ADMIN_006 | "Action requires secondary approval" | Rate change > 0.5% |
| `AdminFintracReportError` | 422 | ADMIN_007 | "Invalid reporting period: {detail}" | Future date or bad format |

### 6.1 Exception Definitions (`modules/admin/exceptions.py`)
```python
from common.exceptions import AppException

class AdminNotFoundError(AppException):
    error_code = "ADMIN_001"
    http_status = 404

class AdminBusinessRuleError(AppException):
    error_code = "ADMIN_003"
    http_status = 409
    
class AdminApprovalRequiredError(AppException):
    error_code = "ADMIN_006"
    http_status = 202  # Accepted for processing
```

---

## 7. Missing Details Resolution

### 7.1 Admin Authorization Scope
- **Implementation:** JWT claims include `permissions: List[str]` validated against `ADMIN_PERMISSIONS` mapping.
- **Middleware:** `require_admin_permission(permission: str)` dependency for each endpoint.

### 7.2 Audit Log Retention Policy
- **Database:** PostgreSQL partitioned table `audit_logs_y2024m01`, `audit_logs_y2024m02`, etc.
- **Automation:** Monthly cron job creates new partition; 5-year-old partitions archived to S3 Glacier.
- **Access:** Read-only replicas for auditor queries; primary DB denies long-running queries.

### 7.3 Admin Action Approval Workflow
- **Critical Actions:** User role changes, rate changes >0.5%, PII bulk export.
- **Flow:** 
  1. Primary admin requests action → stored in `approval_requests` table
  2. Secondary admin approves via `POST /admin/approvals/{request_id}/approve`
  3. Action executed by system user; both admins logged in audit trail
- **Timeout:** Approval requests expire after 24 hours.

### 7.4 User Activity Dashboard Support
- **Endpoint:** `GET /admin/metrics/user-activity` (for Grafana)
- **Response:** Aggregated stats: login counts, role distribution, deactivation rate
- **Real-time:** WebSocket `ws://admin/audit-stream` for live audit events (auditor role only)

### 7.5 System Health Monitoring
- **Metrics:** Prometheus counters for each admin action, latency histograms.
- **Alerts:** PagerDuty alert on `ADMIN_003` (business rule violation) or failed FINTRAC report generation.
- **Endpoint:** `GET /admin/health` returns DB replication lag, audit log queue depth.

### 7.6 Sensitive Action Notifications
- **Recipients:** Configurable in `common/config.py` (`SECURITY_TEAM_EMAILS`, `COMPLIANCE_SLACK_WEBHOOK`)
- **Triggers:** `LENDER_PRODUCT_RATE_CHANGED`, `USER_ROLE_CHANGED` to super_admin, `FINTRAC_RECORD_CREATED` for >$50k transactions
- **Format:** Structured JSON to Slack/email; includes action, admin email, entity ID, timestamp; **excludes PII**.