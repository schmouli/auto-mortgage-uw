# Docker & Deployment Module

## Module README

### Overview
The Docker & Deployment module defines the containerized infrastructure and orchestration for the Canadian Mortgage Underwriting System. It utilizes Docker and Docker Compose to manage a microservices architecture consisting of 11 distinct services. This setup ensures isolation, scalability, and consistency across development, staging, and production environments.

### Architecture
The system is deployed as a set of interconnected containers:
1.  **Frontend**: React application build served by Nginx (Port 3000).
2.  **Backend**: FastAPI application handling core logic (Port 7000).
3.  **Orchestrator**: API Gateway layer coordinating requests between frontend and microservices.
4.  **Task Queue**: Redis for caching and message brokering.
5.  **Workers**: Celery (async tasks) and Celery Beat (scheduled tasks).
6.  **Data Store**: PostgreSQL 15 for persistent relational data.
7.  **Object Storage**: MinIO for secure document storage.
8.  **Microservices**:
    *   **DPT**: Document Processing Transformer.
    *   **Policy**: XML Policy service.
    *   **Decision**: Underwriting Decision engine.

### Network Topology
*   **Ingress**: External traffic enters via the main **Nginx** reverse proxy.
*   **Routing**:
    *   `/` routes to the **Frontend** (React).
    *   `/api` routes to the **Orchestrator** or **Backend**.
*   **Internal Communication**: Services communicate via internal Docker networks. The Backend/Orchestrator connects to PostgreSQL, Redis, and MinIO internally.

### Usage

**Starting the system:**
```bash
# Ensure .env is configured
docker-compose up -d
```

**Viewing logs:**
```bash
docker-compose logs -f backend
docker-compose logs -f orchestrator
```

**Stopping the system:**
```bash
docker-compose down
```

### Health Checks
All services expose a `/health` or `/metrics` endpoint where applicable to monitor status via Prometheus.

---

## Configuration Notes

### Environment Variables
This module relies on a shared `.env` file in the project root. Ensure the following variables are set for the deployment to function correctly.

#### Database & Cache
```ini
# PostgreSQL
POSTGRES_USER=mortgage_admin
POSTGRES_PASSWORD=secure_password_change_me
POSTGRES_DB=mortgage_db
DATABASE_URL=postgresql+asyncpg://mortgage_admin:secure_password_change_me@postgres:5432/mortgage_db

# Redis
REDIS_URL=redis://redis:6379/0
```

#### Application Security
```ini
# Backend & Orchestrator
SECRET_KEY=your_ultra_secure_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENVIRONMENT=development # or production
```

#### Object Storage (MinIO)
```ini
# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=mortgage-docs
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
USE_SSL=False
```

#### Microservice Endpoints
```ini
# Internal Service URLs
DPT_SERVICE_URL=http://dpt:8000
POLICY_SERVICE_URL=http://policy:8000
DECISION_SERVICE_URL=http://decision:8000
ORCHESTRATOR_URL=http://orchestrator:8000
```

#### Regulatory & Financial
```ini
# OSFI B-20
QUALIFYING_RATE_DEFAULT=5.25
STRESS_TEST_BUFFER=2.0

# Logging
LOG_LEVEL=INFO
CORRELATION_ID_HEADER=X-Correlation-ID
```

---

## API Documentation

**Note:** The Docker & Deployment module itself is an infrastructure configuration and does not expose direct API endpoints via a `routes.py` file. The API endpoints are exposed by the **Backend**, **Orchestrator**, and specific **Microservices** defined within this deployment context.

Please refer to the specific API documentation for:
*   `docs/api/Orchestrator.md`
*   `docs/api/Underwriting.md`
*   `docs/api/Borrowers.md`

---

## CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Docker & Deployment: Initial containerization setup for 11-service architecture.
- Infrastructure: Added PostgreSQL 15, Redis 7, and MinIO services.
- Reverse Proxy: Configured Nginx routing for React frontend and API gateway.
- Microservices: Defined orchestration for DPT, Policy, and Decision services.
```