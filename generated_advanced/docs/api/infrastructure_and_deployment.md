Here is the documentation for the **Infrastructure & Deployment** module.

### 1. API Documentation

**File:** `docs/api/infrastructure_deployment.md`

```markdown
# Infrastructure & Deployment API

## GET /api/v1/health

Liveness probe. Checks if the API service is running. Returns 200 if the service is up.

**Response (200):**
```json
{
  "status": "ok",
  "timestamp": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 503: Service Unavailable (System shutting down)

---

## GET /api/v1/health/ready

Readiness probe. Checks if the service is ready to accept traffic (i.e., dependencies like PostgreSQL, Redis, and Object Storage are reachable).

**Response (200):**
```json
{
  "status": "ready",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "storage": "healthy"
  },
  "timestamp": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 503: Service Unavailable (One or more dependencies are down)
  ```json
  {
    "status": "not_ready",
    "checks": {
      "database": "unhealthy",
      "redis": "healthy",
      "storage": "healthy"
    },
    "detail": "Database connection timed out"
  }
  ```

---

## GET /api/v1/metrics

Prometheus metrics endpoint for observability. Exposes request latencies, error rates, and custom business metrics (e.g., active underwriting calculations).

**Response (200):**
```text
# HELP request_duration_seconds Request duration in seconds
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.005"} 10
...
```

**Errors:**
- 401: Not authenticated (if metrics are protected)

---
```

### 2. Module README

**File:** `docs/modules/infrastructure_deployment.md`

```markdown
# Infrastructure & Deployment Module

## Overview
This module defines the infrastructure-as-code (IaC) and runtime configurations for the Canadian Mortgage Underwriting System. It supports two distinct environments:
1.  **Local Development:** A self-contained Docker Compose environment.
2.  **Production:** A scalable Kubernetes deployment on AWS/GCP.

## Architecture
The system consists of 8 core services orchestrated via Docker Compose (local) or Kubernetes (prod):
- **Frontend:** Next.js/Vue interface.
- **Orchestrator:** Central API Gateway (FastAPI).
- **Decision Engine:** Core logic for GDS/TDS/CMHC calculations.
- **Policy Engine:** Rules and regulatory compliance checking.
- **DPT (Data Processing Tool):** Batch processing for ETL.
- **Celery:** Asynchronous task queue for background jobs.
- **PostgreSQL:** Primary database (RDS/Cloud SQL in prod).
- **Redis:** Caching layer (ElastiCache/Memorystore in prod).
- **MinIO/S3:** Object storage for documents and proof of income.

## Key Functions

### Environment Management
- **Local:** Uses `docker compose up` to spin up all dependencies.
- **Prod:** Uses Helm charts or raw K8s manifests to manage Deployments, Services, and Ingress.

### Observability & Compliance
- **Health Checks:** Implements `/health` (liveness) and `/health/ready` (readiness) endpoints to satisfy K8s probe requirements and load balancer configurations.
- **Logging:** Structured JSON logs via `structlog` with `correlation_id` tracing across all 8 services to satisfy FINTRAC audit trail requirements.
- **Metrics:** OpenTelemetry integration exposed at `/metrics`.

## Usage Examples

### Local Development
1.  **Start Services:**
    ```bash
    cp .env.example .env
    uv run docker compose up -d
    ```
2.  **Run Migrations:**
    ```bash
    uv run alembic upgrade head
    ```
3.  **View Logs:**
    ```bash
    uv run docker compose logs -f orchestrator
    ```

### Production Deployment
1.  **Configure Secrets:** Ensure Kubernetes secrets are created for DB passwords and API keys.
2.  **Deploy:**
    ```bash
    kubectl apply -f k8s/
    ```
3.  **Verify Health:**
    ```bash
    kubectl get pods
    curl https://api.mortgage-system.com/api/v1/health/ready
    ```

## Security Notes
- **PIPEDA Compliance:** Ensure `.env` files are never committed. Sensitive data (SIN/DOB) encryption keys must be stored in AWS Secrets Manager or GCP Secret Manager, not in ConfigMaps.
- **OSFI B-20:** Ensure logging configurations capture the *result* of stress tests without logging the raw financial input data.
```

### 3. Configuration Notes

**File:** `.env.example` (Updates)

```bash
# ==========================================
# Infrastructure & Deployment Configuration
# ==========================================

# Environment
ENVIRONMENT=local
DEBUG=True

# --- Database (PostgreSQL) ---
# Local uses Docker Compose service name; Prod uses RDS/Cloud SQL endpoint
DATABASE_URL=postgresql+asyncpg://mortgage_user:changeme@postgres:5432/mortgage_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# --- Cache (Redis) ---
# Local uses Docker Compose service name; Prod uses ElastiCache endpoint
REDIS_URL=redis://:changeme@redis:6379/0

# --- Object Storage ---
# Local: MinIO | Prod: AWS S3 or GCP Cloud Storage
STORAGE_BACKEND=local # options: local, s3, gcs
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_S3_ENDPOINT=http://minio:9000
AWS_S3_BUCKET=mortgage-docs-dev
AWS_REGION=us-east-1

# --- Security & Encryption ---
# Keys for AES-256 encryption of PII (SIN, DOB) per PIPEDA
PII_ENCRYPTION_KEY=changeme_change_me_please
SECRET_KEY=changeme_for_jwt_sessions
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# --- Observability ---
# Correlation ID header name
CORRELATION_ID_HEADER=X-Correlation-ID
# Enable OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

### 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Infrastructure & Deployment: Added Docker Compose configuration for local development (8 services).
- Infrastructure & Deployment: Added Kubernetes manifests for production deployment.
- Infrastructure & Deployment: Implemented `/health` and `/health/ready` endpoints for service monitoring.
- Infrastructure & Deployment: Integrated OpenTelemetry tracing and Prometheus metrics export.

### Changed
- Updated project structure to support multi-service orchestration.
- Centralized environment variable management in .env.example.

### Fixed
- N/A
```