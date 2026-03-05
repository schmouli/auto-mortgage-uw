# Infrastructure & Deployment API

## GET /health

Check the liveness of the infrastructure orchestrator.

**Request:**
None (No body required).

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 503: Service Unavailable (Database or Redis connection failed)

---

## GET /api/v1/infra/status

Retrieve the aggregated health status of all dependent services (Postgres, Redis, MinIO/S3, Celery).

**Request:**
None (No body required).

**Response (200):**
```json
{
  "postgres": "up",
  "redis": "up",
  "storage": "up",
  "celery_broker": "up",
  "services": {
    "dpt": "healthy",
    "policy": "healthy",
    "decision": "healthy",
    "orchestrator": "healthy"
  }
}
```

**Errors:**
- 503: One or more dependencies are down
- 401: Not authenticated (Admin access required for detailed status)

---

# Infrastructure & Deployment

## Overview

The Infrastructure & Deployment module manages the lifecycle, configuration, and health of the Canadian Mortgage Underwriting System. It supports two primary environments: **Local Development** (via Docker Compose) and **Production** (via Kubernetes on AWS/GCP).

## Key Functions

### Local Development
Designed for rapid iteration using Docker Compose. It spins up the following 9 services:
1.  **postgres**: PostgreSQL 15 database.
2.  **redis**: Caching and message broker.
3.  **minio**: S3-compatible object storage for document uploads.
4.  **dpt**: Data Processing Team microservice.
5.  **policy**: Policy rules engine microservice.
6.  **decision**: Decision engine microservice.
7.  **orchestrator**: Central API gateway and workflow manager.
8.  **frontend**: UI layer (React/Vue).
9.  **celery**: Asynchronous task worker.

### Production Deployment
Designed for high availability and scalability using Kubernetes.
-   **Compute**: Kubernetes Deployments with separate Deployments/Services for each component.
-   **Storage**: AWS S3 or GCP Cloud Storage replaces MinIO.
-   **Database**: AWS RDS or GCP Cloud SQL replaces local Postgres.
-   **Caching**: AWS ElastiCache or GCP Memorystore replaces local Redis.
-   **Hardware**: GPU nodes are **not** enabled by default for this specific architecture (CPU-based underwriting).

## Usage Examples

### Starting Local Environment
Ensure `uv` is installed and `.env` is configured.

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f orchestrator

# Stop services
docker-compose down
```

### Checking Health
Verify all services are running before commencing work.

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/infra/status
```

### Production Deployment (K8s)
Apply the Kubernetes manifests located in `k8s/`.

```bash
kubectl apply -f k8s/namespaces/
kubectl apply -f k8s/configmaps/
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/services/
```

---

# Configuration Notes

## Environment Variables

Create a `.env` file in the root directory or update the existing `.env.example`.

```ini
# Infrastructure & Deployment Configuration

# Runtime
ENVIRONMENT=local|production
DEBUG=True
LOG_LEVEL=INFO

# Database (Local Postgres or RDS)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=mortgage_admin
POSTGRES_PASSWORD=change_me_secure_password
POSTGRES_DB=mortgage_underwriting

# Redis (Local or ElastiCache)
REDIS_URL=redis://localhost:6379/0

# Storage (MinIO or S3)
STORAGE_TYPE=minio|s3|gcs
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
AWS_REGION=us-east-1
AWS_S3_BUCKET=mortgage-docs-prod

# GPU Configuration
GPU_ENABLED=False
CUDA_VISIBLE_DEVICES=""

# Application Ports
ORCHESTRATOR_PORT=8000
FRONTEND_PORT=3000
```

---

# CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Infrastructure & Deployment: Initial scaffolding for Docker Compose and Kubernetes environments.
- Health Check endpoints: Added `/health` and `/api/v1/infra/status` for monitoring service dependencies.
- Configuration: Added `.env.example` with support for local MinIO and production S3/GCS backends.

### Changed
- Updated project structure to support multi-service deployment (dpt, policy, decision, orchestrator).

### Fixed
- Fixed network configuration in Docker Compose to allow service discovery via container names.
```