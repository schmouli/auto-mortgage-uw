# Docker & Deployment

## Module README

### Overview

The Docker & Deployment module manages the containerized infrastructure of the Canadian Mortgage Underwriting System. It utilizes Docker Compose to orchestrate 11 distinct services, ensuring a scalable, isolated, and maintainable environment.

The architecture follows a microservices pattern where the **Orchestrator** acts as the central API gateway, coordinating with internal services (Decision, Policy, DPT) and external infrastructure (PostgreSQL, Redis, MinIO). An Nginx reverse proxy manages traffic routing, serving the React frontend and proxying API requests to the backend.

### Architecture Diagram

```text
Internet
   |
[ Nginx (Port 80/443) ]
   |-----------------------|
   | (Static Files)        | (/api/v1/*)
[ Frontend (React) ]    [ Orchestrator (FastAPI) ]
                              |
          +-------------------+-------------------+
          |                   |                   |
   [ Decision Service ] [ Policy Service ] [ DPT Service ]
          |                   |                  
          +-------------------+-------------------+
                              |
          +---------------------------------------+
          |           [ Shared Data Layer ]       |
          |  [ PostgreSQL 15 ]   [ Redis 7 ]      |
          |                                       |
          |            [ Object Storage ]         |
          |            [ MinIO ]                  |
          +---------------------------------------+
                              |
                    [ Celery Beat ] ----> [ Celery Worker ]
```

### Services

1.  **backend**: Core FastAPI application handling mortgage logic.
2.  **frontend**: React build artifacts served by Nginx.
3.  **postgres**: PostgreSQL 15 database for persistent data.
4.  **redis**: In-memory data store for caching and Celery broker.
5.  **celery**: Asynchronous task worker for background jobs (e.g., PDF generation).
6.  **celery-beat**: Scheduler for periodic tasks (e.g., nightly compliance checks).
7.  **nginx**: Reverse proxy; routes `/` to frontend and `/api` to backend.
8.  **minio**: S3-compatible object storage for secure document uploads.
9.  **dpt**: Document Processing Transformer (OCR/Data extraction).
10. **policy**: XML Policy service for rule evaluation.
11. **decision**: Underwriting Decision service.
12. **orchestrator**: API Gateway layer coordinating requests to microservices.

### Usage Examples

#### Starting the Environment

To start all services in detached mode:

```bash
docker-compose up -d
```

#### Viewing Logs

To view logs for the orchestrator and backend services:

```bash
docker-compose logs -f orchestrator backend
```

#### Rebuilding Services

After changes to the `Dockerfile` or dependencies:

```bash
docker-compose up -d --build
```

#### Database Migrations

Apply Alembic migrations to the PostgreSQL container:

```bash
docker-compose exec backend alembic upgrade head
```

### Configuration Notes

*   **Networking**: All services communicate via a dedicated Docker network. Service discovery uses hostnames matching the service names (e.g., `postgres`, `redis`).
*   **Persistence**: PostgreSQL and MinIO data are persisted in named Docker volumes to survive container restarts.
*   **Security**:
    *   Inter-service communication is internal to the Docker network.
    *   Environment variables for secrets (DB passwords, API keys) are injected from the `.env` file.
    *   Ensure `MINIO_ROOT_USER` and `POSTGRES_PASSWORD` are set to strong values in production.

---

## Configuration Notes (.env.example)

```ini
# =============================================================================
# Docker & Deployment Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# Application (Backend/Orchestrator)
# -----------------------------------------------------------------------------
APP_NAME="Canadian Mortgage Underwriting System"
ENVIRONMENT=development
DEBUG=True
SECRET_KEY=change_me_in_production_please
API_V1_PREFIX=/api/v1

# -----------------------------------------------------------------------------
# Database (PostgreSQL 15)
# -----------------------------------------------------------------------------
POSTGRES_USER=mortgage_admin
POSTGRES_PASSWORD=secure_password_123
POSTGRES_DB=mortgage_db
DATABASE_URL=postgresql+asyncpg://mortgage_admin:secure_password_123@postgres:5432/mortgage_db

# -----------------------------------------------------------------------------
# Cache & Broker (Redis 7)
# -----------------------------------------------------------------------------
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# -----------------------------------------------------------------------------
# Object Storage (MinIO)
# -----------------------------------------------------------------------------
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=minio_secure_password
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=mortgage-docs
MINIO_SECURE=False # Set to True if using SSL in production

# -----------------------------------------------------------------------------
# Internal Service URLs
# -----------------------------------------------------------------------------
DPT_SERVICE_URL=http://dpt:8000
POLICY_SERVICE_URL=http://policy:8000
DECISION_SERVICE_URL=http://decision:8000

# -----------------------------------------------------------------------------
# Frontend
# -----------------------------------------------------------------------------
FRONTEND_PORT=3000

# -----------------------------------------------------------------------------
# Regulatory & Security
# -----------------------------------------------------------------------------
# AES-256 Key for PII encryption (SIN, DOB) - Must be 32 bytes url-safe base64 encoded
PII_ENCRYPTION_KEY=change_this_to_a_32_byte_url_safe_key
```

---

## CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Docker & Deployment: Initial Docker Compose configuration for 11 services.
- Infrastructure: Added Nginx reverse proxy configuration for routing /api and static assets.
- Infrastructure: Integrated MinIO for S3-compatible document storage.
- Infrastructure: Configured Celery Beat and Worker for background task processing.
- Services: Added stub definitions for DPT, Policy, Decision, and Orchestrator services.
```

---

## API Documentation

*Note: This module defines infrastructure and does not expose REST API endpoints directly. API interactions are handled by the `backend` and `orchestrator` services. Refer to their specific documentation for endpoint details.*