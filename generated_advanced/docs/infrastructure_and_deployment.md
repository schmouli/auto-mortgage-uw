# Infrastructure & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Infrastructure & Deployment Design Plan

**File:** `docs/design/infrastructure-deployment.md`

---

## 1. Endpoints

### 1.1 Service Health & Observability Endpoints (Per Service)

Each microservice implements these standard endpoints in its `routes.py`:

| Method | Path | Auth | Purpose | Response Schema |
|--------|------|------|---------|-----------------|
| `GET` | `/health` | Public | Liveness probe (service running) | `{"status": "healthy\|unhealthy", "service": "name", "timestamp": "ISO8601"}` |
| `GET` | `/ready` | Public | Readiness probe (dependencies ready) | `{"status": "ready\|not_ready", "checks": {"db": "ok\|fail", "redis": "ok\|fail"}, "version": "semver"}` |
| `GET` | `/metrics` | Public | Prometheus metrics | Text/plain OpenMetrics format |
| `GET` | `/api/v1/config` | Admin | Runtime configuration audit | `{"service": "name", "config_hash": "sha256", "last_deployed": "ISO8601"}` |

### 1.2 Infrastructure Management Endpoints (Orchestrator Service)

| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `GET` | `/api/v1/infrastructure/health` | Authenticated | N/A | `{"overall_status": "healthy\|degraded", "services": [{...}], "gds_compliant": true}` | `INFRA_001` |
| `POST` | `/api/v1/infrastructure/deployments` | Admin-only | `DeploymentTriggerSchema` | `{"deployment_id": "uuid", "status": "queued", "services": ["list"]}` | `INFRA_002`, `INFRA_003` |
| `GET` | `/api/v1/infrastructure/deployments/{id}` | Admin-only | N/A | `DeploymentStatusSchema` | `INFRA_004` |
| `POST` | `/api/v1/infrastructure/services/{name}/restart` | Admin-only | N/A | `{"status": "restarting", "pod_name": "..."}` | `INFRA_005` |

**Request Schemas:**
```python
# DeploymentTriggerSchema
{
  "services": List[str],  # ["dpt", "policy", "decision", ...]
  "version": str,         # Git SHA or semver
  "environment": str,     # "staging" | "production"
  "force": bool,          # Force rollout even if health checks fail
  "retain_backups": bool  # Keep previous version pods for rollback
}

# DeploymentStatusSchema
{
  "deployment_id": UUID,
  "status": "queued|running|success|failed|rolled_back",
  "services": List[ServiceDeploymentStatus],
  "started_at": datetime,
  "completed_at": Optional[datetime],
  "created_by": str  # Hashed user ID (PIPEDA compliance)
}
```

---

## 2. Models & Database

### 2.1 Infrastructure Module Models (`modules/infrastructure/models.py`)

```python
from sqlalchemy import Column, UUID, String, DateTime, Boolean, JSON, Integer, ForeignKey
from common.database import Base
import uuid

class DeploymentLog(Base):
    """Immutable audit trail for all deployments (FINTRAC compliance)"""
    __tablename__ = "deployment_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    service_name = Column(String(50), nullable=False, index=True)  # dpt, policy, etc.
    environment = Column(String(20), nullable=False)  # staging, production
    version_from = Column(String(100), nullable=False)
    version_to = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # started, success, failed, rolled_back
    triggered_by = Column(String(64), nullable=False)  # Hashed user ID
    error_code = Column(String(20), nullable=True)
    error_detail = Column(String(500), nullable=True)  # No PII logged
    
    # Audit fields (mandatory)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(64), nullable=False, default="system")
    
    # Indexes for compliance queries
    __table_args__ = (
        Index('idx_deployment_env_time', environment, created_at),
        Index('idx_deployment_service_status', service_name, status),
    )

class ServiceRegistry(Base):
    """Runtime service discovery registry (ephemeral)"""
    __tablename__ = "service_registry"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(50), nullable=False, unique=True)
    pod_name = Column(String(100), nullable=False)
    namespace = Column(String(50), nullable=False, default="default")
    ip_address = Column(String(45), nullable=False)  # IPv6 ready
    port = Column(Integer, nullable=False)
    version = Column(String(100), nullable=False)
    is_healthy = Column(Boolean, nullable=False, default=True)
    last_check_in = Column(DateTime, nullable=False)
    gpu_allocated = Column(Boolean, nullable=False, default=False)  # For dpt service
    
    # Composite index for health aggregation queries
    __table_args__ = (
        Index('idx_service_health', service_name, is_healthy, last_check_in),
    )

class InfrastructureConfig(Base):
    """Version-controlled infrastructure parameters"""
    __tablename__ = "infrastructure_config"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(JSON, nullable=False)  # Typed JSON per key
    is_sensitive = Column(Boolean, nullable=False, default=False)  # If true, value is KMS-encrypted
    version = Column(Integer, nullable=False, default=1)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(64), nullable=False)
```

### 2.2 Extensions to Existing Models

All existing models must add:
```python
# Add to every ORM model in the system
__table_args__ = (
    # Enable row-level security for multi-tenant compliance
    {"postgresql_enable_row_level_security": True},
    # Force WAL archiving for FINTRAC 5-year retention
    {"postgresql_wal_level": "replica"},
)
```

---

## 3. Business Logic

### 3.1 Health Check Orchestration (`modules/infrastructure/services.py`)

```python
async def perform_cascading_health_check(
    service_names: List[str]
) -> Dict[str, HealthStatus]:
    """
    Execute health checks in dependency order:
    1. Data layer (postgres, redis, minio/s3)
    2. GPU layer (dpt)
    3. Business logic layer (policy, decision)
    4. API layer (orchestrator, frontend)
    
    Returns: {"service_name": HealthStatus, ...}
    """
    # Implementation must log each check for OSFI auditability
    # Never log connection strings or credentials
    pass

async def calculate_gds_tds_compliance_metrics() -> ComplianceReport:
    """
    Query all underwriting calculations from past 24h and verify:
    - 100% of GDS/TDS calculations include stress test
    - 0% exceed OSFI limits (GDS > 39%, TDS > 44%)
    - All calculations have audit logs
    
    Returns: ComplianceReport with pass/fail status
    """
    # Regulatory requirement: Run hourly via Celery beat
    # Store results in immutable audit table
    pass
```

### 3.2 Deployment State Machine

```
State Transitions:
[Idle] --(deployment triggered)--> [Pre-flight checks]
[Pre-flight] --(checks pass)--> [Rolling update]
[Pre-flight] --(checks fail)--> [Rejected]
[Rolling update] --(all pods healthy)--> [Complete]
[Rolling update] --(timeout/health fail)--> [Rollback initiated]
[Rollback initiated] --(previous version healthy)--> [Rolled back]
[Rollback initiated] --(rollback fails)--> [Manual intervention required]
```

**Pre-flight checks include:**
- Database migration compatibility (NEVER modify existing migrations)
- Secrets availability from Vault/AWS Secrets Manager
- GPU node capacity for dpt service
- CMHC premium tier cache validity
- FINTRAC audit table replication lag < 5s

### 3.3 Autoscaling Logic

**Horizontal Pod Autoscaler Rules:**
- **orchestrator**: Scale on CPU > 70% OR queue depth > 100
- **dpt**: Scale on GPU utilization > 80% (custom metric) OR queue depth > 50
- **policy/decision**: Scale on request rate > 1000 RPM per pod
- **frontend**: Scale on response time p95 > 500ms

**Scale-down constraints:**
- Must retain min 2 pods per service for HA
- Never scale down dpt to 0 (model loading time > 5min)
- Respect FINTRAC audit buffer: Keep previous pods for 1h after scale-down

---

## 4. Migrations

### 4.1 New Tables (Alembic revision: `infra_001_create_audit_tables.py`)

```python
def upgrade():
    # deployment_logs table
    op.create_table(
        'deployment_logs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('deployment_id', UUID(), nullable=False),
        sa.Column('service_name', sa.String(50), nullable=False),
        sa.Column('environment', sa.String(20), nullable=False),
        sa.Column('version_from', sa.String(100), nullable=False),
        sa.Column('version_to', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('triggered_by', sa.String(64), nullable=False),
        sa.Column('error_code', sa.String(20), nullable=True),
        sa.Column('error_detail', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_deployment_env_time', 'environment', 'created_at'),
        sa.Index('idx_deployment_service_status', 'service_name', 'status')
    )
    
    # service_registry table (TTL 5min on rows)
    op.create_table(
        'service_registry',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('service_name', sa.String(50), nullable=False),
        sa.Column('pod_name', sa.String(100), nullable=False),
        sa.Column('namespace', sa.String(50), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(100), nullable=False),
        sa.Column('is_healthy', sa.Boolean(), nullable=False),
        sa.Column('last_check_in', sa.DateTime(), nullable=False),
        sa.Column('gpu_allocated', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name'),
        sa.Index('idx_service_health', 'service_name', 'is_healthy', 'last_check_in')
    )
    
    # infrastructure_config table with RLS
    op.create_table(
        'infrastructure_config',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('config_key', sa.String(100), nullable=False),
        sa.Column('config_value', JSON(), nullable=False),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key')
    )
    
    # Enable row-level security for FINTRAC compliance
    op.execute("ALTER TABLE deployment_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE service_registry ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE infrastructure_config ENABLE ROW LEVEL SECURITY;")
```

### 4.2 Data Migration (Alembic revision: `infra_002_seed_health_check_users.py`)

```python
def upgrade():
    # Create system user for health check audit logs
    op.execute("""
        INSERT INTO users (id, hashed_sin, role, created_at, created_by)
        VALUES (
            gen_random_uuid(),
            'system_health_check',  # Non-PII identifier
            'system',
            NOW(),
            'migration'
        );
    """)
```

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling

**Encryption at Rest:**
- PostgreSQL: AWS RDS encryption with KMS CMK (Customer Managed Key)
- S3/MinIO: AES-256-SSE with bucket policies denying unencrypted uploads
- Redis: In-transit encryption (TLS 1.3), at-rest snapshot encryption
- Secrets: Vault transit encryption or AWS KMS envelope encryption

**Encryption in Transit:**
- All inter-service communication: mTLS (mutual TLS) via Linkerd or Istio
- Certificate rotation: Automatic every 30 days, never hardcoded
- Frontend: TLS 1.3 only, HSTS enabled, cipher suites restricted to modern sets

**PII Protection:**
- Health check endpoints must never return SIN, DOB, income, banking data
- Pod names must not contain PII (use UUIDs, not applicant names)
- Container logs filtered by Fluentd/Vector to redact PII patterns

### 5.2 FINTRAC Audit Requirements

**Immutable Audit Trail:**
- `deployment_logs` table: Append-only, no UPDATE/DELETE privileges
- WAL archiving to S3 with object lock (compliance mode, 5-year retention)
- Database snapshots: Daily, retained for 5 years, stored in separate compliance account
- Container logs: Ship to CloudWatch Logs with 5-year retention policy

**Transaction Flagging:**
- All deployments to production are "transactions > $10,000 equivalent"
- Log every deployment with: timestamp, user (hashed), service, version
- Use `INFRATRANS` as transaction type for FINTRAC reporting

### 5.3 OSFI B-20 Compliance

**Stress Test Validation:**
- Hourly Celery task validates all GDS/TDS calculations in past hour
- If any calculation missing stress test: Alert #security-critical channel
- Block deployment if validation fails (pre-flight check)
- Metrics exposed: `mortgage_gds_tds_compliance_ratio` (must be 1.0)

**Audit Logging:**
- Every ratio calculation logs to `underwriting_audit_log` table
- Include: `qualifying_rate`, `gds_ratio`, `tds_ratio`, `loan_amount`, `property_value`
- Never log: SIN, DOB, applicant name, income

### 5.4 Kubernetes Security Posture

**Network Policies:**
```yaml
# Deny all by default
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress

# Allow only specific paths
# Example: dpt service only accessible from orchestrator
```

**Pod Security Standards:**
- Enforce `restricted` profile (PSA)
- Run as non-root (UID > 10000)
- Read-only root filesystem
- drop: ALL capabilities
- seccompProfile: RuntimeDefault

**Secrets Management:**
- Use External Secrets Operator to sync from AWS Secrets Manager
- Secrets mounted as tmpfs volumes (in-memory only)
- Automatic rotation via rotation lambda

---

## 6. Error Codes & HTTP Responses

### 6.1 Infrastructure-Specific Exceptions (`modules/infrastructure/exceptions.py`)

```python
from common.exceptions import AppException

class ServiceHealthError(AppException):
    """Service failed health check"""
    def __init__(self, service: str, detail: str):
        super().__init__(
            status_code=503,
            error_code="INFRA_001",
            message=f"Service {service} unhealthy: {detail}"
        )

class DeploymentRejectedError(AppException):
    """Pre-flight checks failed"""
    def __init__(self, reason: str):
        super().__init__(
            status_code=409,
            error_code="INFRA_002",
            message=f"Deployment rejected: {reason}"
        )

class DeploymentConflictError(AppException):
    """Another deployment in progress"""
    def __init__(self, deployment_id: str):
        super().__init__(
            status_code=409,
            error_code="INFRA_003",
            message=f"Deployment {deployment_id} already in progress"
        )

class DeploymentNotFoundError(AppException):
    """Requested deployment does not exist"""
    def __init__(self, deployment_id: str):
        super().__init__(
            status_code=404,
            error_code="INFRA_004",
            message=f"Deployment {deployment_id} not found"
        )

class InfrastructureConfigurationError(AppException):
    """Invalid or missing infrastructure config"""
    def __init__(self, key: str):
        super().__init__(
            status_code=500,
            error_code="INFRA_005",
            message=f"Configuration error for key: {key}"
        )
```

### 6.2 Error Response Schema (All Services)

```json
{
  "detail": "Human-readable message without PII",
  "error_code": "INFRA_XXX",
  "correlation_id": "uuid-for-tracing",
  "timestamp": "2024-01-15T14:30:00Z",
  "service": "service-name",
  "version": "1.2.3"
}
```

### 6.3 Retry Strategy & Circuit Breaker

**Per-Service Configuration:**
- **dpt (GPU)**: Retry 2 times, 30s timeout, circuit breaker open after 5 failures
- **policy/decision**: Retry 3 times, 10s timeout, circuit breaker open after 10 failures
- **orchestrator**: Retry 1 time, 5s timeout, circuit breaker open after 3 failures
- **frontend**: No retries, fail fast to avoid client timeout

**Circuit Breaker State:**
- Closed: Normal operation
- Open: Return 503 immediately, health checks every 30s
- Half-Open: Allow one probe request, close if success

---

## 7. Additional Design Elements (Beyond Standard Sections)

### 7.1 Docker Compose (Development)

**File:** `docker-compose.yml` (root)

```yaml
services:
  postgres:
    image: postgres:15.2-alpine
    environment:
      POSTGRES_USER: mortgage_dev
      POSTGRES_PASSWORD: ${DB_PASSWORD}  # From .env, never committed
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mortgage_dev"]
      interval: 5s
      timeout: 3s
      retries: 5
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-fintrl-compliance.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
    ports:
      - "9000:9000"
      - "9001:9001"

  dpt:
    build:
      context: ./services/dpt
      dockerfile: Dockerfile.gpu
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      MODEL_PATH: /models/donut-base
      CUDA_VISIBLE_DEVICES: 0
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s  # Model load time ~2min
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy

  policy:
    build: ./services/policy
    environment:
      DATABASE_URL: postgresql://mortgage_dev:${DB_PASSWORD}@postgres:5432/mortgage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]
    depends_on:
      postgres:
        condition: service_healthy

  decision:
    build: ./services/decision
    environment:
      DATABASE_URL: postgresql://mortgage_dev:${DB_PASSWORD}@postgres:5432/mortgage
      POLICY_SERVICE_URL: http://policy:8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]
    depends_on:
      policy:
        condition: service_healthy

  orchestrator:
    build: ./services/orchestrator
    environment:
      DATABASE_URL: postgresql://mortgage_dev:${DB_PASSWORD}@postgres:5432/mortgage
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      DPT_SERVICE_URL: http://dpt:8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/ready"]
    depends_on:
      redis:
        condition: service_healthy
      dpt:
        condition: service_healthy

  frontend:
    build: ./services/frontend
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
    depends_on:
      orchestrator:
        condition: service_healthy

  celery-worker:
    build: ./services/orchestrator
    command: celery -A app.celery worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://mortgage_dev:${DB_PASSWORD}@postgres:5432/mortgage
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy

volumes:
  postgres_data:
  minio_data:
```

### 7.2 Kubernetes Production Manifests

**Namespace & Resource Quotas:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mortgage-prod
  labels:
    pod-security.kubernetes.io/enforce: restricted
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: mortgage-quota
  namespace: mortgage-prod
spec:
  hard:
    requests.cpu: "200"
    requests.memory: 400Gi
    requests.nvidia.com/gpu: "8"
    limits.cpu: "400"
    limits.memory: 800Gi
    limits.nvidia.com/gpu: "16"
    persistentvolumeclaims: "50"
```

**GPU Node Pool (dpt service):**
```yaml
# Node pool configuration for AWS EKS
# Instance type: g4dn.xlarge (NVIDIA T4) or g5.xlarge (A10)
# Minimum nodes: 1 (to avoid cold start)
# Maximum nodes: 10
# Taints: nvidia.com/gpu=true:NoSchedule
# Labels: workload-type=gpu-inference

apiVersion: apps/v1
kind: Deployment
metadata:
  name: dpt-service
spec:
  replicas: 2
  template:
    spec:
      nodeSelector:
        workload-type: gpu-inference
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: dpt
          resources:
            requests:
              nvidia.com/gpu: 1
              memory: "8Gi"
            limits:
              nvidia.com/gpu: 1
              memory: "12Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 120  # Model load time
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 120
            periodSeconds: 10
```

**Horizontal Pod Autoscaler:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orchestrator-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orchestrator
  minReplicas: 3
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
          name: mortgage_application_queue_depth
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

### 7.3 MLFlow Integration

**MLFlow Deployment:**
```yaml
# Separate namespace for ML platform
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-tracking
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: mlflow
          image: python:3.11-slim
          command: ["mlflow", "server"]
          args:
            - "--backend-store-uri=postgresql://$(DB_USER):$(DB_PASS)@rds-proxy:5432/mlflow"
            - "--default-artifact-root=s3://mortgage-mlflow-artifacts/prod"
            - "--host=0.0.0.0"
            - "--port=5000"
          envFrom:
            - secretRef:
                name: mlflow-secrets
---
apiVersion: v1
kind: Service
metadata:
  name: mlflow-tracking
spec:
  type: ClusterIP
  ports:
    - port: 5000
      targetPort: 5000
```

**Model Retraining Pipeline:**
```python
# Celery task in orchestrator/services.py
@app.task(bind=True, max_retries=3)
def trigger_model_retraining(self, model_type: str):
    """
    Triggered when model drift detected (monitoring threshold > 0.15)
    Creates new model version in MLFlow, runs A/B test in staging
    """
    # 1. Fetch new training data from audit tables (no PII)
    # 2. Submit training job to GPU node pool
    # 3. Register model in MLFlow with tags: {"compliance": "osfi-verified"}
    # 4. Deploy to staging with 10% traffic split
    # 5. Auto-promote to production after 7 days if error rate < 0.1%
    pass
```

### 7.4 CI/CD Pipeline (GitHub Actions)

**File:** `.github/workflows/deploy-production.yml`

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
    paths-ignore: ['docs/**', 'tests/**']

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run pip-audit
        run: |
          uv run pip-audit --desc --format=json > audit-report.json
          if grep -q "VULNERABILITY" audit-report.json; then
            echo "::error::Security vulnerabilities found"
            exit 1
          fi
      - name: Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'mortgage-underwriting:${{ github.sha }}'
          format: 'sarif'
          severity: 'CRITICAL,HIGH'

  test:
    needs: security-scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: uv run pytest -m unit --cov=modules --cov-fail-under=90
      - name: Run integration tests
        run: uv run pytest -m integration --cov=modules
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/mortgage_test

  deploy-staging:
    needs: test
    environment: staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/MortgageStagingDeployRole
      - name: Deploy to EKS staging
        run: |
          kubectl apply -f k8s/staging/
          kubectl rollout status deployment/orchestrator -n mortgage-staging --timeout=5m
      - name: Run smoke tests
        run: uv run pytest tests/smoke/test_staging.py

  deploy-production:
    needs: deploy-staging
    environment: production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify FINTRAC audit replication
        run: |
          LAG=$(psql -c "SELECT replication_lag FROM monitoring.replica_status;" -t)
          if (( $(echo "$LAG > 5" | bc -l) )); then
            echo "::error::Replication lag too high for FINTRAC compliance"
            exit 1
          fi
      - name: Create deployment audit record
        run: |
          psql -c "INSERT INTO deployment_logs (deployment_id, service_name, ...) VALUES (...)"
      - name: Deploy to EKS production
        run: |
          kubectl apply -f k8s/production/
          kubectl rollout status deployment/orchestrator -n mortgage-prod --timeout=10m
      - name: Verify OSFI compliance metrics
        run: |
          uv run python scripts/verify_osfi_compliance.py --env=production
```

### 7.5 Monitoring & Alerting

**Prometheus Rules:**
```yaml
groups:
  - name: mortgage-critical
    rules:
      - alert: OSFINonCompliance
        expr: mortgage_gds_tds_compliance_ratio < 1.0
        for: 0m  # Immediate alert
        labels:
          severity: critical
          team: compliance
        annotations:
          summary: "OSFI B-20 compliance violation detected"
          description: "Some mortgage calculations missing stress test or exceeding limits"

      - alert: FINTRACAuditFailure
        expr: rate(fintrl_audit_log_insert_failures[5m]) > 0
        for: 1m
        labels:
          severity: critical
          team: security
        annotations:
          summary: "FINTRAC audit log insertion failing"
          description: "Immutable audit trail may be compromised"

      - alert: PIIExposureRisk
        expr: increase(pii_pattern_detected_in_logs[5m]) > 0
        for: 0m
        labels:
          severity: critical
          team: security
        annotations:
          summary: "Potential PII detected in logs"
          description: "Check log stream immediately for PIIPIPEDA violation"
```

**Grafana Dashboards:**
- **OSFI Compliance Dashboard**: Real-time GDS/TDS calculation audit
- **FINTRAC Audit Dashboard**: Deployment logs, transaction volumes, replication lag
- **Infrastructure Health**: Pod status, GPU utilization, queue depths
- **Cost Optimization**: GPU node utilization, S3 storage costs

### 7.6 Backup & Disaster Recovery

**PostgreSQL (RDS):**
- Automated backups: Daily at 02:00 UTC, retained 35 days
- Manual snapshots: Before every production deployment, retained 5 years
- Point-in-time recovery: Enabled, 7-day window
- Cross-region replication: To `ca-central-1` (secondary Canadian region)
- Recovery Time Objective (RTO): < 1 hour
- Recovery Point Objective (RPO): < 5 minutes

**S3/MinIO (Documents):**
- Versioning: Enabled on all buckets
- Object lock: Compliance mode, 5-year retention
- Cross-region replication: Async to secondary region
- Lifecycle policy: Transition to Glacier after 1 year

**Redis (ElastiCache):**
- Backup window: 03:00-04:00 UTC daily
- Retention: 7 days (does not contain FINTRAC data)
- Cluster mode: Enabled with 3 shards for HA

**Disaster Recovery Runbook:**
1. **Detection**: Automated via Route53 health checks + CloudWatch alarms
2. **Failover**: Update Route53 to point to secondary region
3. **Validation**: Run `verify_osfi_compliance.py` in secondary region
4. **Notification**: PagerDuty alert to on-call SRE + compliance team
5. **Documentation**: All steps logged to FINTRAC audit table

---

## 8. Security Scanning & Compliance Checks

**Pre-Commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/zricethezav/gitleaks
    hooks:
      - id: gitleaks  # Prevents secret commit
  
  - repo: local
    hooks:
      - id: pip-audit
        name: pip-audit
        entry: uv run pip-audit
        language: system
        pass_filenames: false
```

**Container Scanning (CI):**
- **Trivy**: Scan for CVEs in base images, fail on CRITICAL/HIGH
- **Snyk**: Dependency vulnerability scanning
- **Hadolint**: Dockerfile linting (no root user, no secrets in ENV)

**Compliance Scanning (Weekly):**
- **Prowler**: AWS CIS Benchmark compliance
- **kube-bench**: Kubernetes CIS Benchmark
- **OPA Gatekeeper**: Enforce policies (no latest tags, resource limits required)

---

## 9. Load Balancing & CDN

**Application Load Balancer (ALB):**
- **SSL Policy**: ELBSecurityPolicy-TLS-1-3-2021-06
- **WAF Rules**: OWASP Top 10, rate limiting (1000 req/min per IP)
- **Access Logs**: S3 bucket with 5-year retention, no PII in query params
- **Health Checks**: Use `/ready` endpoint, 30s interval

**CloudFront CDN (Frontend):**
- **Origin**: ALB in `ca-central-1`
- **Geo Restriction**: Allow only CA and US (FINTRAC data residency)
- **Cache Policy**: No caching on `/api/*`, cache static assets for 1 day
- **Security Headers**: 
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `Content-Security-Policy: default-src 'self'`
  - `X-Content-Type-Options: nosniff`

---

## 10. Environment Variables (.env.example)

```bash
# PostgreSQL
DB_PASSWORD=change_me_in_production
DATABASE_URL=postgresql://mortgage_dev:${DB_PASSWORD}@localhost:5432/mortgage

# Redis
REDIS_PASSWORD=change_me_in_production
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0

# MinIO/S3
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=mortgage-documents

# Security
JWT_SECRET_KEY=generate_with_openssl_rand_32
ENCRYPTION_KEY=generate_32_byte_hex_for_aes_256
MLFLOW_TRACKING_URI=http://localhost:5000

# Feature flags
ENABLE_FINTRAC_AUDIT=true
ENABLE_OSFI_STRESS_TEST_VALIDATION=true
ENABLE_PII_REDACTION=true

# GPU (development)
NVIDIA_VISIBLE_DEVICES=0
CUDA_VISIBLE_DEVICES=0
```

**WARNING**: `.env` must never be committed. Use `.env.example` as template. In production, all secrets from AWS Secrets Manager.

---

## 11. Compliance Summary Checklist

| Requirement | Implementation | Verification Method |
|-------------|----------------|---------------------|
| **OSFI B-20** | Stress test in all calculations, GDS/TDS ≤ limits | Hourly Celery task + Prometheus alert |
| **FINTRAC** | Immutable audit tables, 5-year retention, transaction logging | WAL archiving + S3 object lock + Prowler scan |
| **CMHC** | LTV calculation with Decimal, premium tier lookup | Unit tests + integration tests on every PR |
| **PIPEDA** | AES-256 encryption, SHA256 SIN lookups, PII redaction | Container scan + log analysis + annual pentest |
| **Never hardcode secrets** | AWS Secrets Manager + External Secrets Operator | kube-bench + OPA Gatekeeper |
| **Decimal for money** | SQLAlchemy Numeric(15,4) fields, Pydantic Decimal | mypy strict mode + ruff checks |
| **Audit fields** | `created_at`, `updated_at`, `created_by` on all models | Alembic migration generator enforces |

---

**Design Status**: Ready for implementation review by SRE and Compliance teams.