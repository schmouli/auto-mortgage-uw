# Design: Infrastructure & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

```markdown
# Infrastructure & Deployment Design Plan

**Module:** infrastructure_deployment  
**File:** docs/design/infrastructure-deployment.md  
**Last Updated:** 2024-01-15  
**Compliance Frameworks:** OSFI B-20, FINTRAC, CMHC, PIPEDA  

---

## 1. Endpoints

### 1.1 Health & Observability Endpoints

Each service exposes standardized health check endpoints for Docker Compose and Kubernetes probes.

| Service | Method | Path | Purpose | Auth |
|---------|--------|------|---------|------|
| orchestrator | GET | `/api/v1/health/live` | Liveness probe (process alive) | public |
| orchestrator | GET | `/api/v1/health/ready` | Readiness probe (db, redis, dependencies) | public |
| orchestrator | GET | `/api/v1/health/startup` | Startup probe (initial load) | public |
| decision | GET | `/api/v1/health/live` | Liveness probe | public |
| decision | GET | `/api/v1/health/ready` | Readiness probe | public |
| dpt | GET | `/api/v1/health/live` | Liveness probe | public |
| dpt | GET | `/api/v1/health/ready` | Readiness probe (GPU availability) | public |
| policy | GET | `/api/v1/health/live` | Liveness probe | public |
| policy | GET | `/api/v1/health/ready` | Readiness probe (policy rules loaded) | public |
| frontend | GET | `/health` | SPA health check | public |
| celery-worker | GET | `/health` | Celery worker liveness | public |

### 1.2 Request/Response Schemas

**Health Check Response (all services):**
```python
# schemas.py
from pydantic import BaseModel, Field
from datetime import datetime

class HealthStatus(BaseModel):
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    timestamp: datetime
    version: str
    git_commit: str | None
    checks: dict[str, dict] = Field(default_factory=dict)

class HealthCheckResponse(BaseModel):
    service: str
    environment: str = Field(..., pattern="^(local|dev|staging|prod)$")
    data: HealthStatus
```

**Example 200 OK Response:**
```json
{
  "service": "orchestrator",
  "environment": "prod",
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-15T14:30:00Z",
    "version": "1.2.3",
    "git_commit": "a1b2c3d",
    "checks": {
      "postgres": {"status": "healthy", "latency_ms": 2},
      "redis": {"status": "healthy", "latency_ms": 1},
      "dpt": {"status": "healthy", "latency_ms": 45}
    }
  }
}
```

**Error Responses:**
```json
// 503 Service Unavailable - Readiness failure
{
  "detail": "Dependency check failed",
  "error_code": "INFRA_503",
  "data": {
    "failed_checks": ["postgres", "redis"],
    "service": "orchestrator"
  }
}
```

### 1.3 Metrics Endpoint (Prometheus)

| Service | Method | Path | Auth |
|---------|--------|------|------|
| All | GET | `/metrics` | internal network only (mTLS) |

**Exposed Metrics:**
- `http_requests_total` (counter, labeled: method, endpoint, status_code)
- `http_request_duration_seconds` (histogram)
- `underwriting_gds_ratio` (gauge, labeled: application_id) - **OSFI audit**
- `underwriting_tds_ratio` (gauge, labeled: application_id) - **OSFI audit**
- `fintrac_transaction_amount_cad` (histogram, buckets: [0, 10000, 100000]) - **FINTRAC**
- `celery_tasks_processed_total` (counter, labeled: task_name, status)

---

## 2. Models & Database

### 2.1 Infrastructure Audit Log Model

**Table:** `infrastructure.deployment_audit`

```python
# modules/infrastructure/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, INET
from common.database import Base
import uuid
from datetime import datetime

class DeploymentAudit(Base):
    """Immutable audit trail for all deployments and infrastructure changes - FINTRAC 5-year retention"""
    __tablename__ = "deployment_audit"
    __table_args__ = (
        Index('idx_deployment_audit_timestamp', 'created_at'),
        Index('idx_deployment_audit_service', 'service_name'),
        {
            'postgresql_partition_by': 'RANGE (created_at)',
            'postgresql_partitions': 'start_monthly'
        }
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Service identification
    service_name = Column(String(50), nullable=False)  # orchestrator, dpt, policy, etc.
    version = Column(String(20), nullable=False)
    git_commit = Column(String(40), nullable=False)
    
    # Deployment metadata
    environment = Column(String(10), nullable=False)  # local, dev, staging, prod
    deployment_type = Column(String(20), nullable=False)  # docker, kubernetes, helm
    triggered_by = Column(String(100), nullable=False)  # CI/CD user or system
    
    # Network & location (for FINTRAC compliance)
    source_ip = Column(INET)  # For audit trail - PIPEDA: not logged in plaintext in app logs
    region = Column(String(50))  # aws-region, gcp-zone
    
    # Status & outcome
    status = Column(String(20), nullable=False)  # success, failed, rolled_back
    error_message = Column(Text)  # Only on failure, no PII
    
    # Immutable audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_by = Column(String(100), nullable=False, default="system")
    
    # Additional metadata (OSFI audit requirements)
    metadata = Column(JSON)  # Stores: stress_test_enabled, gds_threshold, tds_threshold

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # FINTRAC: Ensure immutability - no updates allowed
        if hasattr(self, 'updated_at'):
            raise ValueError("DeploymentAudit records are immutable")
```

**Partitioning Strategy:** Monthly partitions for 5-year FINTRAC retention, automated partition creation via pg_partman.

### 2.2 Configuration Management Model

**Table:** `infrastructure.service_configuration`

```python
class ServiceConfiguration(Base):
    """Centralized configuration management - PIPEDA: encrypts sensitive values"""
    __tablename__ = "service_configuration"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(50), nullable=False, unique=True, index=True)
    
    # Encrypted configuration values (PIPEDA compliance)
    config_data_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted JSON
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    
    # Version tracking for rollback
    version = Column(Integer, nullable=False, default=1)
    
    # OSFI compliance: track which config version was active for each underwriting decision
    def get_decrypted_config(self) -> dict:
        """Decrypts configuration - logs access for FINTRAC audit"""
        # Implementation uses common/security.py encrypt_pii/decrypt_pii
        pass
```

---

## 3. Business Logic & Deployment Patterns

### 3.1 Local Development (Docker Compose)

**File:** `docker-compose.yml` (9 services)

```yaml
services:
  postgres:
    image: postgres:15.2-alpine
    environment:
      POSTGRES_DB: mortgage_underwriting
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # From .env, never committed
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - underwriting-net

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    networks:
      - underwriting-net

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    ports:
      - "9000:9000"  # S3 API
      - "9001:9001"  # Console
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    networks:
      - underwriting-net

  dpt:
    build:
      context: .
      dockerfile: modules/dpt/Dockerfile
      target: gpu-dev  # NVIDIA runtime
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./modules/dpt:/app/modules/dpt
    networks:
      - underwriting-net

  policy:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8001:8000"
    networks:
      - underwriting-net

  decision:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - OSFI_STRESS_TEST_RATE=${OSFI_STRESS_TEST_RATE:-5.25}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8002:8000"
    networks:
      - underwriting-net

  orchestrator:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - DPT_SERVICE_URL=http://dpt:8000
      - POLICY_SERVICE_URL=http://policy:8000
      - DECISION_SERVICE_URL=http://decision:8000
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    networks:
      - underwriting-net

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A modules.orchestrator.celery_app worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./modules:/app/modules
    networks:
      - underwriting-net

  frontend:
    image: node:20-alpine
    working_dir: /app
    command: npm run dev
    volumes:
      - ./frontend:/app
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
    depends_on:
      orchestrator:
        condition: service_started
    networks:
      - underwriting-net

  mlflow:
    image: python:3.11-slim
    command: pip install mlflow && mlflow server --host 0.0.0.0 --port 5000
    ports:
      - "5000:5000"
    volumes:
      - mlflow_data:/mlflow
    networks:
      - underwriting-net

volumes:
  postgres_data:
  minio_data:
  mlflow_data:

networks:
  underwriting-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

**Environment Variables (.env.example - committed, .env - gitignored):**
```bash
# PostgreSQL
POSTGRES_USER=mortgage_dev
POSTGRES_PASSWORD=dev_password_change_in_prod  # PIPEDA: Never commit real secrets

# Redis
REDIS_PASSWORD=redis_dev_password

# MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# OSFI B-20 (auditable configuration)
OSFI_STRESS_TEST_RATE=5.25
GDS_HARD_LIMIT=39.0
TDS_HARD_LIMIT=44.0

# FINTRAC (5-year retention config)
AUDIT_RETENTION_YEARS=5
LARGE_TRANSACTION_THRESHOLD=10000.00  # CAD

# CMHC Insurance Tiers (Decimal precision)
CMHC_PREMIUM_80_85=0.0280
CMHC_PREMIUM_85_90=0.0310
CMHC_PREMIUM_90_95=0.0400

# Security
ENCRYPTION_KEY=  # AES-256 key, base64 encoded, from env only
JWT_SECRET=      # HS256 secret, from env only
CORS_ORIGINS=http://localhost:3000

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:14268/api/traces
PROMETHEUS_PORT=9090
```

### 3.2 Production Deployment (Kubernetes)

**Namespace & Resource Quotas:**
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mortgage-underwriting-prod
  labels:
    compliance: "osfi-fintrac-pipeda"
    cost-center: "underwriting"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: underwriting-quota
  namespace: mortgage-underwriting-prod
spec:
  hard:
    requests.cpu: "100"
    requests.memory: 200Gi
    requests.nvidia.com/gpu: "8"  # GPU quota for dpt
    limits.cpu: "200"
    limits.memory: 400Gi
    limits.nvidia.com/gpu: "16"
```

**GPU Node Pool for DPT (Donut Inference):**
```yaml
# k8s/dpt-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dpt-service
  namespace: mortgage-underwriting-prod
spec:
  replicas: 3  # HPA will manage
  selector:
    matchLabels:
      app: dpt-service
  template:
    metadata:
      labels:
        app: dpt-service
        compliance: "pipeda"  # For network policies
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      nodeSelector:
        accelerator: nvidia-t4  # OR nvidia-a10 for high-volume
      containers:
      - name: dpt
        image: ghcr.io/yourorg/dpt:v1.2.3
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "8Gi"
            cpu: "2"
          limits:
            nvidia.com/gpu: 1
            memory: "12Gi"
            cpu: "4"
        envFrom:
        - secretRef:
            name: dpt-secrets  # PIPEDA: encrypted secrets
        livenessProbe:
          httpGet:
            path: /api/v1/health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 5
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
---
apiVersion: v1
kind: Service
metadata:
  name: dpt-service
  namespace: mortgage-underwriting-prod
spec:
  selector:
    app: dpt-service
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

**Horizontal Pod Autoscaler (HPA):**
```yaml
# k8s/hpa-orchestrator.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orchestrator-hpa
  namespace: mortgage-underwriting-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orchestrator-service
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### 3.3 MLFlow Integration (Model Versioning)

**File:** `k8s/mlflow-deployment.yaml`
```yaml
# Dedicated MLFlow server for model versioning
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-server
  namespace: mortgage-underwriting-prod
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: mlflow
        image: python:3.11-slim
        command: ["mlflow", "server"]
        args: [
          "--host", "0.0.0.0",
          "--port", "5000",
          "--backend-store-uri", "$(DATABASE_URL)",
          "--default-artifact-root", "s3://mortgage-mlflow-artifacts"
        ]
        envFrom:
        - secretRef:
            name: mlflow-secrets
```

**Model Retraining Pipeline (Airflow DAG):**
```python
# dags/retrain_donut_model.py
from airflow import DAG
from datetime import datetime, timedelta

default_args = {
    'owner': 'ml-ops',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'retrain_donut_monthly',
    default_args=default_args,
    description='Monthly retraining of Donut document processing model',
    schedule_interval='@monthly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'pipeda', 'compliance']
) as dag:
    
    # Task 1: Extract anonymized training data (PIPEDA: no PII)
    extract_task = KubernetesPodOperator(
        task_id='extract_training_data',
        image='ghcr.io/yourorg/ml-pipeline:v1',
        cmds=['python', 'extract.py'],
        env_vars={
            'ENCRYPTION_KEY_FROM_VAULT': '{{ vault.secret }}',  # HashiCorp Vault
            'FINTRAC_AUDIT_LOG': 'true'
        }
    )
    
    # Task 2: Train on GPU node
    train_task = KubernetesPodOperator(
        task_id='train_model',
        image='ghcr.io/yourorg/ml-training:v1',
        resources={'limit_gpu': 1},
        node_selector={'accelerator': 'nvidia-t4'},
        cmds=['python', 'train.py'],
        env_vars={
            'MLFLOW_TRACKING_URI': 'http://mlflow-server:5000',
            'REGISTER_MODEL': 'true'
        }
    )
    
    # Task 3: Validate against OSFI test suite
    validate_task = KubernetesPodOperator(
        task_id='validate_osfi_compliance',
        image='ghcr.io/yourorg/validation-suite:v1',
        cmds=['pytest', 'tests/osfi_compliance/'],
        env_vars={
            'GDS_THRESHOLD': '39.0',
            'TDS_THRESHOLD': '44.0',
            'STRESS_TEST_RATE': '5.25'
        }
    )
    
    # Task 4: Deploy with canary strategy
    deploy_task = KubernetesPodOperator(
        task_id='deploy_canary',
        image='ghcr.io/yourorg/argocd-cli:v1',
        cmds=['argocd', 'app', 'set', 'dpt-service', '--image', 'dpt:{{ ti.xcom_pull("train_model") }}']
    )
    
    extract_task >> train_task >> validate_task >> deploy_task
```

---

## 4. Migrations

### 4.1 New Alembic Migration: `001_create_infrastructure_audit_tables.py`

```python
"""Create infrastructure audit tables for compliance tracking"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB

revision = '001_create_infrastructure_audit_tables'
down_revision = '000_initial'
branch_labels = None
depends_on = None

def upgrade():
    # Create partitioned table for deployment audit (FINTRAC 5-year retention)
    op.execute("""
        CREATE TABLE infrastructure.deployment_audit (
            id UUID PRIMARY KEY,
            service_name VARCHAR(50) NOT NULL,
            version VARCHAR(20) NOT NULL,
            git_commit VARCHAR(40) NOT NULL,
            environment VARCHAR(10) NOT NULL,
            deployment_type VARCHAR(20) NOT NULL,
            triggered_by VARCHAR(100) NOT NULL,
            source_ip INET,
            region VARCHAR(50),
            status VARCHAR(20) NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP NOT NULL,
            created_by VARCHAR(100) NOT NULL,
            metadata JSONB
        ) PARTITION BY RANGE (created_at);
    """)
    
    # Create initial partitions for next 12 months
    for month in range(12):
        op.execute(f"""
            CREATE TABLE infrastructure.deployment_audit_y2024m{month+1:02d}
            PARTITION OF infrastructure.deployment_audit
            FOR VALUES FROM ('2024-{month+1:02d}-01') TO ('2024-{month+2:02d}-01');
        """)
    
    # Indexes for audit queries
    op.create_index('idx_deployment_audit_timestamp', 'deployment_audit', ['created_at'], schema='infrastructure')
    op.create_index('idx_deployment_audit_service', 'deployment_audit', ['service_name'], schema='infrastructure')
    op.create_index('idx_deployment_audit_env_status', 'deployment_audit', ['environment', 'status'], schema='infrastructure')
    
    # Create service configuration table (encrypted)
    op.create_table(
        'service_configuration',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('service_name', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('config_data_encrypted', sa.LargeBinary, nullable=False),  # AES-256
        sa.Column('version', sa.Integer, nullable=False, default=1),
        sa.Column('created_at', sa.DateTime, nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('updated_by', sa.String(100), nullable=False),
        schema='infrastructure'
    )
    
    # Grant read-only access to audit table for compliance team
    op.execute("GRANT SELECT ON infrastructure.deployment_audit TO compliance_auditor_role;")

def downgrade():
    op.drop_table('service_configuration', schema='infrastructure')
    op.drop_index('idx_deployment_audit_env_status', schema='infrastructure')
    op.drop_index('idx_deployment_audit_service', schema='infrastructure')
    op.drop_index('idx_deployment_audit_timestamp', schema='infrastructure')
    op.execute("DROP TABLE infrastructure.deployment_audit CASCADE;")
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements

**Configuration Enforcement:**
- **Stress Test Rate:** Loaded from `ServiceConfiguration` table, encrypted at rest
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44% - enforced in decision service
- **Audit Logging:** All ratio calculations logged to `deployment_audit.metadata` with:
  ```json
  {
    "stress_test_rate_applied": 5.25,
    "gds_calculated": 37.2,
    "tds_calculated": 42.1,
    "gds_threshold": 39.0,
    "tds_threshold": 44.0,
    "application_id": "uuid",
    "timestamp": "2024-01-15T14:30:00Z"
  }
  ```

### 5.2 FINTRAC Compliance

**Immutable Audit Trail:**
- All deployment events written to `deployment_audit` table
- **5-year retention:** Automated partition management via pg_partman
- **PIPEDA + FINTRAC:** `source_ip` stored in audit table but **never** in application logs
- **Transaction Tracking:** Transactions > CAD $10,000 flagged in `metadata`:
  ```json
  {
    "transaction_type": "LARGE_PURCHASE",
    "amount_cad": 15000.00,
    "identity_verified": true,
    "verification_method": "document_scan"
  }
  ```

**Access Control:**
```sql
-- Read-only role for FINTRAC auditors
CREATE ROLE fintrac_auditor WITH LOGIN;
GRANT SELECT ON infrastructure.deployment_audit TO fintrac_auditor;
GRANT SELECT ON mortgage_applications.transaction_log TO fintrac_auditor;
```

### 5.3 PIPEDA Data Handling

**Encryption at Rest:**
- All secrets in Kubernetes `Secret` objects encrypted with **KMS** (AWS KMS or GCP KMS)
- `ServiceConfiguration.config_data_encrypted` uses AES-256-GCM via `common/security.py`
- **Never** log: SIN, DOB, income, banking data
- **Hashed lookups:** SIN → SHA256 for database queries

**Network Security:**
- **mTLS** between all microservices (Istio or Linkerd)
- NetworkPolicies restrict traffic:
  ```yaml
  # k8s/network-policy.yaml
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  metadata:
    name: deny-pii-services
    namespace: mortgage-underwriting-prod
  spec:
    podSelector:
      matchLabels:
        compliance: "pipeda"
    policyTypes:
    - Ingress
    - Egress
    ingress:
    - from:
      - podSelector:
          matchLabels:
            app: orchestrator
      ports:
      - protocol: TCP
        port: 8000
    egress: []  # No external egress for PII-handling services
  ```

### 5.4 Secret Management

**Local:** `.env` file (gitignored)  
**Production:** HashiCorp Vault or cloud-native secret manager

**Vault Policy Example:**
```hcl
# Vault policy for orchestrator service
path "secret/data/mortgage-underwriting/prod/orchestrator" {
  capabilities = ["read"]
}

path "secret/data/mortgage-underwriting/prod/database" {
  capabilities = ["read"]
}

# FINTRAC: Rotate encryption keys every 90 days
path "transit/keys/underwriting-encryption/rotate" {
  capabilities = ["update"]
}
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Infrastructure-Specific Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Compliance Trigger |
|-----------------|-------------|------------|-----------------|-------------------|
| `ServiceHealthError` | 503 | `INFRA_503` | "Service {service} unhealthy: {detail}" | Log to deployment_audit |
| `ConfigurationError` | 500 | `INFRA_500` | "Invalid configuration: {key}" | FINTRAC audit if PII-related |
| `DeploymentFailedError` | 409 | `INFRA_409` | "Deployment {version} failed: {reason}" | Log to deployment_audit |
| `SecretNotFoundError` | 500 | `INFRA_501` | "Secret {name} not found in vault" | FINTRAC audit |
| `GPUResourceError` | 503 | `INFRA_504` | "GPU unavailable for dpt service" | OSFI: document processing delay |
| `DatabaseConnectionError` | 503 | `INFRA_505` | "Database connection failed: {detail}" | FINTRAC: log to audit trail |

### 6.2 Health Check Failure Responses

**Example: Decision Service Database Failure**
```json
{
  "detail": "Database connection failed",
  "error_code": "INFRA_505",
  "data": {
    "service": "decision",
    "failed_dependency": "postgres",
    "timestamp": "2024-01-15T14:30:00Z",
    "fintrac_audit_id": "01928374-5629-472b-9c3d-7a1b8e9f4c2d"  # Always included for FINTRAC
  }
}
```

**Example: DPT GPU Unavailability**
```json
{
  "detail": "GPU resource exhausted",
  "error_code": "INFRA_504",
  "data": {
    "service": "dpt",
    "gpu_requested": "nvidia.com/gpu: 1",
    "gpu_available": 0,
    "osfi_impact": "document_processing_delayed",
    "fallback_mode": "cpu_inference"  # Graceful degradation
  }
}
```

### 6.3 Compliance Error Logging

All infrastructure errors **must** include `fintrac_audit_id` in response when related to:
- Identity verification delays
- Document processing failures
- Configuration changes affecting underwriting rules
- Large transaction processing

**Logging Structure (structlog):**
```python
# common/logging.py
import structlog

logger = structlog.get_logger()

def log_infrastructure_error(error_code: str, service: str, detail: str, **kwargs):
    """FINTRAC compliant error logging - never includes PII"""
    logger.error(
        "infrastructure_error",
        error_code=error_code,
        service=service,
        detail=detail,
        fintrac_audit_id=kwargs.get("fintrac_audit_id"),
        # Explicitly exclude: sin, dob, income, banking_data
        _filter_keys=["sin", "dob", "income", "banking"]
    )
```

---

## 7. CI/CD Pipeline (GitHub Actions)

**File:** `.github/workflows/deploy-prod.yml`

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
    paths:
      - 'modules/**'
      - 'Dockerfile'
      - 'k8s/**'

env:
  REGISTRY: ghcr.io
  IMAGE_TAG: ${{ github.sha }}

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run pip-audit
        run: |
          uv run pip-audit --desc --format=json > audit-report.json
          # FINTRAC: Block deploy on critical vulnerabilities
          if jq '.vulnerabilities[] | select(.severity == "critical")' audit-report.json; then
            echo "::error::Critical vulnerabilities found"
            exit 1
          fi
      
      - name: Upload audit report
        uses: actions/upload-artifact@v4
        with:
          name: pip-audit-report
          path: audit-report.json
          retention-days: 2555  # FINTRAC: 7-year retention for security logs

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15.2
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run unit tests
        run: uv run pytest -m unit --cov=modules --cov-report=xml
      
      - name: Run integration tests
        run: uv run pytest -m integration --cov=modules
      
      - name: OSFI compliance tests
        run: uv run pytest tests/compliance/test_osfi_stress_test.py -v

  build-and-push:
    needs: [security-scan, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build images
        run: |
          docker build -t ${{ env.REGISTRY }}/dpt:${{ env.IMAGE_TAG }} -f modules/dpt/Dockerfile .
          docker build -t ${{ env.REGISTRY }}/orchestrator:${{ env.REGISTRY }} .
      
      - name: Push to registry
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | docker login ${{ env.REGISTRY }} -u ${{ github.actor }} --password-stdin
          docker push ${{ env.REGISTRY }}/dpt:${{ env.IMAGE_TAG }}
          docker push ${{ env.REGISTRY }}/orchestrator:${{ env.IMAGE_TAG }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/dpt-service dpt=${{ env.REGISTRY }}/dpt:${{ env.IMAGE_TAG }}
          kubectl set image deployment/orchestrator-service orchestrator=${{ env.REGISTRY }}/orchestrator:${{ env.IMAGE_TAG }}
          kubectl rollout status deployment/dpt-service --timeout=10m
      
      - name: Record deployment audit
        run: |
          # Write to deployment_audit table via psql
          psql "${{ secrets.DATABASE_URL }}" -c "
            INSERT INTO infrastructure.deployment_audit 
            (id, service_name, version, git_commit, environment, deployment_type, triggered_by, status)
            VALUES 
            (gen_random_uuid(), 'dpt-service', '${{ env.IMAGE_TAG }}', '${{ github.sha }}', 'prod', 'kubernetes', '${{ github.actor }}', 'success');
          "
        # FINTRAC: This insert is immutable and retained for 5 years
```

---

## 8. Backup & Disaster Recovery

### 8.1 PostgreSQL (RDS/Cloud SQL)

**Automated Backups:**
- Daily snapshots at 02:00 UTC
- Point-in-time recovery: 7 days retention
- Cross-region replica for DR (RPO < 5 min)

**FINTRAC Compliance Script:**
```bash
# scripts/backup-verification.sh
#!/bin/bash
# Verify backup integrity for FINTRAC audit

BACKUP_DATE=$(date -d "yesterday" +%Y-%m-%d)
pg_dump --section=pre-data --section=data --section=post-data \
  "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}/mortgage_underwriting" \
  --table="infrastructure.deployment_audit" \
  --table="mortgage_applications.*" \
  --file="/backups/fintrac-audit-${BACKUP_DATE}.sql"

# Verify no PII in backup logs
if grep -E "(sin|dob|income|banking)" "/backups/fintrac-audit-${BACKUP_DATE}.sql"; then
  echo "ERROR: PII detected in backup"
  exit 1
fi

# Upload to S3 with 5-year retention
aws s3 cp "/backups/fintrac-audit-${BACKUP_DATE}.sql" \
  s3://mortgage-backups/fintrac/ \
  --storage-class GLACIER \
  --tagging "retention=fintrac-5y"
```

### 8.2 Redis (ElastiCache)

- AOF persistence enabled
- Snapshot every 60 minutes
- Multi-AZ replication

### 8.3 Object Storage (S3/Cloud Storage)

**Versioning & Lifecycle:**
```yaml
# Terraform: S3 bucket configuration
resource "aws_s3_bucket" "mortgage_documents" {
  bucket = "mortgage-documents-prod"
  
  versioning {
    enabled = true
  }
  
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.fintrac_key.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }
  
  lifecycle_rule {
    id      = "fintrac-retention"
    enabled = true
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
    expiration {
      days = 1825  # 5 years
    }
  }
}
```

---

## 9. Monitoring & Alerting

### 9.1 Prometheus Rules (OSFI & FINTRAC)

**File:** `monitoring/prometheus-rules.yml`
```yaml
groups:
- name: osfi_compliance
  interval: 60s
  rules:
  - alert: GDSRatioExceeded
    expr: underwriting_gds_ratio > 39
    for: 0m
    labels:
      severity: critical
      compliance: osfi-b20
    annotations:
      summary: "GDS ratio exceeded 39% (application {{ $labels.application_id }})"
      description: "Stress test calculation may be incorrect. Immediate review required."
  
  - alert: TDSRatioExceeded
    expr: underwriting_tds_ratio > 44
    for: 0m
    labels:
      severity: critical
      compliance: osfi-b20
    annotations:
      summary: "TDS ratio exceeded 44%"

- name: fintrac_large_transactions
  interval: 30s
  rules:
  - alert: LargeTransactionProcessed
    expr: fintrac_transaction_amount_cad > 10000
    for: 0m
    labels:
      severity: info
      compliance: fintrac
    annotations:
      summary: "Transaction > CAD $10,000 processed"
      description: "Ensure identity verification audit log exists for {{ $labels.transaction_id }}"

- name: infrastructure
  interval: 30s
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High 5xx error rate in {{ $labels.service }}"
```

### 9.2 Grafana Dashboards

**Dashboard UID:** `infrastructure-compliance-overview`
- Panel: OSFI GDS/TDS threshold violations (real-time)
- Panel: FINTRAC large transaction volume (daily)
- Panel: Deployment success rate by service
- Panel: GPU utilization for dpt service
- Panel: Celery task queue depth

---

## 10. Load Balancing & CDN

### 10.1 Ingress Configuration

**File:** `k8s/ingress.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mortgage-ingress
  namespace: mortgage-underwriting-prod
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "1000r/m"
    nginx.ingress.kubernetes.io/rate-limit-key: "$binary_remote_addr"
spec:
  tls:
  - hosts:
    - api.mortgage.ca
    secretName: mortgage-tls
  rules:
  - host: api.mortgage.ca
    http:
      paths:
      - path: /api/v1
        pathType: Prefix
        backend:
          service:
            name: orchestrator-service
            port:
              number: 8000
```

### 10.2 CDN for Frontend

**CloudFront Configuration:**
- Origin: S3 bucket `mortgage-frontend-prod`
- WAF rules: Rate limiting, SQL injection protection
- Cache policy: No cache for `/api/v1/*`
- Security headers: HSTS, CSP, X-Frame-Options

---

## 11. Security Scanning & Compliance Checks

### 11.1 Pre-Deploy Checklist

```bash
# Makefile target
.PHONY: pre-deploy-audit
pre-deploy-audit:
    # 1. Pip-audit for vulnerabilities
    uv run pip-audit --desc --format=json > security/audit.json
    
    # 2. Check for hardcoded secrets
    git secrets --scan-history
    
    # 3. Verify no float usage in financial modules
    grep -r "float" modules/underwriting/**/*.py && exit 1 || echo "✓ No float usage"
    
    # 4. Verify PIPEDA encryption on models
    uv run pytest tests/compliance/test_pipeda_encryption.py -v
    
    # 5. OSFI stress test validation
    uv run pytest tests/compliance/test_osfi_stress_test.py -v
    
    # 6. FINTRAC audit trail validation
    uv run pytest tests/compliance/test_fintrac_immutable_audit.py -v
    
    # 7. Generate SBOM
    uv run pip-licenses --format=json --output-file=security/sbom.json
```

### 11.2 Container Security

**Dockerfile Requirements:**
```dockerfile
# Non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Security scanning in CI
# Trivy scan
RUN trivy image --exit-code 1 --severity HIGH,CRITICAL \
    --no-progress ${REGISTRY}/${SERVICE}:${IMAGE_TAG}
```

---

## 12. Disaster Recovery Runbook

### 12.1 RTO/RPO Objectives

| Service | RTO | RPO | DR Strategy |
|---------|-----|-----|-------------|
| PostgreSQL | 1 hour | 5 min | Cross-region replica + PITR |
| Redis | 15 min | 1 hour | Multi-AZ + AOF |
| dpt (GPU) | 30 min | N/A | HPA + node pool in secondary region |
| orchestrator | 10 min | N/A | HPA + multi-zone |
| MLFlow | 2 hours | 24 hours | S3 artifact backup |

### 12.2 Failover Procedure

```bash
# 1. Promote read replica
aws rds promote-read-replica-db-cluster --db-cluster-identifier mortgage-db-dr

# 2. Update Kubernetes secrets
kubectl patch secret database-url \
  -n mortgage-underwriting-prod \
  --from-literal=url="postgresql://...dr-region..."

# 3. Restart services
kubectl rollout restart deployment/orchestrator-service -n mortgage-underwriting-prod

# 4. Record DR event in audit log
psql "${DR_DATABASE_URL}" -c "
  INSERT INTO infrastructure.deployment_audit 
  VALUES (...'disaster_recovery'...);
"
```

---

## 13. Cost Optimization

**Resource Recommendations:**
- **dpt GPU nodes:** Use spot instances for non-production (70% cost reduction)
- **PostgreSQL:** Enable RDS Aurora Serverless v2 for dev environments
- **Redis:** Use ElastiCache reserved instances for 1-year term
- **S3:** Intelligent-Tiering for document storage (40% savings)

**Monitoring Cost:**
```yaml
# Prometheus recording rule
- record: monthly_infrastructure_cost
  expr: sum by (service) (avg_over_time(service_cost_usd[30d]))
```

---

**WARNING:** This design plan assumes all financial calculations use `Decimal` types and PII fields are encrypted with AES-256 as per PIPEDA. If implementation deviates, add explicit validation checks in CI/CD pipeline.