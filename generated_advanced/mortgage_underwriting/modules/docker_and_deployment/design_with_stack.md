# Design: Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Docker & Deployment Module Design Plan

## 1. Endpoints

### Health Check Endpoints (All Services)

**Backend Health Check**
- **Method:** `GET /api/v1/health`
- **Auth:** Public (no authentication)
- **Response Schema:**
  ```json
  {
    "status": "healthy|degraded|unhealthy",
    "service": "mortgage-underwriting-backend",
    "version": "string",
    "checks": {
      "database": {"status": "ok|error", "latency_ms": "Decimal"},
      "redis": {"status": "ok|error", "latency_ms": "Decimal"},
      "minio": {"status": "ok|error", "latency_ms": "Decimal"}
    },
    "timestamp": "ISO 8601 datetime"
  }
  ```
- **Error Responses:**
  - `503 Service Unavailable` - `DEPLOY_001` - "Service unhealthy: {service} check failed"
  - `500 Internal Server Error` - `DEPLOY_002` - "Health check execution failed"

**Orchestrator Health Check**
- **Method:** `GET /api/v1/orchestrator/health`
- **Auth:** Service-to-service (mTLS)
- **Response Schema:**
  ```json
  {
    "status": "healthy|degraded|unhealthy",
    "service": "orchestrator",
    "dependencies": {
      "backend": {"status": "ok|error", "latency_ms": "Decimal"},
      "decision": {"status": "ok|error", "latency_ms": "Decimal"},
      "policy": {"status": "ok|error", "latency_ms": "Decimal"},
      "dpt": {"status": "ok|error", "latency_ms": "Decimal"}
    },
    "timestamp": "ISO 8601 datetime"
  }
  ```

**Service-Specific Health Checks**
- **DPT Service:** `GET /api/v1/dpt/health` - Validates model loading status
- **Decision Service:** `GET /api/v1/decision/health` - Validates calculation engine
- **Policy Service:** `GET /api/v1/policy/health` - Validates XML schema cache

**Deployment Status Endpoint** (Admin Only)
- **Method:** `GET /api/v1/admin/deployment/status`
- **Auth:** Admin-only (JWT + role claim)
- **Response Schema:**
  ```json
  {
    "environment": "development|staging|production",
    "version": "string",
    "services": {
      "backend": {"status": "running|stopped", "replicas": "int", "image": "string"},
      "postgres": {"status": "running|stopped", "volume_size_gb": "Decimal"},
      "redis": {"status": "running|stopped"},
      "minio": {"status": "running|stopped", "bucket_count": "int"}
    },
    "regulatory_compliance": {
      "fintrac_retention_years": "int",
      "encryption_enabled": "bool",
      "audit_logging": "bool"
    }
  }
  ```

## 2. Models & Database

### Deployment Metadata Tables

**Table: `deployment_audit_logs`**
```sql
CREATE TABLE deployment_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(50) NOT NULL, -- 'deploy', 'rollback', 'scale', 'config_update'
    service_name VARCHAR(100) NOT NULL,
    version VARCHAR(50),
    executed_by VARCHAR(100), -- Service account or user ID
    status VARCHAR(20) NOT NULL, -- 'started', 'success', 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL,
    -- FINTRAC compliance: immutable audit trail
    CONSTRAINT deployment_audit_logs_immutable CHECK (updated_at IS NULL)
);
CREATE INDEX idx_deployment_audit_logs_created_at ON deployment_audit_logs(created_at);
CREATE INDEX idx_deployment_audit_logs_service_action ON deployment_audit_logs(service_name, action);
```

**Table: `service_health_history`**
```sql
CREATE TABLE service_health_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    check_duration_ms INTEGER,
    error_details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_service_health_history_service_timestamp ON service_health_history(service_name, created_at DESC);
CREATE INDEX idx_service_health_history_status ON service_health_history(status) WHERE status != 'healthy';
```

**Table: `configuration_secrets`**
```sql
-- PIPEDA compliance: encrypted configuration
CREATE TABLE configuration_secrets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(200) UNIQUE NOT NULL,
    encrypted_value BYTEA NOT NULL, -- AES-256 encrypted
    description TEXT,
    last_rotated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_configuration_secrets_key ON configuration_secrets(key);
```

**Table: `fintrac_retention_metadata`**
```sql
-- FINTRAC 5-year retention tracking
CREATE TABLE fintrac_retention_metadata (
    record_id UUID PRIMARY KEY,
    record_type VARCHAR(50) NOT NULL, -- 'transaction', 'identity_verification'
    retention_start_date DATE NOT NULL,
    scheduled_deletion_date DATE NOT NULL, -- +5 years from retention_start_date
    deleted_at TIMESTAMPTZ, -- NULL until actually deleted
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_fintrac_retention_deletion_date ON fintrac_retention_metadata(scheduled_deletion_date) WHERE deleted_at IS NULL;
```

## 3. Business Logic

### Health Check Orchestration Logic
```python
# orchestrator/services/health_service.py
async def perform_comprehensive_health_check() -> HealthStatus:
    """
    Executes parallel health checks to all dependent services
    with circuit breaker pattern to prevent cascade failures
    """
    checks = await asyncio.gather(
        check_backend_health(timeout=5),
        check_decision_service(timeout=3),
        check_policy_service(timeout=3),
        check_dpt_service(timeout=5),
        check_minio_health(timeout=3),
        return_exceptions=True
    )
    
    # Determine overall status
    failed_count = sum(1 for c in checks if isinstance(c, Exception))
    if failed_count == 0:
        return HealthStatus.HEALTHY
    elif failed_count <= 2:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.UNHEALTHY

# OSFI B-20 compliance: Health check must verify calculation engine availability
async def check_decision_service(timeout: int) -> ServiceHealth:
    """
    Validates decision service can perform GDS/TDS calculations
    with stress test rate validation
    """
    response = await http_client.get(
        f"{DECISION_SERVICE_URL}/health",
        timeout=timeout
    )
    if response.status_code != 200:
        raise ServiceUnavailableError("decision_service")
    
    # Verify qualifying rate calculation capability
    health_data = response.json()
    if not health_data.get("can_calculate_stress_test"):
        logger.error("decision_service.stress_test_unavailable")
        raise BusinessRuleViolationError("stress_test_capability_missing")
    
    return ServiceHealth(status="ok", latency_ms=response.elapsed * 1000)
```

### Secrets Rotation Logic
```python
# orchestrator/services/secrets_service.py
async def rotate_encryption_key(old_key: str, new_key: str) -> RotationResult:
    """
    PIPEDA compliance: Periodic encryption key rotation
    - Re-encrypts all PII fields in database
    - Updates configuration_secrets table
    - Creates audit trail
    """
    async with get_async_session() as session:
        # 1. Update application configuration
        await session.execute(
            update(ConfigurationSecrets)
            .where(ConfigurationSecrets.key == "ENCRYPTION_KEY")
            .values(encrypted_value=encrypt_with_new_key(new_key))
        )
        
        # 2. Re-encrypt PII in applicant table
        applicants = await session.execute(
            select(Applicant).where(Applicant.sin_encrypted.isnot(None))
        )
        for applicant in applicants.scalars():
            decrypted_sin = decrypt_with_old_key(applicant.sin_encrypted, old_key)
            applicant.sin_encrypted = encrypt_with_new_key(decrypted_sin, new_key)
        
        # 3. Re-encrypt PII in co_applicant table
        # 4. Create audit log
        await session.commit()
    
    return RotationResult(success=True, records_updated=len(applicants))
```

### FINTRAC Retention Enforcement
```python
# celery/tasks/retention_tasks.py
@celery.task(name="fintrac.enforce_retention_policy")
async def enforce_fintrac_retention_policy():
    """
    Daily task to identify and soft-delete records past 5-year retention
    - Queries fintrac_retention_metadata table
    - Marks records as deleted (never hard delete)
    - Logs deletion for audit purposes
    """
    cutoff_date = date.today() - timedelta(days=365 * 5)
    
    records_to_delete = await session.execute(
        select(FintracRetentionMetadata)
        .where(FintracRetentionMetadata.scheduled_deletion_date <= cutoff_date)
        .where(FintracRetentionMetadata.deleted_at.is_(None))
    )
    
    for record in records_to_delete.scalars():
        # Soft delete the actual record based on type
        if record.record_type == "transaction":
            await session.execute(
                update(TransactionRecord)
                .where(TransactionRecord.id == record.record_id)
                .values(deleted_at=datetime.utcnow())
            )
        
        # Mark metadata as deleted
        record.deleted_at = datetime.utcnow()
        
        # FINTRAC audit requirement: log all deletions
        logger.info(
            "fintrac.record_deleted",
            record_id=str(record.record_id),
            record_type=record.record_type,
            retention_start_date=record.retention_start_date.isoformat()
        )
    
    await session.commit()
```

## 4. Migrations

### New Migration: `001_create_deployment_tables.py`
```python
# alembic/versions/001_create_deployment_tables.py
def upgrade():
    # Deployment audit logs (FINTRAC compliance)
    op.create_table(
        'deployment_audit_logs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=True),
        sa.Column('executed_by', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_deployment_audit_logs_created_at', 'deployment_audit_logs', ['created_at'])
    op.create_index('idx_deployment_audit_logs_service_action', 'deployment_audit_logs', ['service_name', 'action'])

    # Service health history
    op.create_table(
        'service_health_history',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('check_duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_details', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_service_health_history_service_timestamp', 'service_health_history', ['service_name', sa.text('created_at DESC')])
    op.create_index('idx_service_health_history_status', 'service_health_history', ['status'], 
                    postgresql_where=sa.text("status != 'healthy'"))

    # Encrypted configuration secrets (PIPEDA compliance)
    op.create_table(
        'configuration_secrets',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('key', sa.String(length=200), nullable=False),
        sa.Column('encrypted_value', sa.LargeBinary(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('idx_configuration_secrets_key', 'configuration_secrets', ['key'])

    # FINTRAC retention tracking
    op.create_table(
        'fintrac_retention_metadata',
        sa.Column('record_id', UUID(), nullable=False),
        sa.Column('record_type', sa.String(length=50), nullable=False),
        sa.Column('retention_start_date', sa.Date(), nullable=False),
        sa.Column('scheduled_deletion_date', sa.Date(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('record_id')
    )
    op.create_index('idx_fintrac_retention_deletion_date', 'fintrac_retention_metadata', ['scheduled_deletion_date'], 
                    postgresql_where=sa.column('deleted_at').is_(None))

def downgrade():
    op.drop_index('idx_fintrac_retention_deletion_date')
    op.drop_table('fintrac_retention_metadata')
    op.drop_index('idx_configuration_secrets_key')
    op.drop_table('configuration_secrets')
    op.drop_index('idx_service_health_history_status')
    op.drop_index('idx_service_health_history_service_timestamp')
    op.drop_table('service_health_history')
    op.drop_index('idx_deployment_audit_logs_service_action')
    op.drop_index('idx_deployment_audit_logs_created_at')
    op.drop_table('deployment_audit_logs')
```

## 5. Security & Compliance

### Secrets Management Strategy
**PIPEDA & OSFI Requirements:**
- **NEVER** commit secrets to repository or .env files in production
- Use Docker secrets for sensitive data:
  ```yaml
  # docker-compose.production.yml
  secrets:
    db_password:
      external: true
    encryption_key:
      external: true
    jwt_secret:
      external: true
  ```
- Backend service mounts secrets as read-only files:
  ```yaml
  services:
    backend:
      secrets:
        - source: db_password
          target: /run/secrets/db_password
          uid: '1000'
          gid: '1000'
          mode: 0400
  ```
- Application reads secrets from `/run/secrets/` at startup, not from environment variables

### Network Isolation
```yaml
# docker-compose.yml
networks:
  frontend_network:
    driver: bridge
    internal: false  # Exposed to reverse proxy only
  backend_network:
    driver: bridge
    internal: true   # No external access
  database_network:
    driver: bridge
    internal: true
  regulatory_network:
    driver: bridge
    internal: true   # For FINTRAC/CMHC audit services

services:
  nginx:
    networks:
      - frontend_network
  backend:
    networks:
      - frontend_network
      - backend_network
      - regulatory_network
  postgres:
    networks:
      - database_network
      - regulatory_network
  redis:
    networks:
      - backend_network
```

### FINTRAC Compliance in Deployment
- **Immutable Audit Trail:** All deployment actions logged to `deployment_audit_logs` table
- **5-Year Retention:** Celery beat task runs daily to enforce retention policy
- **Transaction Flagging:** Environment variable `FINTRAC_REPORTING_THRESHOLD=10000` configured at deployment
- **No Data Deletion:** All tables use soft deletes; hard delete operations are blocked at database level

### PIPEDA Encryption at Rest
- **Database Encryption:** PostgreSQL `pgcrypto` extension for field-level encryption
- **MinIO Encryption:** Server-side encryption enabled with `MINIO_KMS_AUTO_ENCRYPTION=on`
- **Key Rotation:** Quarterly rotation of `ENCRYPTION_KEY` via Celery scheduled task
- **PII Fields:** SIN, DOB, banking info encrypted with AES-256-GCM in `applicant` and `co_applicant` tables

### OSFI B-20 Calculation Verification
- **Decision Service:** Must be deployed with validated calculation libraries
- **Health Check:** Verifies stress test rate calculation capability on startup
- **Audit Logging:** All GDS/TDS calculations logged with correlation_id for regulatory audit

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Regulatory Context |
|-----------------|-------------|------------|-----------------|-------------------|
| `DeploymentHealthError` | 503 | `DEPLOY_001` | "Service {service_name} unhealthy: {check_failed}" | OSFI: Calculation engine availability |
| `HealthCheckExecutionError` | 500 | `DEPLOY_002` | "Health check failed: {error}" | General operational error |
| `SecretsRotationError` | 500 | `DEPLOY_003` | "Key rotation failed for {service}: {detail}" | PIPEDA: Encryption key management |
| `NetworkIsolationViolation` | 403 | `DEPLOY_004` | "Network policy violation: {service} cannot access {resource}" | Security: Service mesh violation |
| `FintracRetentionError` | 500 | `DEPLOY_005` | "Retention policy enforcement failed: {record_id}" | FINTRAC: 5-year retention requirement |
| `ConfigurationValidationError` | 422 | `DEPLOY_006` | "Invalid configuration: {key} - {reason}" | Deployment configuration |
| `ServiceDependencyError` | 503 | `DEPLOY_007` | "Critical dependency {service} unavailable" | OSFI: Decision service dependency |
| `EncryptionKeyExpired` | 500 | `DEPLOY_008` | "Encryption key expired: rotation required" | PIPEDA: Key lifecycle management |

### Structured Error Response Format
All deployment-related errors return:
```json
{
  "detail": "Service decision unhealthy: stress test calculation unavailable",
  "error_code": "DEPLOY_001",
  "correlation_id": "uuid-v4-string",
  "timestamp": "2024-01-15T10:30:00Z",
  "regulatory_impact": "OSFI_B20" // For compliance-related errors
}
```

---

**File Location:** `docs/design/docker-deployment.md`