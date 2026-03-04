# Design: Admin Panel
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: OnLendHub - Canadian Mortgage Underwriting

# OnLendHub Admin Panel - Architecture Design

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         API Gateway (Kong/Nginx)                    │
│                    ────────────────────────────────────────         │
│                    │ Rate Limiting │ mTLS │ IP Whitelist │         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│                    FastAPI Admin Service                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐    │
│  │ REST API │  │  gRPC    │  │WS Real-  │  │  Health Check   │    │
│  │ Layer    │  │ Service  │  │time Dash │  │  & Metrics      │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬────────┘    │
│       │             │             │                 │               │
│  ┌────▼─────────────▼─────────────▼─────────────────▼─────────────┐ │
│  │              Service Layer (Business Logic)                     │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │ │
│  │  │ UserMgmt │  │LenderMgmt│  │Approval  │  │ AuditLog │       │ │
│  │  │ Service  │  │ Service  │  │ Workflow │  │ Service  │       │ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │ │
│  └───────┼─────────────┼─────────────┼─────────────┼───────────────┘ │
│          │             │             │             │                 │
│  ┌───────▼─────────────▼─────────────▼─────────────▼───────────────┐ │
│  │              Repository Layer (SQLAlchemy 2.0)                   │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │ │
│  │  │ UserRepo │  │LenderRepo│  │Approval  │  │ AuditRepo│        │ │
│  │  │          │  │          │  │Repo      │  │          │        │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└────────────────────────┬──────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────────────────┐
│   PostgreSQL 15 (Primary) ────► Read Replicas                        │
│   ├─ audit_logs (JSONB + GIN)                                        │
│   ├─ approval_requests                                               │
│   └─ WAL Archival to S3 (Immutable)                                  │
└────────────────────────┬──────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────────────────┐
│   RabbitMQ ──► Celery Workers (Async Audit Logging)                  │
│   Redis (Cache/Sessions/Rate Limiting)                               │
│   S3 Glacier (7-year FINTRAC retention)                              │
│   Prometheus + Grafana + Alertmanager                                │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 2. Database Schema Design

### Core Tables

```sql
-- Enhanced audit_logs with compliance features
CREATE TABLE audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    correlation_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100),
    old_value JSONB,
    new_value JSONB,
    ip_address INET,
    user_agent TEXT,
    approval_id UUID REFERENCES approval_requests(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retention_tier VARCHAR(20) DEFAULT 'hot' -- hot/warm/cold
);
CREATE INDEX idx_audit_logs_correlation ON audit_logs(correlation_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_action ON audit_logs USING GIN (action);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);

-- Approval workflow for sensitive actions
CREATE TABLE approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requestor_id UUID NOT NULL REFERENCES users(id),
    action_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending/approved/rejected/expired
    approver_id UUID REFERENCES users(id),
    approval_comment TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_expires CHECK (expires_at > created_at)
);
CREATE INDEX idx_approval_status ON approval_requests(status, expires_at);

-- Admin role-based permissions (ABAC-ready)
CREATE TABLE admin_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL, -- { "resources": ["users", "lenders"], "actions": ["read", "write"] }
    is_super_admin BOOLEAN DEFAULT FALSE,
    requires_mfa BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_admin_roles (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    role_id UUID NOT NULL REFERENCES admin_roles(id),
    assigned_by UUID REFERENCES users(id),
    assigned_at TIMESTAMPTZ DEFAULT NOW()
);

-- Lender product rate versioning for audit trail
CREATE TABLE lender_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id UUID NOT NULL REFERENCES lenders(id),
    product_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    rate DECIMAL(10,4) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    version INT NOT NULL DEFAULT 1,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(lender_id, product_code, version)
);
CREATE INDEX idx_lender_products_active ON lender_products(lender_id, is_active, effective_from);
```

---

## 3. API Endpoint Specifications

### 3.1 Admin User Management

```python
# GET /admin/users
class UserListResponse(BaseModel):
    users: List[UserAdminView]
    total: int
    page: int
    per_page: int
    
    class Config:
        # Performance: Use ORM mode with selectinload for roles
        from_attributes = True

# PUT /admin/users/{id}/deactivate
class DeactivateUserRequest(BaseModel):
    reason: str = Field(..., min_length=10)
    requires_approval: bool = True
    
# PUT /admin/users/{id}/role
class UpdateRoleRequest(BaseModel):
    role_id: UUID
    justification: str
    send_notification: bool = True
```

### 3.2 Lender & Product Management

```python
# POST /admin/lenders
class CreateLenderRequest(BaseModel):
    name: str
    institution_number: str = Field(..., pattern=r"^\d{3}$")
    contact_info: Dict[str, Any]
    
# POST /admin/lenders/{id}/products
class AddProductRequest(BaseModel):
    product_code: str
    name: str
    rate: Decimal = Field(..., decimal_places=4)
    # Triggers approval workflow if rate < market_rate - 2%
```

### 3.3 Audit & Compliance

```python
# GET /admin/audit-logs
class AuditLogQuery(BaseModel):
    entity_type: Optional[str] = None
    user_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    correlation_id: Optional[UUID] = None
    
    @validator('date_to')
    def date_range_valid(cls, v, values):
        if values.get('date_from') and v:
            assert v > values['date_from'], "date_to must be after date_from"
        return v

# GET /admin/fintrac/reports
class FintracReportResponse(BaseModel):
    report_id: str
    generation_date: datetime
    report_type: Literal["LCTR", "STR", "EFTR"]
    status: Literal["pending", "filed", "amended"]
    data_url: str  # Pre-signed S3 URL (5-min expiry)
```

### 3.4 New Endpoints for Missing Requirements

```python
# POST /admin/approvals (for sensitive actions)
class ApprovalRequestPayload(BaseModel):
    action: str
    resource: str
    payload: Dict[str, Any]
    
# GET /admin/dashboard/activity-stream (WebSocket)
class ActivityStreamMessage(BaseModel):
    event_type: str
    timestamp: datetime
    user: UserSummary
    action: str
    resource: str

# GET /admin/system/health
class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    checks: Dict[str, ComponentHealth]
    last_audit_purge: datetime
```

---

## 4. Security & Authorization Design

### 4.1 OAuth2 Scope Definition (ABAC + RBAC)

```python
# scopes.py
class AdminScopes:
    # Role-based scopes
    SUPER_ADMIN = "admin:*"
    COMPLIANCE_READ = "admin:compliance:read"
    COMPLIANCE_WRITE = "admin:compliance:write"
    USER_MANAGE = "admin:users:manage"
    LENDER_MANAGE = "admin:lenders:manage"
    RATE_CHANGE = "admin:rates:change"
    AUDIT_READ = "admin:audit:read"
    
    # Resource-specific scopes with attributes
    LENDER_SCOPE = "admin:lender:{lender_id}:*"
    PRODUCT_SCOPE = "admin:lender:{lender_id}:product:{product_id}"

# Dependency injection for authorization
async def require_admin_permission(
    required_permission: str,
    user: User = Depends(get_current_user),
    resource: Dict = Depends(extract_resource)
) -> User:
    """Attribute-based access control"""
    if user.role.is_super_admin:
        return user
    
    # Check resource-level permissions
    if not await permission_service.check(
        user.id,
        required_permission,
        resource
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Insufficient permissions",
                "required": required_permission,
                "resource": resource
            }
        )
    return user
```

### 4.2 mTLS Implementation

```yaml
# Kubernetes deployment
apiVersion: v1
kind: ConfigMap
metadata:
  name: admin-panel-ssl
data:
  ssl-ca-cert: |
    # CA cert for mutual TLS
  ssl-server-cert: |
    # Server certificate with SAN: admin.onlendhub.ca
```

```python
# FastAPI mTLS config
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.load_cert_chain('server.crt', 'server.key')
ssl_context.load_verify_locations('ca.crt')

uvicorn.run(
    app,
    host="0.0.0.0",
    port=8443,
    ssl=ssl_context,
    limit_concurrency=100  # DDoS protection
)
```

---

## 5. Audit Logging System (Async & Immutable)

### 5.1 Dual-Write Pattern

```python
# audit_service.py
class AuditService:
    def __init__(self, db: AsyncSession, celery: Celery):
        self.db = db
        self.celery = celery
    
    async def log_action(
        self,
        user_id: UUID,
        action: str,
        entity_type: str,
        entity_id: str,
        old_value: Dict,
        new_value: Dict,
        correlation_id: UUID,
        requires_approval: bool = False
    ) -> UUID:
        """Async audit logging with write-ahead to WAL"""
        
        # 1. Write to PostgreSQL (hot storage)
        audit_id = uuid4()
        audit_record = AuditLog(
            id=audit_id,
            correlation_id=correlation_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
            retention_tier='hot'
        )
        
        # 2. Async queue for cold storage
        self.celery.send_task(
            'tasks.archive_audit_log',
            args=[audit_record.dict()],
            queue='audit'
        )
        
        # 3. Trigger notifications if sensitive
        if action in AuditTrackedActions.SENSITIVE_ACTIONS:
            await self._trigger_security_alert(audit_record)
        
        return audit_id

# Celery task for immutable archival
@celery_app.task(bind=True, max_retries=3)
def archive_audit_log(self, audit_data: Dict):
    """Write to S3 with WORM compliance"""
    try:
        s3_key = f"audit-logs/{audit_data['created_at'][:10]}/{audit_data['id']}.json"
        s3_client.put_object(
            Bucket='onlendhub-audit-immutable',
            Key=s3_key,
            Body=json.dumps(audit_data),
            ServerSideEncryption='aws:kms',
            StorageClass='GLACIER_IR',
            Tagging=f"retention=fintrac&expiry={audit_data['created_at'][:4] + 5}"
        )
    except Exception as e:
        raise self.retry(exc=e, countdown=60)
```

### 5.2 Tracked Actions Enum

```python
class AuditTrackedActions:
    APPLICATION_STATUS_CHANGE = "application:status:change"
    UW_DECISION_OVERRIDE = "underwriting:decision:override"
    DOCUMENT_VERIFY_REJECT = "document:verification:action"
    FINTRAC_RECORD_UPDATE = "fintrac:record:update"
    USER_ROLE_CHANGE = "user:role:change"
    LENDER_RATE_CHANGE = "lender:rate:change"
    
    SENSITIVE_ACTIONS = {
        UW_DECISION_OVERRIDE,
        USER_ROLE_CHANGE,
        LENDER_RATE_CHANGE
    }
```

---

## 6. Missing Details - Deep Dive

### 6.1 Admin Authorization Scope Definition

**Implementation**: Hybrid RBAC + ABAC model

```python
# roles.yaml (version controlled)
roles:
  super_admin:
    permissions: ["*"]
    requires_mfa: true
    approval_required: false
    
  compliance_officer:
    permissions:
      - "admin:compliance:*"
      - "admin:audit:*"
      - "admin:fintrac:*"
    requires_mfa: true
    approval_required: false
    allowed_ip_ranges: ["10.0.2.0/24"]  # Office only
    
  lender_admin:
    permissions:
      - "admin:lender:{lender_id}:read"
      - "admin:lender:{lender_id}:product:write"
    requires_mfa: true
    approval_required: true  # For rate changes
    lender_scope: true
```

**Complexity Handling**: Use policy engine (OPA - Open Policy Agent) for real-time permission evaluation.

```rego
# policy.rego
package onlendhub.authz

default allow = false

allow {
    input.user.role.is_super_admin
}

allow {
    some permission in input.user.role.permissions
    permission == input.required_permission
    input.resource.lender_id in input.user.assigned_lenders
}
```

### 6.2 Audit Log Retention Policy

**Tiered Storage Strategy**:
- **Hot (0-90 days)**: PostgreSQL primary table, partitioned by month
- **Warm (90 days-2 years)**: PostgreSQL read replica, compressed partitions
- **Cold (2-7 years)**: S3 Glacier Instant Retrieval
- **Frozen (7+ years)**: S3 Glacier Deep Archive (if required by OSFI)

```python
# retention_policy.py
class AuditRetentionPolicy:
    FINTRAC_RETENTION_YEARS = 7
    OSFI_RETENTION_YEARS = 7
    
    async def enforce_policy(self):
        """Daily cron job"""
        cutoff_date = datetime.now() - timedelta(days=90)
        
        # Move to warm storage
        await self.db.execute("""
            ALTER TABLE audit_logs 
            DETACH PARTITION audit_logs_y2024m01;
            
            -- Compress and attach to read replica
        """)
        
        # Archive to S3 Glacier
        logs_to_archive = await self.db.execute(
            select(AuditLog).where(AuditLog.created_at < cutoff_date)
        )
        
        for log in logs_to_archive:
            await self._archive_to_glacier(log)
```

### 6.3 Admin Action Approval Workflow

**State Machine Design** (using SQLAlchemy ORM + Temporal.io for complex workflows)

```python
# approval_workflow.py
class ApprovalStateMachine:
    def __init__(self, approval_id: UUID):
        self.approval_id = approval_id
    
    async def request_approval(self, payload: Dict, expires_in: int = 24):
        """Create approval request and notify approvers"""
        
        # Store in DB
        approval = ApprovalRequest(
            requestor_id=payload['user_id'],
            action_type=payload['action'],
            resource_type=payload['entity_type'],
            resource_id=payload['entity_id'],
            payload=payload,
            expires_at=datetime.now() + timedelta(hours=expires_in)
        )
        
        # Send to approvers' queue (compliance team)
        await notification_service.send_to_group(
            group="compliance_approvers",
            template="approval_request",
            data={
                "approval_id": approval.id,
                "action": payload['action'],
                "requestor": payload['user_name'],
                "resource": f"{payload['entity_type']}:{payload['entity_id']}"
            },
            priority="high"
        )
        
        # Start timeout workflow
        await temporal_client.start_workflow(
            "approval_timeout_wf",
            args=[approval.id],
            task_queue="approvals",
            workflow_id=f"approval-timeout-{approval.id}"
        )
    
    async def approve(self, approver_id: UUID, comment: str):
        """Approve and execute action"""
        async with self.db.transaction():
            approval = await self._get_and_lock()
            
            if approval.status != "pending":
                raise ApprovalExpiredError()
            
            # Update status
            approval.status = "approved"
            approval.approver_id = approver_id
            approval.approval_comment = comment
            
            # Execute the deferred action
            await self._execute_action(approval.payload)
            
            # Log the approval decision
            await audit_service.log_action(
                user_id=approver_id,
                action="approval:grant",
                entity_type="approval_request",
                entity_id=str(approval.id),
                old_value={"status": "pending"},
                new_value={"status": "approved"}
            )
```

**Approval Matrix**:
| Action | Requires Approval | Approver Group | Timeout | Auto-escalation |
|--------|-------------------|----------------|---------|-----------------|
| User Deactivation | No (if self) | Manager | 24h | Yes |
| Role Change (to admin) | Yes | Compliance | 48h | Yes |
| Lender Rate Change >2% | Yes | Risk Committee | 72h | No |
| FINTRAC Record Amend | Yes | Compliance + Legal | 96h | No |

### 6.4 User Activity Dashboard Design

**Real-time Architecture**:
- **Backend**: FastAPI WebSocket endpoint with Redis Pub/Sub
- **Frontend**: React + WebSocket reconnection logic
- **Analytics**: ClickHouse for OLAP queries on audit logs

```python
# websocket_dashboard.py
@app.websocket("/admin/dashboard/activity-stream")
async def activity_stream(
    websocket: WebSocket,
    user: User = Depends(require_admin_permission("admin:dashboard:read"))
):
    await websocket.accept()
    
    # Subscribe to Redis channel
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("audit:events")
    
    # Send historical baseline
    recent_activity = await audit_service.get_recent_activity(limit=50)
    await websocket.send_json({
        "type": "baseline",
        "data": recent_activity
    })
    
    # Stream real-time events
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                event = json.loads(message['data'])
                
                # Filter by user permissions
                if await permission_service.can_view_event(user, event):
                    await websocket.send_json({
                        "type": "event",
                        "data": event
                    })
    except WebSocketDisconnect:
        await pubsub.unsubscribe()

# Metrics aggregation service
class DashboardMetricsService:
    async def get_risk_indicators(self):
        """Detect suspicious patterns"""
        return {
            "unusual_rate_changes": await self._detect_outliers(),
            "after_hours_activity": await self._get_after_hours_logins(),
            "failed_approval_attempts": await self._count_failed_approvals(),
            "mfa_bypass_attempts": await self._detect_mfa_bypass()
        }
```

### 6.5 System Health Monitoring Integration

**Observability Stack**:
- **Metrics**: Prometheus with custom FastAPI instrumentation
- **Tracing**: OpenTelemetry with Jaeger backend
- **Logging**: ELK Stack with JSON structured logs
- **Alerting**: Alertmanager with PagerDuty integration

```python
# monitoring.py
from prometheus_client import Counter, Histogram, Gauge

# Custom metrics
ADMIN_ACTIONS = Counter(
    'admin_actions_total',
    'Total admin actions by type',
    ['action', 'status', 'user_role']
)

AUDIT_LOG_AGE = Histogram(
    'audit_log_age_seconds',
    'Time between action and audit log write'
)

DB_CONNECTION_POOL = Gauge(
    'db_pool_connections',
    'Active DB connections'
)

# Health check endpoint
@app.get("/admin/system/health", tags=["monitoring"])
async def health_check(
    deep: bool = False,
    user: User = Depends(require_admin_permission("admin:system:health"))
):
    checks = {
        "postgres": await db_health_check(),
        "redis": await redis_health_check(),
        "temporal": await temporal_health_check(),
        "audit_archival": await s3_health_check()
    }
    
    status = "healthy" if all(c['status'] == 'ok' for c in checks.values()) else "degraded"
    
    # Deep health includes audit log lag
    if deep:
        checks['audit_lag'] = await get_audit_lag()
    
    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": checks
    }

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    path = request.url.path
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=path,
        status=response.status_code
    ).observe(duration)
    
    return response
```

### 6.6 Sensitive Action Notification Recipients

**Notification Service with Template Engine**:

```python
# notification_service.py
class NotificationRouter:
    def __init__(self):
        self.recipients = {
            "high_risk": ["security@onlendhub.ca", "compliance@onlendhub.ca"],
            "compliance": ["compliance@onlendhub.ca", "legal@onlendhub.ca"],
            "operational": ["ops@onlendhub.ca"],
            "lender_specific": self._get_lender_admins
        }
    
    async def route_notification(
        self,
        event: AuditLog,
        severity: Literal["low", "medium", "high", "critical"]
    ):
        """Route based on action type and severity"""
        
        # Determine recipients
        if event.action in [
            AuditTrackedActions.UW_DECISION_OVERRIDE,
            AuditTrackedActions.FINTRAC_RECORD_UPDATE
        ]:
            recipients = self.recipients["compliance"]
        elif event.action == AuditTrackedActions.USER_ROLE_CHANGE:
            recipients = self.recipients["high_risk"]
        elif event.action == AuditTrackedActions.LENDER_RATE_CHANGE:
            recipients = await self.recipients["lender_specific"](event.entity_id)
        else:
            recipients = self.recipients["operational"]
        
        # Send via multiple channels
        tasks = []
        for channel in ['email', 'slack']:
            tasks.append(
                self._send_notification(
                    channel=channel,
                    recipients=recipients,
                    template=f"{event.action}_{severity}",
                    context={
                        "user": event.user_id,
                        "action": event.action,
                        "resource": f"{event.entity_type}:{event.entity_id}",
                        "timestamp": event.created_at.isoformat(),
                        "ip": str(event.ip_address)
                    }
                )
            )
        
        await asyncio.gather(*tasks, return_exceptions=True)

# Notification templates (stored in DB)
NOTIFICATION_TEMPLATES = {
    "user:role:change_critical": {
        "subject": "CRITICAL: Admin Role Change Detected",
        "body": """
        User {user} changed role for resource {resource} at {timestamp}.
        IP: {ip}
        Immediate review required.
        """,
        "escalation_policy": "page_oncall_compliance"
    }
}
```

---

## 7. Implementation Layers

### 7.1 Repository Pattern (SQLAlchemy 2.0 Async)

```python
# repositories/audit_repository.py
class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, audit_log: AuditLog) -> AuditLog:
        """Insert with RETURNING for immediate confirmation"""
        result = await self.session.execute(
            insert(AuditLog).values(**audit_log.dict()).returning(AuditLog)
        )
        return result.scalar_one()
    
    async def query_with_filters(
        self,
        filters: AuditLogQuery,
        limit: int = 100
    ) -> List[AuditLog]:
        """Complex query with GIN index optimization"""
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        
        if filters.correlation_id:
            stmt = stmt.where(AuditLog.correlation_id == filters.correlation_id)
        
        if filters.entity_type:
            stmt = stmt.where(AuditLog.entity_type == filters.entity_type)
        
        if filters.user_id:
            stmt = stmt.where(AuditLog.user_id == filters.user_id)
        
        # Time range query with partition pruning
        if filters.date_from and filters.date_to:
            stmt = stmt.where(
                AuditLog.created_at.between(filters.date_from, filters.date_to)
            )
        
        result = await self.session.execute(stmt.limit(limit))
        return result.scalars().all()
```

### 7.2 Service Layer with Unit of Work

```python
# services/lender_service.py
class LenderService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
    
    async def update_product_rate(
        self,
        lender_id: UUID,
        product_id: UUID,
        new_rate: Decimal,
        user: User
    ) -> UUID:
        """Complex transaction with approval workflow"""
        
        async with self.uow:
            # Check permission
            await permission_service.check(
                user.id,
                "admin:lender:product:rate:change",
                {"lender_id": lender_id}
            )
            
            # Get current product
            product = await self.uow.lender_products.get(product_id)
            
            # Calculate rate delta
            rate_delta = ((new_rate - product.rate) / product.rate) * 100
            
            # If delta > 2%, require approval
            requires_approval = abs(rate_delta) > 2
            
            # Create audit trail BEFORE change
            audit_id = await self.uow.audit_logs.log_action(
                user_id=user.id,
                action=AuditTrackedActions.LENDER_RATE_CHANGE,
                entity_type="lender_product",
                entity_id=str(product_id),
                old_value={"rate": str(product.rate), "version": product.version},
                new_value={"rate": str(new_rate), "version": product.version + 1},
                requires_approval=requires_approval
            )
            
            if requires_approval:
                # Create approval request
                approval_id = await self.uow.approvals.request(
                    requestor_id=user.id,
                    action_type="rate_change",
                    resource_type="lender_product",
                    resource_id=str(product_id),
                    payload={
                        "lender_id": str(lender_id),
                        "product_id": str(product_id),
                        "old_rate": str(product.rate),
                        "new_rate": str(new_rate),
                        "audit_id": str(audit_id)
                    },
                    expires_in=72
                )
                
                await self.uow.commit()
                return approval_id
            
            # Otherwise, execute immediately
            await self.uow.lender_products.update_rate(product_id, new_rate)
            await self.uow.commit()
            
            return audit_id
```

---

## 8. Infrastructure & Deployment

### 8.1 Kubernetes Manifests

```yaml
# admin-panel-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: admin-panel
spec:
  replicas: 3
  selector:
    matchLabels:
      app: admin-panel
  template:
    metadata:
      labels:
        app: admin-panel
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: admin-panel-sa
      containers:
      - name: admin-api
        image: onlendhub/admin-panel:1.0.0
        ports:
        - containerPort: 8443
          name: https
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: admin-db-credentials
              key: url
        - name: AUDIT_S3_BUCKET
          value: "onlendhub-audit-immutable"
        - name: TEMPORAL_HOST
          value: "temporal.onlendhub.svc.cluster.local"
        volumeMounts:
        - name: ssl-certs
          mountPath: /etc/ssl/certs
          readOnly: true
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /admin/system/health
            port: 8443
            scheme: HTTPS
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /admin/system/health?deep=true
            port: 8443
            scheme: HTTPS
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: ssl-certs
        secret:
          secretName: admin-panel-tls
---
# NetworkPolicy for admin panel
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: admin-panel-netpol
spec:
  podSelector:
    matchLabels:
      app: admin-panel
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: api-gateway
    - ipBlock:
        cidr: 10.0.0.0/8  # Office VPN only
    ports:
    - protocol: TCP
      port: 8443
```

### 8.2 CI/CD Pipeline (GitLab CI)

```yaml
# .gitlab-ci.yml
stages:
  - test
  - security-scan
  - compliance-check
  - deploy

admin-panel-test:
  stage: test
  script:
    - pytest tests/admin/ --cov=admin_panel --cov-fail-under=90
    - pytest tests/integration/test_audit_trail.py
  artifacts:
    reports:
      junit: test-results.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

admin-panel-security:
  stage: security-scan
  script:
    - bandit -r admin_panel/ -f json -o bandit-report.json
    - safety check --json --output safety-report.json
  artifacts:
    reports:
      sast: bandit-report.json

admin-panel-compliance:
  stage: compliance-check
  script:
    # Verify audit log schema matches FINTRAC requirements
    - python scripts/verify_fintrac_schema.py
    # Check retention policy configs
    - python scripts/verify_retention_policy.py
  only:
    - main

admin-panel-deploy-prod:
  stage: deploy
  script:
    - kubectl apply -f k8s/admin-panel/
    - kubectl rollout status deployment/admin-panel -n production
    - pytest tests/smoke/test_admin_panel.py --env=prod
  environment:
    name: production
    url: https://admin.onlendhub.ca
  only:
    - main
  when: manual  # Requires approval
```

---

## 9. Code Examples - Critical Path

### 9.1 Audit Log Decorator (AOP Pattern)

```python
# decorators.py
def audit_trail(action: str, entity_type: str):
    """Decorator for automatic audit logging"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = kwargs.get('user') or kwargs.get('current_user')
            
            # Get entity_id from path parameters
            entity_id = kwargs.get('entity_id') or kwargs.get('id')
            
            # Store old value before execution
            old_value = await get_current_state(entity_type, entity_id)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Log after execution
            await audit_service.log_action(
                user_id=user.id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                old_value=old_value,
                new_value=await get_current_state(entity_type, entity_id),
                correlation_id=kwargs.get('correlation_id', uuid4())
            )
            
            return result
        return wrapper
    return decorator

# Usage
@audit_trail(
    action=AuditTrackedActions.USER_ROLE_CHANGE,
    entity_type="user"
)
async def update_user_role(
    user_id: UUID,
    role_id: UUID,
    user: User = Depends(get_current_user)
):
    # Function logic here
    pass
```

### 9.2 Decimal Handling for Rates

```python
# financial_types.py
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.types import TypeDecorator

class RateDecimal(TypeDecorator):
    """SQLAlchemy type for mortgage rates"""
    impl = Numeric(precision=10, scale=4)
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            # Ensure proper rounding
            return Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return Decimal(value)
        return value

# Usage in model
class LenderProduct(Base):
    __tablename__ = "lender_products"
    
    rate: Mapped[Decimal] = mapped_column(RateDecimal, nullable=False)
    
    @validates('rate')
    def validate_rate(self, key, rate):
        if rate < 0 or rate > 50:
            raise ValueError("Rate must be between 0 and 50%")
        return rate
```

---

## 10. Complexity Considerations

### 10.1 Distributed Transaction Handling

**Problem**: Audit logging must succeed even if main transaction fails (compliance requirement).

**Solution**: Outbox Pattern + Event Sourcing

```python
# outbox_pattern.py
class OutboxMessage(Base):
    """Reliable audit event publishing"""
    __tablename__ = "outbox_messages"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str]
    payload: Mapped[Dict] = mapped_column(JSONB)
    created_at: Mapped[datetime]
    published_at: Mapped[Optional[datetime]]
    retry_count: Mapped[int] = mapped_column(default=0)

# In transaction
async def create_lender_with_audit():
    async with uow:
        lender = await uow.lenders.create(lender_data)
        
        # Write to outbox within same transaction
        outbox = OutboxMessage(
            event_type="lender:created",
            payload={
                "lender_id": str(lender.id),
                "created_by": str(user.id),
                "timestamp": datetime.now().isoformat()
            }
        )
        await uow.outbox.add(outbox)
        await uow.commit()  # Both or none
    
    # Async publish to audit service
    await event_bus.publish(outbox)
```

### 10.2 Rate Limiting & DDoS Protection

```python
# rate_limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://redis:6379",
    strategy="moving-window"  # More accurate than fixed-window
)

# Apply to sensitive endpoints
@app.put("/admin/users/{id}/role")
@limiter.limit("5/minute")  # Stricter limit for role changes
@limiter.limit("20/hour")
async def update_user_role(...):
    pass
```

### 10.3 Data Consistency & Replication Lag

**Solution**: Read-after-write consistency using correlation IDs

```python
# In user service
async def deactivate_user(user_id: UUID):
    correlation_id = uuid4()
    
    # Write to primary
    await db_primary.execute(
        update(User).where(User.id == user_id).values(is_active=False)
    )
    
    # Wait for replication (configurable)
    await wait_for_replication(
        correlation_id=correlation_id,
        timeout=2.0,
        read_replicas=['db-replica-1', 'db-replica-2']
    )
    
    # Now safe to read from replica
    return await db_replica.get(user_id)
```

---

## 11. Compliance & Security Checklist

- [ ] **FINTRAC Compliance**: All audit logs include IP, timestamp, user agent
- [ ] **OSFI Guideline B-13**: Rate change approvals logged with justification
- [ ] **PIPEDA**: Audit logs anonymized after 1 year (internal policy)
- [ ] **SOC 2 Type II**: Immutable audit trail with SHA-256 checksums
- [ ] **ISO 27001**: Role-based access with quarterly access reviews
- [ ] **Penetration Testing**: Admin endpoints in scope for annual pentest
- [ ] **Disaster Recovery**: Audit logs replicated to secondary region (CA-CENTRAL-1)

---

## 12. Performance Targets

| Metric | Target | Implementation |
|--------|--------|----------------|
| API Response Time (p95) | < 200ms | Connection pooling, Redis cache |
| Audit Log Write Latency | < 50ms | Async Celery + PostgreSQL UNLOGGED table |
| Dashboard Load Time | < 1s | Materialized views + WebSocket |
| Concurrent Admin Users | 100+ | Kubernetes HPA (2-10 replicas) |
| Audit Query (1M rows) | < 500ms | Partitioning + GIN indexes |

---

This architecture addresses all requirements and missing details while maintaining compliance with Canadian financial regulations (FINTRAC, OSFI) and implementing enterprise-grade security patterns.