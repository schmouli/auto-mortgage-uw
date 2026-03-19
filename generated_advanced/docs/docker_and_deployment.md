# Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Docker & Deployment Module Design Plan

**Module Identifier:** `DEPLOYMENT`  
**Design Document:** `docs/design/docker-deployment.md`  
**Version:** 1.0  
**Regulatory Coverage:** FINTRAC (log retention), PIPEDA (secrets management), OSFI B-20 (service availability)

---

## 1. Endpoints

### 1.1 Core Health & Observability Endpoints

| Service | Method | Path | Purpose | Auth |
|---------|--------|------|---------|------|
| Backend | `GET` | `/api/v1/health` | Liveness probe (200 if responsive) | Public |
| Backend | `GET` | `/api/v1/ready` | Readiness probe (200 if DB/Redis connected) | Public |
| Backend | `GET` | `/metrics` | Prometheus metrics | Public (internal network) |
| Orchestrator | `GET` | `/api/v1/orchestrator/health` | Service mesh health aggregation | Authenticated |
| Orchestrator | `GET` | `/api/v1/orchestrator/services/{service_name}/health` | Individual service health check | Authenticated |
| Nginx | `GET` | `/health` | Reverse proxy health (returns 204) | Public |

### 1.2 Orchestrator API Endpoints

**`GET /api/v1/orchestrator/services/health`**
- **Request:** None
- **Response (200):**
  ```json
  {
    "status": "healthy|degraded|unhealthy",
    "timestamp": "2024-01-15T14:30:00Z",
    "services": {
      "backend": {"status": "healthy", "response_time_ms": 45},
      "dpt": {"status": "healthy", "response_time_ms": 120},
      "policy": {"status": "unhealthy", "error_code": "DEPLOYMENT_004"}
    }
  }
  ```
- **Error Responses:**
  - `503 Service Unavailable` + `{"detail": "Orchestrator unreachable", "error_code": "DEPLOYMENT_001"}`

**`POST /api/v1/orchestrator/services/{service_name}/restart`**
- **Request:** `{"force": false}`
- **Response (202):** `{"status": "restart_initiated", "service": "dpt"}`
- **Auth:** Admin-only (JWT scope `deployment:admin`)
- **Error Responses:**
  - `403 Forbidden` + `{"detail": "Insufficient permissions", "error_code": "DEPLOYMENT_002"}`
  - `404 Not Found` + `{"detail": "Service not found", "error_code": "DEPLOYMENT_003"}`

---

## 2. Models & Database

### 2.1 ORM Models

**No new SQLAlchemy models required** for the deployment module itself. The module operates at the infrastructure layer. However, the following audit considerations apply to **existing models** across all modules:

| Model | Audit Field | FINTRAC Requirement | Implementation |
|-------|-------------|---------------------|----------------|
| All tables | `created_at` | 5-year retention | `sa.DateTime(timezone=True), nullable=False, index=True` |
| All tables | `created_by` | Immutable audit trail | `sa.String(255), nullable=False` (user UUID) |
| All tables | `updated_at` | Optional update tracking | `sa.DateTime(timezone=True), onupdate=func.now()` **BUT** FINTRAC-critical tables must be **append-only** |

**Note:** Tables storing FINTRAC-reportable transactions (e.g., `transactions`, `identity_verifications`) must be **append-only** with no `UPDATE` or `DELETE` operations. Use `INSERT` only with versioning.

### 2.2 Optional Service Registry (If Dynamic Discovery Required)

```python
# Optional: Only if not using Docker DNS or service mesh
class ServiceRegistry(Base):
    __tablename__ = "service_registry"
    
    id = sa.Column(UUID, primary_key=True)
    service_name = sa.Column(sa.String(100), nullable=False, unique=True, index=True)
    endpoint_url = sa.Column(sa.String(500), nullable=False)
    health_check_path = sa.Column(sa.String(200), nullable=False)
    is_active = sa.Column(sa.Boolean, default=True, index=True)
    last_heartbeat = sa.Column(sa.DateTime(timezone=True))
    # Audit fields
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = sa.Column(sa.String(255), nullable=False)
```

---

## 3. Business Logic

### 3.1 Health Check Algorithm

```python
# Pseudocode for /api/v1/ready endpoint
async def readiness_check():
    checks = {
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
        "minio": await check_minio_connection(),
        "encryption_key_valid": validate_encryption_key()
    }
    
    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        raise ServiceUnavailableError(
            detail="Dependency not ready", 
            error_code="DEPLOYMENT_005",
            failed_checks={k: v for k, v in checks.items() if not v}
        )
```

### 3.2 Circuit Breaker Logic for Microservices

| Service | Failure Threshold | Timeout | Recovery Strategy | FINTRAC Impact |
|---------|------------------|---------|-------------------|----------------|
| dpt | 5 failures in 60s | 30s | Exponential backoff 2ⁿ seconds | Document processing delays must be logged |
| policy | 3 failures in 30s | 10s | Immediate retry ×1, then backoff | Policy decisions must not be cached if they affect B-20 calculations |
| decision | 2 failures in 10s | 5s | Fast failover to standby instance | GDS/TDS calculations must have 99.9% availability (OSFI requirement) |
| minio | 3 failures in 60s | 15s | Retry with secondary endpoint | Document storage failures trigger FINTRAC retention alerts |

### 3.3 Graceful Shutdown Sequence

1. **SIGTERM received** → Set `is_terminating=True`
2. **Stop accepting new requests** → Return `503 Service Unavailable` with `Retry-After: 30`
3. **Drain active requests** → Wait up to 30s for in-flight requests to complete
4. **Close connections** → DB, Redis, MinIO connections closed
5. **Log termination** → `structlog` event `service_shutdown` with `correlation_id` and `active_requests_count`
6. **Exit** → `sys.exit(0)`

**FINTRAC Compliance:** All in-flight FINTRAC-reportable transactions must be committed before shutdown. Use `asyncio.shield()` for critical writes.

---

## 4. Migrations

### 4.1 Database Migrations

**No new Alembic migrations** required for this module. However, the following **must be enforced** on existing migrations:

- **Append-only constraint:** Add `postgresql_using='INSERT_ONLY'` check constraint on FINTRAC-critical tables
- **Index optimization:** Create composite indexes for health check queries:
  ```sql
  CREATE INDEX idx_transactions_created_at_status 
  ON transactions (created_at, status) 
  WHERE created_at >= NOW() - INTERVAL '5 years';  -- FINTRAC retention window
  ```

### 4.2 Infrastructure "Migrations"

| Change Type | Description | Rollback Strategy |
|-------------|-------------|-------------------|
| Network policy | Isolate `postgres` from public ingress | Delete policy |
| Secret rotation | Rotate `ENCRYPTION_KEY` using key hierarchy | Use previous key version for decryption |
| Volume expansion | Increase MinIO volume from 100GB → 500GB | Snapshot-based rollback |

---

## 5. Security & Compliance

### 5.1 PIPEDA: Secrets Management

**Strictly forbidden:** Storing `ENCRYPTION_KEY`, `SECRET_KEY`, `MINIO_SECRET_KEY` in `.env` files or Docker images.

**Required Implementation:**
- **Development:** Use `docker-compose secrets` (bind-mount from host with 0600 permissions)
- **Production:** Use HashiCorp Vault or AWS Secrets Manager with dynamic credentials
- **Key Rotation:** 
  - `ENCRYPTION_KEY`: Versioned keys, support decryption with N-1 version
  - `SECRET_KEY`: Rotate every 90 days, force re-authentication
  - Database credentials: Rotate every 30 days, use connection pooling with credential refresh

**PIPEDA Audit:** Log all secret access with `correlation_id`, `user_id`, `timestamp` (never log the secret value).

### 5.2 FINTRAC: Log Retention & Immutability

| Log Type | Retention | Storage | Immutability |
|----------|-----------|---------|--------------|
| Application logs (JSON) | 5 years | MinIO/S3 with WORM | Object lock, legal hold |
| Transaction audit trails | 5 years | PostgreSQL (append-only) | Row-level security, no UPDATE/DELETE |
| Identity verification logs | 5 years | Encrypted in MinIO | SHA-256 checksums, verify on read |
| Access logs (Nginx) | 2 years | Local volume (compressed) | Logrotate with `copytruncate` |

**Log Format (structlog):**
```json
{
  "timestamp": "2024-01-15T14:30:00Z",
  "level": "info",
  "correlation_id": "uuid-1234",
  "service": "backend",
  "event": "fintrac_transaction_logged",
  "transaction_id": "sha256_hash",
  "user_id": "user_uuid",
  "amount_cad": "15000.00"
}
```
**Never log:** `sin`, `dob`, `income`, `banking_data`, `encryption_key`

### 5.3 OSFI B-20: Service Availability Requirements

- **Uptime SLA:** 99.9% for GDS/TDS calculation endpoints (`/api/v1/underwriting/calculate`)
- **Stress Test Service:** `decision` service must be **highly available** (2+ replicas, anti-affinity rules)
- **Disaster Recovery:** RTO < 1 hour, RPO < 5 minutes for underwriting decisions
- **Monitoring:** Alert if `decision` service latency > 500ms or error rate > 0.1%

### 5.4 Network Isolation

```yaml
# Docker Compose network topology
networks:
  frontend:
    driver: bridge
    internal: false  # Exposes Nginx only
  backend:
    driver: bridge
    internal: true   # No internet access
  data:
    driver: bridge
    internal: true   # PostgreSQL, MinIO, Redis only
  ml:
    driver: bridge
    internal: true   # dpt, decision services
```

**Access Matrix:**
| Service | frontend | backend | data | ml | Internet |
|---------|----------|---------|------|----|----------|
| Nginx | ✓ | ✓ | ✗ | ✗ | ✓ (443 only) |
| Backend | ✗ | ✓ | ✓ | ✓ | ✗ |
| PostgreSQL | ✗ | ✗ | ✓ | ✗ | ✗ |
| dpt | ✗ | ✗ | ✗ | ✓ | ✗ |

---

## 6. Error Codes & HTTP Responses

### 6.1 Deployment-Specific Exceptions

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger |
|-----------------|-------------|------------|-----------------|---------|
| `ServiceUnavailableError` | 503 | DEPLOYMENT_001 | "Service {name} unavailable: {reason}" | Health check failure |
| `DeploymentPermissionError` | 403 | DEPLOYMENT_002 | "Admin privileges required for {action}" | Non-admin accessing restart endpoint |
| `ServiceNotFoundError` | 404 | DEPLOYMENT_003 | "Service {name} not found in registry" | Invalid service name in orchestrator |
| `HealthCheckFailedError` | 502 | DEPLOYMENT_004 | "Health check failed for {service}: {detail}" | Circuit breaker open |
| `DependencyNotReadyError` | 503 | DEPLOYMENT_005 | "Dependency {name} not ready" | DB/Redis unreachable |
| `SecretRotationError` | 500 | DEPLOYMENT_006 | "Secret rotation failed: {detail}" | Vault connectivity issue |

### 6.2 Structured Error Response Format

All errors must return:
```json
{
  "detail": "Human-readable message",
  "error_code": "DEPLOYMENT_XXX",
  "correlation_id": "uuid-1234",
  "timestamp": "2024-01-15T14:30:00Z",
  "service": "backend"
}
```

### 6.3 Retry-After Headers

For 503 errors, include:
```
Retry-After: 30
X-Service-Status: degraded
X-Fintrac-Impact: "Transaction logging delayed but not blocked"
```

---

## 7. Dockerfile Specifications (Multi-Stage)

### 7.1 Backend Dockerfile (`backend/Dockerfile`)

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system --no-cache

# Stage 2: Runtime
FROM python:3.12-slim as runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
EXPOSE 7000
USER 1000:1000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7000/api/v1/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000"]
```

**Image size target:** < 200MB

### 7.2 Frontend Dockerfile (`frontend/Dockerfile`)

```dockerfile
# Stage 1: Build
FROM node:20-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=2s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1
```

### 7.3 Decision Service Dockerfile (`services/decision/Dockerfile`)

```dockerfile
FROM python:3.12-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential
COPY requirements-decision.txt ./
RUN pip install --user -r requirements-decision.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY ./services/decision /app
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8001
HEALTHCHECK CMD python -c "import requests; requests.get('http://localhost:8001/health').raise_for_status()"
CMD ["python", "main.py"]
```

**All service images must be scanned with `uv run pip-audit` and `trivy` before deployment.**

---

## 8. Resource Limits & Volume Strategy

### 8.1 Kubernetes-Style Resource Requests/Limits (for Docker Compose equivalent)

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Notes |
|---------|-------------|-----------|----------------|--------------|-------|
| backend | 500m | 1000m | 512Mi | 1Gi | Gunicorn workers = 2×CPU cores |
| postgres | 1000m | 2000m | 2Gi | 4Gi | Critical for FINTRAC retention |
| redis | 200m | 500m | 256Mi | 512Mi | Persistence enabled |
| decision | 1000m | 2000m | 1Gi | 2Gi | OSFI B-20 SLA requirement |
| dpt | 2000m | 4000m | 4Gi | 8Gi | GPU optional (nvidia.com/gpu: 1) |
| minio | 500m | 1000m | 1Gi | 2Gi | WORM storage for FINTRAC |

### 8.2 Volume Mounts

```yaml
volumes:
  postgres_data:
    driver: local
  minio_data:
    driver: local
  uploads_temp:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: size=5g,uid=1000  # PIPEDA: Transient storage for unencrypted files
  secrets:
    driver: local
    driver_opts:
      type: none
      device: /run/secrets
      o: bind,ro  # PIPEDA: Secrets mounted read-only
```

**Mount points:**
- `postgres:/var/lib/postgresql/data`
- `minio:/data`
- `uploads_temp:/uploads` (backend) - **Must be ephemeral, encrypted at rest**
- `secrets:/run/secrets` (all services)

---

## 9. Log Aggregation Strategy

### 9.1 Architecture

```
[Services] → (stdout/json) → Vector (sidecar) → (filter/enrich) → MinIO (cold) + Loki (hot)
```

**Vector configuration:**
```toml
[sources.app_logs]
type = "stdin"
format = "json"

[transforms.scrub_pii]
type = "remap"
source = '''
  del(.sin)
  del(.dob)
  del(.banking_data)
  .transaction_id = sha256(.transaction_id)
'''

[sinks.minio]
type = "aws_s3"
bucket = "fintrac-logs"
encoding.codec = "ndjson"
storage_class = "GLACIER"  # 5-year retention
```

### 9.2 Correlation ID Propagation

- **Nginx:** `proxy_set_header X-Correlation-ID $request_id;`
- **FastAPI:** Middleware to read/generate `X-Correlation-ID`
- **Celery:** Pass via `task_headers`
- **Logs:** All services must include `correlation_id` in JSON output

---

## 10. Secrets Management Implementation

### 10.1 Docker Compose (Development)

```yaml
secrets:
  encryption_key:
    file: ./secrets/encryption_key.txt  # 0600 permissions, not in git
  db_password:
    file: ./secrets/db_password.txt
  secret_key:
    file: ./secrets/secret_key.txt

services:
  backend:
    secrets:
      - encryption_key
    environment:
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
```

**Loading in Python:**
```python
# common/config.py
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    encryption_key: str = Field(..., env='ENCRYPTION_KEY_FILE')
    
    def load_encryption_key(self) -> str:
        with open(self.encryption_key, 'r') as f:
            return f.read().strip()
```

### 10.2 Production (Vault)

```python
# HashiCorp Vault integration
from hvac import Client

def get_secret(path: str) -> str:
    client = Client(url='http://vault:8200', token=os.getenv('VAULT_TOKEN'))
    return client.secrets.kv.v2.read_secret_version(path=path)['data']['data']['value']
```

**PIPEDA Compliance:** All secret access logged with `correlation_id`, `user_id`, `timestamp`.

---

## 11. Deployment Checklist

- [ ] All Docker images pass `pip-audit` (zero vulnerabilities)
- [ ] Trivy scan shows 0 CRITICAL, 0 HIGH vulnerabilities
- [ ] `ENCRYPTION_KEY` is 32 bytes (AES-256) and base64-encoded
- [ ] `SECRET_KEY` is 64+ character random string from `secrets.token_urlsafe(64)`
- [ ] `.env.example` exists with no real secrets
- [ ] Health checks return within 3s
- [ ] Log aggregation verified (MinIO bucket created with WORM)
- [ ] Network policies prevent `postgres` from internet access
- [ ] Resource limits tested under load (k6 script: 100 req/s for 5 min)
- [ ] FINTRAC retention policy applied to MinIO logs (5-year lifecycle)
- [ ] PIPEDA encryption verified (SIN/DOB encrypted in DB, not in logs)
- [ ] OSFI B-20 decision service has 2+ replicas with anti-affinity
- [ ] Secrets mounted with 0600 permissions, not in image layers
- [ ] `docker-compose.yml` uses `version: '3.8'` with `secrets:` top-level key

---

**Warning:** This module does not contain business logic models or database migrations. All references to "models" and "migrations" in this document apply to **infrastructure as code** and **configuration management**, not SQLAlchemy ORM.