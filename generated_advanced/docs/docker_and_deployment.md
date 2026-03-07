# Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Docker & Deployment Design Plan

**Module Name:** `deployment`  
**Design Doc:** `docs/design/docker-deployment.md`  
**Scope:** Container orchestration, service discovery, secrets management, and production deployment configuration for the Canadian Mortgage Underwriting System.

---

## 1. Endpoints

### 1.1 Health & Monitoring Endpoints

All services expose health endpoints for Docker HEALTHCHECK and load balancer integration.

| Service | Method | Path | Auth | Purpose |
|---------|--------|------|------|---------|
| backend | GET | `/api/v1/health` | Public | Liveness/readiness probe |
| backend | GET | `/api/v1/health/dependencies` | Public | Checks DB, Redis, MinIO |
| orchestrator | GET | `/api/v1/orchestrator/health` | Public | Celery worker status |
| dpt | GET | `/api/v1/dpt/health` | Public | Document processor status |
| policy | GET | `/api/v1/policy/health` | Public | XML policy service status |
| decision | GET | `/api/v1/decision/health` | Public | Underwriting engine status |
| nginx | GET | `/nginx-health` | Public | Reverse proxy status |

#### 1.1.1 Backend Health Response Schema
```python
class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    uptime_seconds: int
    checks: dict[str, bool]  # db: true, redis: true, minio: true
    timestamp: datetime
```

#### 1.1.2 Dependencies Health Response
```python
class DependencyHealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    database: ComponentHealth
    redis: ComponentHealth
    minio: ComponentHealth

class ComponentHealth(BaseModel):
    status: Literal["up", "down"]
    latency_ms: float | None
    last_error: str | None
```

**Error Responses:**
- `503 Service Unavailable` → `DEPLOYMENT_001`: "Service dependency unavailable: {name}"
- `500 Internal Server Error` → `DEPLOYMENT_002`: "Health check failed: {detail}"

---

### 1.2 Orchestrator Management Endpoints

| Method | Path | Auth | Request Body | Response |
|--------|------|------|--------------|----------|
| POST | `/api/v1/orchestrator/tasks/retry` | Admin | `{"task_id": str, "max_retries": int}` | `{"status": "queued"}` |
| GET | `/api/v1/orchestrator/tasks/{task_id}` | Admin | - | `TaskStatusResponse` |
| POST | `/api/v1/orchestrator/services/resync` | Admin | `{"service": str}` | `{"status": "resync_queued"}` |

**TaskStatusResponse Schema:**
```python
class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["pending", "started", "success", "failure", "retry"]
    result: dict | None
    traceback: str | None
    created_at: datetime
    completed_at: datetime | None
```

---

## 2. Models & Database

### 2.1 Deployment Audit Log Model
**Table:** `deployment_audit_log`  
**Purpose:** Immutable audit trail of all deployments and service restarts (FINTRAC 5-year retention)

```python
class DeploymentAuditLog(Base):
    __tablename__ = "deployment_audit_log"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "service_start", "service_stop", "deploy"
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # dev/staging/prod
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failure
    error_message: Mapped[str | None] = mapped_column(Text)
    
    # Audit fields (mandatory)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)  # CI/CD user or systemd
    
    # Indexes
    __table_args__ = (
        Index("idx_deployment_log_service_env", "service_name", "environment"),
        Index("idx_deployment_log_created_at", "created_at"),
    )
```

### 2.2 Service Configuration Version Model
**Table:** `service_config_version`  
**Purpose:** Track configuration changes for compliance audits

```python
class ServiceConfigVersion(Base):
    __tablename__ = "service_config_version"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # SHA256
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Full config (no secrets)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    deployed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("idx_config_version_service", "service_name", "deployed_at"),
    )
```

---

## 3. Business Logic

### 3.1 Health Check Orchestration
```python
# services.py
async def perform_health_checks() -> DependencyHealthResponse:
    """
    Sequentially checks critical dependencies with 5s timeout each.
    Logs results with correlation_id for auditability.
    """
    # Check DB: SELECT 1
    # Check Redis: PING
    # Check MinIO: list_buckets()
    # Returns degraded if any check fails latency SLA (>500ms)
```

### 3.2 Secrets Management Logic
```python
# Must NOT use os.environ.get() in handlers per conventions
class SecretsManager:
    @staticmethod
    async def get_encryption_key() -> str:
        """Fetches from Vault or K8s secret; caches in memory with 5min TTL"""
    
    @staticmethod
    async def rotate_minio_credentials() -> tuple[str, str]:
        """Triggers credential rotation via Vault dynamic secrets"""
```

### 3.3 Log Aggregation Strategy
- All services emit JSON logs via structlog to stdout
- Fluentd sidecar containers collect and forward to centralized Loki/ELK
- Correlation ID injected via OpenTelemetry headers (`x-correlation-id`)
- FINTRAC compliance: Logs retained for 5 years in immutable S3 bucket with WORM policy

### 3.4 Resource Limit Enforcement
```yaml
# Per-service resource quotas
backend:    {cpu: "2", memory: "4Gi", replicas: 3}
postgres:   {cpu: "4", memory: "8Gi", storage: "500Gi"}
redis:      {cpu: "1", memory: "2Gi"}
celery:     {cpu: "2", memory: "3Gi", replicas: 2}
nginx:      {cpu: "1", memory: "1Gi"}
minio:      {cpu: "2", memory: "4Gi", storage: "1Ti"}
dpt:        {cpu: "4", memory: "8Gi", replicas: 2}  # GPU optional
policy:     {cpu: "1", memory: "1Gi", replicas: 2}
decision:   {cpu: "2", memory: "3Gi", replicas: 2}
orchestrator: {cpu: "1", memory: "2Gi", replicas: 1}
```

---

## 4. Migrations

### 4.1 New Tables
```sql
-- migration: 001_create_deployment_audit_log
CREATE TABLE deployment_audit_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    environment VARCHAR(20) NOT NULL,
    host VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL
);
CREATE INDEX idx_deployment_log_service_env ON deployment_audit_log(service_name, environment);
CREATE INDEX idx_deployment_log_created_at ON deployment_audit_log(created_at);

-- migration: 002_create_service_config_version
CREATE TABLE service_config_version (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    config_hash VARCHAR(64) NOT NULL UNIQUE,
    config_snapshot JSONB NOT NULL,
    deployed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deployed_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_config_version_service ON service_config_version(service_name, deployed_at);
```

### 4.2 Existing Tables Modifications
- Add `correlation_id` column to all audit log tables (FINTRAC traceability)

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Compliance
- **Stress Test Calculation:** Deployed as immutable versioned service (`decision` service). All rate changes trigger new config version audit.
- **Audit Logging:** Every GDS/TDS calculation logged with `correlation_id`, retained 5 years via centralized log aggregator.
- **Service Isolation:** `decision` service runs in separate network namespace with mTLS-only communication.

### 5.2 FINTRAC Compliance
- **Immutable Audit Trail:** `deployment_audit_log` table is INSERT-only. No UPDATE/DELETE privileges granted to application user.
- **5-Year Retention:** PostgreSQL partitions by `created_at` month; automated S3 archival after 1 year.
- **Transaction Flagging:** `celery-beat` scheduler runs daily job to flag transactions >CAD $10,000; logs written to `fintrac_reporting` topic with 5-year retention.

### 5.3 PIPEDA Data Handling
- **Encryption at Rest:** All volumes mounted with LUKS encryption. PostgreSQL uses `pgcrypto` for PII fields.
- **Secrets Management:** `ENCRYPTION_KEY` never stored in `.env`. Must be injected via:
  - **Development:** Docker secret file (`/run/secrets/encryption_key`)
  - **Production:** HashiCorp Vault with dynamic credentials
- **Network Isolation:** `backend`, `postgres`, `minio` services placed in `sensitive-data` network; `frontend`, `nginx` in `public` network.

### 5.4 Authentication & Authorization
| Service | Public | Authenticated | Admin-only | mTLS Required |
|---------|--------|---------------|------------|---------------|
| backend API | - | All endpoints | - | Yes (service-to-service) |
| orchestrator | - | - | All endpoints | Yes |
| dpt | - | - | - | Yes |
| policy | - | - | - | Yes |
| decision | - | - | - | Yes |
| nginx | All | - | - | No |
| minio | - | - | Console only | Yes |

---

## 6. Error Codes & HTTP Responses

### 6.1 Deployment Module Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `ServiceHealthError` | 503 | `DEPLOYMENT_001` | "Service dependency unavailable: {name}" | DB/Redis/MinIO down |
| `HealthCheckFailedError` | 500 | `DEPLOYMENT_002` | "Health check failed: {detail}" | Uncaught exception |
| `SecretsUnavailableError` | 500 | `DEPLOYMENT_003` | "Secrets manager unreachable: {detail}" | Vault/K8s timeout |
| `ConfigValidationError` | 422 | `DEPLOYMENT_004` | "Invalid configuration: {field} {reason}" | Missing required env var |
| `ResourceLimitExceededError` | 409 | `DEPLOYMENT_005` | "Resource quota exceeded: {resource}" | OOM, CPU throttle |
| `NetworkIsolationError` | 403 | `DEPLOYMENT_006` | "Network policy violation: {detail}" | Unauthorized inter-service call |

### 6.2 Global Error Handler
```python
# common/exceptions.py
class DeploymentException(AppException):
    """Base for all deployment-related errors"""
    def __init__(self, error_code: str, message: str, detail: dict | None = None):
        self.error_code = error_code
        self.message = message
        self.detail = detail
        super().__init__(self.message)

# Returns JSON: {"detail": "...", "error_code": "DEPLOYMENT_001"}
```

---

## 7. Dockerfile Specifications (Multi-Stage)

### 7.1 Backend Dockerfile
```dockerfile
# syntax=docker/dockerfile:1.4
FROM python:3.12-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system --no-cache

FROM python:3.12-slim as runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*

RUN groupadd -r mortgage && useradd -r -g mortgage mortgage
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=mortgage:mortgage . .

USER mortgage
EXPOSE 7000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7000/api/v1/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000", "--workers", "4"]
```

### 7.2 Frontend Dockerfile
```dockerfile
FROM node:20-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine as runtime
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/nginx-health || exit 1
EXPOSE 3000
```

### 7.3 Service Dockerfiles (dpt/policy/decision/orchestrator)
Follow same pattern: `builder` stage installs deps, `runtime` stage uses non-root user, includes health checks on port 8000-9000 range.

---

## 8. Docker Compose Overrides

### 8.1 `docker-compose.override.yml` (Development)
```yaml
services:
  backend:
    volumes:
      - ./modules:/app/modules:ro
      - ./common:/app/common:ro
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=debug
  
  postgres:
    ports:
      - "5432:5432"  # Expose for local debugging
  
  minio:
    ports:
      - "9001:9000"  # Console
      - "9002:9001"  # API
```

### 8.2 `docker-compose.prod.yml` (Production)
```yaml
services:
  backend:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    secrets:
      - encryption_key
      - database_url
  
secrets:
  encryption_key:
    external: true
  database_url:
    external: true
```

---

## 9. Volume Mount Strategy

| Service | Volume | Path | Purpose | Backup Required |
|---------|--------|------|---------|-----------------|
| postgres | `pg_data` | `/var/lib/postgresql/data` | Database persistence | Daily + WAL |
| minio | `minio_data` | `/data` | Document storage | Continuous (S3 sync) |
| backend | `uploads_temp` | `/uploads` | Temporary file processing | No (ephemeral) |
| redis | `redis_data` | `/data` | Session cache | No (TTL data) |

**Security:** All volumes use `driver: local` with encryption enabled. In production, use CSI driver with KMS integration.

---

## 10. Network Isolation

```yaml
networks:
  public:
    driver: bridge
    internal: false
  sensitive-data:
    driver: bridge
    internal: true  # No internet access
  policy-net:
    driver: bridge
    internal: true
```

**Service Attachments:**
- `public`: nginx, frontend
- `sensitive-data`: backend, postgres, redis, minio
- `policy-net`: policy, decision, dpt, orchestrator

**mTLS:** Inter-service communication enforced via Linkerd or Istio sidecars. Certificates rotated every 24h.

---

## 11. Secrets Management (Production)

**DO NOT commit `.env` file.** Use one of:

1. **Docker Swarm Secrets** (Simple):
   ```bash
   echo "my-encryption-key" | docker secret create encryption_key -
   ```

2. **HashiCorp Vault** (Recommended):
   - AppRole authentication for each service
   - Dynamic PostgreSQL credentials (1h TTL)
   - KV v2 for static secrets (ENCRYPTION_KEY, MINIO creds)
   - Automated rotation via `celery-beat`

3. **Kubernetes Secrets + External Secrets Operator**:
   - Secrets stored in AWS Secrets Manager / Azure Key Vault
   - Synced to K8s secrets automatically

**Development:** Use `.env.example` (committed) + `.env` (gitignored) with dummy values.

---

## 12. Observability

### 12.1 Logging
- **Format:** JSON via structlog
- **Fields:** `timestamp`, `level`, `event`, `correlation_id`, `service`, `environment`
- **PIPEDA Compliance:** `correlation_id` only logged; no SIN/DOB/income in logs
- **Retention:** 30 days hot in Loki, 5 years cold in S3 (FINTRAC)

### 12.2 Metrics
- **Endpoint:** `/metrics` on each service (Prometheus client)
- **Key Metrics:**
  - `gds_tds_calculation_duration_seconds` (histogram)
  - `application_rejection_total` (counter by reason)
  - `service_dependency_health` (gauge)
  - `pii_encryption_failures_total` (counter)

### 12.3 Tracing
- **OpenTelemetry:** Traces exported to Jaeger/Tempo
- **Sampling:** 100% for decision service, 10% for others
- **PIPEDA:** Traces exclude PII attributes

---

## 13. CI/CD Integration

### 13.1 Pre-Deploy Checks (GitHub Actions)
```yaml
- name: Security Scan
  run: |
    uv run pip-audit
    docker scan mortgage_uw/backend:latest

- name: Compliance Check
  run: |
    python scripts/validate_env_vars.py  # Ensures no secrets in .env
    python scripts/validate_audit_fields.py  # All models have created_at/updated_at
```

### 13.2 Deployment Workflow
1. Build images with `git SHA` tag
2. Run migration job (`alembic upgrade head`)
3. Rolling update with health check verification
4. Record deployment event in `deployment_audit_log`

---

## 14. Disaster Recovery

- **RTO:** 1 hour (decision service), 4 hours (full system)
- **RPO:** 5 minutes (database), 1 hour (documents)
- **Backup Strategy:**
  - PostgreSQL: Continuous WAL archiving + daily pg_dump to MinIO
  - MinIO: Server-side replication to DR region
  - Config: Versioned in Git + Vault

---

**WARNING:** This design assumes production deployment on either Docker Swarm or Kubernetes. For bare Docker Compose, reduce replica counts and omit mTLS/network policies.