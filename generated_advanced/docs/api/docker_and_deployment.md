# Docker & Deployment API & Operations Guide

## Overview

This module defines the containerized architecture and deployment strategy for the Canadian Mortgage Underwriting System. It orchestrates 11 distinct services using Docker Compose, handling reverse proxying, background task processing, document storage, and microservice coordination.

### Architecture Diagram

```text
Internet
    |
[ Nginx (Port 80/443) ]
    |-------------------------------------|
    |                                     |
[ Frontend (React) ]              [ Backend (FastAPI) ]
    |                                     |
    |---[ Static Assets ]           [ Orchestrator API ]
                                         |
    -------------------------------------|
    |            |              |         |
[ Postgres ] [ Redis ] [ MinIO ] [ Policy/Decision/DPT Services ]
    |            |              |
[ Celery Worker] [ Celery Beat ]
```

---

## API Documentation

The following endpoints are exposed by the **Orchestrator** service and the **Nginx** gateway to manage system health and deployment status.

### GET /health

System-wide health check endpoint (proxied through Nginx). Used by Kubernetes/Docker health checks.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-02T10:00:00Z",
  "services": {
    "backend": "up",
    "postgres": "up",
    "redis": "up",
    "minio": "up"
  }
}
```

**Errors:**
- 503: Service Unavailable (if critical dependencies are down)

---

### GET /api/v1/orchestrator/status

Retrieves the real-time status of all internal microservices (Policy, Decision, DPT).

**Response (200):**
```json
{
  "orchestrator_id": "orch-123",
  "services": {
    "policy_service": {
      "status": "running",
      "version": "1.2.0",
      "last_heartbeat": "2026-03-02T10:00:00Z"
    },
    "decision_engine": {
      "status": "running",
      "version": "2.0.4",
      "queue_depth": 0
    },
    "dpt_service": {
      "status": "running",
      "active_jobs": 3
    }
  }
}
```

**Errors:**
- 503: Orchestrator unable to reach downstream services

---

### GET /metrics

Prometheus metrics endpoint for system observability (Memory, CPU, Request Latency).

**Response (200):**
```text
# HELP app_request_duration_seconds Request duration in seconds
# TYPE app_request_duration_seconds histogram
app_request_duration_seconds_bucket{le="0.1"} 5
...
```

---

## Module README

### Docker & Deployment Module

This module contains the necessary configuration to run the entire mortgage underwriting stack locally via Docker Compose or in a containerized production environment.

#### Services

1.  **backend**: FastAPI application (Python 3.12). Handles core logic and API requests.
2.  **frontend**: React production build served by Nginx.
3.  **postgres**: PostgreSQL 15 database. Persists financial and applicant data.
4.  **redis**: Redis 7. Used for Celery brokering and caching.
5.  **celery**: Asynchronous worker for background tasks (e.g., PDF generation, email notifications).
6.  **celery-beat**: Scheduler for periodic tasks (e.g., daily compliance reports).
7.  **nginx**: Reverse proxy. Routes traffic to frontend (`/`) or backend (`/api`).
8.  **minio**: S3-compatible object storage. Stores applicant documents (encrypted).
9.  **dpt**: Document Processing Transformer. OCR and data extraction service.
10. **policy**: XML Policy Service. Retrieves regulatory rules.
11. **decision**: Underwriting Decision Service. Runs risk models.
12. **orchestrator**: API Gateway. Coordinates requests between frontend and microservices.

#### Quick Start

**Prerequisites:**
- Docker Engine & Docker Compose
- `uv` package manager (for local dev)

**Running the stack:**

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Start all services
docker-compose up -d

# 3. Check logs
docker-compose logs -f backend

# 4. Access the application
open http://localhost
```

#### Development Workflow

While Docker is used for dependencies (DB, Redis), the backend is typically run locally using `uv` for hot-reloading:

```bash
# Run dependencies only
docker-compose up -d postgres redis minio

# Run backend locally
uv run uvicorn mortgage_underwriting.main:app --reload --port 7000
```

#### Security & Compliance (PIPEDA)

- **Encryption**: All data at rest in MinIO is encrypted using AES-256. Keys are managed via `MINIO_SECRET_KEY`.
- **Logging**: Structlog is configured to redact PII (SIN, DOB) before outputting to stdout.
- **Networking**: Internal services (Policy, Decision) are not exposed to the host machine; they communicate only via the internal Docker network.

---

## Configuration Notes

This module relies on specific environment variables to configure the containerized services. Update `.env.example` with production-grade values before deployment.

### Environment Variables

```bash
# --- Application Configuration ---
ENVIRONMENT=development
DEBUG=false
API_V1_PREFIX=/api/v1
SECRET_KEY=change_this_production_secret_key

# --- Database (Postgres) ---
POSTGRES_USER=mortgage_admin
POSTGRES_PASSWORD=secure_password_123
POSTGRES_DB=mortgage_underwriting
DATABASE_URL=postgresql+asyncpg://mortgage_admin:secure_password_123@postgres:5432/mortgage_underwriting

# --- Redis (Celery) ---
REDIS_URL=redis://:redis_password@redis:6379/0
CELERY_BROKER_URL=redis://:redis_password@redis:6379/0

# --- MinIO (Document Storage) ---
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=complex_minio_secret
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=underwriting-docs
MINIO_USE_SSL=false

# --- External Microservices ---
POLICY_SERVICE_URL=http://policy:8001
DECISION_SERVICE_URL=http://decision:8002
DPT_SERVICE_URL=http://dpt:8003

# --- Observability ---
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
LOG_LEVEL=INFO
```

### Volume Persistence

The following Docker volumes are persisted to ensure data safety across container restarts:
- `postgres_data`: Database files.
- `redis_data`: Cache persistence.
- `minio_data`: Stored applicant documents.

### Networking

- **Internal Network**: `mortgage-net`. All services communicate within this network.
- **Exposed Ports**:
  - `80`: HTTP (Nginx)
  - `443`: HTTPS (Nginx) - *Requires SSL certificate mount*
  - `5432`: PostgreSQL (Mapped to host only for debugging; remove in prod)