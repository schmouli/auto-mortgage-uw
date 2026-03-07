# Design: Admin Panel
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Admin Panel Module Design

**File:** `docs/design/admin-panel.md`

---

## 1. Endpoints

### User Management
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| **GET** | `/api/v1/admin/users` | admin-only | `AdminUserListQuery` (page, limit, role, is_active) | `AdminUserListResponse` (users[], total) | 401, 403 |
| **PUT** | `/api/v1/admin/users/{id}/deactivate` | admin-only | `UserDeactivateRequest` (reason: str, requires_approval: bool) | `UserDeactivateResponse` (user_id, status, deactivation_date) | 401, 403, 404, 409 |
| **PUT** | `/api/v1/admin/users/{id}/role` | super-admin-only | `UserRoleUpdateRequest` (new_role: str, justification: str) | `UserRoleUpdateResponse` (user_id, old_role, new_role, effective_at) | 401, 403, 404, 422, 409 |

### Lender Management
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| **POST** | `/api/v1/admin/lenders` | admin-only | `LenderCreateRequest` (name, code, contact_email, is_active) | `LenderResponse` (id, name, code, created_at) | 401, 403, 422, 409 |
| **PUT** | `/api/v1/admin/lenders/{id}` | admin-only | `LenderUpdateRequest` (name?, code?, contact_email?, is_active?) | `LenderResponse` | 401, 403, 404, 422, 409 |
| **POST** | `/api/v1/admin/lenders/{id}/products` | admin-only | `ProductCreateRequest` (name, rate: Decimal, max_ltv: Decimal, insurance_required: bool) | `ProductResponse` (id, name, rate, max_ltv, created_at) | 401, 403, 404, 422 |
| **PUT** | `/api/v1/admin/lenders/{id}/products/{prod_id}` | admin-only | `ProductUpdateRequest` (name?, rate?, max_ltv?, insurance_required?, is_active?) | `ProductResponse` | 401, 403, 404, 422, 409 |
| **DELETE** | `/api/v1/admin/lenders/{id}/products/{prod_id}` | admin-only | `ProductDeactivateRequest` (reason: str) | `ProductDeactivateResponse` (prod_id, deactivated_at) | 401, 403, 404, 409 |

### Audit & Compliance
| Method | Path | Auth | Request Body | Response | Errors |
|--------|------|------|--------------|----------|--------|
| **GET** | `/api/v1/admin/audit-logs` | admin-only | `AuditLogQuery` (page, limit, user_id?, entity_type?, date_from?, date_to?) | `AuditLogListResponse` (logs[], total) | 401, 403 |
| **GET** | `/api/v1/admin/fintrac/reports` | admin-only + fintrac-viewer | `FintracReportQuery` (report_type, quarter, year) | `FintracReportResponse` (report_id, generated_at, transactions[], summary) | 401, 403, 422 |

---

## 2. Models & Database

### `admin_audit_logs` Table
```sql
CREATE TABLE admin_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL CHECK (action IN (
        'USER_DEACTIVATE', 'USER_ROLE_CHANGE', 'LENDER_CREATE', 'LENDER_UPDATE',
        'PRODUCT_CREATE', 'PRODUCT_UPDATE', 'PRODUCT_DEACTIVATE', 'APPLICATION_STATUS_CHANGE',
        'UW_OVERRIDE', 'DOCUMENT_VERIFY', 'DOCUMENT_REJECT', 'FINTRAC_RECORD_CREATE'
    )),
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    old_value JSONB,  -- ENCRYPTED if contains PII (see Security section)
    new_value JSONB,  -- ENCRYPTED if contains PII
    ip_address INET NOT NULL,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Composite indexes for common query patterns
    CONSTRAINT idx_audit_user_created UNIQUE (user_id, created_at DESC),
    CONSTRAINT idx_audit_entity_lookup UNIQUE (entity_type, entity_id, created_at DESC)
);

-- Partitioning by created_at for 5-year retention
CREATE TABLE admin_audit_logs_y2024 PARTITION OF admin_audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE admin_audit_logs_y2025 PARTITION OF admin_audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Index for FINTRAC reporting queries
CREATE INDEX idx_audit_fintrac ON admin_audit_logs (action, created_at) 
    WHERE action LIKE 'FINTRAC_%';
```

### `admin_action_approvals` Table (for sensitive actions)
```sql
CREATE TABLE admin_action_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id UUID NOT NULL REFERENCES users(id),
    approver_id UUID REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    target_entity_type VARCHAR(30) NOT NULL,
    target_entity_id VARCHAR(100) NOT NULL,
    request_payload JSONB NOT NULL,  -- ENCRYPTED
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    
    CONSTRAINT idx_approval_pending UNIQUE (target_entity_type, target_entity_id, status) 
        WHERE status = 'pending'
);
```

---

## 3. Business Logic

### Audit Logging Service
```python
class AuditLogService:
    async def log_action(
        self,
        user_id: UUID,
        action: AuditActionEnum,
        entity_type: str,
        entity_id: str,
        old_value: dict | None,
        new_value: dict | None,
        ip_address: IPvAnyAddress,
        user_agent: str | None,
        encrypt_fields: list[str] = None
    ) -> None:
        """
        FINTRAC Requirement: Immutable record creation
        PIPEDA Requirement: Encrypt PII in JSON fields
        """
        # Encrypt sensitive fields before storage
        if encrypt_fields:
            old_value = self._encrypt_pii_fields(old_value, encrypt_fields)
            new_value = self._encrypt_pii_fields(new_value, encrypt_fields)
        
        # Write to admin_audit_logs (cannot be updated/deleted)
        await self.repository.create_audit_log(...)
        
        # OSFI Compliance: Log underwriting overrides separately
        if action == AuditActionEnum.UW_OVERRIDE:
            await self._log_osfi_override_details(...)
```

### Approval Workflow Engine
```python
class ApprovalWorkflowService:
    """
    Sensitive actions require dual-control approval:
    - User role changes (super admin only)
    - Lender product rate changes > 0.5%
    - UW decision overrides
    """
    async def submit_for_approval(
        self,
        requester_id: UUID,
        action_type: str,
        target: tuple[str, str],
        payload: dict,
        requires_approval: bool = True
    ) -> ApprovalResponse:
        if not requires_approval:
            return await self._execute_direct(payload)
        
        # Create pending approval record
        approval_id = await self.repository.create_approval_request(
            requester_id=requester_id,
            action_type=action_type,
            target_entity_type=target[0],
            target_entity_id=target[1],
            request_payload=payload
        )
        
        # Send notification to approval group
        await self.notification_service.notify_approvers(
            approval_id=approval_id,
            action_type=action_type,
            requester_id=requester_id
        )
        
        return ApprovalResponse(approval_id=approval_id, status="pending")
```

### FINTRAC Report Generator
```python
class FintracReportService:
    async def generate_report(self, quarter: int, year: int) -> FintracReport:
        """
        FINTRAC Requirement: 5-year retention, immutable records
        Generates report of all transactions > CAD $10,000
        """
        start_date, end_date = self._get_quarter_dates(quarter, year)
        
        # Query audit logs for FINTRAC actions
        logs = await self.repository.get_fintrac_logs(
            date_from=start_date,
            date_to=end_date
        )
        
        # Filter transactions > $10,000
        reportable_transactions = [
            log for log in logs
            if self._extract_transaction_amount(log.new_value) > Decimal('10000.00')
        ]
        
        return FintracReport(
            report_id=f"FINTRAC-{year}-Q{quarter}-{uuid4()}",
            generated_at=datetime.utcnow(),
            transactions=reportable_transactions,
            summary=self._generate_summary(reportable_transactions)
        )
```

---

## 4. Migrations

### Alembic Migration: `001_create_admin_audit_logs.py`
```python
"""Create admin audit logs and approval tables."""

def upgrade():
    # Create admin_audit_logs table with partitions
    op.execute("""
        CREATE TABLE admin_audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            action VARCHAR(50) NOT NULL,
            entity_type VARCHAR(30) NOT NULL,
            entity_id VARCHAR(100) NOT NULL,
            old_value JSONB,
            new_value JSONB,
            ip_address INET NOT NULL,
            user_agent TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) PARTITION BY RANGE (created_at);
    """)
    
    # Create yearly partitions for 5-year retention
    for year in [2024, 2025, 2026, 2027, 2028]:
        op.execute(f"""
            CREATE TABLE admin_audit_logs_y{year} PARTITION OF admin_audit_logs
                FOR VALUES FROM ('{year}-01-01') TO ('{year+1}-01-01');
        """)
    
    # Create indexes
    op.create_index('idx_audit_user_created', 'admin_audit_logs', ['user_id', 'created_at DESC'], unique=True)
    op.create_index('idx_audit_entity_lookup', 'admin_audit_logs', ['entity_type', 'entity_id', 'created_at DESC'], unique=True)
    op.create_index('idx_audit_fintrac', 'admin_audit_logs', ['action', 'created_at'], 
                    postgresql_where="action LIKE 'FINTRAC_%'")

    # Create admin_action_approvals table
    op.create_table('admin_action_approvals',
        sa.Column('id', UUID(), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('requester_id', UUID(), nullable=False),
        sa.Column('approver_id', UUID(), nullable=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_entity_type', sa.String(30), nullable=False),
        sa.Column('target_entity_id', sa.String(100), nullable=False),
        sa.Column('request_payload', JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW() + INTERVAL \'24 hours\'')),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
    )
    
    op.create_index('idx_approval_pending', 'admin_action_approvals', 
                    ['target_entity_type', 'target_entity_id', 'status'], unique=True,
                    postgresql_where="status = 'pending'")

def downgrade():
    op.drop_table('admin_action_approvals')
    op.drop_table('admin_audit_logs')
```

---

## 5. Security & Compliance

### FINTRAC Compliance
- **5-Year Retention**: Partitioned tables auto-archive after 5 years via pg_cron job
- **Immutable Records**: `admin_audit_logs` has no UPDATE/DELETE triggers; INSERT only
- **Transaction Flagging**: All `new_value` JSON payloads with `transaction_amount > 10000` automatically flagged in audit log
- **Report Generation**: `/admin/fintrac/reports` endpoint accessible only to `fintrac-viewer` role

### PIPEDA Data Handling
- **Encryption at Rest**: AES-256 encryption for `old_value` and `new_value` fields when they contain:
  - SIN (encrypt before storing SHA256)
  - DOB
  - Banking information (account numbers, transit numbers)
  - Income amounts
- **Data Minimization**: Audit logs only store fields that changed, not full PII payloads
- **Logging**: structlog configured to exclude `old_value`, `new_value`, `ip_address` from JSON output; only log metadata

### OSFI B-20 Requirements
- **Audit Trail**: All UW decision overrides (`UW_OVERRIDE` action) must log:
  - Original GDS/TDS calculations
  - Stress test rate used
  - Override justification
  - Approver identity
- **Stress Test Enforcement**: Admin cannot modify qualifying rates; rates managed by `config` module with audit trail

### Authorization Matrix
```python
# Role-based access control
ROLE_PERMISSIONS = {
    "admin": ["read:users", "deactivate:user", "read:lenders", "write:lenders", 
              "read:audit_logs", "write:products"],
    "super_admin": ["*"],  # All permissions
    "fintrac_viewer": ["read:fintrac_reports"],
    "admin_approver": ["approve:sensitive_actions"]
}

# Sensitive actions requiring approval
APPROVAL_REQUIRED_FOR = {
    "USER_ROLE_CHANGE": {"min_approver_role": "super_admin", "timeout_hours": 24},
    "PRODUCT_RATE_CHANGE": {"threshold": Decimal("0.50"), "min_approver_role": "admin_approver"},
    "UW_OVERRIDE": {"min_approver_role": "admin_approver", "timeout_hours": 4}
}
```

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `AdminUnauthorizedError` | 401 | ADMIN_001 | "Admin authentication required" | Missing/invalid JWT token |
| `AdminForbiddenError` | 403 | ADMIN_002 | "Insufficient permissions: {required_role}" | Role check fails |
| `AdminResourceNotFoundError` | 404 | ADMIN_003 | "{resource_type} not found: {id}" | User/lender/product lookup fails |
| `AdminValidationError` | 422 | ADMIN_004 | "{field}: {reason}" | Pydantic validation fails |
| `AdminBusinessRuleError` | 409 | ADMIN_005 | "{rule} violated: {detail}" | Approval required but not obtained |
| `AdminApprovalExpiredError` | 410 | ADMIN_006 | "Approval request expired" | Approval not completed within timeout |
| `AdminFintracReportError` | 422 | ADMIN_007 | "FINTRAC report generation failed: {reason}" | Invalid quarter/year or no data |

**Error Response Format:**
```json
{
  "detail": "Insufficient permissions: super_admin required",
  "error_code": "ADMIN_002",
  "correlation_id": "req-550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Special Handling:**
- **PIPEDA Compliance**: All 422 errors sanitize PII from error messages; use field masks like `sin: [REDACTED]`
- **FINTRAC Audit**: All 401/403 errors log failed access attempts to `admin_audit_logs` with `action='ACCESS_DENIED'`
- **Rate Limiting**: Admin endpoints rate-limited to 100 req/min per IP; breaches log to audit trail

---

## 7. Additional Considerations (Missing Details)

### Admin Authorization Scope
- Implement OAuth2 scopes: `admin:read`, `admin:write`, `fintrac:read`
- Use JWT claims with `role` and `permissions` array
- mTLS for inter-service admin API calls

### Audit Log Retention Policy
- **Active**: 2 years in primary partitions
- **Cold Storage**: Years 3-5 auto-moved to S3 Glacier via pg_cron + pg_send_file
- **Deletion**: After 5 years, hard delete via scheduled job with FINTRAC compliance certificate

### Admin Action Approval Workflow
- Slack/Email notifications to `#admin-approvals` channel
- Approval dashboard at `/admin/approvals/pending`
- Emergency override requires 2 super admins + logs to separate `emergency_access_logs` table

### User Activity Dashboard
- Real-time view via `/admin/audit-logs/stream` (SSE endpoint)
- Metrics: `admin_actions_total`, `admin_approvals_pending`, `admin_fintrac_reports_generated`
- Prometheus alerts for >10 failed admin login attempts/hour

### System Health Monitoring
- Liveness probe: `/admin/health/live`
- Readiness probe: `/admin/health/ready` (checks audit log write latency < 100ms)
- pg_cron job monitoring for partition maintenance

### Sensitive Action Notifications
- Recipients: `admin-approvers@lender.com`, `compliance-team@lender.com`
- Format: Encrypted email with approval link (expires in 4 hours)
- SMS fallback for super admin actions using Twilio with audit trail

---

**WARNING**: This module handles highly privileged operations. All code must undergo:
1. Static security scan (`uv run pip-audit`)
2. Role-based access control unit tests (100% coverage)
3. FINTRAC compliance review before production deployment