# Infrastructure & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Infrastructure & Deployment Module Design Plan

**Feature Slug:** `infrastructure-deployment`  
**Document Path:** `docs/design/infrastructure-deployment.md`  
**Module Identifier:** `INFRA`  

---

## 1. Endpoints

### 1.1 Service Health & Monitoring Endpoints

| Service | Method | Path | Auth | Description |
|---------|--------|------|------|-------------|
| All Services | GET | `/health/live` | Public | Liveness probe (TCP socket) |
| All Services | GET | `/health/ready` | Public | Readiness probe (DB, Redis, dependencies) |
| Orchestrator | GET | `/api/v1/infra/deployment/status/{deployment_id}` | Admin | Fetch deployment status |
| Orchestrator | POST | `/api/v1/infra/deployment/rollback` | Admin | Trigger rollback |
| All Services | GET | `/metrics` | Private (monitoring) | Prometheus metrics |
| DPT Service | GET | `/api/v1/infra/donut/health` | Admin | GPU/ML model health check |

#### 1.1.1 GET /health/ready
**Request Schema:** None (query params only)  
**Response Schema (200):**
```python
{
    "status": "healthy"|"degraded"|"unhealthy",
    "timestamp": "datetime",
    "checks": {
        "database": {"status": "ok"|"error", "latency_ms": int},
        "redis": {"status": "ok"|"error", "latency_ms": int},
        "storage": {"status": "ok"|"error"},
        "gpu": {"status": "ok"|"error", "memory_utilization": Decimal},  # Only for DPT
    },
    "version": "string"  # Git commit SHA
}
```
**Error Responses:**
- `503 Service Unavailable` + `INFRA_001` if any critical check fails
- `500 Internal Server Error` + `INFRA_002` on unexpected health check failure

#### 1.1.2 GET /api/v1/infra/deployment/status/{deployment_id}
**Request Schema:** Path parameter `deployment_id: str` (UUID)  
**Response Schema (200):**
```python
{
    "deployment_id": "uuid",
    "service_name": "orchestrator|dpt|policy|decision|frontend",
    "status": "pending|running|success|failed|rollback_in_progress",
    "started_at": "datetime",
    "completed_at": "datetime|null",
    "git_commit": "string",
    "error_log": "string|null",
    "rolled_back_by": "uuid|null"  # User ID
}
```
**Authentication:** JWT with `admin` role required  
**Error Responses:**
- `404 Not Found` + `INFRA_003` if deployment_id not found
- `403 Forbidden` + `INFRA_004` if non-admin access

#### 1.1.3 POST /api/v1/infra/deployment/rollback
**Request Schema:**
```python
{
    "deployment_id": "uuid",  # Required
    "reason": "string",  # Required, min_length=10
    "target_version": "string|null"  # Git commit SHA, null = previous stable
}
```
**Response Schema (202):**
```python
{
    "rollback_id": "uuid",
    "status": "queued",
    "estimated_completion": "datetime"
}
```
**Authentication:** JWT with `admin` role required  
**Error Responses:**
- `422 Unprocessable Entity` + `INFRA_005` if deployment_id is current production
- `409 Conflict` + `INFRA_006` if rollback already in progress
- `400 Bad Request` + `INFRA_007` if target_version not in history

---

## 2. Models & Database

### 2.1 Infrastructure Schema (`infra` schema in PostgreSQL)

#### 2.1.1 `deployment_log` Table
```python
Table: infra.deployment_log
Columns:
- id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- service_name: VARCHAR(50) NOT NULL  # Enum: ['orchestrator', 'dpt', 'policy', 'decision', 'frontend', 'celery']
- git_commit: VARCHAR(40) NOT NULL  # SHA1 hash
- status: VARCHAR(30) NOT NULL DEFAULT 'pending'  # Enum: ['pending','running','success','failed','rollback_in_progress','rolled_back']
- started_at: TIMESTAMP NOT NULL DEFAULT NOW()
- completed_at: TIMESTAMP NULL
- error_log: TEXT NULL
- rolled_back_by: UUID NULL REFERENCES users.id
- created_by: UUID NOT NULL REFERENCES users.id
- created_at: TIMESTAMP NOT NULL DEFAULT NOW()
- updated_at: TIMESTAMP NOT NULL DEFAULT NOW()

Indexes:
- CREATE INDEX idx_deployment_log_service_status ON infra.deployment_log(service_name, status)
- CREATE INDEX idx_deployment_log_started_at ON infra.deployment_log(started_at DESC)
- CREATE INDEX idx_deployment_log_git_commit ON infra.deployment_log(git_commit)

Audit Fields: created_at, updated_at (mandatory)
```

#### 2.1.2 `service_registry` Table
```python
Table: infra.service_registry
Columns:
- id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- service_name: VARCHAR(50) UNIQUE NOT NULL
- current_version: VARCHAR(40) NOT NULL  # Git commit SHA
- current_replicas: INTEGER NOT NULL DEFAULT 1
- min_replicas: INTEGER NOT NULL DEFAULT 1
- max_replicas: INTEGER NOT NULL DEFAULT 10
- hpa_enabled: BOOLEAN NOT NULL DEFAULT FALSE
- gpu_required: BOOLEAN NOT NULL DEFAULT FALSE
- last_heartbeat: TIMESTAMP NOT NULL DEFAULT NOW()
- created_at: TIMESTAMP NOT NULL DEFAULT NOW()
- updated_at: TIMESTAMP NOT NULL DEFAULT NOW()

Indexes:
- CREATE UNIQUE INDEX idx_service_registry_name ON infra.service_registry(service_name)
- CREATE INDEX idx_service_registry_heartbeat ON infra.service_registry(last_heartbeat)

Audit Fields: created_at, updated_at
```

#### 2.1.3 `environment_config` Table
```python
Table: infra.environment_config
Columns:
- id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- env_name: VARCHAR(20) NOT NULL  # 'local', 'staging', 'production'
- config_key: VARCHAR(100) NOT NULL
- config_value: TEXT NOT NULL  # Encrypted if contains secrets
- is_secret: BOOLEAN NOT NULL DEFAULT FALSE
- created_by: UUID NOT NULL REFERENCES users.id
- created_at: TIMESTAMP NOT NULL DEFAULT NOW()
- updated_at: TIMESTAMP NOT NULL DEFAULT NOW()

Indexes:
- CREATE UNIQUE INDEX idx_env_config_key ON infra.environment_config(env_name, config_key)
- CREATE INDEX idx_env_config_secret ON infra.environment_config(is_secret) WHERE is_secret = TRUE

Audit Fields: created_at, updated_at
Encrypted Fields: config_value when is_secret=TRUE (AES-256 via common/security.py encrypt_pii())
```

---

## 3. Business Logic

### 3.1 Health Check Algorithm
```python
# Pseudocode for /health/ready
async def readiness_check():
    results = {}
    # Database check
    try:
        start = time.now()
        await db.execute("SELECT 1")
        results["database"] = {"status": "ok", "latency_ms": time.now() - start}
    except Exception as e:
        results["database"] = {"status": "error", "latency_ms": -1}
        log.error("db_health_failed", error=str(e), correlation_id=...)

    # Redis check
    try:
        await redis.ping()
        results["redis"] = {"status": "ok"}
    except:
        results["redis"] = {"status": "error"}

    # Storage check (S3/MinIO)
    try:
        await storage_client.head_bucket(Bucket=config.BUCKET_NAME)
        results["storage"] = {"status": "ok"}
    except:
        results["storage"] = {"status": "error"}

    # GPU check (DPT service only)
    if service_name == "dpt":
        try:
            gpu_memory = await get_gpu_memory_utilization()
            if gpu_memory > 90:
                results["gpu"] = {"status": "error", "memory_utilization": gpu_memory}
            else:
                results["gpu"] = {"status": "ok", "memory_utilization": gpu_memory}
        except:
            results["gpu"] = {"status": "error", "memory_utilization": Decimal("0")}

    # Determine overall status
    if any(v["status"] == "error" for v in results.values()):
        raise ServiceUnavailableException(detail=results)
    
    return {"status": "healthy", "checks": results}
```

### 3.2 Deployment State Machine
```
State Transitions:
pending → running: On Kubernetes Job start
running → success: All pods ready, health checks pass
running → failed: Pod crash loop, health check timeout, or init container failure
any → rollback_in_progress: Admin triggers rollback
rollback_in_progress → rolled_back: Previous version pods healthy
rollback_in_progress → failed: Rollback failed (manual intervention required)

Timeout Rules:
- Running → Failed after 15 minutes if no pods reach ready state
- Rollback must complete within 10 minutes or escalate alert
```

### 3.3 Horizontal Pod Autoscaling Rules
```python
# For orchestrator and dpt services
hpa_metrics:
- type: cpu
  target_utilization: 70%
- type: memory
  target_utilization: 80%
- type: http_requests_per_second
  target_value: 1000  # requests per second per pod

# DPT service additional GPU scaling
gpu_hpa_metrics:
- type: gpu_memory_utilization
  target_value: 75%  # Scale when GPU memory >75%
- type: queue_length  # Celery task queue
  target_value: 50  # Scale when >50 pending tasks

Scaling Constraints:
- min_replicas: 2 (production), 1 (staging)
- max_replicas: 20 (orchestrator), 10 (dpt), 5 (other services)
- stabilization_window: 300 seconds (scale down)
- cooldown_period: 60 seconds (scale up)
```

### 3.4 Backup & Disaster Recovery Logic
```python
# Daily automated backup job
backup_job:
  schedule: "0 2 * * *"  # 2 AM UTC
  retention: 30 days  # FINTRAC 5-year retention handled by S3 Glacier
  databases:
    - postgres_main: full SQL dump to s3://mortgage-backups/db/
    - redis: RDB snapshot to s3://mortgage-backups/cache/
  
# Point-in-time recovery
pitr_recovery:
  rpo: 5 minutes  # Recovery Point Objective
  rto: 30 minutes  # Recovery Time Objective
  wal_archiving: enabled to S3
  cross_region_replication: s3://mortgage-backups to ca-central-1

# Disaster recovery trigger conditions
dr_trigger:
  - Primary region API error rate > 50% for 5 minutes
  - Primary region database unreachable > 3 minutes
  - Manual trigger by SRE team
```

---

## 4. Migrations

### 4.1 New Alembic Migration: `infra_setup`
```python
# migration id: 2024_01_001_create_infra_schema
def upgrade():
    # Create infra schema
    op.execute("CREATE SCHEMA IF NOT EXISTS infra")
    
    # Create deployment_log table
    op.create_table(
        'deployment_log',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('service_name', sa.String(length=50), nullable=False),
        sa.Column('git_commit', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('rolled_back_by', sa.UUID(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['rolled_back_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='infra'
    )
    
    # Create service_registry table
    op.create_table(
        'service_registry',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('service_name', sa.String(length=50), nullable=False),
        sa.Column('current_version', sa.String(length=40), nullable=False),
        sa.Column('current_replicas', sa.Integer(), server_default='1', nullable=False),
        sa.Column('min_replicas', sa.Integer(), server_default='1', nullable=False),
        sa.Column('max_replicas', sa.Integer(), server_default='10', nullable=False),
        sa.Column('hpa_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('gpu_required', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='infra'
    )
    
    # Create environment_config table
    op.create_table(
        'environment_config',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('env_name', sa.String(length=20), nullable=False),
        sa.Column('config_key', sa.String(length=100), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=False),
        sa.Column('is_secret', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='infra'
    )
    
    # Create indexes
    op.create_index('idx_deployment_log_service_status', 'deployment_log', ['service_name', 'status], schema='infra')
    op.create_index('idx_deployment_log_started_at', 'deployment_log', [sa.text('started_at DESC')], schema='infra')
    op.create_index('idx_service_registry_name', 'service_registry', ['service_name'], unique=True, schema='infra')
    op.create_index('idx_env_config_key', 'environment_config', ['env_name', 'config_key'], unique=True, schema='infra')
    op.create_index('idx_env_config_secret', 'environment_config', ['is_secret'], schema='infra', postgresql_where=sa.text("is_secret = true"))

def downgrade():
    op.drop_index('idx_env_config_secret', table_name='environment_config', schema='infra')
    op.drop_index('idx_env_config_key', table_name='environment_config', schema='infra')
    op.drop_index('idx_service_registry_name', table_name='service_registry', schema='infra')
    op.drop_index('idx_deployment_log_started_at', table_name='deployment_log', schema='infra')
    op.drop_index('idx_deployment_log_service_status', table_name='deployment_log', schema='infra')
    op.drop_table('environment_config', schema='infra')
    op.drop_table('service_registry', schema='infra')
    op.drop_table('deployment_log', schema='infra')
    op.execute("DROP SCHEMA IF EXISTS infra")
```

### 4.2 Data Migration: Seed Service Registry
```python
# migration id: 2024_01_002_seed_services
def upgrade():
    # Pre-populate service registry for production deployment
    op.execute("""
        INSERT INTO infra.service_registry (service_name, current_version, min_replicas, max_replicas, hpa_enabled, gpu_required)
        VALUES 
            ('orchestrator', 'unknown', 2, 20, true, false),
            ('dpt', 'unknown', 1, 10, true, true),
            ('policy', 'unknown', 2, 5, false, false),
            ('decision', 'unknown', 2, 5, false, false),
            ('frontend', 'unknown', 2, 10, true, false),
            ('celery', 'unknown', 1, 5, true, false)
        ON CONFLICT (service_name) DO NOTHING
    """)
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 & FINTRAC Compliance in Infrastructure
- **Audit Logging**: All deployment events must be logged with `correlation_id`, `user_id`, and `timestamp` to immutable log storage (S3 with object lock). Logs retained for 5 years per FINTRAC.
- **Immutable Infrastructure**: Kubernetes deployments use `readOnlyRootFilesystem: true` to prevent post-deployment modification. All changes trigger new deployment log entry.
- **Transaction Threshold Monitoring**: Infrastructure must support FINTRAC $10,000 reporting by ensuring `decision` service logs include `transaction_amount` field with appropriate flagging. Log pipeline routes flagged transactions to secure audit bucket.
- **Stress Test Compliance**: Infrastructure must guarantee that `qualifying_rate` calculation (max(rate+2%, 5.25%)) is never cached or approximated. All calculations run in isolated `policy` service pods with CPU/memory limits to prevent numerical precision loss.

### 5.2 PIPEDA Data Handling
- **Encryption at Rest**: All environment configs with `is_secret=TRUE` encrypted using AES-256-GCM via `common/security.encrypt_pii()`. Keys stored in AWS KMS or HashiCorp Vault, never in Kubernetes secrets as plaintext.
- **Encryption in Transit**: mTLS enforced between all services using Linkerd or Istio. Certificate rotation every 30 days. Frontend→API uses TLS 1.3 with HSTS.
- **Data Minimization**: Infrastructure logs must NEVER contain SIN, DOB, income, or banking data. Log scrubber middleware automatically redacts patterns matching `/\d{9}/` (SIN) and `/\d{4}-\d{2}-\d{2}/` (DOB).
- **Secret Management**: Use external-secrets operator to sync Vault/AWS Secrets Manager to Kubernetes secrets. Secrets mounted as tmpfs volumes (RAM-only). No environment variables for secrets.

### 5.3 Security Scanning & Hardening
- **Pre-Deployment Scanning**: `uv run pip-audit` and `trivy image scan` must pass in CI pipeline. High/Critical CVEs block deployment.
- **Runtime Scanning**: Falco deployed in Kubernetes to detect anomalous behavior (e.g., shell in container, unexpected network connections).
- **Network Policies**: Default deny-all with explicit allow rules between namespaces. `frontend` cannot directly access `postgres`, must go through `orchestrator`.
- **Pod Security Standards**: Enforce `restricted` profile (runAsNonRoot, drop ALL capabilities, readOnlyRootFilesystem).

### 5.4 Authentication & Authorization
- **Inter-service Auth**: gRPC services use mTLS with SPIFFE/SPIRE for workload identity. REST services use JWT with `service` role.
- **Admin Endpoints**: All `/api/v1/infra/*` endpoints require JWT with `admin` role AND IP whitelist from VPN bastion host.
- **CI/CD Auth**: GitHub Actions OIDC tokens federated to AWS/GCP IAM roles. No long-lived credentials.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `InfraHealthCheckFailed` | 503 | `INFRA_001` | "Service unhealthy: {check_name}" | Database/redis/storage check fails |
| `InfraUnexpectedError` | 500 | `INFRA_002` | "Health check internal error" | Exception during health check execution |
| `DeploymentNotFoundError` | 404 | `INFRA_003` | "Deployment {id} not found" | Invalid deployment_id query |
| `InfraAccessDeniedError` | 403 | `INFRA_004` | "Admin access required for {resource}" | Non-admin accesses admin endpoint |
| `RollbackNotAllowedError` | 422 | `INFRA_005` | "Cannot rollback current production deployment" | Attempt to rollback active production |
| `RollbackInProgressError` | 409 | `INFRA_006` | "Rollback already in progress for {service}" | Concurrent rollback attempts |
| `InvalidVersionError` | 400 | `INFRA_007` | "Version {version} not in deployment history" | target_version doesn't exist |
| `ServiceHeartbeatTimeout` | 500 | `INFRA_008` | "Service {name} heartbeat expired" | last_heartbeat > 5 minutes ago |
| `SecretDecryptionError` | 500 | `INFRA_009` | "Failed to decrypt config key {key}" | KMS/Vault unavailable or key rotated |
| `GPUResourceExhausted` | 503 | `INFRA_010` | "GPU node pool capacity exhausted" | Cannot schedule DPT pod due to GPU limits |

### 6.1 Error Response Structure
All infrastructure errors follow:
```json
{
    "detail": "Human-readable message",
    "error_code": "INFRA_XXX",
    "correlation_id": "uuid",
    "timestamp": "ISO8601",
    "service": "orchestrator|dpt|policy|..."
}
```

### 6.2 Retry & Circuit Breaker Policies
- **Health Check Failures**: Exponential backoff (1s, 2s, 4s... max 30s) for 3 attempts before marking service down
- **Database Connection**: Circuit breaker opens after 5 failures in 60s, half-open after 30s
- **External API Calls** (KMS, S3): Timeout 5s, retry 3 times with jitter
- **gRPC Inter-service**: Use envoy proxy with default retry policy (3 attempts, timeout 10s)

---

## 7. CI/CD Pipeline Design (Supplementary)

### 7.1 GitHub Actions Workflow Stages
```yaml
# .github/workflows/deploy.yml
jobs:
  security_scan:
    steps:
      - run: uv run pip-audit --output json > audit.json
      - run: trivy image --exit-code 1 --severity HIGH,CRITICAL .
  
  test:
    steps:
      - run: pytest -m unit
      - run: pytest -m integration --cov-report=xml
  
  build:
    steps:
      - run: docker build -t mortgage-{service}:${{ github.sha }} .
      - run: docker push ghcr.io/mortgage/{service}:${{ github.sha }}
  
  deploy_staging:
    needs: [security_scan, test, build]
    steps:
      - run: kubectl apply -f k8s/staging/{service}-deployment.yaml
      - run: kubectl rollout status --timeout=15m
  
  deploy_production:
    needs: [deploy_staging]
    environment: production
    steps:
      - run: kubectl apply -f k8s/production/{service}-deployment.yaml
      - run: echo "deployment_id=$(uuidgen)" >> $GITHUB_OUTPUT
      - run: kubectl wait --for=condition=available --timeout=15m deployment/{service}
      - run: |
          curl -X POST https://orchestrator/api/v1/infra/deployment/log \
            -H "Authorization: Bearer ${{ secrets.ADMIN_JWT }}" \
            -d '{"service": "${{ matrix.service }}", "commit": "${{ github.sha }}", "status": "success"}'
```

### 7.2 ArgoCD GitOps Configuration
```yaml
# k8s/argocd/app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  project: mortgage-underwriting
  source:
    repoURL: https://github.com/mortgage/underwriting.git
    targetRevision: HEAD
    path: k8s/production
  destination:
    server: https://kubernetes.default.svc
    namespace: mortgage-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

---

## 8. Monitoring & Alerting

### 8.1 Prometheus Metrics
```python
# metrics exposed by each service
mortgage_http_requests_total{method, endpoint, status}
mortgage_http_request_duration_seconds{method, endpoint}
mortgage_database_query_duration_seconds{operation}
mortgage_redis_ops_total{operation, status}
mortgage_deployment_status{service, version, status}
mortgage_gpu_memory_utilization{service="dpt"}
mortgage_task_queue_length{service="celery"}
```

### 8.2 AlertManager Rules
```yaml
# Alert on FINTRAC-relevant failures
- alert: HighErrorRate
  expr: rate(mortgage_http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
    compliance: "FINTRAC"
  annotations:
    summary: "Service {{ $labels.service }} error rate >5%"

- alert: DeploymentFailed
  expr: mortgage_deployment_status{status="failed"} > 0
  for: 0m
  labels:
    severity: critical
  annotations:
    summary: "Deployment {{ $labels.service }} failed"

- alert: GPUResourceExhausted
  expr: mortgage_gpu_memory_utilization > 90
  for: 3m
  labels:
    severity: warning
  annotations:
    summary: "DPT GPU memory >90%, scaling may fail"
```

---

## 9. Docker Compose Services (Local Development)

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15.2
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mortgage"]
      interval: 5s
      timeout: 3s
      retries: 5
  
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
  
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
  
  dpt:
    build: ./modules/dpt
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
      interval: 10s
      timeout: 5s
      retries: 3
  
  orchestrator:
    build: .
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
  
  celery:
    build: .
    command: celery -A modules.tasks worker --pool=gevent --concurrency=4
    depends_on:
      - redis
      - postgres
```

---

## 10. Production Kubernetes Manifests

### 10.1 DPT Deployment (GPU-enabled)
```yaml
# k8s/production/dpt-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dpt
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: dpt
        image: ghcr.io/mortgage/dpt:${GIT_COMMIT}
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: 8Gi
            cpu: 2
          limits:
            nvidia.com/gpu: 1
            memory: 12Gi
            cpu: 4
        securityContext:
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop: ["ALL"]
      nodeSelector:
        node.kubernetes.io/instance-type: g4dn.xlarge  # AWS GPU node
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Exists"
        effect: "NoSchedule"
```

### 10.2 HorizontalPodAutoscaler
```yaml
# k8s/production/orchestrator-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orchestrator-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orchestrator
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
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

---

## 11. Load Balancing & CDN

### 11.1 AWS ALB Configuration
```yaml
# Terraform snippet
resource "aws_lb" "mortgage_api" {
  name               = "mortgage-api-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.mortgage_alb.id]
  subnets            = data.aws_subnets.public.ids
  
  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb-logs"
    enabled = true
  }
}

resource "aws_lb_target_group" "orchestrator" {
  name     = "orchestrator-tg"
  port     = 8000
  protocol = "HTTPS"
  health_check {
    path                = "/health/ready"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}
```

### 11.2 CloudFront CDN (Frontend)
```yaml
# CloudFront distribution for frontend static assets
origins:
  - domain_name: mortgage-frontend.s3.ca-central-1.amazonaws.com
    origin_access_control: OAC_MORTGAGE_FRONTEND

cache_behaviors:
  - path_pattern: /api/*
    target_origin_id: alb-orchestrator
    forwarded_values:
      headers: ["Authorization", "Correlation-ID"]
      cookies: none
    ttl: 0  # No caching for API calls

  - path_pattern: /*
    target_origin_id: s3-frontend
    compress: true
    ttl: 86400  # Cache static assets for 1 day

# Security headers
response_headers_policy:
  content_security_policy: "default-src 'self'; script-src 'self' 'unsafe-inline';"
  strict_transport_security: "max-age=31536000; includeSubDomains; preload"
  x_content_type_options: "nosniff"
```

---

**WARNING**: This design assumes the existence of a `users` table in the main application schema for `created_by` foreign keys. If the `users` table resides in a different schema, the foreign key definitions must be updated accordingly.