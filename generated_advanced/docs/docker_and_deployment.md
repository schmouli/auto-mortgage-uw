# Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Docker & Deployment Design Plan

**Module Identifier**: `deployment`  
**Error Code Prefix**: `DEPLOY`  
**Design Doc Location**: `docs/design/docker-deployment.md`

---

## 1. Endpoints

### 1.1 System Health & Monitoring Endpoints

**`GET /api/v1/system/health`** (Public, rate-limited)  
Aggregated health check for all services. Returns 200 only if all critical services are healthy.

**Request**: None  
**Response Schema**:
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2024-01-15T14:30:00Z",
  "version": "1.2.3",
  "services": {
    "backend": {"status": "healthy", "response_time_ms": 45},
    "postgres": {"status": "healthy", "active_connections": 12},
    "redis": {"status": "healthy", "memory_usage_percent": 23.5},
    "minio": {"status": "healthy", "disk_available_gb": 450.2},
    "celery": {"status": "healthy", "active_workers": 4, "pending_tasks": 0},
    "dpt": {"status": "healthy", "model_loaded": true},
    "policy": {"status": "healthy", "xml_schemas_valid": true},
    "decision": {"status": "healthy", "ruleset_version": "v2024.1"}
  },
  "regulatory_compliance": {
    "fintrac_retention_enabled": true,
    "encryption_at_rest": true,
    "audit_logging": true
  }
}
```

**Error Responses**:
- `503 Service Unavailable` → `DEPLOY_001` (One or more critical services down)
- `429 Too Many Requests` → `DEPLOY_002` (Health check rate limit exceeded)

---

**`GET /api/v1/system/ready`** (Public)  
Kubernetes-style readiness probe for backend container.

**Response**: `200 OK` with `{"ready": true}` if database and Redis connections are active.

**Error Responses**:
- `503 Service Unavailable` → `DEPLOY_003` (Database or Redis unreachable)

---

**`GET /api/v1/system/live`** (Public)  
Liveness probe for backend container.

**Response**: `200 OK` with `{"alive": true}` if process is running.

---

### 1.2 Orchestrator Service Endpoints

**`GET /api/v1/orchestrator/services/{service_name}/status`** (Authenticated, admin-only)  
Retrieve detailed status of any service.

**Path Parameter**: `service_name` (enum: backend, dpt, policy, decision, etc.)  
**Response Schema**:
```json
{
  "service_name": "dpt",
  "status": "active",
  "last_heartbeat": "2024-01-15T14:29:55Z",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "resource_usage": {
    "cpu_percent": 45.2,
    "memory_mb": 512.3
  }
}
```

**Error Responses**:
- `404 Not Found` → `DEPLOY_004` (Service name invalid)
- `401 Unauthorized` → `SECURITY_001` (Missing/invalid token)
- `403 Forbidden` → `SECURITY_002` (Insufficient privileges)

---

## 2. Models & Database

### 2.1 PostgreSQL Service Configuration

**Image**: `postgres:15-alpine`  
**Custom Configuration** (`postgresql.conf` overrides):
```ini
max_connections = 200
shared_buffers = 512MB
effective_cache_size = 2GB
work_mem = 8MB
maintenance_work_mem = 256MB
checkpoint_timeout = 10min
max_wal_size = 2GB
```

**Volume Mounts**:
- `/var/lib/postgresql/data` → Named volume `postgres_data` (encrypted filesystem)
- `/docker-entrypoint-initdb.d/init-audit.sql` → Custom script to create audit schema

**Environment Variables** (via Docker secrets):
- `POSTGRES_DB=mortgage_uw`
- `POSTGRES_USER=mortgage_uw`
- `POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password`

**Resource Limits**:
- CPU: 2.0 (reserved: 1.0)
- Memory: 4GB (reserved: 2GB)
- Swap: Disabled

---

### 2.2 Redis Service Configuration

**Image**: `redis:7-alpine`  
**Configuration** (`redis.conf`):
```conf
maxmemory 1gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
```

**Volume Mounts**:
- `/data` → Named volume `redis_data` (ephemeral, for Celery broker only)

**Resource Limits**:
- CPU: 0.5 (reserved: 0.25)
- Memory: 1GB (reserved: 512MB)

---

### 2.3 MinIO Object Storage Configuration

**Image**: `minio/minio:RELEASE.2024-01-16T16-07-38Z`  
**Command**: `server /data --console-address ":9001"`  
**Environment Variables** (via Docker secrets):
- `MINIO_ROOT_USER_FILE=/run/secrets/minio_access_key`
- `MINIO_ROOT_PASSWORD_FILE=/run/secrets/minio_secret_key`

**Volume Mounts**:
- `/data` → Named volume `minio_data` (encrypted filesystem)

**Resource Limits**:
- CPU: 1.0 (reserved: 0.5)
- Memory: 1GB (reserved: 512MB)

**Bucket Policy**: On startup, create buckets:
- `mortgage-documents` (versioning enabled, retention 5 years for FINTRAC)
- `audit-logs` (versioning enabled, retention 7 years)

---

### 2.4 Configuration Models (Orchestrator)

**File**: `modules/deployment/models.py`

```python
class ServiceHealth(Base):
    __tablename__ = "service_health"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    service_name: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20))  # healthy, degraded, unhealthy
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[str] = mapped_column(String(20))
    cpu_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    memory_mb: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        Index('idx_service_health_name_time', 'service_name', 'last_heartbeat'),
    )

class DeploymentAuditLog(Base):
    __tablename__ = "deployment_audit_log"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)  # service_start, service_stop, config_change
    service_name: Mapped[str] = mapped_column(String(50), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB)
    ip_address: Mapped[str] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        Index('idx_audit_log_event_time', 'event_type', 'created_at'),
    )
```

---

## 3. Business Logic

### 3.1 Service Orchestration Logic

**Orchestrator Service** (`modules/deployment/services.py`):

```python
class OrchestrationService:
    async def poll_service_health(self, service_name: str) -> ServiceHealthDTO:
        """Poll individual service health endpoint with 5s timeout."""
        # Circuit breaker pattern: 3 failures → open circuit for 60s
        # Retry logic: 3 attempts with exponential backoff
        # mTLS authentication for inter-service communication
        pass
    
    async def aggregate_system_health(self) -> SystemHealthDTO:
        """Aggregate health from all services."""
        # Critical path: postgres, redis, backend must be healthy
        # Non-critical: dpt, policy can be degraded
        # Cache result for 5 seconds to prevent thundering herd
        pass
    
    async def restart_service(self, service_name: str, user_id: UUID) -> None:
        """Gracefully restart a service via Docker API."""
        # Audit log entry mandatory
        # Only allow if no active underwriting transactions
        # Rolling restart: wait for health before next container
        pass
```

### 3.2 Health Check Logic

**Backend Health Check** (`modules/deployment/health_checks.py`):

```python
async def check_database():
    """Verify PostgreSQL connectivity and replication lag < 5s."""
    # Execute SELECT 1
    # Check pg_stat_replication if standby
    # Return latency in ms

async def check_redis():
    """Verify Redis PING response and memory usage < 80%."""
    # Execute PING
    # Check INFO memory

async def check_minio():
    """Verify MinIO bucket accessibility and encryption enabled."""
    # HEAD request on health bucket
    # Verify bucket policy
```

### 3.3 FINTRAC Retention Policy Enforcement

**Celery Beat Schedule** (`modules/deployment/celery_tasks.py`):

```python
@celery_app.task
def enforce_fintrac_retention():
    """Archive documents older than 5 years to cold storage."""
    # Query documents with created_at > 5 years
    # Move from MinIO hot bucket to cold bucket
    # Update audit log with archival location
    # Send notification to compliance team

@celery_app.task
def verify_encryption_at_rest():
    """Daily verification that all PII fields are encrypted."""
    # Scan database for SIN/DOB fields
    # Verify AES-256 encryption markers
    # Alert if plaintext detected
```

---

## 4. Migrations

### 4.1 Alembic Migration Strategy

**Migration Runner Container**: Separate one-shot container `migration-runner`  
**Dockerfile**:
```dockerfile
FROM backend:latest
CMD ["alembic", "upgrade", "head"]
```

**Execution Order**:
1. Start `postgres` service
2. Run `migration-runner` (must exit 0 before backend starts)
3. Start `backend` service

**Rollback Procedure**:
```bash
# Manual rollback via dedicated container
docker run --rm -v postgres_data:/var/lib/postgresql/data \
  mortgage_uw/backend:latest alembic downgrade -1
```

**Migration Audit**: Each migration logs to `deployment_audit_log` table with:
- `event_type`: `migration_applied`
- `details`: `{"revision": "abc123", "down_revision": "def456"}`

### 4.2 Database Initialization

**Init Script** (`/docker-entrypoint-initdb.d/01-audit-schema.sql`):
```sql
-- Create separate schema for audit logs
CREATE SCHEMA IF NOT EXISTS audit;
GRANT ALL ON SCHEMA audit TO mortgage_uw;

-- Create table for FINTRAC transaction records (immutable)
CREATE TABLE audit.fintrac_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL,
    amount CAD_DECIMAL NOT NULL,  -- Custom domain
    transaction_type VARCHAR(50) NOT NULL,
    customer_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL
);
-- NEVER grant UPDATE or DELETE on this table
```

---

## 5. Security & Compliance

### 5.1 Secrets Management

**Docker Secrets** (Production):
```yaml
# secrets.yml (not committed)
secrets:
  postgres_password:
    external: true  # Managed by Docker Swarm/K8s
  encryption_key:
    external: true
  minio_access_key:
    external: true
  minio_secret_key:
    external: true
```

**Development Fallback**: Use `.env.example` with placeholder values, never commit `.env`.

**Secrets Rotation**:
- PostgreSQL: Rotate via `ALTER USER` command, requires 30s downtime window
- Encryption Key: Implement key versioning in `common/security.py`
- MinIO: Rotate via MinIO admin API, update Docker secrets

### 5.2 Network Isolation

**Docker Networks**:
```yaml
networks:
  frontend:
    driver: bridge
    internal: false  # Exposes Nginx only
  backend:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.20.0.0/16
  database:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.21.0.0/16
  storage:
    driver: bridge
    internal: true
```

**Service Attachments**:
- `nginx` → `frontend` network only
- `backend`, `orchestrator` → `frontend`, `backend` networks
- `postgres`, `redis` → `database` network only
- `minio` → `storage` network only
- `dpt`, `policy`, `decision` → `backend` network only

### 5.3 Encryption in Transit

**mTLS Configuration**:
- All inter-service communication uses mTLS
- Certificate authority: HashiCorp Vault PKI
- Certificate rotation: 24h TTL, auto-renewal
- Backend verifies client certs for `/api/v1/*` endpoints

**Nginx TLS**:
- TLS 1.3 only
- Certificates mounted from Docker secrets (`/run/secrets/tls_cert`)
- HSTS enabled: `max-age=31536000; includeSubDomains; preload`

### 5.4 Regulatory Compliance Implementation

**OSFI B-20**:
- Stress test calculations logged to `audit.osfi_calculations` table
- Log format: JSON with `correlation_id`, `gds_ratio`, `tds_ratio`, `qualifying_rate`
- Prometheus metric: `osfi_stress_test_total{outcome="pass|fail"}`

**FINTRAC**:
- All transaction records immutable via PostgreSQL row-level security
- Documents > $10,000 flagged with `high_value=True` in MinIO metadata
- Retention: MinIO lifecycle policy moves to glacier after 5 years
- Audit logs shipped to SIEM in real-time (Splunk/ELK)

**PIPEDA**:
- SIN/DOB encrypted at rest using AES-256-GCM with key rotation
- Database fields marked with `EncryptedType` from `sqlalchemy-utils`
- MinIO bucket encryption enabled: `MINIO_KMS_AUTO_ENCRYPTION=on`
- Data minimization: Document processing service (dpt) redacts PII after extraction

---

## 6. Error Codes & HTTP Responses

### 6.1 Deployment-Specific Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ServiceUnavailableError` | 503 | DEPLOY_001 | "Service {name} is unavailable" | Health check fails 3 consecutive times |
| `HealthCheckTimeoutError` | 504 | DEPLOY_005 | "Health check timeout for {service}" | Polling exceeds 5s threshold |
| `SecretsAccessError` | 500 | DEPLOY_006 | "Failed to access secret: {secret_name}" | Docker secret not found or permission denied |
| `NetworkIsolationError` | 403 | DEPLOY_007 | "Network policy violation: {detail}" | Service tries to access unauthorized network |
| `ConfigurationValidationError` | 422 | DEPLOY_002 | "Invalid configuration: {field}" | Environment variable missing or malformed |
| `MigrationFailedError` | 500 | DEPLOY_008 | "Migration {revision} failed: {detail}" | Alembic upgrade returns non-zero exit code |
| `RetentionPolicyError` | 500 | DEPLOY_009 | "FINTRAC retention enforcement failed" | Archival task fails after 3 retries |

### 6.2 Structured Error Response Format

All deployment errors return:
```json
{
  "detail": "Service postgres is unavailable",
  "error_code": "DEPLOY_001",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T14:30:00Z",
  "service": "orchestrator"
}
```

### 6.3 Retry and Circuit Breaker Policies

| Service | Max Retries | Circuit Breaker Threshold | Recovery Timeout |
|---------|-------------|---------------------------|------------------|
| postgres | 3 | 5 failures in 60s | 120s |
| redis | 3 | 10 failures in 60s | 30s |
| minio | 3 | 5 failures in 60s | 60s |
| dpt | 2 | 3 failures in 120s | 180s |
| policy | 2 | 3 failures in 120s | 180s |
| decision | 2 | 3 failures in 120s | 180s |

---

## 7. Dockerfile Specifications

### 7.1 Backend Dockerfile (`backend/Dockerfile`)

```dockerfile
# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install uv package manager
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.12-slim as runtime

# Create non-root user
RUN groupadd -r mortgage && useradd -r -g mortgage mortgage

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=mortgage:mortgage . /app

WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7000/api/v1/system/live')"

USER mortgage

# Run migrations then start app
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 7000"]
```

### 7.2 Frontend Dockerfile (`frontend/Dockerfile`)

```dockerfile
# Build stage
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# Runtime stage
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built app
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

### 7.3 Document Processing Transformer (DPT) Dockerfile

```dockerfile
FROM python:3.12-slim as builder

WORKDIR /app

# Install donut dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install donut-python transformers torch --no-cache-dir

COPY requirements.txt .
RUN pip install -r requirements.txt

# Runtime stage
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . /app
WORKDIR /app

HEALTHCHECK --interval=60s --timeout=10s --retries=2 \
    CMD python health_check.py

CMD ["python", "dpt_service.py"]
```

---

## 8. Docker Compose Configuration

### 8.1 Core Services (`docker-compose.core.yml`)

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: mortgage_uw
      POSTGRES_USER: mortgage_uw
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    networks:
      - database
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

  redis:
    image: redis:7-alpine
    command: redis-server /etc/redis.conf
    volumes:
      - ./redis.conf:/etc/redis.conf
      - redis_data:/data
    networks:
      - database
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 1G

  minio:
    image: minio/minio:RELEASE.2024-01-16T16-07-38Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER_FILE: /run/secrets/minio_access_key
      MINIO_ROOT_PASSWORD_FILE: /run/secrets/minio_secret_key
      MINIO_KMS_AUTO_ENCRYPTION: "on"
    secrets:
      - minio_access_key
      - minio_secret_key
    volumes:
      - minio_data:/data
    networks:
      - storage
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  minio_data:
    driver: local

networks:
  database:
    internal: true
  storage:
    internal: true

secrets:
  postgres_password:
    external: true
  minio_access_key:
    external: true
  minio_secret_key:
    external: true
```

### 8.2 Application Services (`docker-compose.app.yml`)

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://mortgage_uw:@postgres:5432/mortgage_uw
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY_FILE: /run/secrets/secret_key
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
      ENVIRONMENT: production
    secrets:
      - secret_key
      - encryption_key
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - frontend
      - backend
      - database
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.5'
          memory: 2G
        reservations:
          cpus: '0.75'
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - backend
      - frontend
    networks:
      - frontend
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  orchestrator:
    build:
      context: ./orchestrator
      dockerfile: Dockerfile
    environment:
      SERVICES_CONFIG_FILE: /run/secrets/services_config
    secrets:
      - services_config
    networks:
      - backend
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

---

## 9. Log Aggregation & Observability

### 9.1 Logging Configuration

**structlog Configuration** (`common/logging.py`):
```python
import structlog
from opentelemetry import trace

def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Add correlation ID from OpenTelemetry
            lambda _, __, event_dict: {
                **event_dict,
                "correlation_id": trace.get_current_span().get_span_context().trace_id,
                "service": "backend",
                "environment": settings.ENVIRONMENT,
            },
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

### 9.2 Log Shipping

**Vector Configuration** (`vector.toml`):
```toml
[sources.backend_logs]
type = "docker_logs"
include_labels = ["com.docker.compose.service=backend"]

[transforms.parse_json]
type = "remap"
inputs = ["backend_logs"]
source = """
. = parse_json(.message) ?? {}
"""

[sinks.splunk]
type = "splunk_hec"
inputs = ["parse_json"]
endpoint = "${SPLUNK_HEC_ENDPOINT}"
token = "${SPLUNK_HEC_TOKEN}"
encoding.codec = "json"
healthcheck.enabled = true
```

### 9.3 Prometheus Metrics

**Metrics Endpoint** (`/metrics`):
```
# HELP mortgage_gds_ratio Gross Debt Service ratio
# TYPE mortgage_gds_ratio gauge
mortgage_gds_ratio{application_id="123", outcome="pass"} 0.35

# HELP mortgage_tds_ratio Total Debt Service ratio
# TYPE mortgage_tds_ratio gauge
mortgage_tds_ratio{application_id="123", outcome="pass"} 0.42

# HELP service_health_status Service health (1=healthy, 0=unhealthy)
# TYPE service_health_status gauge
service_health_status{service="postgres"} 1
service_health_status{service="redis"} 1
```

---

## 10. Resource Limits & Autoscaling

### 10.1 Per-Service Resource Matrix

| Service | CPU Limit | CPU Reserve | Memory Limit | Memory Reserve | Replica Count |
|---------|-----------|-------------|--------------|----------------|---------------|
| backend | 1.5 | 0.75 | 2GB | 1GB | 3-10 (HPA) |
| frontend | 0.5 | 0.25 | 512MB | 256MB | 2-5 (HPA) |
| postgres | 2.0 | 1.0 | 4GB | 2GB | 1 (2 with Patroni) |
| redis | 0.5 | 0.25 | 1GB | 512MB | 1 (3 with Sentinel) |
| minio | 1.0 | 0.5 | 1GB | 512MB | 4 (distributed) |
| celery worker | 2.0 | 1.0 | 3GB | 1.5GB | 2-8 (HPA) |
| nginx | 0.5 | 0.25 | 512MB | 256MB | 2 |

### 10.2 Horizontal Pod Autoscaler Rules

**Backend HPA**:
```yaml
apiVersion: autoscaling/v2
spec:
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
        averageValue: "10"
```

---

## 11. Volume Mount Strategy

### 11.1 Persistent Volumes

| Volume | Driver | Backup Frequency | Encryption | Snapshots |
|--------|--------|------------------|------------|-----------|
| postgres_data | local (prod: CSI) | Daily at 02:00 UTC | LUKS + AES-256 | 7-day retention |
| minio_data | local (prod: CSI) | Daily at 03:00 UTC | MinIO SSE-S3 | Versioning enabled |
| audit_logs | local (prod: CSI) | Real-time ship | LUKS + AES-256 | 30-day retention |
| uploads_temp | tmpfs (ephemeral) | N/A | N/A | N/A |

### 11.2 Backup & Recovery

**PostgreSQL**:
```bash
# Daily pg_dump to MinIO
pg_dump -Fc mortgage_uw | aws s3 cp - s3://mortgage-backups/postgres/$(date +%Y-%m-%d).dump

# Point-in-time recovery enabled via WAL archiving to MinIO
archive_command = 'aws s3 cp %p s3://mortgage-backups/wal/%f'
```

**MinIO**:
```bash
# Cross-region replication to DR site
mc replicate add minio/mortgage-documents --remote-bucket dr-site
```

---

## 12. Secrets Management Implementation

### 12.1 Docker Compose Override for Secrets

**`docker-compose.secrets.yml`** (Production only):
```yaml
secrets:
  postgres_password:
    file: /run/secrets/postgres_password
  encryption_key:
    file: /run/secrets/encryption_key
  secret_key:
    file: /run/secrets/secret_key
  minio_access_key:
    file: /run/secrets/minio_access_key
  minio_secret_key:
    file: /run/secrets/minio_secret_key
  services_config:
    file: /run/secrets/services_config

# Production overlay removes all environment variable definitions
```

### 12.2 Vault Integration (Future-Ready)

**Vault Agent Sidecar** (Kubernetes):
```yaml
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "mortgage-app"
  vault.hashicorp.com/agent-inject-secret-database: "secret/data/mortgage/db"
  vault.hashicorp.com/agent-inject-template-database: |
    {{ with secret "secret/data/mortgage/db" }}
    DATABASE_URL=postgresql://mortgage_uw:{{ .Data.data.password }}@postgres:5432/mortgage_uw
    {{ end }}
```

---

## 13. WARNING: Missing Critical Details

The following deployment aspects require additional specification before implementation:

1. **Network Policies**: Exact CIDR ranges and firewall rules for production environment
2. **Load Balancer**: Configuration for distributing traffic across nginx replicas
3. **Disaster Recovery**: RTO/RPO targets and failover procedures
4. **Certificate Management**: ACME provider configuration for TLS certificates
5. **Monitoring Alerting**: PagerDuty/Opsgenie integration thresholds
6. **Cost Optimization**: Spot instance configuration for non-critical services
7. **Compliance Scanning**: Trivy/Aqua scan schedule for container images

**Recommendation**: Address these in a follow-up infrastructure architecture review before production deployment.