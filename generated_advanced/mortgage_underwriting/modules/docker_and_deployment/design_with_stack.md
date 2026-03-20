# Design: Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Docker & Deployment Module Design Plan

**Module Identifier:** DEPLOYMENT  
**Feature Slug:** docker-deployment  
**File:** docs/design/docker-deployment.md

---

## 1. Endpoints

### 1.1 Orchestrator Service (Primary API Gateway)
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `POST` | `/api/v1/applications` | Authenticated | `ApplicationSubmitSchema` | `201 {"application_id": uuid, "status": "submitted"}` | `DEPLOYMENT_001`, `DEPLOYMENT_002`, `DEPLOYMENT_005` |
| `GET` | `/api/v1/applications/{application_id}` | Authenticated | - | `200 ApplicationStatusSchema` | `DEPLOYMENT_001`, `DEPLOYMENT_003` |
| `POST` | `/api/v1/applications/{application_id}/documents` | Authenticated | `multipart/form-data` (file) | `201 {"document_id": uuid, "upload_status": "processed"}` | `DEPLOYMENT_002`, `DEPLOYMENT_004` |
| `GET` | `/api/v1/applications/{application_id}/decision` | Authenticated | - | `200 DecisionSchema` | `DEPLOYMENT_001`, `DEPLOYMENT_003` |
| `GET` | `/api/v1/health` | Public | - | `200 {"status": "healthy", "services": {...}}` | `DEPLOYMENT_006` |

### 1.2 Backend Service (FastAPI)
| Method | Path | Auth | Request Body | Response | Error Codes |
|--------|------|------|--------------|----------|-------------|
| `POST` | `/api/v1/underwriting/calculate` | Service-to-Service (mTLS) | `UnderwritingInputSchema` | `200 RatioCalculationSchema` | `DEPLOYMENT_007`, `DEPLOYMENT_008` |
| `GET` | `/api/v1/health` | Public | - | `200 {"status": "healthy", "db": "connected", "redis": "connected"}` | `DEPLOYMENT_006` |

### 1.3 Internal Service Health Endpoints (All Services)
| Method | Path | Auth | Response |
|--------|------|------|----------|
| `GET` | `/health` | Public (internal network) | `200 {"service": "name", "status": "healthy", "version": "x.y.z"}` |

**Request/Response Schema Definitions:**

```python
# ApplicationSubmitSchema
{
    "applicant": {
        "first_name": str,  # required, max_length=50
        "last_name": str,   # required, max_length=50
        "sin_hash": str,    # required, SHA256 hash
        "dob_encrypted": str, # required, AES-256 encrypted
        "gross_annual_income": Decimal, # required, gt=0
    },
    "property": {
        "address": str,     # required
        "purchase_price": Decimal, # required, gt=0
        "down_payment": Decimal, # required, gte=0
    },
    "loan": {
        "amount": Decimal,  # required, gt=0
        "term_years": int, # required, 1-30
        "contract_rate": Decimal, # required, gt=0
    }
}

# ApplicationStatusSchema
{
    "application_id": uuid,
    "status": Enum["submitted", "under_review", "documents_pending", "approved", "rejected"],
    "created_at": datetime,
    "updated_at": datetime,
    "decision": Optional[DecisionSchema]
}

# DecisionSchema
{
    "gds_ratio": Decimal,
    "tds_ratio": Decimal,
    "qualifying_rate": Decimal,  # OSFI B-20 stress test rate
    "insurance_required": bool,
    "insurance_premium": Optional[Decimal],
    "decision": Enum["approved", "rejected", "manual_review"],
    "reasons": List[str]
}
```

---

## 2. Models & Database

### 2.1 Orchestrator Service Models

**Table: `orchestration_jobs`**
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PrimaryKey | - |
| `application_id` | UUID | ForeignKey(applications.id) | Composite (application_id, status) |
| `job_type` | VARCHAR(50) | NotNull | - |
| `status` | VARCHAR(20) | NotNull, Check: queued, running, completed, failed | - |
| `payload_encrypted` | TEXT | NotNull (AES-256) | - |
| `result_encrypted` | TEXT | Nullable (AES-256) | - |
| `retry_count` | INTEGER | NotNull, Default=0 | - |
| `created_at` | TIMESTAMPTZ | NotNull, Default=now() | - |
| `updated_at` | TIMESTAMPTZ | NotNull, Default=now() | - |

**Table: `service_health`**
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PrimaryKey | - |
| `service_name` | VARCHAR(100) | NotNull, Unique | Unique |
| `status` | VARCHAR(20) | NotNull | - |
| `last_check` | TIMESTAMPTZ | NotNull | - |
| `version` | VARCHAR(20) | Nullable | - |
| `error_message_encrypted` | TEXT | Nullable (AES-256) | - |

**Table: `deployment_audit_logs`**
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PrimaryKey | - |
| `event_type` | VARCHAR(50) | NotNull | Composite (event_type, created_at) |
| `service_name` | VARCHAR(100) | NotNull | - |
| `environment` | VARCHAR(20) | NotNull | - |
| `user_id` | UUID | Nullable (for manual deploys) | - |
| `details_encrypted` | TEXT | NotNull (AES-256) | - |
| `created_at` | TIMESTAMPTZ | NotNull, Default=now() | BRIN index |

### 2.2 Volume Mount Strategy

| Service | Volume Name | Mount Path | Purpose | Persistence |
|---------|-------------|------------|---------|-------------|
| `postgres` | `pg_data` | `/var/lib/postgresql/data` | Database files | **Persistent** |
| `minio` | `minio_data` | `/data` | Document storage | **Persistent** |
| `backend` | `uploads` | `/app/uploads` | Temporary file uploads | Ephemeral (24h) |
| `nginx` | `logs` | `/var/log/nginx` | Access/error logs | **Persistent** |
| `redis` | `redis_data` | `/data` | Session cache | Ephemeral (LRU) |

---

## 3. Business Logic

### 3.1 Service Health Check Algorithm
```python
async def perform_health_check(service_name: str) -> dict:
    """
    Checks service health with dependency validation
    """
    # 1. Check service HTTP health endpoint
    # 2. Verify database connectivity (if applicable)
    # 3. Verify Redis connectivity (if applicable)
    # 4. Check resource utilization (< 80% CPU/Memory)
    # 5. Validate dependency services (cascading health)
    
    return {
        "status": "healthy|degraded|unhealthy",
        "checks": {
            "http": True,
            "database": True,
            "redis": True,
            "resources": {"cpu_percent": 45, "memory_percent": 62},
            "dependencies": {"postgres": "healthy", "redis": "healthy"}
        }
    }
```

### 3.2 Orchestration Workflow State Machine
```
submitted → documents_pending → underwriting_started → 
  → (approved|rejected|manual_review) → finalized
```

**Transition Rules:**
- `submitted → documents_pending`: Application created, awaiting document upload
- `documents_pending → underwriting_started`: All required documents uploaded
- `underwriting_started → approved`: GDS ≤ 39% AND TDS ≤ 44% AND LTV ≤ 95%
- `underwriting_started → rejected`: GDS > 44% OR TDS > 49% OR LTV > 95%
- `underwriting_started → manual_review`: 39% < GDS ≤ 44% OR 44% < TDS ≤ 49%

### 3.3 Secrets Rotation Logic
- **Rotation Schedule:** ENCRYPTION_KEY every 90 days, DATABASE_URL credentials every 60 days
- **Zero-downtime:** Dual-key support during rotation period (old + new key active)
- **Audit:** Log rotation events in `deployment_audit_logs` with encrypted details

---

## 4. Migrations

### 4.1 New Tables
```sql
-- migration: 001_create_orchestration_tables
CREATE TABLE orchestration_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    payload_encrypted TEXT NOT NULL,
    result_encrypted TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orchestration_jobs_application_status ON orchestration_jobs(application_id, status);
CREATE INDEX idx_orchestration_jobs_status ON orchestration_jobs(status);

CREATE TABLE service_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(100) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    last_check TIMESTAMPTZ NOT NULL,
    version VARCHAR(20),
    error_message_encrypted TEXT
);

CREATE UNIQUE INDEX idx_service_health_name ON service_health(service_name);

CREATE TABLE deployment_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    environment VARCHAR(20) NOT NULL,
    user_id UUID,
    details_encrypted TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_deployment_logs_event_time ON deployment_audit_logs(event_type, created_at);
CREATE INDEX idx_deployment_logs_created_at ON deployment_audit_logs USING BRIN(created_at);
```

### 4.2 Existing Tables Modifications
```sql
-- Add encrypted fields to existing applications table
ALTER TABLE applications ADD COLUMN sin_hash VARCHAR(64) NOT NULL;
ALTER TABLE applications ADD COLUMN dob_encrypted TEXT NOT NULL;
ALTER TABLE applications ADD COLUMN income_encrypted TEXT NOT NULL;
```

---

## 5. Security & Compliance

### 5.1 Secrets Management Strategy
**WARNING:** NEVER commit secrets to version control. Use one of:

1. **Docker Swarm Secrets** (Development)
   ```
   echo "mysecret" | docker secret create db_password -
   ```

2. **HashiCorp Vault** (Production Recommended)
   - KV v2 engine for static secrets
   - Database secrets engine for dynamic DB credentials
   - Transit engine for encryption key management
   - AppRole authentication for services

3. **AWS Secrets Manager** (Alternative)
   - Rotation Lambda functions for automatic credential rotation
   - IAM roles for service access

**Implementation Pattern:**
```python
# In common/config.py
class Settings(BaseSettings):
    database_url: SecretStr = Field(default=None)
    
    def get_database_url(self) -> str:
        if self.environment == "production":
            # Fetch from Vault
            return vault_client.get_secret("database/creds/mortgage_uw")
        return self.database_url.get_secret_value()
```

### 5.2 Network Isolation
```yaml
# docker-compose.networks.yml
networks:
  frontend:
    driver: bridge
    internal: false
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
  document-processing:
    driver: bridge
    internal: true
```

**Service Placement:**
- `nginx`: frontend, backend networks
- `backend`, `orchestrator`: backend, database networks
- `postgres`, `redis`: database network only
- `minio`, `dpt`, `policy`, `decision`: document-processing network

### 5.3 FINTRAC Compliance (Logging)
- **Log Retention:** 5 years in `deployment_audit_logs` (BRIN index for time-series queries)
- **Immutable Logs:** Write-once to volume mount, no deletion API
- **Transaction Flags:** Log all document uploads > CAD $10,000 equivalent with `event_type = "large_document_upload"`
- **PII Masking:** All logs use `sin_hash` not raw SIN; income values encrypted

### 5.4 PIPEDA Data Handling
- **Encryption at Rest:** AES-256-GCM for all `*_encrypted` fields
- **Encryption in Transit:** mTLS between all services, TLS 1.3 for external-facing nginx
- **Data Minimization:** Orchestrator only passes required fields to each service
- **Key Rotation:** ENCRYPTION_KEY rotated every 90 days, re-encrypt data in background job

### 5.5 OSFI B-20 Enforcement
- **Stress Test Rate:** `qualifying_rate = max(contract_rate + 2%, 5.25%)` calculated in `decision` service
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44% enforced at API gateway level (orchestrator returns 422 if violated)
- **Audit Trail:** Every ratio calculation logged in `orchestration_jobs` with encrypted payload

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ServiceUnavailableError` | 503 | `DEPLOYMENT_001` | "Service {name} is unavailable" | Health check fails for critical service |
| `ConfigurationError` | 500 | `DEPLOYMENT_002` | "Invalid configuration: {detail}" | Missing required env var or secret |
| `ResourceNotFoundError` | 404 | `DEPLOYMENT_003` | "Resource {resource} not found" | Application ID not found in orchestrator |
| `PayloadTooLargeError` | 413 | `DEPLOYMENT_004` | "Upload exceeds MAX_UPLOAD_SIZE_MB" | File size > 10MB |
| `BusinessRuleViolationError` | 422 | `DEPLOYMENT_005` | "OSFI B-20 violation: {detail}" | GDS/TDS exceeds limits |
| `HealthCheckFailedError` | 503 | `DEPLOYMENT_006` | "Health check failed: {service}" | Dependency service unhealthy |
| `UnderwritingCalculationError` | 502 | `DEPLOYMENT_007` | "Calculation failed in {service}" | Decision service returns error |
| `ValidationError` | 422 | `DEPLOYMENT_008` | "Field validation failed: {field}" | Pydantic validation error |

### 6.1 Error Response Format
```json
{
  "detail": "Service postgres is unavailable",
  "error_code": "DEPLOYMENT_001",
  "correlation_id": "01928374-abc1-4567-8901-abcdef123456",
  "timestamp": "2024-01-15T14:30:00Z",
  "service": "orchestrator"
}
```

### 6.2 Retry Strategy
- **Transient Errors:** `DEPLOYMENT_001`, `DEPLOYMENT_006` → Retry with exponential backoff (max 3 attempts)
- **Permanent Errors:** `DEPLOYMENT_002`, `DEPLOYMENT_005` → No retry, return immediately
- **Circuit Breaker:** After 5 consecutive failures, trip breaker for 60 seconds

---

## 7. Dockerfile Specifications (Multi-Stage)

### 7.1 Backend Dockerfile
```dockerfile
# syntax=docker/dockerfile:1.4
FROM python:3.12-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system --no-cache

FROM python:3.12-slim as runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1001 appuser

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=appuser:appuser . .

USER appuser
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
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

### 7.3 Document Processing Transformer (DPT) Dockerfile
```dockerfile
FROM python:3.12-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dpt.txt .
RUN pip install --user --no-cache-dir -r requirements-dpt.txt

FROM python:3.12-slim as runtime

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1002 dptuser

WORKDIR /app
COPY --from=builder /root/.local /home/dptuser/.local
COPY --chown=dptuser:dptuser . .

USER dptuser
EXPOSE 8000

HEALTHCHECK CMD python -c "import requests; requests.get('http://localhost:8000/health')"
CMD ["python", "app.py"]
```

---

## 8. Resource Limits & Monitoring

| Service | CPU Limit | Memory Limit | Restart Policy | Log Driver |
|---------|-----------|--------------|----------------|------------|
| `backend` | 2 cores | 4GB | unless-stopped | json-file (max-size: 100m) |
| `postgres` | 4 cores | 8GB | unless-stopped | json-file (max-size: 200m) |
| `redis` | 0.5 cores | 1GB | unless-stopped | json-file (max-size: 50m) |
| `celery` | 1 core | 2GB | unless-stopped | json-file (max-size: 100m) |
| `nginx` | 0.5 cores | 512MB | unless-stopped | json-file (max-size: 50m) |
| `minio` | 1 core | 2GB | unless-stopped | json-file (max-size: 100m) |
| `dpt` | 2 cores | 6GB (GPU optional) | unless-stopped | json-file (max-size: 100m) |
| `orchestrator` | 1 core | 2GB | unless-stopped | json-file (max-size: 100m) |

**Log Aggregation:** All services ship JSON logs to stdout/stderr, collected by Fluentd sidecar containers forwarding to centralized Loki cluster with 5-year retention for FINTRAC compliance.

---

## 9. Deployment Commands

```bash
# Development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Production (with secrets)
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml mortgage_uw

# Health check
curl -H "X-Correlation-ID: $(uuidgen)" http://localhost/api/v1/health
```