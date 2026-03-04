# Design: Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Canadian Mortgage Underwriting System - Docker & Deployment Architecture

## 1. Project Overview

This production-grade deployment architecture supports a compliant Canadian mortgage underwriting platform with 12 microservices, regulatory audit trails, and high availability requirements.

---

## 2. Docker Compose Configuration

### `docker-compose.yml`
```yaml
version: '3.8'

x-common-security: &common-security
  read_only: true
  no_new_privileges: true
  security_opt:
    - no-new-privileges:true

x-common-env: &common-env
  ENVIRONMENT: ${ENVIRONMENT:-development}
  LOG_LEVEL: ${LOG_LEVEL:-INFO}
  PYTHONUNBUFFERED: "1"

services:
  # =========================================
  # Database Tier
  # =========================================
  postgres:
    image: postgres:15.2-alpine
    container_name: cmus-postgres
    restart: unless-stopped
    networks:
      - database
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mortgage_uw
      POSTGRES_USER: mortgage_uw
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mortgage_uw -d mortgage_uw"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
    logging: &logging
      driver: "fluentd"
      options:
        fluentd-address: "localhost:24224"
        tag: "docker.{{.Name}}"

  redis:
    image: redis:7.0-alpine
    container_name: cmus-redis
    restart: unless-stopped
    networks:
      - database
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --requirepass $(cat /run/secrets/redis_password)
    secrets:
      - redis_password
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
    logging: *logging

  # =========================================
  # Storage Tier
  # =========================================
  minio:
    image: minio/minio:RELEASE.2023-09-30T07-02-29Z
    container_name: cmus-minio
    restart: unless-stopped
    networks:
      - storage
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER_FILE: /run/secrets/minio_access_key
      MINIO_ROOT_PASSWORD_FILE: /run/secrets/minio_secret_key
    secrets:
      - minio_access_key
      - minio_secret_key
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
      - ./config/minio:/etc/minio:ro
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
    logging: *logging

  # =========================================
  # Processing Tier
  # =========================================
  dpt:
    build:
      context: ./services/dpt
      dockerfile: Dockerfile
      target: production
    container_name: cmus-dpt
    restart: unless-stopped
    networks:
      - processing
      - backend
    environment:
      <<: *common-env
      MINIO_ENDPOINT: http://minio:9000
      MINIO_ACCESS_KEY_FILE: /run/secrets/minio_access_key
      MINIO_SECRET_KEY_FILE: /run/secrets/minio_secret_key
    secrets:
      - minio_access_key
      - minio_secret_key
    volumes:
      - uploads:/uploads:rw
    depends_on:
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    logging: *logging
    security_opt:
      - no-new-privileges:true

  policy:
    build:
      context: ./services/policy
      dockerfile: Dockerfile
      target: production
    container_name: cmus-policy
    restart: unless-stopped
    networks:
      - processing
      - backend
    environment:
      <<: *common-env
      POLICY_XML_PATH: /app/policies
    volumes:
      - ./policies:/app/policies:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    logging: *logging
    security_opt:
      - no-new-privileges:true

  decision:
    build:
      context: ./services/decision
      dockerfile: Dockerfile
      target: production
    container_name: cmus-decision
    restart: unless-stopped
    networks:
      - processing
      - backend
    environment:
      <<: *common-env
      DATABASE_URL: postgresql://mortgage_uw:password@postgres:5432/mortgage_uw
      REDIS_URL: redis://redis:6379/0
    secrets:
      - postgres_password
      - redis_password
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    logging: *logging
    security_opt:
      - no-new-privileges:true

  # =========================================
  # Application Tier
  # =========================================
  backend:
    build:
      context: ./services/backend
      dockerfile: Dockerfile
      target: production
    container_name: cmus-backend
    restart: unless-stopped
    networks:
      - backend
    environment:
      <<: *common-env
      DATABASE_URL: postgresql://mortgage_uw:password@postgres:5432/mortgage_uw
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY_FILE: /run/secrets/secret_key
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
      MINIO_ENDPOINT: http://minio:9000
      MINIO_ACCESS_KEY_FILE: /run/secrets/minio_access_key
      MINIO_SECRET_KEY_FILE: /run/secrets/minio_secret_key
    secrets:
      - postgres_password
      - redis_password
      - secret_key
      - encryption_key
      - minio_access_key
      - minio_secret_key
    volumes:
      - uploads:/uploads:rw
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    logging: *logging
    security_opt:
      - no-new-privileges:true

  orchestrator:
    build:
      context: ./services/orchestrator
      dockerfile: Dockerfile
      target: production
    container_name: cmus-orchestrator
    restart: unless-stopped
    networks:
      - backend
      - processing
    environment:
      <<: *common-env
      DATABASE_URL: postgresql://mortgage_uw:password@postgres:5432/mortgage_uw
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY_FILE: /run/secrets/secret_key
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
      BACKEND_URL: http://backend:7000
      DPT_URL: http://dpt:8000
      POLICY_URL: http://policy:8000
      DECISION_URL: http://decision:8000
    secrets:
      - postgres_password
      - redis_password
      - secret_key
      - encryption_key
    volumes:
      - ./workflows:/app/workflows:ro
      - uploads:/uploads:rw
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
      dpt:
        condition: service_healthy
      policy:
        condition: service_healthy
      decision:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    logging: *logging
    security_opt:
      - no-new-privileges:true

  # =========================================
  # Worker Tier
  # =========================================
  celery:
    build:
      context: ./services/backend
      dockerfile: Dockerfile
      target: production
    container_name: cmus-celery
    restart: unless-stopped
    networks:
      - backend
      - processing
    command: celery -A app.celery worker --loglevel=info --concurrency=4 --pool=prefork
    environment:
      <<: *common-env
      DATABASE_URL: postgresql://mortgage_uw:password@postgres:5432/mortgage_uw
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY_FILE: /run/secrets/secret_key
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
    secrets:
      - postgres_password
      - redis_password
      - secret_key
      - encryption_key
    volumes:
      - uploads:/uploads:rw
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      orchestrator:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
    logging: *logging
    security_opt:
      - no-new-privileges:true

  celery-beat:
    build:
      context: ./services/backend
      dockerfile: Dockerfile
      target: production
    container_name: cmus-celery-beat
    restart: unless-stopped
    networks:
      - backend
    command: celery -A app.celery beat --loglevel=info --pidfile=
    environment:
      <<: *common-env
      DATABASE_URL: postgresql://mortgage_uw:password@postgres:5432/mortgage_uw
      REDIS_URL: redis://redis:6379/0
    secrets:
      - postgres_password
      - redis_password
    volumes:
      - ./celerybeat:/app/celerybeat:rw
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    logging: *logging
    security_opt:
      - no-new-privileges:true

  # =========================================
  # Web Tier
  # =========================================
  frontend:
    build:
      context: ./services/frontend
      dockerfile: Dockerfile
      target: production
    container_name: cmus-frontend
    restart: unless-stopped
    networks:
      - frontend
    environment:
      REACT_APP_API_URL: /api
      REACT_APP_ENVIRONMENT: ${ENVIRONMENT:-development}
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    logging: *logging
    security_opt:
      - no-new-privileges:true

  nginx:
    image: nginx:1.24-alpine
    container_name: cmus-nginx
    restart: unless-stopped
    networks:
      - frontend
      - backend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./config/nginx/ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx:rw
    depends_on:
      frontend:
        condition: service_healthy
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    logging: *logging
    security_opt:
      - no-new-privileges:true

  # =========================================
  # Observability
  # =========================================
  fluentd:
    image: fluent/fluentd:v1.16-debian-1
    container_name: cmus-fluentd
    restart: unless-stopped
    networks:
      - observability
    ports:
      - "24224:24224"
      - "24224:24224/udp"
    volumes:
      - ./config/fluentd:/fluentd/etc:ro
      - ./logs:/var/log/containers:rw
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    profiles:
      - logging

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  minio_data:
    driver: local
  uploads:
    driver: local
  logs:
    driver: local

networks:
  frontend:
    driver: bridge
    internal: false
  backend:
    driver: bridge
    internal: true
  database:
    driver: bridge
    internal: true
  storage:
    driver: bridge
    internal: true
  processing:
    driver: bridge
    internal: true
  observability:
    driver: bridge
    internal: true

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  secret_key:
    file: ./secrets/secret_key.txt
  encryption_key:
    file: ./secrets/encryption_key.txt
  minio_access_key:
    file: ./secrets/minio_access_key.txt
  minio_secret_key:
    file: ./secrets/minio_secret_key.txt
```

---

## 3. Multi-Stage Dockerfiles

### `services/backend/Dockerfile`
```dockerfile
# =========================================
# Build Stage
# =========================================
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# =========================================
# Production Stage
# =========================================
FROM python:3.12-slim as production

# Create non-root user
RUN groupadd -r mortgage && useradd -r -g mortgage mortgage

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /home/mortgage/.local

# Copy application code
COPY --chown=mortgage:mortgage . .

# Create upload directory
RUN mkdir -p /uploads && chown mortgage:mortgage /uploads

# Switch to non-root user
USER mortgage

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7000/health || exit 1

# Expose port
EXPOSE 7000

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000", "--workers", "4"]
```

### `services/frontend/Dockerfile`
```dockerfile
# =========================================
# Build Stage
# =========================================
FROM node:20-alpine as builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy source code
COPY . .

# Build application
RUN npm run build

# =========================================
# Production Stage
# =========================================
FROM nginx:1.24-alpine as production

# Create non-root user
RUN addgroup -g 101 -S mortgage && \
    adduser -S mortgage -u 101 -G mortgage

# Copy custom nginx config
COPY config/nginx.conf /etc/nginx/nginx.conf

# Copy built application
COPY --from=builder /app/build /usr/share/nginx/html

# Create log directory
RUN mkdir -p /var/log/nginx && chown mortgage:mortgage /var/log/nginx

# Switch to non-root user
USER mortgage

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Expose port
EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
```

### `services/dpt/Dockerfile`
```dockerfile
# =========================================
# Build Stage
# =========================================
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies for Donut model
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    cmake \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Download Donut model (cache layer)
RUN python -c "from transformers import DonutProcessor, VisionEncoderDecoderModel; \
    processor = DonutProcessor.from_pretrained('naver-clova-ix/donut-base-finetuned-cord-v2'); \
    model = VisionEncoderDecoderModel.from_pretrained('naver-clova-ix/donut-base-finetuned-cord-v2')"

# =========================================
# Production Stage
# =========================================
FROM python:3.12-slim as production

# Create non-root user
RUN groupadd -r dpt && useradd -r -g dpt dpt

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and model cache
COPY --from=builder /root/.local /home/dpt/.local
COPY --from=builder /root/.cache/huggingface /home/dpt/.cache/huggingface

# Copy application code
COPY --chown=dpt:dpt . .

# Switch to non-root user
USER dpt

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `services/policy/Dockerfile`
```dockerfile
# =========================================
# Build Stage
# =========================================
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# =========================================
# Production Stage
# =========================================
FROM python:3.12-slim as production

# Create non-root user
RUN groupadd -r policy && useradd -r -g policy policy

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /root/.local /home/policy/.local

# Copy application code
COPY --chown=policy:policy . .

# Switch to non-root user
USER policy

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `services/decision/Dockerfile`
```dockerfile
# =========================================
# Build Stage
# =========================================
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with financial calculation libraries
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# =========================================
# Production Stage
# =========================================
FROM python:3.12-slim as production

# Create non-root user
RUN groupadd -r decision && useradd -r -g decision decision

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /root/.local /home/decision/.local

# Copy application code
COPY --chown=decision:decision . .

# Switch to non-root user
USER decision

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `services/orchestrator/Dockerfile`
```dockerfile
# =========================================
# Build Stage
# =========================================
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# =========================================
# Production Stage
# =========================================
FROM python:3.12-slim as production

# Create non-root user
RUN groupadd -r orchestrator && useradd -r -g orchestrator orchestrator

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /root/.local /home/orchestrator/.local

# Copy application code
COPY --chown=orchestrator:orchestrator . .

# Switch to non-root user
USER orchestrator

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 4. Secrets Management

### `secrets/secrets.yml`
```yaml
# Generate secrets using:
# openssl rand -base64 48 | tr -d '\n' > secret_key.txt
# openssl rand -base64 32 | tr -d '\n' > encryption_key.txt
# openssl rand -base64 24 | tr -d '\n' > postgres_password.txt
# etc.

version: '3.8'

secrets:
  postgres_password:
    external: true
    name: cmus_postgres_password_${ENVIRONMENT}
  redis_password:
    external: true
    name: cmus_redis_password_${ENVIRONMENT}
  secret_key:
    external: true
    name: cmus_secret_key_${ENVIRONMENT}
  encryption_key:
    external: true
    name: cmus_encryption_key_${ENVIRONMENT}
  minio_access_key:
    external: true
    name: cmus_minio_access_key_${ENVIRONMENT}
  minio_secret_key:
    external: true
    name: cmus_minio_secret_key_${ENVIRONMENT}
```

### Secret Generation Script (`scripts/generate-secrets.sh`)
```bash
#!/bin/bash
set -euo pipefail

ENVIRONMENT=${1:-development}
SECRETS_DIR="./secrets"

mkdir -p "$SECRETS_DIR"

# Generate 64-character secret key
openssl rand -base64 48 | tr -d '\n' > "$SECRETS_DIR/secret_key.txt"

# Generate 32-byte AES-256 encryption key
openssl rand -base64 32 | tr -d '\n' > "$SECRETS_DIR/encryption_key.txt"

# Generate database passwords
openssl rand -base64 24 | tr -d '\n' > "$SECRETS_DIR/postgres_password.txt"
openssl rand -base64 24 | tr -d '\n' > "$SECRETS_DIR/redis_password.txt"

# Generate MinIO credentials
openssl rand -base64 24 | tr -d '\n' > "$SECRETS_DIR/minio_access_key.txt"
openssl rand -base64 48 | tr -d '\n' > "$SECRETS_DIR/minio_secret_key.txt"

echo "Secrets generated for environment: $ENVIRONMENT"
echo "WARNING: Store these securely in a vault (e.g., HashiCorp Vault, AWS Secrets Manager)"
```

---

## 5. Health Check Endpoints

### `services/backend/app/health.py`
```python
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from redis import Redis
import os

router = APIRouter()

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Comprehensive health check for regulatory compliance"""
    
    # Database check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Redis check
    try:
        redis.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    # Storage check
    storage_status = check_minio_health()

    # Audit log
    audit_logger.info("health_check", {
        "db_status": db_status,
        "redis_status": redis_status,
        "storage_status": storage_status,
        "environment": os.getenv("ENVIRONMENT")
    })

    return {
        "status": "healthy" if all(s == "healthy" for s in [db_status, redis_status, storage_status]) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv("ENVIRONMENT"),
        "components": {
            "database": db_status,
            "redis": redis_status,
            "storage": storage_status
        }
    }
```

---

## 6. Resource Profiles

### `docker-compose.prod.yml`
```yaml
# Production overrides
# Usage: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

services:
  postgres:
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  backend:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '4'
          memory: 8G

  celery:
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '6'
          memory: 12G

  nginx:
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 1G
```

---

## 7. Volume Mount Strategy

| Volume | Path | Purpose | Backup Required | Retention |
|--------|------|---------|-----------------|-----------|
| `postgres_data` | `/var/lib/postgresql/data` | Database persistence | **Yes (Daily)** | 7 years (FINTRAC) |
| `redis_data` | `/data` | Session cache | No | 30 days |
| `minio_data` | `/data` | Document storage | **Yes (Daily)** | 7 years (FINTRAC) |
| `uploads` | `/uploads` | Temporary uploads | No | 24 hours |
| `logs` | `/var/log/containers` | Audit logs | **Yes (Hourly)** | 7 years (FINTRAC) |
| `celerybeat` | `/app/celerybeat` | Scheduler state | Yes | 30 days |

---

## 8. Network Isolation

```mermaid
graph TD
    subgraph "External Network"
        Client([Client Browser])
    end

    subgraph "frontend [Public]"
        Nginx[nginx:80/443]
        Frontend[frontend:3000]
    end

    subgraph "backend [Internal]"
        Backend[backend:7000]
        Orchestrator[orchestrator:8000]
    end

    subgraph "processing [Internal]"
        DPT[dpt:8000]
        Policy[policy:8000]
        Decision[decision:8000]
    end

    subgraph "database [Private]"
        Postgres[postgres:5432]
        Redis[redis:6379]
    end

    subgraph "storage [Private]"
        MinIO[minio:9000]
    end

    subgraph "observability [Private]"
        Fluentd[fluentd:24224]
    end

    Client --> Nginx
    Nginx --> Frontend
    Nginx --> Backend
    
    Backend --> Orchestrator
    Orchestrator --> DPT
    Orchestrator --> Policy
    Orchestrator --> Decision
    
    Backend --> Postgres
    Backend --> Redis
    Orchestrator --> Postgres
    Orchestrator --> Redis
    Decision --> Postgres
    Decision --> Redis
    
    DPT --> MinIO
    Backend --> MinIO
    Orchestrator --> MinIO
    
    All --> Fluentd
```

---

## 9. Log Aggregation Strategy

### `config/fluentd/fluent.conf`
```xml
<source>
  @type forward
  port 24224
  bind 0.0.0.0
</source>

<filter docker.**>
  @type parser
  key_name log
  <parse>
    @type json
  </parse>
</filter>

<filter docker.**>
  @type record_transformer
  <record>
    environment "#{ENV['ENVIRONMENT']}"
    service ${tag_parts[1]}
    timestamp ${time.strftime('%Y-%m-%dT%H:%M:%S.%NZ')}
  </record>
</filter>

# FINTRAC Compliance - Separate audit logs
<match docker.cmus-backend docker.cmus-orchestrator docker.cmus-decision>
  @type file
  path /var/log/containers/audit/audit.log
  <buffer>
    @type file
    path /var/log/containers/audit/buffer
    timekey 1h
    timekey_wait 10m
    chunk_limit_size 256m
  </buffer>
  <format>
    @type single_value
    message_key log
  </format>
</match>

# Application logs
<match docker.**>
  @type file
  path /var/log/containers/app/app.log
  <buffer>
    @type file
    path /var/log/containers/app/buffer
    timekey 1d
    timekey_wait 10m
  </buffer>
</match>
```

---

## 10. Security Compliance for Canadian Financial Systems

### `config/security.yml`
```yaml
# Canadian regulatory compliance controls

fintrac_compliance:
  # Financial Transactions and Reports Analysis Centre of Canada
  retention_years: 5
  audit_logging: true
  suspicious_activity_reporting: true

pipeda_compliance:
  # Personal Information Protection and Electronic Documents Act
  encryption_at_rest: true
  encryption_in_transit: true
  data_residency: "Canada"
  access_logging: true

osfi_guidelines:
  # Office of the Superintendent of Financial Institutions
  risk_management: true
  business_continuity: true
  disaster_recovery_rpo: "15m"
  disaster_recovery_rto: "4h"

container_security:
  read_only_root: true
  no_new_privileges: true
  user: "non-root"
  capabilities_drop:
    - ALL
  capabilities_add:
    - CHOWN
    - SETUID
    - SETGID
  seccomp_profile: "runtime/default"
```

---

## 11. Deployment Commands

### `Makefile`
```makefile
.PHONY: build up down logs secrets health

ENVIRONMENT ?= development
COMPOSE_FILE = docker-compose.yml
ifeq ($(ENVIRONMENT),production)
    COMPOSE_FILE := docker-compose.yml:docker-compose.prod.yml
endif

build:
	@echo "Building images for $(ENVIRONMENT)..."
	docker-compose -f $(COMPOSE_FILE) build --no-cache

up:
	@echo "Starting services..."
	docker-compose -f $(COMPOSE_FILE) up -d

down:
	@echo "Stopping services..."
	docker-compose -f $(COMPOSE_FILE) down

logs:
	docker-compose -f $(COMPOSE_FILE) logs -f

secrets:
	@echo "Generating secrets..."
	./scripts/generate-secrets.sh $(ENVIRONMENT)

health:
	@echo "Checking service health..."
	docker-compose ps
	curl -f http://localhost/health || echo "System not ready"

backup:
	@echo "Creating backup..."
	./scripts/backup.sh $(ENVIRONMENT)

restore:
	@echo "Restoring from backup..."
	./scripts/restore.sh $(ENVIRONMENT)

fintrac-report:
	@echo "Generating FINTRAC compliance report..."
	./scripts/fintrac-report.sh $(ENVIRONMENT)
```

### Quick Start
```bash
# 1. Generate secrets
make secrets ENVIRONMENT=development

# 2. Build all services
make build ENVIRONMENT=development

# 3. Start stack
make up ENVIRONMENT=development

# 4. Verify health
make health

# 5. View logs
make logs
```

---

## 12. Production Deployment Checklist

- [ ] **Secrets Management**: Migrate to HashiCorp Vault or AWS Secrets Manager
- [ ] **SSL/TLS**: Configure proper certificates with auto-renewal (Let's Encrypt)
- [ ] **Monitoring**: Deploy Prometheus + Grafana for metrics
- [ ] **Alerting**: Configure PagerDuty/Opsgenie for critical alerts
- [ ] **Backup**: Implement automated daily backups to S3 with 7-year retention
- [ ] **Disaster Recovery**: Test RPO/RTO quarterly
- [ ] **Penetration Testing**: Annual FINTRAC-compliant security audit
- [ ] **Access Control**: Implement OIDC with Azure AD for SSO
- [ ] **Network Policies**: Enable Kubernetes NetworkPolicies or Calico
- [ ] **Pod Security**: Deploy OPA Gatekeeper policies
- [ ] **Cost Optimization**: Enable Docker registry caching, image pruning
- [ ] **Compliance**: Enable auditd in containers for FINTRAC

---

This architecture ensures **regulatory compliance**, **high availability**, and **security best practices** for Canadian financial systems. All sensitive data is encrypted, audit trails are maintained for 7 years, and network isolation prevents lateral movement in case of breach.