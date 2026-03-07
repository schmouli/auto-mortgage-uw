# Infrastructure & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Infrastructure & Deployment Module Design

**Module Identifier:** `infrastructure_deployment`  
**Design Document:** `docs/design/infrastructure-deployment.md`  
**Scope:** Local development orchestration, production Kubernetes deployment, service health monitoring, configuration management, and deployment audit trails.

---

## 1. Endpoints

### 1.1 System Health & Service Discovery

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/infrastructure/health` | Public | Overall system health aggregate |
| `GET` | `/api/v1/infrastructure/services` | Authenticated | List all registered services with status |
| `GET` | `/api/v1/infrastructure/services/{service_name}/health` | Authenticated | Detailed health check for specific service |
| `POST` | `/api/v1/infrastructure/config/validate` | Admin-only | Validate environment configuration |
| `GET` | `/api/v1/infrastructure/deployment/status` | Admin-only | Current deployment version and status |

---

### 1.2 Request/Response Schemas

#### `GET /api/v1/infrastructure/health`
**Response 200 OK**
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2024-01-15T14:30:00Z",
  "services": {
    "postgres": {"status": "healthy", "response_time_ms": 12},
    "redis": {"status": "healthy", "response_time_ms": 3},
    "dpt": {"status": "degraded", "error": "GPU memory utilization > 90%"},
    "orchestrator": {"status": "healthy", "active_workflows": 42}
  },
  "version": "1.2.3"
}
```

#### `GET /api/v1/infrastructure/services`
**Response 200 OK**
```json
{
  "services": [
    {
      "name": "dpt",
      "endpoint": "http://dpt:8000",
      "health_check_url": "http://dpt:8000/api/v1/dpt/health",
      "status": "healthy",
      "last_heartbeat": "2024-01-15T14:29:58Z",
      "version": "1.2.3"
    }
  ]
}
```

#### `POST /api/v1/infrastructure/config/validate`
**Request Body**
```json
{
  "environment": "staging",
  "service_name": "orchestrator",
  "config": {
    "max_concurrent_workflows": 100,
    "redis_url": "redis://redis:6379/0",
    "database_url": "postgresql+asyncpg://user:pass@postgres:5432/mortgage"
  }
}
```

**Response 200 OK**
```json
{
  "valid": true,
  "warnings": [
    "DATABASE_URL uses unencrypted connection in production"
  ]
}
```

**Response 422 Validation Error**
```json
{
  "detail": "Configuration validation failed",
  "error_code": "INFRA_002",
  "validation_errors": [
    {"field": "max_concurrent_workflows", "reason": "must be >= 1"}
  ]
}
```

---

### 1.3 Error Responses

| HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-------------|------------|-----------------|-------------------|
| `404` | `INFRA_001` | "Service '{service_name}' not found" | Service not in registry |
| `422` | `INFRA_002` | "Configuration validation failed: {detail}" | Invalid config schema |
| `409` | `INFRA_003` | "Deployment in progress for {service_name}" | Concurrent deployment attempt |
| `500` | `INFRA_004` | "Health check failed: {reason}" | Service unreachable or timeout |
| `403` | `INFRA_005` | "Admin access required" | Non-admin access to admin endpoints |

---

## 2. Models & Database

### 2.1 `service_registry` Table
```sql
CREATE TABLE service_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,  -- dpt, policy, decision, orchestrator, etc.
    endpoint VARCHAR(255) NOT NULL,
    health_check_url VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',  -- unknown, healthy, degraded, unhealthy
    last_heartbeat TIMESTAMPTZ,
    version VARCHAR(20),
    metadata JSONB,  -- service-specific metadata (e.g., GPU memory for dpt)
    
    -- Audit fields (FINTRAC compliance)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT chk_status CHECK (status IN ('unknown', 'healthy', 'degraded', 'unhealthy'))
);

CREATE INDEX idx_service_registry_status ON service_registry(status);
CREATE INDEX idx_service_registry_name ON service_registry(name);
```

### 2.2 `deployment_config` Table
```sql
CREATE TABLE deployment_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment VARCHAR(20) NOT NULL,  -- development, staging, production
    service_name VARCHAR(50) NOT NULL,
    config_json JSONB NOT NULL,  -- Encrypted sensitive values within JSON
    version VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL,  -- User identity (hashed) FINTRAC audit
    
    -- Indexes
    UNIQUE(environment, service_name, version)
);

CREATE INDEX idx_deployment_config_active ON deployment_config(environment, service_name) WHERE is_active = true;
CREATE INDEX idx_deployment_config_version ON deployment_config(service_name, version);
```

### 2.3 `deployment_audit_log` Table (FINTRAC Immutable Trail)
```sql
CREATE TABLE deployment_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action VARCHAR(50) NOT NULL,  -- deploy, rollback, config_update
    service_name VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    deployed_by VARCHAR(100) NOT NULL,  -- Hashed user identifier
    status VARCHAR(20) NOT NULL,  -- started, success, failed
    logs TEXT,  -- Deployment logs (no PII)
    
    -- FINTRAC compliance: immutable, 5-year retention
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes for retention policy queries
    CONSTRAINT deployment_audit_log_retention CHECK (created_at >= NOW() - INTERVAL '5 years')
);

CREATE INDEX idx_deployment_audit_log_service ON deployment_audit_log(service_name, created_at);
CREATE INDEX idx_deployment_audit_log_user ON deployment_audit_log(deployed_by, created_at);
```

### 2.4 `encrypted_environment_variables` Table (PIPEDA Compliance)
```sql
CREATE TABLE encrypted_environment_variables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL,
    encrypted_value BYTEA NOT NULL,  -- AES-256 encrypted
    service_name VARCHAR(50) NOT NULL,
    environment VARCHAR(20) NOT NULL,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL,
    
    UNIQUE(key, service_name, environment)
);

CREATE INDEX idx_env_vars_lookup ON encrypted_environment_variables(service_name, environment);
```

---

## 3. Business Logic

### 3.1 Health Check Orchestration Algorithm
```python
# services.py: HealthCheckService
async def perform_health_check(service_name: str) -> ServiceHealth:
    """
    1. Retrieve service from registry
    2. HTTP GET to service.health_check_url with 5s timeout
    3. Parse response: {"status": "healthy", "details": {...}}
    4. Update service_registry.last_heartbeat and status
    5. Log metrics: response_time, status (no PII)
    6. Return structured health report
    """
    # Timeout: 5s for HTTP, 3s for TCP health checks
    # Retry: 3 attempts with exponential backoff
    # Status mapping: HTTP 200 + {"status": "healthy"} → healthy
    #                 HTTP 200 + {"status": "degraded"} → degraded
    #                 Timeout or HTTP ≠ 200 → unhealthy
```

### 3.2 Configuration Validation Rules
```python
# schemas.py: ConfigValidationSchema
validation_rules = {
    "database_url": {
        "required": True,
        "pattern": r"^postgresql\+asyncpg://.*",
        "forbidden_in_prod": ["localhost", "127.0.0.1"]
    },
    "redis_url": {
        "required": True,
        "pattern": r"^redis://.*"
    },
    "minio_endpoint": {
        "required_if_env": "development",
        "pattern": r"^https?://.*"
    },
    "s3_bucket_name": {
        "required_if_env": "production",
        "pattern": r"^[a-z0-9\-]+$"
    },
    "celery_broker_url": {
        "required": True,
        "pattern": r"^redis://.*|^amqp://.*"
    },
    "gpu_memory_limit_mb": {
        "required_if_service": "dpt",
        "min": 4096,  # 4GB minimum for Donut model
        "max": 16384  # 16GB maximum per pod
    }
}
```

### 3.3 Deployment State Machine
```
State Transitions:
  ┌─────────────┐
  │   pending   │
  └──────┬──────┘
         │ deploy()
         ▼
  ┌─────────────┐
  │  deploying  │◄──────┐
  └──────┬──────┘       │
         │              │ rollback()
         ▼              │
  ┌─────────────┐       │
  │   running   │──────►│
  └──────┬──────┘       │
         │              │
         │ failure      │
         ▼              │
  ┌─────────────┐       │
  │   failed    │       │
  └─────────────┘       │
         ▲              │
         │ retry()      │
         └──────┬───────┘
                │
                ▼
         ┌─────────────┐
         │  terminated │
         └─────────────┘
```

**Transition Rules:**
- `pending → deploying`: Validated config, sufficient resources, no active deployment
- `deploying → running`: All pods healthy, health checks passing for 60s
- `deploying → failed`: Pod crash loop, health check failure, image pull error
- `running → failed`: Critical error detected, OOMKilled, GPU failure
- `any → terminated`: Manual intervention, scale-to-zero, end-of-life

---

### 3.4 GPU Resource Management for DPT Service
```python
# services.py: DPTResourceManager
async def allocate_gpu_resources(requested_memory_mb: int) -> GPUAllocation:
    """
    1. Query node GPU metrics (NVIDIA DCGM)
    2. Check available memory on T4/A10 nodes
    3. Reserve GPU memory for Donut model inference
    4. Log allocation: {node_id, gpu_id, memory_mb} (no PII)
    5. Return allocation or raise InsufficientGPUError
    
    Constraints:
    - Max 1 DPT pod per GPU (isolation)
    - Minimum 8GB memory reservation
    - Automatic fallback to CPU if GPU unavailable (with warning)
    """
```

---

## 4. Migrations

### 4.1 New Tables
```python
# Alembic migration: 001_create_infrastructure_tables.py
def upgrade():
    # service_registry table (see section 2.1)
    # deployment_config table (see section 2.2)
    # deployment_audit_log table (see section 2.3)
    # encrypted_environment_variables table (see section 2.4)
    
    # Add foreign key constraints
    op.create_foreign_key(
        'fk_deployment_config_service',
        'deployment_config', 'service_registry',
        ['service_name'], ['name']
    )
```

### 4.2 Indexes for Performance
```python
# Composite index for health check queries
op.create_index(
    'idx_service_registry_heartbeat',
    'service_registry',
    ['status', 'last_heartbeat'],
    postgresql_where="status IN ('healthy', 'degraded')"
)

# Partial index for active configs
op.create_index(
    'idx_deployment_config_active_unique',
    'deployment_config',
    ['environment', 'service_name'],
    unique=True,
    postgresql_where="is_active = true"
)
```

### 4.3 Data Migration (Initial Seed)
```python
# Seed service_registry with default services
def seed_services():
    services = [
        {"name": "postgres", "endpoint": "postgresql://postgres:5432", "health_check_url": "tcp://postgres:5432"},
        {"name": "redis", "endpoint": "redis://redis:6379", "health_check_url": "redis://redis:6379/health"},
        {"name": "minio", "endpoint": "http://minio:9000", "health_check_url": "http://minio:9000/minio/health/live"},
        {"name": "dpt", "endpoint": "http://dpt:8000", "health_check_url": "http://dpt:8000/api/v1/dpt/health"},
        {"name": "policy", "endpoint": "http://policy:8000", "health_check_url": "http://policy:8000/api/v1/policy/health"},
        {"name": "decision", "endpoint": "http://decision:8000", "health_check_url": "http://decision:8000/api/v1/decision/health"},
        {"name": "orchestrator", "endpoint": "http://orchestrator:8000", "health_check_url": "http://orchestrator:8000/api/v1/orchestrator/health"},
        {"name": "frontend", "endpoint": "http://frontend:3000", "health_check_url": "http://frontend:3000/health"},
        {"name": "celery", "endpoint": "redis://redis:6379", "health_check_url": "redis://redis:6379/health"}
    ]
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Auditability**: All deployment events logged to `deployment_audit_log` with immutable retention
- **Stress Test Configuration**: Ensure `dpt` service can access GPU resources for stress test calculations
- **GDS/TDS Calculation Logging**: Deployment logs must not contain financial data, only service metadata

### 5.2 FINTRAC Compliance
- **Immutable Audit Trail**: `deployment_audit_log` table has no UPDATE/DELETE operations
- **5-Year Retention**: PostgreSQL partition policy: `RETENTION_INTERVAL = '5 years'`
- **Identity Verification**: `deployed_by` field stores SHA256 hash of user identity (never plaintext)
- **Transaction Flagging**: Deployments > $10,000 (infrastructure cost) flagged in audit log (for cloud resource costs)

### 5.3 PIPEDA Data Handling
- **Encryption at Rest**: `encrypted_environment_variables.encrypted_value` uses AES-256-GCM
- **Encryption in Transit**: mTLS enforced between all services
- **No PII in Logs**: Health check logs exclude connection strings, credentials
- **Data Minimization**: Only store required service metadata, no user data

### 5.4 Authentication & Authorization
```yaml
# RBAC Matrix
endpoints:
  /api/v1/infrastructure/health:
    - role: public
      methods: [GET]
  
  /api/v1/infrastructure/services:
    - role: authenticated_user
      methods: [GET]
  
  /api/v1/infrastructure/services/*/health:
    - role: authenticated_user
      methods: [GET]
  
  /api/v1/infrastructure/config/validate:
    - role: admin
      methods: [POST]
  
  /api/v1/infrastructure/deployment/status:
    - role: admin
      methods: [GET, POST]
```

### 5.5 Secret Management
```python
# common/security.py: get_encrypted_env_var()
async def get_encrypted_env_var(key: str, service: str, env: str) -> str:
    """
    1. Fetch encrypted value from database
    2. Decrypt using AWS KMS or HashiCorp Vault
    3. Cache in memory for 5 minutes (max)
    4. Never log decrypted value
    5. Return plaintext value to service
    """
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# modules/infrastructure_deployment/exceptions.py
class InfrastructureException(AppException):
    """Base exception for infrastructure module"""
    pass

class ServiceNotFoundError(InfrastructureException):
    """Service not in registry"""
    http_status = 404
    error_code = "INFRA_001"

class HealthCheckFailedError(InfrastructureException):
    """Service health check timeout or failure"""
    http_status = 503
    error_code = "INFRA_004"

class ConfigurationValidationError(InfrastructureException):
    """Invalid configuration schema or values"""
    http_status = 422
    error_code = "INFRA_002"

class DeploymentConflictError(InfrastructureException):
    """Concurrent deployment in progress"""
    http_status = 409
    error_code = "INFRA_003"

class InsufficientGPUError(InfrastructureException):
    """No GPU resources available for DPT"""
    http_status = 503
    error_code = "INFRA_006"
```

### 6.2 Error Response Structure
```json
{
  "detail": "Service 'dpt' health check failed after 3 attempts",
  "error_code": "INFRA_004",
  "correlation_id": "c5f7e2a1-8b3d-4f9e-9c1a-7d6e5f8b2a3c",
  "metadata": {
    "service": "dpt",
    "attempts": 3,
    "timeout_ms": 5000
  }
}
```

---

## 7. Docker Compose Configuration (Local Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15.2-alpine
    environment:
      POSTGRES_DB: mortgage_underwriting
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - underwriting_net

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - underwriting_net

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - underwriting_net

  dpt:
    build: ./modules/dpt
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - MINIO_ENDPOINT=http://minio:9000
      - GPU_MEMORY_LIMIT_MB=${DPT_GPU_MEMORY:-8192}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/dpt/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    networks:
      - underwriting_net

  policy:
    build: ./modules/policy
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - OSFI_QUALIFYING_RATE=${OSFI_QUALIFYING_RATE:-5.25}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/policy/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - underwriting_net

  decision:
    build: ./modules/decision
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - POLICY_SERVICE_URL=http://policy:8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/decision/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
      policy:
        condition: service_healthy
    networks:
      - underwriting_net

  orchestrator:
    build: ./modules/orchestrator
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/2
      - DPT_SERVICE_URL=http://dpt:8000
      - DECISION_SERVICE_URL=http://decision:8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/orchestrator/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      dpt:
        condition: service_healthy
      decision:
        condition: service_healthy
    networks:
      - underwriting_net

  frontend:
    build: ./frontend
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      orchestrator:
        condition: service_healthy
    networks:
      - underwriting_net

  celery:
    build: ./modules/orchestrator
    command: celery -A orchestrator.celery_app worker --loglevel=info --pool=gevent --concurrency=10
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/mortgage_underwriting
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/2
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/2
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - underwriting_net

volumes:
  postgres_data:
  redis_data:
  minio_data:

networks:
  underwriting_net:
    driver: bridge
```

---

## 8. Kubernetes Production Deployment

### 8.1 Namespace & Resource Quotas
```yaml
# k8s/00-namespace.yml
apiVersion: v1
kind: Namespace
metadata:
  name: mortgage-underwriting-prod
  labels:
    name: mortgage-underwriting-prod
    environment: production
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: underwriting-quota
  namespace: mortgage-underwriting-prod
spec:
  hard:
    requests.cpu: "50"
    requests.memory: 200Gi
    limits.cpu: "100"
    limits.memory: 400Gi
    requests.nvidia.com/gpu: "10"
```

### 8.2 PostgreSQL (RDS) Configuration
```yaml
# k8s/01-postgres-config.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-config
  namespace: mortgage-underwriting-prod
data:
  POSTGRES_DB: "mortgage_underwriting_prod"
  POSTGRES_HOST: "mortgage-db.abc123.us-east-1.rds.amazonaws.com"
  POSTGRES_PORT: "5432"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: mortgage-underwriting-prod
type: Opaque
data:
  POSTGRES_USER: <base64-encoded-username>
  POSTGRES_PASSWORD: <base64-encoded-password>
```

### 8.3 DPT Service (GPU-Enabled)
```yaml
# k8s/04-dpt-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dpt-service
  namespace: mortgage-underwriting-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: dpt-service
  template:
    metadata:
      labels:
        app: dpt-service
    spec:
      nodeSelector:
        accelerator: nvidia-t4  # GPU node pool
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Equal"
          value: "present"
          effect: "NoSchedule"
      containers:
        - name: dpt
          image: registry.example.com/mortgage/dpt:v1.2.3
          resources:
            requests:
              cpu: "4"
              memory: "16Gi"
              nvidia.com/gpu: "1"
            limits:
              cpu: "8"
              memory: "32Gi"
              nvidia.com/gpu: "1"
          envFrom:
            - configMapRef:
                name: dpt-config
            - secretRef:
                name: dpt-secret
          livenessProbe:
            httpGet:
              path: /api/v1/dpt/health
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /api/v1/dpt/health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
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
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dpt-hpa
  namespace: mortgage-underwriting-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dpt-service
  minReplicas: 2
  maxReplicas: 10
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
          name: mortgage_underwriting_active_workflows
        target:
          type: AverageValue
          averageValue: "50"
```

### 8.4 MLFlow Model Registry
```yaml
# k8s/10-mlflow-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-registry
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
            "--backend-store-uri", "postgresql://user:pass@rds-host:5432/mlflow",
            "--default-artifact-root", "s3://mortgage-mlflow-artifacts/"
          ]
          env:
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aws-mlflow-secret
                  key: access-key
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aws-mlflow-secret
                  key: secret-key
```

---

## 9. CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Run pip-audit
        run: |
          uv run pip-audit --desc --format=json > audit-report.json
          if grep -q "VULNERABILITY" audit-report.json; then
            echo "::error::Security vulnerabilities found"
            exit 1
          fi

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15.2
        env:
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          uv run pytest -m "unit or integration" --cov=modules --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build-and-push:
    needs: [security-scan, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsDeploy
      - name: Build and push images
        run: |
          for service in dpt policy decision orchestrator; do
            docker build -t registry.example.com/mortgage/${service}:${GITHUB_SHA} ./modules/${service}
            docker push registry.example.com/mortgage/${service}:${GITHUB_SHA}
          done

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/dpt-service dpt=registry.example.com/mortgage/dpt:${GITHUB_SHA} -n mortgage-underwriting-prod
          kubectl rollout status deployment/dpt-service -n mortgage-underwriting-prod --timeout=10m
          # Log deployment to audit trail
          echo "${GITHUB_ACTOR}" | sha256sum > deployed_by_hash
          kubectl exec -n mortgage-underwriting-prod deployment/orchestrator -- \
            python -m modules.infrastructure_deployment.services.log_deployment \
            --service dpt --version ${GITHUB_SHA} --deployed_by $(cat deployed_by_hash)
```

---

## 10. Monitoring & Alerting

### 10.1 Prometheus Metrics
```python
# modules/infrastructure_deployment/services.py
from prometheus_client import Counter, Histogram, Gauge

# Service health metrics
service_health_status = Gauge(
    'mortgage_service_health_status',
    'Health status of services (1=healthy, 0=unhealthy)',
    ['service_name', 'environment']
)

deployment_duration = Histogram(
    'mortgage_deployment_duration_seconds',
    'Time taken for deployment',
    ['service_name', 'status']
)

# Financial calculation audit metric (OSFI B-20)
gds_tds_calculation_audit = Counter(
    'mortgage_gds_tds_calculations_total',
    'Total GDS/TDS calculations performed',
    ['calculation_type', 'result']  # result: pass/fail
)
```

### 10.2 Grafana Dashboards
- **Service Health Overview**: Real-time status of all 8 services
- **GPU Utilization**: DPT GPU memory, temperature, utilization
- **Deployment Frequency**: Success/failure rates per service
- **Financial Compliance**: GDS/TDS calculation counts, stress test application rate

### 10.3 Alertmanager Rules
```yaml
# k8s/alerting-rules.yml
groups:
  - name: mortgage-underwriting
    rules:
      - alert: ServiceDown
        expr: mortgage_service_health_status == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.service_name }} is unhealthy"
      
      - alert: HighGPUUsage
        expr: nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes > 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "DPT GPU memory utilization > 90%"
      
      - alert: DeploymentFailure
        expr: rate(mortgage_deployment_duration_seconds_count{status="failed"}[5m]) > 0.1
        labels:
          severity: high
        annotations:
          summary: "Deployment failure rate > 10% in last 5 minutes"
```

---

## 11. Backup & Disaster Recovery

### 11.1 PostgreSQL (RDS)
```bash
# Automated daily snapshots, 7-day retention
# Point-in-time recovery enabled
# WAL archiving to S3 for 30 days

# Disaster recovery runbook
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier mortgage-db-prod \
  --target-db-instance-identifier mortgage-db-dr \
  --restore-time 2024-01-15T14:30:00Z
```

### 11.2 Redis (ElastiCache)
- **RDB Snapshots**: Every 6 hours, retained for 3 days
- **AOF Enabled**: For point-in-time recovery
- **Multi-AZ**: Automatic failover to replica

### 11.3 MinIO/S3
- **Versioning**: Enabled on all buckets
- **Lifecycle Policy**: Transition to Glacier after 90 days
- **Cross-Region Replication**: Replicate to DR region
- **CMHC Compliance**: Insurance documents retained for 5 years

### 11.4 MLFlow Models
- **Model Versioning**: All models versioned in S3
- **Backup Strategy**: S3 replication to DR region
- **Rollback Procedure**: kubectl set image to previous version tag

---

## 12. Load Balancing & CDN

### 12.1 Ingress Configuration
```yaml
# k8s/ingress.yml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mortgage-ingress
  namespace: mortgage-underwriting-prod
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
    - hosts:
        - api.mortgage-underwriting.ca
      secretName: mortgage-tls
  rules:
    - host: api.mortgage-underwriting.ca
      http:
        paths:
          - path: /api/v1/dpt
            pathType: Prefix
            backend:
              service:
                name: dpt-service
                port:
                  number: 80
          - path: /api/v1/orchestrator
            pathType: Prefix
            backend:
              service:
                name: orchestrator-service
                port:
                  number: 80
```

### 12.2 CloudFront CDN
- **Origin**: S3 bucket for static documents (appraisal reports)
- **Cache Policy**: No caching for PII documents
- **WAF Rules**: Rate limiting, SQL injection protection
- **Geo-Restriction**: Block non-Canadian IPs for admin endpoints

---

## 13. Security Scanning & Compliance Checks

### 13.1 Pre-Deployment Scanning
```bash
# In CI pipeline
uv run pip-audit --desc --format=json > audit-report.json
uv run safety check --json > safety-report.json
uv run bandit -r modules/ -f json > bandit-report.json

# Container scanning
trivy image --severity HIGH,CRITICAL registry.example.com/mortgage/dpt:${GITHUB_SHA}
```

### 13.2 Runtime Compliance
```python
# modules/infrastructure_deployment/services.py: ComplianceChecker
async def runtime_compliance_check():
    """
    1. Verify all services running latest patched images
    2. Check for exposed secrets in environment variables
    3. Validate mTLS certificates expiry > 30 days
    4. Audit GPU allocation for DPT (no unauthorized access)
    5. Log compliance status to deployment_audit_log
    """
```

---

## 14. Environment Variables Template

```bash
# .env.example (PIPEDA compliant - no real secrets)
POSTGRES_USER=mortgage_user
POSTGRES_PASSWORD=<encrypted-via-aws-kms>
REDIS_PASSWORD=<encrypted-via-aws-kms>
MINIO_ACCESS_KEY=<encrypted-via-aws-kms>
MINIO_SECRET_KEY=<encrypted-via-aws-kms>
AWS_ACCESS_KEY_ID=<encrypted-via-aws-kms>
AWS_SECRET_ACCESS_KEY=<encrypted-via-aws-kms>
OSFI_QUALIFYING_RATE=5.25
DPT_GPU_MEMORY=8192
MLFLOW_TRACKING_URI=http://mlflow-registry:5000
```

---

## 15. Implementation Checklist

- [ ] Create `modules/infrastructure_deployment/` with `__init__.py`, `models.py`, `schemas.py`, `services.py`, `routes.py`, `exceptions.py`
- [ ] Implement health check endpoints with 5s timeout and retry logic
- [ ] Create Alembic migration for infrastructure tables
- [ ] Set up Docker Compose with health checks and dependency ordering
- [ ] Write Kubernetes manifests for all 8 services with resource limits
- [ ] Configure GPU node pool and HPA for DPT and orchestrator
- [ ] Integrate MLFlow with S3 artifact storage
- [ ] Implement mTLS between services using cert-manager
- [ ] Set up Prometheus metrics and Grafana dashboards
- [ ] Configure Alertmanager with FINTRAC/OSFI-specific alerts
- [ ] Write GitHub Actions workflow with security scanning
- [ ] Create backup scripts for PostgreSQL (RDS) and Redis
- [ ] Document DR runbook with RTO/RPO targets
- [ ] Implement compliance checker service
- [ ] Add WAF rules for rate limiting and geo-blocking

---

**Regulatory Compliance Summary:**
- **OSFI B-20**: All deployment changes audited, stress test configuration validated
- **FINTRAC**: Immutable `deployment_audit_log` with 5-year retention, hashed user identities
- **CMHC**: S3 lifecycle policies ensure 5-year insurance document retention
- **PIPEDA**: AES-256 encryption for secrets, mTLS in transit, no PII in logs

**Next Steps**: Implement the module following this design, then proceed with integration testing across all 20 modules.