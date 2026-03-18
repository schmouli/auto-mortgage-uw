# Infrastructure & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Infrastructure & Deployment Design Plan

**File:** `docs/design/infrastructure-deployment.md`

---

## 1. Endpoints

### 1.1 Health & Monitoring Endpoints

| Service | Method | Path | Auth | Purpose |
|---------|--------|------|------|---------|
| All Services | GET | `/health/live` | Public | Liveness probe (Kubernetes) |
| All Services | GET | `/health/ready` | Public | Readiness probe (Kubernetes) |
| All Services | GET | `/health/deep` | Service-to-Service mTLS | Deep health: DB, Redis, S3 |
| Orchestrator | GET | `/api/v1/infrastructure/services` | Admin JWT | List all service statuses |
| Orchestrator | POST | `/api/v1/infrastructure/deployments` | Admin JWT | Trigger new deployment |
| Orchestrator | GET | `/api/v1/infrastructure/deployments/{id}` | Admin JWT | Get deployment status |

#### 1.1.1 Request/Response Schemas

**GET /health/ready**
```json
// Response 200 OK
{
  "status": "healthy",
  "service": "orchestrator",
  "timestamp": "2024-01-15T14:30:00Z",
  "checks": {
    "database": "connected",
    "redis": "connected"
  }
}

// Response 503 Service Unavailable
{
  "detail": "Service not ready",
  "error_code": "INFRA_001",
  "failing_checks": ["redis"]
}
```

**GET /api/v1/infrastructure/services**
```json
// Response 200 OK
{
  "services": [
    {
      "name": "dpt",
      "status": "healthy",
      "replicas": 3,
      "version": "1.2.4",
      "last_deployed": "2024-01-15T10:00:00Z"
    }
  ]
}
```

**POST /api/v1/infrastructure/deployments**
```json
// Request
{
  "service": "decision",
  "version": "1.3.0",
  "strategy": "rolling_update",
  "created_by": "admin@lender.ca"
}

// Response 202 Accepted
{
  "deployment_id": "dep_01hqn9k...",
  "status": "in_progress",
  "created_at": "2024-01-15T14:30:00Z"
}
```

### 1.2 Error Responses

| HTTP Status | Error Code | Message Pattern | Trigger |
|-------------|------------|-----------------|---------|
| 503 | INFRA_001 | "Service {name} unhealthy: {check} failed" | Health check failure |
| 401 | INFRA_002 | "mTLS certificate invalid or missing" | Service-to-service auth failure |
| 409 | INFRA_003 | "Deployment already in progress for {service}" | Concurrent deployment attempt |
| 422 | INFRA_004 | "Invalid deployment strategy: {strategy}" | Validation error |
| 404 | INFRA_005 | "Deployment {id} not found" | Resource not found |

---

## 2. Models & Database

### 2.1 Infrastructure State Tables

```python
# Table: infrastructure_deployments
class InfrastructureDeployment(Base):
    __tablename__ = "infrastructure_deployments"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    service_name = Column(String(50), nullable=False, index=True)  # dpt, policy, decision, etc.
    version = Column(String(20), nullable=False)
    status = Column(Enum("pending", "in_progress", "success", "failed"), nullable=False)
    strategy = Column(Enum("rolling_update", "blue_green", "canary"), nullable=False)
    deployed_by = Column(String(255), nullable=False)  # Email for audit trail (FINTRAC)
    
    # Immutable audit fields (FINTRAC 5-year retention)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(255), nullable=False)  # Never updated
    
    # Indexes
    __table_args__ = (
        Index("idx_deployments_service_status", "service_name", "status"),
        Index("idx_deployments_created_at", "created_at"),
    )

# Table: service_health_status
class ServiceHealthStatus(Base):
    __tablename__ = "service_health_status"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    service_name = Column(String(50), nullable=False, index=True)
    replica_id = Column(String(100), nullable=False)
    status = Column(Enum("healthy", "unhealthy", "degraded"), nullable=False)
    check_details = Column(JSONB)  # { "database": "connected", "redis": "failed" }
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Indexes for time-series queries
    __table_args__ = (
        Index("idx_health_service_timestamp", "service_name", "created_at"),
    )

# Table: infrastructure_audit_log (FINTRAC mandatory)
class InfrastructureAuditLog(Base):
    __tablename__ = "infrastructure_audit_log"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    event_type = Column(Enum("deployment", "scaling", "config_change", "access"), nullable=False)
    service_name = Column(String(50), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g., "scale_replicas: 3→5"
    performed_by = Column(String(255), nullable=False)  # Hashed for PIPEDA if contains PII
    
    # Immutable audit trail (FINTRAC)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(255), nullable=False)
    
    # 5-year retention enforced at partition level
    __table_args__ = (
        Index("idx_audit_service_event", "service_name", "event_type"),
        Index("idx_audit_created_at", "created_at"),
    )

# Table: model_versions (MLFlow integration)
class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False, index=True)  # "donut_underwriting"
    version = Column(String(20), nullable=False)
    mlflow_run_id = Column(String(50), nullable=False, unique=True)
    metrics = Column(JSONB)  # { "f1_score": 0.94, "accuracy": 0.96 }
    deployed_at = Column(DateTime(timezone=True))
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(255), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("model_name", "version"),
    )
```

### 2.2 Configuration Management Table

```python
# Table: infrastructure_config
class InfrastructureConfig(Base):
    __tablename__ = "infrastructure_config"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    service_name = Column(String(50), nullable=False, index=True)
    config_key = Column(String(100), nullable=False)
    config_value = Column(EncryptedType)  # AES-256 encryption (PIPEDA)
    is_secret = Column(Boolean, default=False)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    created_by = Column(String(255), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("service_name", "config_key"),
        Index("idx_config_service_key", "service_name", "config_key"),
    )
```

---

## 3. Business Logic

### 3.1 Health Check Orchestration Algorithm

```python
# Pseudocode for orchestrator health aggregation
async def aggregate_service_health(service_name: str) -> dict:
    """
    Collect health from all replicas and determine overall service health.
    Logs every check for FINTRAC audit trail.
    """
    replica_statuses = await get_replica_health_from_k8s(service_name)
    
    total_replicas = len(replica_statuses)
    healthy_replicas = sum(1 for r in replica_statuses if r.status == "healthy")
    
    # FINTRAC audit: log health check event
    await audit_log.create(
        event_type="health_check",
        service_name=service_name,
        action=f"replicas_healthy: {healthy_replicas}/{total_replicas}",
        performed_by="system"
    )
    
    if healthy_replicas == total_replicas:
        return {"status": "healthy", "replicas": replica_statuses}
    elif healthy_replicas >= ceil(total_replicas * 0.5):
        return {"status": "degraded", "replicas": replica_statuses}
    else:
        return {"status": "unhealthy", "replicas": replica_statuses}
```

### 3.2 Deployment State Machine

```python
# State transitions with FINTRAC audit logging
class DeploymentStateMachine:
    """
    Immutable state transitions for deployment tracking.
    Every transition creates an audit log entry (FINTRAC requirement).
    """
    
    async def transition(self, deployment_id: UUID, new_status: str):
        deployment = await db.get(deployment_id)
        
        # Validate transition
        valid_transitions = {
            "pending": ["in_progress"],
            "in_progress": ["success", "failed"],
            "success": [],  # Terminal state
            "failed": []    # Terminal state
        }
        
        if new_status not in valid_transitions[deployment.status]:
            raise DeploymentStateError("Invalid state transition")
        
        # Update status
        deployment.status = new_status
        
        # FINTRAC audit: immutable record
        await InfrastructureAuditLog.create(
            event_type="deployment",
            service_name=deployment.service_name,
            action=f"status_change: {deployment.status}→{new_status}",
            performed_by=deployment.created_by
        )
```

### 3.3 Horizontal Pod Autoscaling Logic

```python
# Target metrics for orchestrator and dpt services
autoscaling_rules = {
    "dpt": {
        "min_replicas": 2,
        "max_replicas": 20,
        "metrics": [
            {"type": "cpu", "target": 70},  # Scale at 70% CPU
            {"type": "gpu", "target": 80},  # Scale at 80% GPU (NVIDIA T4)
            {"type": "queue_length", "target": 100}  # Celery queue depth
        ]
    },
    "orchestrator": {
        "min_replicas": 3,
        "max_replicas": 15,
        "metrics": [
            {"type": "cpu", "target": 65},
            {"type": "request_rate", "target": 1000}  # Requests per second
        ]
    }
}

# Scaling decision algorithm
async def evaluate_scaling(service_name: str) -> int:
    """
    Calculate desired replica count based on metrics.
    Logs scaling decisions for FINTRAC audit.
    """
    current_metrics = await prometheus.get_metrics(service_name)
    current_replicas = await k8s.get_current_replicas(service_name)
    
    desired_replicas = current_replicas
    for metric in autoscaling_rules[service_name]["metrics"]:
        if metric["type"] == "cpu":
            if current_metrics.cpu_percent > metric["target"]:
                desired_replicas = max(desired_replicas, 
                                     ceil(current_replicas * 1.5))
    
    # FINTRAC audit: log scaling event
    if desired_replicas != current_replicas:
        await InfrastructureAuditLog.create(
            event_type="scaling",
            service_name=service_name,
            action=f"scale_replicas: {current_replicas}→{desired_replicas}",
            performed_by="system_autoscaler"
        )
    
    return min(desired_replicas, autoscaling_rules[service_name]["max_replicas"])
```

---

## 4. Migrations

### 4.1 New Tables

```sql
-- migration: 001_create_infrastructure_tables.py
"""
Create infrastructure state management tables with FINTRAC compliance.
All tables include created_at, created_by for 5-year audit retention.
"""

CREATE TABLE infrastructure_deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    strategy VARCHAR(20) NOT NULL,
    deployed_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL
);

CREATE INDEX idx_deployments_service_status ON infrastructure_deployments(service_name, status);
CREATE INDEX idx_deployments_created_at ON infrastructure_deployments(created_at);

CREATE TABLE service_health_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL,
    replica_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    check_details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_health_service_timestamp ON service_health_status(service_name, created_at);

-- FINTRAC mandatory audit table (immutable, 5-year retention)
CREATE TABLE infrastructure_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    performed_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL
);

CREATE INDEX idx_audit_service_event ON infrastructure_audit_log(service_name, event_type);
CREATE INDEX idx_audit_created_at ON infrastructure_audit_log(created_at);

-- Partition audit_log by month for 5-year retention management
CREATE TABLE infrastructure_audit_log_2024_01 PARTITION OF infrastructure_audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    mlflow_run_id VARCHAR(50) NOT NULL UNIQUE,
    metrics JSONB,
    deployed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL
);

CREATE UNIQUE INDEX idx_model_name_version ON model_versions(model_name, version);
```

### 4.2 Index Strategy for Compliance Queries

```sql
-- Index for FINTRAC audit retrieval (5-year lookup)
CREATE INDEX idx_audit_log_retrieval ON infrastructure_audit_log 
    (service_name, event_type, created_at) 
    WHERE created_at >= NOW() - INTERVAL '5 years';

-- Partial index for active deployments
CREATE INDEX idx_active_deployments ON infrastructure_deployments (service_name) 
    WHERE status IN ('pending', 'in_progress');
```

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling

- **Encryption at Rest**: All infrastructure configuration secrets stored in `infrastructure_config.config_value` use SQLAlchemy `EncryptedType` with AES-256-GCM via AWS KMS or HashiCorp Vault
- **Log Sanitization**: structlog processors redact SIN, DOB, income patterns from all infrastructure logs
- **Network Isolation**: Kubernetes NetworkPolicy enforces service-to-service mTLS; frontend cannot directly access database pods
- **Secrets Management**: 
  - Local dev: `.env` file (never committed, use `.env.example`)
  - Production: AWS Secrets Manager or Vault; mounted as volumes, not env vars
  - Rotation: Automatic rotation every 90 days for database credentials

### 5.2 FINTRAC Audit Trail Requirements

- **Immutable Logs**: `infrastructure_audit_log` table has no UPDATE/DELETE operations; INSERT-only
- **5-Year Retention**: PostgreSQL partitions created monthly; automated job moves partitions >5 years to Glacier
- **Transaction Logging**: All deployments, scaling events, config changes logged with `created_by` (hashed if contains user PII)
- **Access Logging**: Every `/api/v1/infrastructure` endpoint call creates audit entry with JWT subject

### 5.3 OSFI B-20 Audit Logging

- **Calculation Audit Storage**: Infrastructure ensures GDS/TDS calculation logs from `decision` service are persisted to `infrastructure_audit_log` with `event_type="underwriting_calculation"`
- **Stress Test Rate Logging**: All qualifying_rate calculations logged with breakdown: `max(contract_rate + 2%, 5.25%)`
- **Retention**: Calculation audit entries retained for 5 years in dedicated partition `audit_log_underwriting_calculations`

### 5.4 Production Security Controls

```yaml
# Kubernetes securityContext (applied to all pods)
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 2000
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop: ["ALL"]

# Network policies
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-only-mtls
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector: {}  # Same namespace
    ports:
    - protocol: TCP
      port: 443
```

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Compliance Note |
|-----------------|-------------|------------|-----------------|-----------------|
| `ServiceUnhealthyError` | 503 | INFRA_001 | "Service {name} unhealthy: {check} failed" | Logged to audit_log |
| `MTLSAuthError` | 401 | INFRA_002 | "mTLS certificate invalid or missing" | FINTRAC access log |
| `DeploymentConflictError` | 409 | INFRA_003 | "Deployment already in progress for {service}" | Prevents race conditions |
| `InvalidStrategyError` | 422 | INFRA_004 | "Invalid deployment strategy: {strategy}" | Validation failure |
| `DeploymentNotFoundError` | 404 | INFRA_005 | "Deployment {id} not found" | Standard resource error |
| `ScalingPolicyViolation` | 403 | INFRA_006 | "Scaling denied: {service} at max_replicas" | Audit logged |
| `ConfigValidationError` | 422 | INFRA_007 | "Config {key}: {reason}" | PIPEDA validation |
| `ModelDeploymentError` | 500 | INFRA_008 | "MLFlow model {name}:{version} deployment failed" | MLFlow integration |

### 6.1 Error Response Structure

All infrastructure errors return structured JSON:
```json
{
  "detail": "Service dpt unhealthy: GPU memory check failed",
  "error_code": "INFRA_001",
  "service": "dpt",
  "timestamp": "2024-01-15T14:30:00Z",
  "request_id": "req_01hqn9k..."  // OpenTelemetry trace ID
}
```

### 6.2 Circuit Breaker Errors

For HPA-protected services:
```json
{
  "detail": "Circuit breaker open: decision service failing health checks",
  "error_code": "INFRA_009",
  "service": "decision",
  "fallback_action": "Traffic routed to last healthy version (v1.2.3)",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## 7. Missing Details Implementation

### 7.1 CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy Infrastructure

jobs:
  build-scan-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Security Scan (pip-audit)
        run: uv run pip-audit --desc
      
      - name: Container Scan (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          severity: 'CRITICAL,HIGH'
      
      - name: Deploy to Staging
        run: |
          uv run kubectl apply -f k8s/staging/
          uv run pytest -m integration --target=staging
      
      - name: FINTRAC Compliance Check
        run: |
          uv run python scripts/audit_log_retention.py --verify-5-year
```

### 7.2 Backup & Disaster Recovery

```python
# backup_strategy.py
"""
Automated backup jobs for 5-year FINTRAC retention.
"""

async def backup_postgresql():
    """WAL archiving to S3 with point-in-time recovery."""
    # Full backup daily at 02:00 UTC
    # WAL streaming every 5 minutes
    # Retention: 7 days hot, 5 years cold (S3 Glacier)

async def backup_redis():
    """RDB snapshots with AOF enabled."""
    # Snapshot every 6 hours
    # ElastiCache automated backups retained for 5 years

async def backup_s3():
    """Cross-region replication for object storage."""
    # Versioning enabled
    # Replication to secondary region (CA-CENTRAL-1 → CA-WEST-1)
    # Object lock for compliance (WORM)
```

### 7.3 Monitoring & Alerting

```yaml
# Prometheus rules
groups:
- name: underwriting_infrastructure
  rules:
  - alert: ServiceUnhealthy
    expr: up{job=~"dpt|policy|decision"} == 0
    for: 5m
    labels:
      severity: critical
      compliance: "FINTRAC"
    annotations:
      message: "Service {{ $labels.job }} is down. Audit log retention at risk."
  
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 10m
    labels:
      severity: warning
      compliance: "OSFI_B20"
    annotations:
      message: "Error rate >5% may impact underwriting calculation audit logging."
```

### 7.4 Load Balancing & CDN

```yaml
# Ingress configuration
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: underwriting-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/auth-tls-verify-client: "on"
spec:
  tls:
  - hosts:
    - api.lender.ca
    secretName: lender-tls-cert
  rules:
  - host: api.lender.ca
    http:
      paths:
      - path: /api/v1/
        backend:
          service:
            name: orchestrator-service
            port:
              number: 443

# CloudFront CDN for frontend
# Origin: S3 bucket with static assets
# WAF rules block requests without valid JWT
# Geo-restriction: CA only (PIPEDA data residency)
```

---

## 8. Docker Compose (Local Development)

```yaml
# docker-compose.dev.yml
services:
  postgres:
    image: postgres:15.2
    environment:
      POSTGRES_USER: mortgage_dev
      POSTGRES_PASSWORD: ${DB_PASSWORD}  # From .env
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mortgage_dev"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]

  dpt:
    build: ./modules/document_processing
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
      interval: 30s

  policy:
    build: ./modules/policy
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]

  decision:
    build: ./modules/decision
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]

  orchestrator:
    build: ./modules/orchestrator
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - orchestrator

  celery:
    build: ./modules/orchestrator
    command: celery -A tasks worker --loglevel=info
    depends_on:
      - redis
      - postgres
```

---

## 9. Kubernetes Production Manifests (Excerpts)

### 9.1 DPT Service (GPU-enabled)

```yaml
# k8s/prod/dpt-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dpt-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: dpt
  template:
    metadata:
      labels:
        app: dpt
    spec:
      nodeSelector:
        accelerator: nvidia-t4  # GPU node pool
      containers:
      - name: dpt
        image: lender-registry/dpt:1.2.4
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "8Gi"
            cpu: "2"
          limits:
            nvidia.com/gpu: 1
            memory: "16Gi"
        envFrom:
        - secretRef:
            name: dpt-secrets  # Mounted from Vault, not env vars
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: dpt-service
spec:
  selector:
    app: dpt
  ports:
  - port: 443
    targetPort: 8000
```

### 9.2 Horizontal Pod Autoscaler

```yaml
# k8s/prod/hpa.yml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dpt-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dpt-service
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: queue_length
      target:
        type: AverageValue
        averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

---

## 10. Compliance Checklist

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| **OSFI B-20 Audit** | Calculation logs stored in `infrastructure_audit_log` | `pytest -m integration test_audit_retention.py` |
| **FINTRAC 5-Year** | Partitioned audit tables, automated Glacier migration | `scripts/verify_retention.py --years=5` |
| **CMHC LTV** | Infrastructure ensures Decimal precision in DB | `mypy --strict modules/decision/models.py` |
| **PIPEDA Encryption** | AES-256-GCM for secrets, mTLS for transit | `trivy fs --security-checks secret .` |
| **No Float for Money** | All financial values use Decimal | `grep -r "float" modules/ && exit 1` |
| **No Secrets in Code** | Vault integration, .env.example only | `git-secrets --scan-history` |

---