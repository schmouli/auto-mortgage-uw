Here is the documentation for the Infrastructure & Deployment module.

### 1. API Documentation

**File:** `docs/api/infrastructure_deployment.md`

```markdown
# Infrastructure & Deployment API

This module provides system-level endpoints for health checks, readiness probes, and metrics exposure, essential for both Docker Compose local development and Kubernetes orchestration.

## GET /health

Liveness probe. Checks if the API server is running. Used by Kubernetes/Docker to restart the container if it crashes.

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

## GET /ready

Readiness probe. Checks if the API server is ready to accept traffic, specifically verifying connectivity to critical dependencies (PostgreSQL, Redis, MinIO/S3).

**Response (200):**
```json
{
  "status": "ready",
  "dependencies": {
    "database": "healthy",
    "cache": "healthy",
    "storage": "healthy"
  }
}
```

**Errors:**
- 503: Service Unavailable (One or more dependencies are down)
```json
{
  "status": "not_ready",
  "dependencies": {
    "database": "unhealthy",
    "cache": "healthy",
    "storage": "healthy"
  }
}
```

---

## GET /metrics

Prometheus metrics endpoint. Exposes application metrics for monitoring and alerting.

**Response (200):**
```text
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/v1/health",status="200"} 1234
...
```

**Errors:**
- 401: Unauthorized (if metrics are protected)
```

### 2. Module README

**File:** `docs/modules/infrastructure_deployment.md`

```markdown
# Infrastructure & Deployment Module

## Overview

The Infrastructure & Deployment module defines the environment configuration, container orchestration, and deployment strategies for the Canadian Mortgage Underwriting System. It supports two primary environments:

1.  **Local Development:** A `docker-compose` setup that spins up the full stack of services (PostgreSQL, Redis, MinIO, Application Services, Frontend, Celery) on a local machine.
2.  **Production:** A Kubernetes (K8s) setup utilizing managed cloud services (AWS/GCP) for scalability and reliability.

## Architecture

### Local Development (Docker Compose)
The system runs 8 distinct services within a isolated Docker network:
-   **postgres:** PostgreSQL 15 database with persistent volume.
-   **redis:** In-memory data store for caching and Celery broker.
-   **minio:** S3-compatible object storage for document uploads (mocking AWS S3).
-   **dpt, policy, decision, orchestrator:** Core FastAPI microservices.
-   **frontend:** Web UI.
-   **celery:** Asynchronous task processor for background jobs (e.g., PDF generation, email notifications).

### Production (Kubernetes)
In production, services are deployed as separate `Deployment` and `Service` objects.
-   **Database:** AWS RDS or GCP Cloud SQL.
-   **Cache:** AWS ElastiCache or GCP Memorystore.
-   **Storage:** AWS S3 or GCP Cloud Storage.
-   **Compute:** EKS (AWS) or GKE (GCP) pods.

## Key Functions

-   **Orchestration:** Manages the startup order and dependencies of all services.
-   **Configuration Management:** Injects environment-specific variables via `.env` files (local) or ConfigMaps/Secrets (K8s).
-   **Observability:** Integrates OpenTelemetry tracing and Structlog JSON logging across all containers.
-   **Health Monitoring:** Provides standardized `/health` and `/ready` endpoints for load balancers and orchestrators.

## Usage Examples

### Local Development
1.  Copy the environment template:
    ```bash
    cp .env.example .env
    ```
2.  Start all services:
    ```bash
    docker-compose up -d
    ```
3.  View logs:
    ```bash
    docker-compose logs -f orchestrator
    ```

### Production Deployment
1.  Configure `k8s/` manifests with your cloud provider specifics (ARNs, IPs).
2.  Apply secrets:
    ```bash
    kubectl apply -f k8s/secrets.yaml
    ```
3.  Deploy services:
    ```bash
    kubectl apply -f k8s/deployments/
    ```

## Security & Compliance

-   **Secrets Management:** Secrets are never committed to git. In local dev, they are in `.env`. In prod, they use Kubernetes Secrets or AWS Parameter Store.
-   **PIPEDA Compliance:** Logs are configured to strictly exclude PII (SIN, DOB). Database backups are encrypted at rest.
-   **Scanning:** `uv run pip-audit` is run in the CI/CD pipeline before building images.
```

### 3. Configuration Notes

**File:** `.env.example` (Updates)

```ini
# ==========================================
# Infrastructure & Deployment Configuration
# ==========================================

# Environment: local, development, staging, production
ENVIRONMENT=local

# --- Database (PostgreSQL) ---
# Local: Use 'postgres' hostname (Docker service name)
# Prod: Use RDS/CloudSQL endpoint
DATABASE_URL=postgresql+asyncpg://mortgage_user:change_me@postgres:5432/mortgage_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# --- Cache (Redis) ---
# Local: Use 'redis' hostname
# Prod: Use ElastiCache/Memorystore endpoint
REDIS_URL=redis://:change_me@redis:6379/0

# --- Object Storage (S3/MinIO) ---
# Local: MinIO credentials
# Prod: AWS IAM Role or Service Account credentials
STORAGE_BACKEND=s3 # options: s3, gcs
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1
S3_ENDPOINT_URL=http://minio:9000 # Local only; omit for production AWS
S3_BUCKET_NAME=mortgage-documents-uploads

# --- Security ---
# Generate using: openssl rand -hex 32
SECRET_KEY=change_this_to_a_random_string_of_32_chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# --- Observability ---
# Correlation ID header name
CORRELATION_ID_HEADER=X-Correlation-ID
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# --- Celery ---
CELERY_BROKER_URL=redis://:change_me@redis:6379/1
CELERY_RESULT_BACKEND=redis://:change_me@redis:6379/2
```

### 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Infrastructure & Deployment: Defined Docker Compose architecture with 8 services (postgres, redis, minio, dpt, policy, decision, orchestrator, frontend, celery).
- Infrastructure & Deployment: Added Kubernetes deployment manifests for production environments (RDS, S3, ElastiCache).
- Infrastructure & Deployment: Implemented `/health`, `/ready`, and `/metrics` endpoints for orchestration and monitoring.
- Configuration: Added `.env.example` with support for both local MinIO and production AWS S3 configurations.

### Changed
- Updated project structure to support multi-service Docker networking.
- Standardized logging output to JSON format for structured log aggregation.

### Fixed
- N/A
```