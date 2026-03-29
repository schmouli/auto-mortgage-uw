# Infrastructure & Deployment API

## GET /api/v1/health

System health check endpoint. Verifies connectivity to critical infrastructure dependencies (PostgreSQL, Redis, Object Storage) and returns the operational status of the application container.

**Request:**
```http
GET /api/v1/health
```

**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-02T10:00:00Z",
  "dependencies": {
    "postgres": "up",
    "redis": "up",
    "minio": "up"
  }
}
```

**Errors:**
- 503: Service Unavailable (one or more dependencies are down)

---

## GET /api/v1/metrics

Prometheus metrics endpoint for scraping application performance data, request latencies, and error rates.

**Request:**
```http
GET /api/v1/metrics
```

**Response (200):**
```text
# HELP request_duration_seconds Request duration
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.005"} 0
...
```

**Errors:**
- 401: Not authenticated (if metrics are protected)

---

# Infrastructure & Deployment Module

## Overview

The Infrastructure & Deployment module manages the lifecycle of the Mortgage Underwriting System across local and production environments. It defines the containerization strategy, service orchestration, and cloud resource provisioning.

This module does not contain business logic but provides the necessary configuration to run the following services:
1. **Frontend**: User interface.
2. **Orchestrator**: API Gateway / Workflow manager.
3. **Decision**: Underwriting logic engine.
4. **Policy**: Rules management service.
5. **DPT**: Data processing/transformation service.
6. **Celery**: Asynchronous task queue.
7. **PostgreSQL**: Database (local or RDS/Cloud SQL).
8. **Redis**: Caching (local or ElastiCache/Memorystore).
9. **MinIO/S3**: Object storage.

## Key Functions

### Local Development
Utilizes `docker-compose` to spin up the entire stack on a single machine.
- **Command**: `uv run docker-compose up --build`
- **Networking**: All services communicate via a bridge network.
- **Persistence**: Named volumes are used for PostgreSQL, Redis, and MinIO to preserve data between restarts.

### Production Deployment
Utilizes Kubernetes manifests (or Helm charts) for scalable deployment.
- **Strategy**: Rolling updates for zero-downtime deployments.
- **Storage**: Replaces local volumes with PVCs backed by AWS EBS or GCP Persistent Disks.
- **Ingress**: Configured via NGINX or AWS ALB for routing external traffic.

### Observability
- **Logging**: Structlog JSON output sent to stdout for aggregation by CloudWatch or Stackdriver.
- **Tracing**: OpenTelemetry instrumentation is auto-injected into all services.
- **Metrics**: Exposed on `/metrics` for Prometheus scraping.

## Usage Examples

### Starting Local Environment
```bash
# Clone repo
git clone <repo_url>
cd mortgage_underwriting

# Start infrastructure
docker-compose up -d postgres redis minio

# Run migrations
uv run alembic upgrade head

# Start application services
uv run uvicorn mortgage_underwriting.main:app --reload
```

### Deploying to Kubernetes
```bash
# Set context to production cluster
kubectl config use-context production-cluster

# Apply secrets (sealed secrets or sops)
kubectl apply -f k8s/secrets/

# Deploy services
kubectl apply -f k8s/services/
```

---

# Configuration Notes

## Environment Variables

Create/update `.env.example` for all new config variables:

```ini
# --- Infrastructure & Deployment Configuration ---

# Application Environment
ENVIRONMENT=local|development|staging|production
DEBUG=false
API_V1_PREFIX=/api/v1

# Database (PostgreSQL)
# Local: Use docker service name. Prod: Use RDS/Cloud SQL endpoint.
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/mortgage_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis Cache
# Local: Use docker service name. Prod: Use ElastiCache endpoint.
REDIS_URL=redis://:password@redis:6379/0

# Object Storage
# Local: MinIO. Prod: AWS S3 or GCP Cloud Storage.
STORAGE_BACKEND=s3|minio|gcs
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET=mortgage-docs-bucket
MINIO_ENDPOINT=http://minio:9000

# Security & Encryption
# Keys for encrypting PII (SIN, DOB) at rest (AES-256)
PII_ENCRYPTION_KEY=32_byte_url_safe_base64_encoded_key
SECRET_KEY=fastapi_jwt_secret_key

# Observability
# Correlation ID header name
CORRELATION_ID_HEADER=X-Correlation-ID
# OpenTelemetry Endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317

# Celery Configuration
CELERY_BROKER_URL=redis://:password@redis:6379/1
CELERY_RESULT_BACKEND=redis://:password@redis:6379/2
```

---

# CHANGELOG.md Update

```markdown
## [2026-03-02]
### Added
- Infrastructure & Deployment: Docker Compose configuration for local development (8 services).
- Infrastructure & Deployment: Kubernetes manifests for production deployment (AWS/GCP).
- Infrastructure & Deployment: Health check endpoints (`/health`, `/metrics`) for observability.
- Infrastructure & Deployment: Environment variable configuration for database, cache, and object storage abstraction.

### Changed
- Updated dependency requirements to include `uvicorn`, `celery`, and `opentelemetry` SDKs.
```

---

```python
# NOTE: Docstrings for routes.py (if applicable)
# Since Infrastructure typically lacks complex business logic routes.py,
# these docstrings are intended for the main.py or health check routes.

async def get_health(
    db: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis)
) -> HealthResponse:
    """
    Perform a health check on the application and its dependencies.
    Verifies connectivity to PostgreSQL and Redis.
    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
```