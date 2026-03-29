# Docker & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Docker & Deployment Design Plan

**File:** `docs/design/docker-deployment.md`

---

## 1. Endpoints

### 1.1 Orchestrator Service Endpoints

| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/health/services` | Admin | - | `{"status": "healthy", "services": [{"name": "backend", "status": "healthy", "last_check": "iso8601", "latency_ms": 45}]}` | `ORCHESTRATOR_001` (Auth failed) |
| `GET` | `/api/v1/health/services/{service_name}` | Admin | - | `{"name": "backend", "status": "healthy", "checks": [{"name": "database", "status": "ok"}]}` | `ORCHESTRATOR_002` (Service not found) |
| `POST` | `/api/v1/deployments` | Admin | `{"service": "backend", "version": "1.2.3", "strategy": "rolling"}` | `{"deployment_id": "uuid", "status": "started"}` | `ORCHESTRATOR_003` (Invalid strategy) |
| `GET` | `/api/v1/deployments/{deployment_id}` | Admin | - | `{"deployment_id": "uuid", "status": "completed", "logs": [...]}` | `ORCHESTRATOR_004` (Deployment not found) |

### 1.2 Service Health Check Endpoints

| Service | Method | Path | Port | Response |
|---------|--------|------|------|----------|
| backend | `GET` | `/api/v1/health` | 7000 | `{"status": "healthy", "checks": {"db": "ok", "redis": "ok"}}` |
| orchestrator | `GET` | `/api/v1/health` | 7001 | `{"status": "healthy", "checks": {"celery": "ok"}}` |
| decision | `GET` | `/health` | 7002 | `{"status": "healthy"}` |
| policy | `GET` | `/health` | 7003 | `{"status": "healthy"}` |
| dpt | `GET` | `/health` | 7004 | `{"status": "healthy", "model_loaded": true}` |
| frontend | `GET` | `/health` | 3000 | `{"status": "healthy"}` |
| postgres | `TCP` | `pg_isready` | 5432 | Exit code 0 |
| redis | `CMD` | `redis-cli ping` | 6379 | `PONG` |
| minio | `GET` | `/minio/health/live` | 9000 | `200 OK` |

---

## 2. Models & Database

### 2.1 Deployment Monitoring Tables

```sql
-- Table: service_health
CREATE TABLE service_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL, -- backend, postgres, redis, etc.
    status VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'unhealthy', 'degraded')),
    latency_ms INTEGER,
    last_check TIMESTAMP WITH TIME ZONE NOT NULL,
    error_message TEXT,
    metadata JSONB, -- service-specific health data
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL, -- system user or admin
    
    -- Indexes
    CONSTRAINT unique_service UNIQUE (service_name)
);

CREATE INDEX idx_service_health_status ON service_health(status);
CREATE INDEX idx_service_health_last_check ON service_health(last_check);

-- Table: deployment_logs (FINTRAC auditable - 5 year retention)
CREATE TABLE deployment_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL, -- start, complete, rollback, fail
    status VARCHAR(20) NOT NULL,
    configuration_snapshot JSONB NOT NULL, -- immutable config at deployment time
    triggered_by VARCHAR(100) NOT NULL,
    
    -- FINTRAC compliance
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL,
    
    -- Indexes
    CONSTRAINT fk_deployment_id FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);

CREATE INDEX idx_deployment_logs_created_at ON deployment_logs(created_at);
CREATE INDEX idx_deployment_logs_service ON deployment_logs(service_name);

-- Table: deployments
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    strategy VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL
);

CREATE INDEX idx_deployments_status ON deployments(status);
CREATE INDEX idx_deployments_started_at ON deployments(started_at);
```

---

## 3. Business Logic

### 3.1 Health Check Orchestration Algorithm

```python
# Check frequency: every 30 seconds
# Failure threshold: 3 consecutive failures → mark unhealthy
# Recovery threshold: 2 consecutive successes → mark healthy

async def orchestrate_health_checks():
    services = ["backend", "postgres", "redis", "minio", "celery", "decision", "policy", "dpt"]
    results = []
    
    for service in services:
        try:
            # Circuit breaker pattern
            if circuit_breaker.is_open(service):
                results.append({"service": service, "status": "circuit_open"})
                continue
                
            health = await check_service_health(service)
            latency = calculate_latency(health.response_time)
            
            # Update service_health table with audit trail
            await update_service_health(
                service_name=service,
                status=determine_status(health),
                latency_ms=latency,
                created_by="system_health_orchestrator"
            )
            
            results.append({"service": service, "status": "checked"})
            
        except Exception as e:
            await log_health_check_failure(service, e)  # FINTRAC auditable log
            circuit_breaker.record_failure(service)
            
    return results
```

### 3.2 Deployment State Machine

```
pending → started → in_progress → (completed | failed | rollback)
    ↑           ↓
    └──────── rollback_completed
```

**Transition Rules:**
- `started`: Validate image exists, secrets mounted, resource quotas available
- `in_progress`: Execute health check on new instance before routing traffic
- `completed`: Update service registry, log immutable snapshot to `deployment_logs`
- `failed`: Automatic rollback to previous version if `strategy=rolling`
- `rollback`: Restore previous configuration, mark deployment as `rollback_completed`

---

## 4. Migrations

### 4.1 New Alembic Migration: `create_deployment_monitoring_tables`

```python
# migrations/versions/2024_xxxxx_create_deployment_monitoring.py

def upgrade():
    # Create service_health table
    op.create_table(
        'service_health',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('service_name', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('last_check', sa.DateTime(timezone=True), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name')
    )
    
    op.create_index('idx_service_health_status', 'service_health', ['status'])
    op.create_index('idx_service_health_last_check', 'service_health', ['last_check'])
    
    # Create deployments table
    op.create_table(
        'deployments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('service_name', sa.String(50), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('strategy', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_deployments_status', 'deployments', ['status'])
    op.create_index('idx_deployments_started_at', 'deployments', ['started_at'])
    
    # Create deployment_logs table (FINTRAC compliance)
    op.create_table(
        'deployment_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('deployment_id', sa.UUID(), nullable=False),
        sa.Column('service_name', sa.String(50), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('configuration_snapshot', sa.JSON(), nullable=False),
        sa.Column('triggered_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_deployment_logs_created_at', 'deployment_logs', ['created_at'])
    op.create_index('idx_deployment_logs_service', 'deployment_logs', ['service_name'])

def downgrade():
    op.drop_index('idx_deployment_logs_service')
    op.drop_index('idx_deployment_logs_created_at')
    op.drop_table('deployment_logs')
    op.drop_index('idx_deployments_started_at')
    op.drop_index('idx_deployments_status')
    op.drop_table('deployments')
    op.drop_index('idx_service_health_last_check')
    op.drop_index('idx_service_health_status')
    op.drop_table('service_health')
```

---

## 5. Security & Compliance

### 5.1 Secrets Management Strategy

```yaml
# docker-compose.production.yml
# DO NOT use .env file in production - use Docker secrets

secrets:
  database_password:
    external: true  # Managed by Docker swarm or external vault
  secret_key:
    external: true
  encryption_key:
    external: true
  minio_secret_key:
    external: true

services:
  backend:
    secrets:
      - source: database_password
        target: /run/secrets/database_password
        mode: 0400
      - source: secret_key
        target: /run/secrets/secret_key
        mode: 0400
```

**Local Development (.env.example only):**
```bash
# .env.example - NEVER commit real secrets
DATABASE_URL=postgresql://mortgage_uw:${DATABASE_PASSWORD}@postgres:5432/mortgage_uw
SECRET_KEY=dev-only-change-in-production
ENCRYPTION_KEY=dev-only-32-byte-key-for-aes-256
```

**PIPEDA Compliance:**
- SIN/DOB encryption keys loaded from `/run/secrets/encryption_key` (file mount)
- Keys never appear in environment variables or logs
- Encryption happens in `common/security.py` using `cryptography.fernet`

### 5.2 Network Isolation

```yaml
# docker-compose.yml
networks:
  frontend:    # React → Nginx only
    driver: bridge
  backend:     # Nginx → FastAPI services
    driver: bridge
    internal: true
  data:        # Services → PostgreSQL/Redis/MinIO
    driver: bridge
    internal: true
  services:    # Inter-service communication (orchestrator → decision/policy/dpt)
    driver: bridge
    internal: true
  monitoring:  # Prometheus, OpenTelemetry
    driver: bridge

# Service network assignments
services:
  nginx:
    networks:
      - frontend
      - backend
  backend:
    networks:
      - backend
      - data
      - services
  postgres:
    networks:
      - data
```

### 5.3 FINTRAC Compliance - Log Retention

```yaml
# docker-compose.production.yml
services:
  # Vector log aggregator for FINTRAC 5-year retention
  vector:
    image: timberio/vector:0.36-alpine
    configs:
      - source: vector_config
        target: /etc/vector/vector.toml
    volumes:
      - fintrac_logs:/var/log/fintrac
    environment:
      - RETENTION_DAYS=1825  # 5 years

  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
        labels: "fintrac_audit"
    # All audit logs written to /var/log/fintrac/ with structured JSON
```

**Log Structure (structlog):**
```json
{
  "timestamp": "2024-01-15T14:30:00Z",
  "level": "info",
  "event": "mortgage_application_submitted",
  "correlation_id": "uuid",
  "fintrac_audit": true,
  "user_id": "hashed_value",
  "transaction_amount": 150000.00,
  "transaction_type": "mortgage_application"
}
```

### 5.4 OSFI B-20 Compliance in Decision Service

```python
# decision/services.py - Stress test calculation
async def calculate_gds_tds(application: MortgageApplication) -> Ratios:
    # MANDATORY: Stress test rate = max(contract_rate + 2%, 5.25%)
    stress_rate = max(application.contract_rate + Decimal('2.00'), Decimal('5.25'))
    
    # PITH calculation using stress_rate
    monthly_payment = calculate_pith(
        principal=application.loan_amount,
        rate=stress_rate,
        amortization=application.amortization_years
    )
    
    gds = (monthly_payment / application.gross_monthly_income) * 100
    tds = ((monthly_payment + application.other_debts) / application.gross_monthly_income) * 100
    
    # Enforce hard limits: GDS ≤ 39%, TDS ≤ 44%
    if gds > Decimal('39.00') or tds > Decimal('44.00'):
        raise UnderwritingRejectedError(
            detail=f"OSFI B-20 limits exceeded: GDS={gds:.2f}%, TDS={tds:.2f}%",
            error_code="OSFI_B20_001"
        )
    
    # Audit log with calculation breakdown (no PII)
    logger.info(
        "osfi_b20_calculation",
        fintrac_audit=True,
        application_id=hash_id(application.id),
        stress_rate=stress_rate,
        gds=gds,
        tds=tds,
        thresholds={"gds_max": 39.00, "tds_max": 44.00}
    )
    
    return Ratios(gds=gds, tds=tds)
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Orchestrator Error Codes

| Exception Class | HTTP Status | Error Code | Message Pattern |
|-----------------|-------------|------------|-----------------|
| `ServiceNotFoundError` | 404 | `ORCHESTRATOR_001` | "Service '{name}' not found in registry" |
| `HealthCheckFailedError` | 503 | `ORCHESTRATOR_002` | "Service '{name}' health check failed: {detail}" |
| `DeploymentValidationError` | 422 | `ORCHESTRATOR_003` | "Invalid deployment strategy: {strategy}" |
| `DeploymentFailedError` | 409 | `ORCHESTRATOR_004` | "Deployment {id} failed: {reason}" |
| `CircuitBreakerOpenError` | 503 | `ORCHESTRATOR_005` | "Circuit breaker open for service '{name}'" |
| `SecretsMountError` | 500 | `ORCHESTRATOR_006` | "Required secret '{secret}' not mounted at {path}" |

### 6.2 FINTRAC Audit Error Codes

| Exception Class | HTTP Status | Error Code | Message Pattern |
|-----------------|-------------|------------|-----------------|
| `FintracLogImmutabilityError` | 500 | `FINTRAC_001` | "Audit log tampering detected: {log_id}" |
| `FintracRetentionViolation` | 403 | `FINTRAC_002` | "Log retention policy violation: {detail}" |

---

## 7. Dockerfile Specifications

### 7.1 Backend Dockerfile (Multi-stage)

```dockerfile
# syntax=docker/dockerfile:1.4

# Builder stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in virtual environment
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.12-slim as runtime

# Create non-root user
RUN groupadd -r mortgage && useradd -r -g mortgage mortgage

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder --chown=mortgage:mortgage /app/.venv /app/.venv

# Copy application code
COPY --chown=mortgage:mortgage . .

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD /app/.venv/bin/python -c "import httpx; httpx.get('http://localhost:7000/api/v1/health').raise_for_status()"

# Use virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Switch to non-root user
USER mortgage

EXPOSE 7000

CMD ["uvicorn", "modules.main:app", "--host", "0.0.0.0", "--port", "7000", "--workers", "4"]
```

### 7.2 Frontend Dockerfile (Multi-stage)

```dockerfile
# Build stage
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# Runtime stage
FROM nginx:alpine as runtime

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built React app
COPY --from=builder /app/build /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
```

### 7.3 PostgreSQL Dockerfile (Extension)

```dockerfile
FROM postgres:15-alpine

# Custom health check script for FINTRAC compliance
COPY healthcheck.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/healthcheck.sh

# Set retention policies for audit logs
COPY init-scripts/ /docker-entrypoint-initdb.d/

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

# FINTRAC: Ensure logs are written to persistent volume
VOLUME ["/var/lib/postgresql/data", "/var/log/postgresql"]
```

---

## 8. Resource Limits & Volumes

### 8.1 Resource Constraints (docker-compose.production.yml)

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
  
  postgres:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
  
  decision:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G  # Financial calculations are CPU-intensive
```

### 8.2 Volume Strategy

```yaml
volumes:
  postgres_data:
    driver: local
  postgres_logs:
    driver: local
  minio_data:
    driver: local
  uploads:
    driver: local
  fintrac_logs:
    driver: local
    driver_opts:
      type: none
      device: /mnt/fintrac-archive
      o: bind

services:
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - postgres_logs:/var/log/postgresql
      - type: bind
        source: /mnt/backup
        target: /backup
        read_only: false
  
  minio:
    volumes:
      - minio_data:/data
  
  backend:
    volumes:
      - uploads:/uploads
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 1G
```

---

## 9. Observability Configuration

### 9.1 OpenTelemetry Collector

```yaml
# docker-compose.monitoring.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.91.0
    configs:
      - source: otel_config
        target: /etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # gRPC
      - "4318:4318"   # HTTP
    networks:
      - monitoring

  prometheus:
    image: prom/prometheus:v2.48.0
    volumes:
      - prometheus_data:/prometheus
    networks:
      - monitoring

# Backend service env vars
ENVIRONMENT:
  OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
  OTEL_SERVICE_NAME: mortgage-underwriting-backend
  OTEL_METRICS_EXPORTER: prometheus
```

---

## 10. Deployment Commands

```bash
# Development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production (with secrets, monitoring, FINTRAC retention)
docker-compose -f docker-compose.yml -f docker-compose.production.yml -f docker-compose.monitoring.yml up -d

# Run health check
curl -H "X-API-Key: ${ADMIN_API_KEY}" http://localhost:7001/api/v1/health/services

# Deploy new version
curl -X POST -H "X-API-Key: ${ADMIN_API_KEY}" \
  -d '{"service": "backend", "version": "1.2.3", "strategy": "rolling"}' \
  http://localhost:7001/api/v1/deployments
```

---

**WARNING:** This design assumes Docker Swarm or Kubernetes for secret management in production. For local development, `.env.example` must be populated with dummy values and `.env` added to `.gitignore`. All FINTRAC audit logs must be backed up to immutable storage (e.g., AWS S3 with Object Lock) for 5-year retention compliance.