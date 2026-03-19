# Design: Infrastructure & Deployment
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Infrastructure & Deployment Design

**File**: `docs/design/infrastructure-deployment.md`

---

## 1. Endpoints

### 1.1 Per-Service Health Checks
Each microservice must expose standardized probe endpoints:

**`GET /health` (Liveness Probe)**
- **Authentication**: None (public for Kubernetes/kubelet)
- **Response Schema**:
  ```json
  {
    "status": "healthy"|"unhealthy",
    "service": "postgres"|"redis"|"minio"|"dpt"|"policy"|"decision"|"orchestrator"|"frontend"|"celery",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "1.2.3"
  }
  ```
- **Status Codes**: 
  - `200 OK` if service process is alive
  - `503 Service Unavailable` if critical internal error
- **Error Code**: `INFRA_002` (HealthCheckFailedError)

**`GET /ready` (Readiness Probe)**
- **Authentication**: None
- **Response Schema**:
  ```json
  {
    "status": "ready"|"not_ready",
    "dependencies": {
      "postgres": "ok"|"fail",
      "redis": "ok"|"fail",
      "minio": "ok"|"fail"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
  ```
- **Status Codes**:
  - `200 OK` if all dependencies healthy
  - `503 Service Unavailable` if any dependency check fails
- **Error Code**: `INFRA_001` (ServiceUnavailableError)

### 1.2 System-Wide Status (Orchestrator Service)
**`GET /api/v1/system/status`**
- **Authentication**: JWT with `admin:read` scope
- **Request**: None
- **Response Schema**:
  ```python
  {
    "overall_status": str,  # "healthy"|"degraded"|"unavailable"
    "services": dict[str, dict],  # Detailed health per service
    "gpu_status": Optional[dict],  # GPU utilization for dpt
    "timestamp": str  # ISO8601
  }
  ```
- **Status Codes**: `200`, `401`, `403`
- **Error Code**: `INFRA_004` if configuration invalid

### 1.3 MLFlow Model Registry Endpoints
**`GET /api/v1/mlflow/models`**
- **Authentication**: Service-to-service mTLS token
- **Response**: List of registered model versions
- **Status Codes**: `200`, `401`, `503`

**`POST /api/v1/mlflow/models/{name}/deploy`**
- **Authentication**: Service token
- **Request Body**:
  ```json
  {
    "version": "string",
    "target_stage": "staging"|"production"
  }
  ```
- **Response**: `{"deployment_id": "uuid", "status": "in_progress"|"failed"}`
- **Status Codes**: `200`, `400`, `401`, `409`
- **Error Code**: `INFRA_003` (DeploymentFailedError)

---

## 2. Models & Database

**Not Applicable** – Infrastructure module does not define business domain ORM models. Configuration managed via:

- **`common/config.py`**: Pydantic v2 `BaseSettings` for service discovery, feature flags
- **Environment Variables**: `.env.development` (gitignored) and committed `.env.example` (dummy values only)
- **Kubernetes**: ConfigMaps for non-sensitive configuration, Secrets for sensitive data

**Infrastructure Audit Log Model** (for FINTRAC/OSFI compliance):
- **Table**: `infrastructure_audit_log`
- **Columns**:
  - `id`: UUID, primary key
  - `event_type`: VARCHAR(50) (e.g., `deployment`, `scale_up`, `secret_rotate`)
  - `service_name`: VARCHAR(100)
  - `status`: VARCHAR(20)
  - `message`: TEXT
  - `created_at`: TIMESTAMPTZ, indexed
- **Retention**: 5 years (FINTRAC requirement) – shipped to S3 Glacier
- **Indexes**: `idx_created_at` for time-range queries

---

## 3. Business Logic

### 3.1 Service Dependency Orchestration
**Startup Order** (enforced via Docker Compose `depends_on` and Kubernetes initContainers):
1. **postgres** (30s init)
2. **redis** (10s init)
3. **minio** (15s init)
4. **policy, decision** (wait for postgres)
5. **dpt** (wait for postgres, redis, minio; GPU detection)
6. **orchestrator** (wait for all above)
7. **frontend** (wait for orchestrator)
8. **celery** (wait for redis, postgres)

**Health Check Criteria**:
- **postgres**: `SELECT 1;` → timeout 5s
- **redis**: `PING` → timeout 3s
- **minio**: `HEAD /mortgage-documents` → timeout 5s
- **dpt**: NVIDIA driver available, VRAM > 2GB, model artifacts exist
- **MLFlow**: `GET /api/2.0/mlflow/experiments` → timeout 10s

### 3.2 Horizontal Pod Autoscaling Logic
**orchestrator**:
- **Metrics**: Custom `http_requests_per_second`, `cpu_utilization`
- **Scale Up**: RPS > 1000 OR CPU > 60% for 2 minutes
- **Scale Down**: RPS < 200 AND CPU < 30% for 5 minutes
- **Bounds**: Min 2 pods, Max 20 pods

**dpt**:
- **Metrics**: `gpu_utilization`, `pending_inference_jobs`
- **Scale Up**: GPU > 70% OR pending_jobs > 50 for 3 minutes
- **Scale Down**: GPU < 20% AND pending_jobs < 10 for 10 minutes
- **Bounds**: Min 1 GPU pod, Max 10 GPU pods
- **Node Selector**: `node-pool: gpu-nodes`

### 3.3 GPU Resource Management
- **Node Pool**: `n1-standard-4` with NVIDIA T4 or A10G
- **Taints**: `nvidia.com/gpu: "true"` (NoSchedule for non-GPU workloads)
- **Resource Requests**: `nvidia.com/gpu: 1` per dpt pod
- **Fallback**: If GPU unavailable, queue inference jobs with 24h TTL; alert on `INFRA_005`

### 3.4 MLFlow Model Lifecycle Orchestration
1. **Training**: Weekly Airflow DAG triggers retraining on new mortgage data
2. **Validation**: Model must achieve >95% accuracy on GDS/TDS stress test calculations
3. **Registration**: Log to MLFlow with OSFI-compliant audit tags
4. **Promotion**: Manual approval via `/api/v1/mlflow/models/{name}/deploy`
5. **Deployment**: Rolling update to dpt pods; old model kept for rollback

---

## 4. Migrations

### 4.1 Infrastructure as Code Versioning
- **Docker Images**: Tagged with `{git_sha}-{semver}` (e.g., `9f3a1b2-v1.2.3`)
- **Kubernetes Manifests**: Stored in `gitops/` repo, versioned by branch
- **Terraform**: State in S3 with DynamoDB locking; versioned modules
- **Rollback**: `kubectl rollout undo deployment/<service>` or Git revert + ArgoCD sync

### 4.2 Database Migration Strategy
- **Execution**: Kubernetes Job runs `alembic upgrade head` pre-deployment
- **Failure Policy**: Migration failure blocks entire deployment pipeline
- **Timeout**: 10 minutes maximum
- **Audit**: Migration ID logged to `infrastructure_audit_log` for FINTRAC traceability
- **Downgrade**: Manual `alembic downgrade` Job if rollback required

### 4.3 Configuration & Secrets Migration
- **ConfigMaps**: Versioned with suffix `-v1`, `-v2`; services mount specific version
- **Secrets**: Rotated via Kubernetes Operator every 90 days
- **Feature Flags**: Managed via Unleash; gradual rollout from 1% → 100%

---

## 5. Security & Compliance

### 5.1 Network Security Policies
```yaml
# Example: Only orchestrator can call decision service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
spec:
  podSelector:
    matchLabels: {app: decision}
  ingress:
  - from:
    - podSelector: {matchLabels: {app: orchestrator}}
    ports: [{protocol: TCP, port: 8000}]
```

### 5.2 Secrets Management
- **Local**: `.env.development` (never commit secrets; only `.env.example`)
- **Production**: 
  - AWS Secrets Manager (if AWS)
  - GCP Secret Manager (if GCP)
  - Azure Key Vault (if Azure)
- **Rotation**: Automatic every 90 days; access logged for PIPEDA audit
- **Encryption**: AES-256 at rest; TLS 1.3 in transit

### 5.3 PIPEDA Data Handling
- **Encryption at Rest**: 
  - S3/Cloud Storage: AES-256-SSE
  - PostgreSQL: `pgcrypto` extension for sensitive fields
  - Redis: Encryption enabled via ElastiCache/Memorystore
- **Encryption in Transit**: mTLS enforced between all services; SPIFFE/SPIRE for cert management
- **PII Logging**: SIN, DOB, income, banking data never appear in logs (enforced via structlog processors)

### 5.4 FINTRAC Compliance
- **5-Year Retention**: All logs shipped to S3 Glacier via Fluentd; lifecycle policy enforces 5-year minimum
- **Immutability**: S3 Object Lock (WORM) for audit logs
- **Transaction Tracking**: All financial transactions tagged with `transaction_type` and `amount_cad`; flagged if > $10,000
- **SIEM Integration**: Real-time log streaming to Splunk/Azure Sentinel

### 5.5 OSFI B-20 Auditability
- **Calculation Logging**: GDS/TDS stress test calculations logged to separate `underwriting_audit_log` service
- **Log Fields**: `correlation_id`, `qualifying_rate`, `gds_ratio`, `tds_ratio`, `timestamp`
- **Storage**: Write-once storage; cryptographically verifiable

### 5.6 Security Scanning Pipeline
- **Container Scanning**: Trivy scan in CI; block deployment on CRITICAL vulnerabilities
- **Dependency Scanning**: `uv run pip-audit` mandatory; fail on known CVEs
- **SAST**: Bandit scan for Python; Semgrep for pattern detection
- **DAST**: OWASP ZAP scan against staging before prod promotion

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ServiceUnavailableError` | 503 | INFRA_001 | "Service {name} is unavailable" | 3 consecutive health check failures |
| `HealthCheckFailedError` | 503 | INFRA_002 | "Health check failed: {detail}" | Dependency timeout or connection error |
| `DeploymentFailedError` | 500 | INFRA_003 | "Deployment {id} failed: {reason}" | Kubernetes rollout failure or image pull error |
| `ConfigurationError` | 500 | INFRA_004 | "Invalid configuration: {key}" | Missing required env var or malformed value |
| `GPUResourceError` | 503 | INFRA_005 | "GPU resources exhausted" | No GPU nodes available or VRAM insufficient |
| `SecretsRotationError` | 500 | INFRA_006 | "Secret rotation failed: {name}" | AWS/GCP Secret Manager API failure |
| `NetworkPolicyViolation` | 403 | INFRA_007 | "Network policy violation: {src}→{dst}" | Unauthorized service-to-service communication |

### 6.1 Error Response Schema
All infrastructure errors return JSON:
```json
{
  "detail": "Service postgres is unavailable: connection timeout after 5s",
  "error_code": "INFRA_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "correlation_id": "req-9f3a1b2c-d4e5-6f7g-8h9i-0j1k2l3m4n5o"
}
```

### 6.2 Retry and Circuit Breaker Logic
- **Health Checks**: Retry 3 times with exponential backoff (1s, 2s, 4s)
- **Database Connections**: SQLAlchemy `pool_pre_ping=True`; reconnect on failure
- **External APIs**: Circuit breaker opens after 5 failures in 60s; half-open after 30s

---

## 7. Additional Infrastructure Components (Integrated)

### 7.1 CI/CD Pipeline
- **Tool**: GitHub Actions (`.github/workflows/deploy.yml`)
- **Stages**: 
  1. **Build**: `docker build` + Trivy scan
  2. **Test**: `pytest -m unit` + `pytest -m integration`
  3. **Audit**: `uv run pip-audit`, `bandit`, `mypy`
  4. **Deploy Staging**: Auto-deploy to `staging` namespace
  5. **Deploy Production**: Manual approval via GitHub Environment
- **GitOps**: ArgoCD syncs `gitops/prod/` folder

### 7.2 Backup and Disaster Recovery
- **PostgreSQL**: RDS automated backups (7 days) + cross-region read replica (RPO 15min, RTO 1hr)
- **Object Storage**: S3 versioning + cross-region replication (RPO 0)
- **Redis**: ElastiCache daily snapshots + multi-AZ (RPO 5min)
- **Disaster Recovery Runbook**: Stored in `docs/runbooks/dr-procedure.md`

### 7.3 Monitoring and Alerting
- **Metrics**: Prometheus scraping `/metrics` endpoints every 15s
- **Tracing**: OpenTelemetry with Jaeger backend; sampled at 10%
- **Logging**: structlog JSON → stdout → Fluentd → Elasticsearch
- **Alerting**: PagerDuty (Critical), Slack #alerts (Warning)
- **Dashboards**: Grafana dashboards for service health, GPU utilization, mortgage application throughput

### 7.4 Load Balancing and CDN
- **Load Balancer**: AWS ALB with SSL termination, WAF OWASP ruleset, rate limit 100 req/s per IP
- **CDN**: CloudFront for frontend static assets (cache policy: 1 hour)
- **DDoS**: AWS Shield Standard + rate limiting at ALB
- **Origin**: ALB → ingress-nginx → FastAPI services

---

**Regulatory Compliance Summary**:
- **OSFI B-20**: Calculation audit logs stored in immutable S3 bucket with 5-year retention
- **FINTRAC**: All transaction logs flagged >$10k; 5-year retention enforced via S3 Glacier
- **CMHC**: LTV calculation audit trails stored separately; infrastructure guarantees availability
- **PIPEDA**: mTLS + AES-256 encryption; SIN/DOB never in logs; secrets rotated every 90 days