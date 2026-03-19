```markdown
# Docker & Deployment API

This module documentation covers the infrastructure setup, container orchestration, and system health endpoints for the Canadian Mortgage Underwriting System.

## API Documentation

The deployment architecture exposes specific health and metrics endpoints required for Docker orchestration (Kubernetes/Docker Compose) and observability.

### GET /health

Check the liveness of the application container. Used by Docker restart policies and Kubernetes liveness probes.

**Response (200):**
```json
{
  "status": "ok",
  "timestamp": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 503: Service Unavailable (System is shutting down)

---

### GET /ready

Check the readiness of the application and its dependencies (PostgreSQL, Redis, MinIO). Used by Kubernetes readiness probes to stop traffic to unready pods.

**Response (200):**
```json
{
  "status": "ready",
  "dependencies": {
    "postgres": "up",
    "redis": "up",
    "minio": "up"
  }
}
```

**Errors:**
- 503: Service Unavailable (Dependencies not ready)

---

### GET /metrics

Exposes Prometheus metrics for application monitoring. Includes request latencies, error rates, and OSFI B-20 specific calculation counters.

**Response (200):**
```text
# HELP request_duration_seconds Request duration
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.005"} 100
...
# HELP osfi_stress_test_calculated_total Total number of stress tests calculated
# TYPE osfi_stress_test_calculated_total counter
osfi_stress_test_calculated_total 5
```

---

### GET /api/v1/orchestrator/status

**Note:** Part of the Orchestrator service. Returns the aggregate status of all microservices (Decision, Policy, DPT).

**Response (200):**
```json
{
  "orchestrator": "healthy",
  "services": {
    "decision": "healthy",
    "policy": "healthy",
    "dpt": "healthy"
  }
}
```

---

## Module README

### Overview

The Docker & Deployment configuration manages the lifecycle of the Canadian Mortgage Underwriting System. It utilizes Docker Compose for local development and CI/CD pipelines, orchestrating 11 distinct services including the FastAPI backend, React frontend, PostgreSQL database, and auxiliary microservices (Policy, Decision, DPT).

### Architecture

The system runs on a bridge network `mortgage_net` with the following service interactions:

1.  **Ingress:** Nginx (Port 80/443) routes traffic.
    *   `/api/v1/*` -> Backend (FastAPI)
    *   `/` -> Frontend (React static files)
2.  **Application Layer:**
    *   **Backend:** FastAPI (Port 7000). Connects to Postgres, Redis, MinIO.
    *   **Orchestrator:** Coordinates calls to internal microservices.
    *   **Internal Microservices:** Policy, Decision, DPT (Internal ports only).
3.  **Data Layer:**
    *   **PostgreSQL 15:** Persistent transactional data.
    *   **Redis 7:** Caching and Celery message broker.
4.  **Async Processing:**
    *   **Celery Worker:** Executes background tasks (e.g., PDF generation).
    *   **Celery Beat:** Scheduler for periodic tasks (e.g., nightly compliance audits).
5.  **Storage:**
    *   **MinIO:** S3-compatible object storage for uploaded documents (mortgage statements, ID).

### Key Functions

*   **Containerization:** Ensures parity between development and production environments using Python 3.12 slim images.
*   **Secrets Management:** Configuration is injected via `.env` files. No secrets are hardcoded in `Dockerfile` or `docker-compose.yml`.
*   **Observability:** Structured JSON logs are emitted to stdout for collection by the container runtime.

### Usage Examples

#### Local Development
Start the full stack:
```bash
uv run docker compose up -d
```

View logs for a specific service (e.g., the decision engine):
```bash
uv run docker compose logs -f decision
```

Rebuild the backend after changes:
```bash
uv run docker compose up -d --build backend
```

#### Database Migrations
Run Alembic migrations inside the running backend container:
```bash
uv run docker compose exec backend alembic upgrade head
```

#### Security Scanning
Before deployment, run the pip-audit security scanner:
```bash
uv run pip-audit
```

---

## Configuration Notes

The following environment variables must be defined in `.env` or provided to the container orchestrator.

### Database & Cache
```bash
# Database Connection (PostgreSQL)
POSTGRES_USER=underwriter_user
POSTGRES_PASSWORD=change_me_production_password
POSTGRES_DB=mortgage_db
DATABASE_URL=postgresql+asyncpg://underwriter_user:change_me_production_password@postgres:5432/mortgage_db

# Redis Connection
REDIS_URL=redis://:change_me_redis_password@redis:6379/0
```

### Application Settings
```bash
# FastAPI
ENVIRONMENT=production
API_V1_PREFIX=/api/v1
SECRET_KEY=your_jwt_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OSFI Compliance
QUALIFYING_RATE_FLOOR=5.25
```

### MinIO Object Storage
```bash
# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_NAME=mortgage-docs
```

### Internal Microservices
```bash
# Service Discovery (Internal Docker Network)
POLICY_SERVICE_URL=http://policy:8001
DECISION_SERVICE_URL=http://decision:8002
DPT_SERVICE_URL=http://dpt:8003
```