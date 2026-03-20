# Admin Panel
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Admin Panel Module Design Plan

**Module Identifier:** `admin`  
**Design Doc:** `docs/design/admin-panel.md`  
**Scope:** Administrative operations, user management, lender configuration, audit log viewing, and FINTRAC compliance reporting

---

## 1. Endpoints

### 1.1 User Management

| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/admin/users` | admin | `AdminUserListQuery` (page, limit, search, role) | `List[AdminUserResponse]` | `ADMIN_001`, `ADMIN_004` |
| `PUT` | `/api/v1/admin/users/{id}/deactivate` | admin | `UserDeactivateRequest` (reason: str, notify_user: bool) | `UserStatusResponse` | `ADMIN_001`, `ADMIN_003`, `ADMIN_005` |
| `PUT` | `/api/v1/admin/users/{id}/role` | admin | `UserRoleUpdateRequest` (new_role: RoleEnum, justification: str) | `UserRoleResponse` | `ADMIN_001`, `ADMIN_003`, `ADMIN_005` |

**Request/Response Details:**

```python
# schemas.py
class AdminUserListQuery(BaseModel):
    page: int = Field(ge=1, default=1)
    limit: int = Field(ge=1, le=100, default=20)
    search: Optional[str] = Field(None, max_length=100)  # email or name prefix
    role: Optional[UserRole] = None

class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    # SIN/DOB explicitly excluded from admin list view

class UserDeactivateRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)
    notify_user: bool = True

class UserRoleUpdateRequest(BaseModel):
    new_role: UserRole
    justification: str = Field(..., min_length=10, max_length=500)

class UserStatusResponse(BaseModel):
    user_id: UUID
    is_active: bool
    deactivated_at: datetime
    deactivated_by: UUID
```

---

### 1.2 Lender & Product Configuration

| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `POST` | `/api/v1/admin/lenders` | admin | `LenderCreateRequest` | `LenderResponse` | `ADMIN_002`, `ADMIN_003` |
| `PUT` | `/api/v1/admin/lenders/{id}` | admin | `LenderUpdateRequest` | `LenderResponse` | `ADMIN_001`, `ADMIN_003` |
| `POST` | `/api/v1/admin/lenders/{id}/products` | admin | `ProductCreateRequest` | `ProductResponse` | `ADMIN_001`, `ADMIN_002`, `ADMIN_003` |
| `PUT` | `/api/v1/admin/lenders/{id}/products/{prod_id}` | admin | `ProductUpdateRequest` | `ProductResponse` | `ADMIN_001`, `ADMIN_003`, `ADMIN_006` |
| `DELETE` | `/api/v1/admin/lenders/{id}/products/{prod_id}` | admin | `ProductDeactivateRequest` (reason: str) | `ProductStatusResponse` | `ADMIN_001`, `ADMIN_003`, `ADMIN_006` |

**Request/Response Details:**

```python
# schemas.py
class LenderCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., pattern=r'^[A-Z]{3,6}$')
    is_active: bool = True

class LenderUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    is_active: Optional[bool] = None

class ProductCreateRequest(BaseModel):
    name: str = Field(..., max_length=100)
    rate: Decimal = Field(..., ge=0, le=50, decimal_places=4)  # OSFI B-20 compliance
    term_months: int = Field(..., ge=6, le=360)
    max_ltv: Decimal = Field(..., ge=0, le=100, decimal_places=2)
    insurance_required: bool
    # CMHC premium tiers enforced via validation

class ProductUpdateRequest(BaseModel):
    rate: Optional[Decimal] = Field(None, ge=0, le=50, decimal_places=4)
    is_active: Optional[bool] = None
    # Rate changes trigger audit + notification if > 0.25% delta

class ProductDeactivateRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=200)
```

---

### 1.3 Audit & Compliance

| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/admin/audit-logs` | admin | `AuditLogQuery` | `PaginatedAuditLogResponse` | `ADMIN_004` |
| `GET` | `/api/v1/admin/fintrac/reports` | admin | `FintracReportQuery` | `List[FintracReportResponse]` | `ADMIN_004` |

**Request/Response Details:**

```python
# schemas.py
class AuditLogQuery(BaseModel):
    page: int = 1
    limit: int = 50
    entity_type: Optional[AuditEntityType] = None
    user_id: Optional[UUID] = None
    action: Optional[AuditAction] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    action: AuditAction
    entity_type: AuditEntityType
    entity_id: str
    # old_value/new_value EXCLUDE PII per PIPEDA
    ip_address: IPv4Address | IPv6Address
    user_agent: str
    created_at: datetime

class FintracReportQuery(BaseModel):
    status: Optional[FintracReportStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    transaction_value_min: Optional[Decimal] = None  # Default 10,000 CAD

class FintracReportResponse(BaseModel):
    report_id: UUID
    transaction_id: UUID
    transaction_type: TransactionType
    transaction_value: Decimal
    customer_id: UUID
    status: FintracReportStatus
    created_at: datetime
    submitted_at: Optional[datetime]
```

---

## 2. Models & Database

### 2.1 New Table: `audit_logs`

```python
# modules/admin/models.py
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET_NULL"), nullable=True, index=True)
    action = Column(SQLAlchemyEnum(AuditAction), nullable=False, index=True)
    entity_type = Column(SQLAlchemyEnum(AuditEntityType), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)  # UUID as string for cross-table ref
    
    # JSONB stores delta changes; PII scrubbed before write per PIPEDA
    old_value = Column(JSONB, nullable=True)  # {field: value} without PII
    new_value = Column(JSONB, nullable=True)  # {field: value} without PII
    
    ip_address = Column(INET, nullable=False)  # FINTRAC requirement
    user_agent = Column(Text, nullable=False)
    
    # Immutable audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        # Composite index for entity lookups (FINTRAC audit trail)
        Index("idx_audit_entity_lookup", "entity_type", "entity_id"),
        # Date range query optimization
        Index("idx_audit_created_at", "created_at"),
        # Action-based filtering
        Index("idx_audit_action", "action"),
    )
```

### 2.2 Enhanced Existing Models

```python
# modules/auth/models.py - Add to User model
class User(Base):
    # ... existing fields ...
    is_admin = Column(Boolean, default=False, nullable=False, index=True)
    admin_role = Column(SQLAlchemyEnum(AdminRole), nullable=True)  # SUPERADMIN, COMPLIANCE_OFFICER, LENDER_ADMIN
    
    # Relationship
    audit_logs = relationship("AuditLog", back_populates="user")
    
    # Admin action approval workflow
    requires_approval_for = Column(ARRAY(SQLAlchemyEnum(SensitiveAction)), default=[])

# modules/lenders/models.py - Add audit triggers
class Product(Base):
    # ... existing fields ...
    # Rate history tracking for CMHC/OSFI compliance
    rate_last_modified_at = Column(DateTime(timezone=True))
    rate_last_modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
```

---

## 3. Business Logic

### 3.1 Admin Authorization Scope

```python
# modules/admin/services.py
class AdminAuthorizationService:
    """
    RBAC hierarchy for admin operations:
    - SUPERADMIN: All operations + user management
    - COMPLIANCE_OFFICER: Audit logs, FINTRAC reports, read-only lender config
    - LENDER_ADMIN: Lender/product config for assigned lenders only
    """
    
    async def check_scope(
        self, 
        admin_user: User, 
        required_permission: AdminPermission,
        target_lender_id: Optional[UUID] = None
    ) -> bool:
        # Enforce lender isolation for LENDER_ADMIN role
        if admin_user.admin_role == AdminRole.LENDER_ADMIN:
            if target_lender_id not in admin_user.assigned_lender_ids:
                raise AdminAuthorizationError("Cross-lender access denied")
        
        # Compliance officers cannot modify user roles
        if admin_user.admin_role == AdminRole.COMPLIANCE_OFFICER:
            if required_permission in [AdminPermission.USER_ROLE_CHANGE]:
                raise AdminAuthorizationError("Permission denied for compliance role")
        
        return True
```

### 3.2 Audit Log Retention Policy

```python
# FINTRAC 5-year retention enforcement
RETENTION_POLICY = {
    "audit_logs": timedelta(days=1825),  # 5 years
    "fintrac_reports": timedelta(days=1825),
    "sensitive_actions": timedelta(days=2555)  # 7 years for rate overrides
}

# Automated archival service (runs monthly)
async def archive_old_audit_logs(cutoff_date: datetime):
    """
    - Move records > 5 years to cold storage (S3 with encryption)
    - Maintain metadata index for compliance queries
    - Never hard-delete FINTRAC-related records
    """
```

### 3.3 Sensitive Action Approval Workflow

```python
# Trigger conditions requiring secondary approval
APPROVAL_TRIGGERS = {
    "rate_change": Decimal("0.0025"),  # 0.25% threshold
    "lender_deactivation": True,
    "user_role_superadmin": True,
    "bulk_fintrac_resubmission": True
}

# Approval request model
class AdminActionApproval(Base):
    __tablename__ = "admin_action_approvals"
    
    id = Column(UUID, primary_key=True)
    requestor_id = Column(ForeignKey("users.id"))
    approver_id = Column(ForeignKey("users.id"), nullable=True)
    action_type = Column(SQLAlchemyEnum(SensitiveAction))
    payload = Column(JSONB)  # Stashed action data
    status = Column(SQLAlchemyEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())
```

### 3.4 State Machine: Admin User Status

```
[active] --(deactivate)--> [inactive]
[inactive] --(activate)--> [active]
[active] --(role_change)--> [active]  # triggers audit + approval if role escalation
```

---

## 4. Migrations

```sql
-- migration/versions/XXXX_create_audit_logs.py
CREATE TYPE audit_action AS ENUM (
    'APPLICATION_STATUS_CHANGE',
    'UW_DECISION_OVERRIDE',
    'DOCUMENT_VERIFY',
    'DOCUMENT_REJECT',
    'FINTRAC_RECORD_CREATE',
    'FINTRAC_RECORD_UPDATE',
    'USER_ROLE_CHANGE',
    'LENDER_PRODUCT_RATE_CHANGE',
    'USER_DEACTIVATE',
    'LENDER_CREATE',
    'PRODUCT_DEACTIVATE'
);

CREATE TYPE audit_entity_type AS ENUM (
    'application',
    'user',
    'lender',
    'product',
    'fintrac_report',
    'document'
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action audit_action NOT NULL,
    entity_type audit_entity_type NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    ip_address INET NOT NULL,
    user_agent TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_entity_lookup ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_user_action ON audit_logs(user_id, action);
CREATE INDEX idx_audit_action ON audit_logs(action);

-- Add admin fields to users table
ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN admin_role VARCHAR(20);
ALTER TABLE users ADD COLUMN assigned_lender_ids UUID[] DEFAULT '{}';

-- Add rate tracking to products
ALTER TABLE products ADD COLUMN rate_last_modified_at TIMESTAMPTZ;
ALTER TABLE products ADD COLUMN rate_last_modified_by UUID REFERENCES users(id);

-- Create approval workflow table
CREATE TABLE admin_action_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requestor_id UUID NOT NULL REFERENCES users(id),
    approver_id UUID REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX idx_approvals_status ON admin_action_approvals(status);
```

---

## 5. Security & Compliance

### 5.1 FINTRAC Requirements
- **Immutable Audit Trail**: `old_value`/`new_value` JSONB fields are write-once. Updates prohibited via DB trigger.
- **5-Year Retention**: Automated archival to encrypted S3 after 5 years. Metadata retained for queryability.
- **$10K Threshold**: All `transaction_value >= CAD 10,000` auto-flagged in audit logs with `action = 'FINTRAC_RECORD_CREATE'`.
- **IP Address Logging**: All admin actions log `ip_address` and `user_agent` for attribution.

### 5.2 PIPEDA Data Handling
- **PII Scrubbing**: Before writing to `audit_logs.old_value`/`new_value`, all fields matching `/.*(sin|dob|income|banking).*/i` are replaced with `{"redacted": true}`.
- **Encrypted Storage**: `audit_logs` table stored in dedicated PostgreSQL tablespace with AES-256 encryption at rest.
- **Access Logging**: All queries against `audit_logs` table logged to separate security log stream (not accessible via API).

### 5.3 OSFI B-20 Implications
- **Rate Change Audits**: Any `LENDER_PRODUCT_RATE_CHANGE` action triggers validation that new rate complies with stress test requirements (qualifying_rate = max(rate + 2%, 5.25%)).
- **GDS/TDS Limits**: Admin overrides of UW decisions (`UW_DECISION_OVERRIDE`) must log pre- and post-override GDS/TDS values to demonstrate compliance.

### 5.4 Authentication & Authorization
```python
# Dependency injection for admin routes
async def require_admin_permission(
    permission: AdminPermission,
    target_lender_id: Optional[UUID] = None
) -> Callable:
    async def checker(
        current_user: User = Depends(get_current_user),
        auth_service: AdminAuthorizationService = Depends()
    ):
        if not current_user.is_admin:
            raise AdminAuthorizationError("Admin access required")
        
        await auth_service.check_scope(current_user, permission, target_lender_id)
        return current_user
    
    return checker

# Usage in routes.py
@router.put("/users/{id}/role")
async def change_user_role(
    user_id: UUID,
    request: UserRoleUpdateRequest,
    admin: User = Depends(require_admin_permission(AdminPermission.USER_ROLE_CHANGE))
):
    # ...
```

---

## 6. Error Codes & HTTP Responses

```python
# modules/admin/exceptions.py
class AdminException(AppException):
    """Base admin module exception"""
    module_code = "ADMIN"

class AdminNotFoundError(AdminException):
    """Resource not found in admin context"""
    http_status = 404
    error_code = "ADMIN_001"
    message_template = "{resource_type} with id {id} not found"

class AdminValidationError(AdminException):
    """Input validation failed"""
    http_status = 422
    error_code = "ADMIN_002"
    message_template = "Validation error: {field} - {reason}"

class AdminAuthorizationError(AdminException):
    """Admin permission denied"""
    http_status = 403
    error_code = "ADMIN_003"
    message_template = "Admin authorization failed: {detail}"

class AdminAuditError(AdminException):
    """Audit log operation failed"""
    http_status = 500
    error_code = "ADMIN_004"
    message_template = "Audit logging failed: {detail}"

class AdminBusinessRuleError(AdminException):
    """Business rule violation"""
    http_status = 409
    error_code = "ADMIN_005"
    message_template = "Business rule violated: {rule}"

class AdminApprovalRequiredError(AdminException):
    """Sensitive action requires approval"""
    http_status = 202  # Accepted for processing
    error_code = "ADMIN_006"
    message_template = "Action requires approval: {action_type}"
    # Response includes approval_request_id for tracking
```

**Error Response Examples:**

```json
// 403 Forbidden - Unauthorized admin action
{
  "detail": "Admin authorization failed: Cross-lender access denied",
  "error_code": "ADMIN_003",
  "module": "admin",
  "correlation_id": "req-550e8400-e29b-41d4-a716-446655440000"
}

// 422 Validation Error
{
  "detail": "Validation error: rate - Must be ≤ 50.0000 for OSFI compliance",
  "error_code": "ADMIN_002",
  "field": "rate",
  "value": "55.0000"
}

// 202 Accepted (requires approval)
{
  "detail": "Action requires approval: LENDER_PRODUCT_RATE_CHANGE",
  "error_code": "ADMIN_006",
  "approval_request_id": "req-123e4567-e89b-12d3-a456-426614174000",
  "required_approvers": 1,
  "status_url": "/api/v1/admin/approvals/req-123e4567-e89b-12d3-a456-426614174000"
}
```

---

## 7. Observability & Monitoring

```python
# structlog configuration for admin actions
logger.bind(
    admin_user_id=user.id,
    admin_role=user.admin_role,
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
    correlation_id=correlation_id
).info(
    "admin_action_executed",
    action=action_type,
    entity_type=entity_type,
    entity_id=entity_id,
    # PII scrubbed from payload
    payload_hash=hashlib.sha256(scrubbed_payload.encode()).hexdigest()
)

# Prometheus metrics
ADMIN_ACTIONS_TOTAL = Counter(
    'admin_actions_total',
    'Total admin actions by type',
    ['action', 'role', 'status']
)

AUDIT_LOG_INSERT_ERRORS = Counter(
    'audit_log_insert_errors_total',
    'Failed audit log insertions'
)
```

---

## 8. Missing Details Resolution

### 8.1 Admin Authorization Scope
**Resolution**: Implement three-tier RBAC (SUPERADMIN, COMPLIANCE_OFFICER, LENDER_ADMIN) with lender isolation and permission matrix.

### 8.2 Audit Log Retention Policy
**Resolution**: 5-year active retention in PostgreSQL, then encrypted archival to S3. Metadata index retained indefinitely. Implemented via monthly Celery task.

### 8.3 Admin Action Approval Workflow
**Resolution**: Sensitive actions (rate changes >0.25%, superadmin role changes) require secondary approval. `admin_action_approvals` table stores pending actions.

### 8.4 User Activity Dashboard
**Resolution**: Expose `/admin/metrics/user-activity` endpoint returning aggregated stats (login counts, actions per user, failed auth attempts). Powered by TimescaleDB continuous aggregates.

### 8.5 System Health Monitoring
**Resolution**: Integrate with existing `/metrics` endpoint. Add admin-specific health checks: audit log insertion latency, approval queue depth, rate change frequency.

### 8.6 Sensitive Action Notifications
**Resolution**: Email + Slack notifications to `compliance@lender.ca` and `#admin-audit` channel for:
- Rate changes >0.25%
- User role changes to SUPERADMIN
- FINTRAC report submissions
- Approval request creation/resolution

---

## 9. Testing Strategy

```python
# tests/integration/test_admin_integration.py
@pytest.mark.integration
async def test_rate_change_triggers_approval_workflow(client, admin_user):
    """Rate change >0.25% requires approval per business rule"""
    response = await client.post(
        f"/admin/lenders/{lender_id}/products",
        json={"rate": "5.5000", "term_months": 60},
        headers=admin_auth_headers
    )
    assert response.status_code == 202
    assert response.json()["error_code"] == "ADMIN_006"
    assert "approval_request_id" in response.json()

@pytest.mark.integration
async def test_audit_log_scrubs_pii(client, admin_user):
    """PIPEDA compliance: SIN/DOB never written to audit logs"""
    # Perform action that would normally log PII
    await client.put(f"/admin/users/{user_id}/role", json={"new_role": "underwriter"})
    
    # Verify audit log entry has redacted values
    audit_entry = await db.execute(select(AuditLog).filter_by(action="USER_ROLE_CHANGE"))
    assert audit_entry.new_value.get("sin") == {"redacted": True}
```

---

## 10. Deployment Checklist

- [ ] Create `admin_action_approvals` table migration
- [ ] Seed initial SUPERADMIN user via secure CLI tool (never in migration)
- [ ] Configure S3 archival bucket with AES-256 encryption
- [ ] Set up Slack webhook for notifications
- [ ] Configure `pip-audit` in CI pipeline for admin module dependencies
- [ ] Run `mypy` on admin module with strict mode enabled
- [ ] Load test audit log insertion (target: <50ms p99 latency)
- [ ] Verify PostgreSQL tablespace encryption for `audit_logs` table

---

**Regulatory Compliance Summary**: This design enforces FINTRAC 5-year retention via automated archival, PIPEDA PII scrubbing in audit trails, OSFI B-20 rate validation, and CMHC premium tier enforcement through product configuration constraints.