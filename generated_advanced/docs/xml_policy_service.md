# XML Policy Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# XML Policy Service - Architecture Design

## Executive Summary
High-performance microservice for managing Canadian lender mortgage policies in MISMO 3.0 XML format, featuring real-time evaluation, cryptographic audit trails, and sub-50ms response times for decision engine integration.

---

## 1. System Architecture

### 1.1 Component Overview
```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Gateway (Envoy)                          │
│                    OAuth2 Proxy + Rate Limiting                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    FastAPI REST Service Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Policy Mgmt  │  │ Evaluation   │  │  Admin       │              │
│  │   Controller │  │   Engine     │  │  Controller  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼──────────────────┼─────────────────┼───────────────────────┘
          │                  │                 │
┌─────────▼──────────────────▼─────────────────▼───────────────────────┐
│                    Service Orchestration Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ XSD Validator│  │ Cache Mgr    │  │ Version Mgr  │              │
│  │  (lxml)      │  │  (Redis)     │  │  (SQLAlchemy)│              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼──────────────────┼─────────────────┼───────────────────────┘
          │                  │                 │
┌─────────▼──────────────────▼─────────────────▼───────────────────────┐
│                        Data Persistence Layer                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ PostgreSQL 15+   │  │ Redis Cluster    │  │ MinIO (XML)      │  │
│  │  - Policies      │  │  - Parsed Cache  │  │  - Versioned     │  │
│  │  - Versions      │  │  - Session       │  │    XML Objects   │  │
│  │  - Audit Logs    │  │  - Rate Limits   │  │  - 7yr Retention │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Implementation Stack

### 2.1 Technology Selection
```json
{
  "runtime": {
    "python": "3.11.8",
    "justification": "Superior XML parsing (lxml), native Decimal support, async performance"
  },
  "framework": {
    "fastapi": "0.109.0",
    "justification": "Automatic OpenAPI 3.1 generation, async/await native, Pydantic validation"
  },
  "xml_processing": {
    "lxml": "5.1.0",
    "xsdata": "24.1",
    "justification": "XSD validation, MISMO 3.0 schema parsing, memory-efficient streaming"
  },
  "database": {
    "postgresql": "15.2",
    "redis": "7.2",
    "drivers": ["asyncpg", "redis-py"]
  },
  "security": {
    "oauth_provider": "Keycloak 23",
    "jwt_algorithm": "RS256",
    "mtls": "Envoy SDS"
  }
}
```

---

## 3. Data Architecture

### 3.1 PostgreSQL Schema
```sql
-- Lender Policies (Current Active)
CREATE TABLE lender_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id VARCHAR(20) NOT NULL,  -- e.g., 'RBC', 'TD'
    version VARCHAR(20) NOT NULL,     -- SemVer: '1.2.3'
    effective_date TIMESTAMPTZ NOT NULL,
    status policy_status_enum NOT NULL DEFAULT 'draft',
    xml_content TEXT NOT NULL CHECK (length(xml_content) > 0),
    parsed_config JSONB NOT NULL,     -- Denormalized for evaluation
    checksum VARCHAR(64) NOT NULL,    -- SHA256 for integrity
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_lender_version UNIQUE (lender_id, version)
);

CREATE INDEX idx_lender_active ON lender_policies (lender_id, status) 
WHERE status = 'active';

-- GIN index for JSONB queries
CREATE INDEX idx_parsed_config ON lender_policies USING GIN (parsed_config);

-- Version History (Immutable)
CREATE TABLE policy_versions (
    id UUID PRIMARY KEY,
    policy_id UUID REFERENCES lender_policies(id),
    version VARCHAR(20) NOT NULL,
    xml_content TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB  -- Contains diff, approval workflow data
);

-- Audit Log (Append-only, tamper-evident)
CREATE TABLE policy_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID,
    action audit_action_enum NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    details JSONB,
    previous_hash VARCHAR(64),  -- Chain for tamper detection
    current_hash VARCHAR(64) GENERATED ALWAYS AS (
        encode(digest(
            concat(id::text, policy_id::text, action::text, timestamp::text, previous_hash), 
            'sha256'
        ), 'hex')
    ) STORED
);
```

### 3.2 Redis Cache Strategy
```python
# Cache hierarchy
CACHE_CONFIG = {
    "L1_MEMORY": {
        "ttl": 300,  # 5 minutes
        "maxsize": 100,  # LRU cache
        "use_case": "Hot policies"
    },
    "L2_REDIS": {
        "ttl": 3600,  # 1 hour
        "key_pattern": "policy:{lender_id}:{version}:{checksum}",
        "use_case": "Parsed policy objects"
    },
    "EVALUATION_CACHE": {
        "ttl": 600,  # 10 minutes
        "key_pattern": "eval:{policy_id}:{app_hash}",
        "use_case": "Idempotent evaluations"
    }
}
```

---

## 4. XML Processing Pipeline

### 4.1 MISMO 3.0 Validation
```python
from lxml import etree
from xsdata.formats.dataclass.parsers import XmlParser
import hashlib

class XMLPolicyValidator:
    def __init__(self, xsd_path: str):
        self.schema = etree.XMLSchema(file=xsd_path)
        self.parser = XmlParser()
    
    async def validate_and_parse(self, xml_content: str) -> PolicyConfig:
        # 1. XSD Validation
        root = etree.fromstring(xml_content.encode())
        if not self.schema.validate(root):
            raise PolicyValidationError(self.schema.error_log)
        
        # 2. Checksum computation
        checksum = hashlib.sha256(xml_content.encode()).hexdigest()
        
        # 3. Parse to Pydantic model
        policy_data = self.parser.from_string(xml_content, LenderPolicyXml)
        
        # 4. Convert to internal Decimal-based model
        config = PolicyConfig(
            ltv=LTVConfig(
                insured=Decimal(str(policy_data.ltv.max_insured)),
                conventional=Decimal(str(policy_data.ltv.max_conventional))
            ),
            gds_max=Decimal(str(policy_data.gds_max)),
            tds_max=Decimal(str(policy_data.tds_max)),
            credit_score_min=int(policy_data.credit_score.min),
            amortization=AmortizationConfig(
                insured=int(policy_data.amortization.max_insured),
                conventional=int(policy_data.amortization.max_conventional)
            ),
            property_types=PropertyTypeFilter(
                allowed=set(policy_data.property_types.allowed.split(", ")),
                excluded=set(policy_data.property_types.excluded.split(", "))
            )
        )
        
        return config, checksum
```

### 4.2 Policy Evaluation Engine
```python
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

class MortgageApplication(BaseModel):
    loan_amount: Decimal = Field(decimal_places=2)
    property_value: Decimal = Field(decimal_places=2)
    gross_income: Decimal = Field(decimal_places=2)
    housing_expenses: Decimal = Field(decimal_places=2)
    total_debt_expenses: Decimal = Field(decimal_places=2)
    credit_score: int
    property_type: str
    is_insured: bool

class PolicyResult(BaseModel):
    approved: bool
    reasons: List[str]
    ltv_ratio: Decimal
    gds_ratio: Decimal
    tds_ratio: Decimal

class PolicyEvaluator:
    def evaluate(self, app: MortgageApplication, policy: PolicyConfig) -> PolicyResult:
        reasons = []
        
        # LTV Calculation (use quantize for precision)
        ltv = (app.loan_amount / app.property_value * Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        max_ltv = policy.ltv.insured if app.is_insured else policy.ltv.conventional
        
        if ltv > max_ltv:
            reasons.append(f"LTV {ltv}% exceeds maximum {max_ltv}%")
        
        # GDS Calculation
        gds = (app.housing_expenses / app.gross_income * Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if gds > policy.gds_max:
            reasons.append(f"GDS {gds}% exceeds maximum {policy.gds_max}%")
        
        # TDS Calculation
        tds = (app.total_debt_expenses / app.gross_income * Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if tds > policy.tds_max:
            reasons.append(f"TDS {tds}% exceeds maximum {policy.tds_max}%")
        
        # Credit Score
        if app.credit_score < policy.credit_score_min:
            reasons.append(f"Credit score {app.credit_score} below minimum {policy.credit_score_min}")
        
        # Property Type
        if app.property_type in policy.property_types.excluded:
            reasons.append(f"Property type {app.property_type} is excluded")
        elif app.property_type not in policy.property_types.allowed:
            reasons.append(f"Property type {app.property_type} not in allowed list")
        
        return PolicyResult(
            approved=len(reasons) == 0,
            reasons=reasons,
            ltv_ratio=ltv,
            gds_ratio=gds,
            tds_ratio=tds
        )
```

---

## 5. API Endpoints

### 5.1 REST API (FastAPI)
```python
@app.get("/policy/lenders", response_model=List[LenderPolicySummary])
async def list_lender_policies(
    status: PolicyStatus = Query(PolicyStatus.active),
    db: AsyncSession = Depends(get_db),
    user: JWTUser = Depends(verify_jwt)
):
    """List all loaded lender policies with optional status filter"""
    return await PolicyService(db).get_policies_by_status(status)

@app.get("/policy/{lender_id}", response_model=LenderPolicyDetail)
async def get_lender_policy(
    lender_id: str,
    version: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    cache: Redis = Depends(get_redis)
):
    """Get specific lender policy (cached)"""
    cache_key = f"policy:{lender_id}:{version or 'latest'}"
    if cached := await cache.get(cache_key):
        return json.loads(cached)
    
    policy = await PolicyService(db).get_policy(lender_id, version)
    await cache.setex(cache_key, 3600, policy.model_dump_json())
    return policy

@app.post("/policy/evaluate", response_model=PolicyEvaluationResult)
async def evaluate_policy(
    request: PolicyEvaluationRequest,
    evaluator: PolicyEvaluator = Depends(),
    cache: Redis = Depends(get_redis)
):
    """Evaluate mortgage application against policy (idempotent)"""
    # Create deterministic hash for caching
    app_hash = hashlib.md5(request.json().encode()).hexdigest()
    cache_key = f"eval:{request.lender_id}:{app_hash}"
    
    if cached := await cache.get(cache_key):
        return json.loads(cached)
    
    policy = await get_lender_policy(request.lender_id)
    result = evaluator.evaluate(request.application, policy.parsed_config)
    
    await cache.setex(cache_key, 600, result.model_dump_json())
    return result

@app.put("/policy/{lender_id}", status_code=202)
async def update_policy(
    lender_id: str,
    xml_file: UploadFile = File(...),
    change_reason: str = Form(...),
    effective_date: Optional[datetime] = Form(None),
    db: AsyncSession = Depends(get_db),
    validator: XMLPolicyValidator = Depends(),
    audit: AuditLogger = Depends(),
    user: JWTUser = Depends(verify_jwt)
):
    """Update lender policy with validation and audit trail"""
    xml_content = await xml_file.read()
    
    # Validate and parse
    config, checksum = await validator.validate_and_parse(xml_content.decode())
    
    # Create new version
    policy_service = PolicyService(db)
    new_version = await policy_service.create_version(
        lender_id=lender_id,
        xml_content=xml_content.decode(),
        config=config,
        checksum=checksum,
        change_reason=change_reason,
        effective_date=effective_date,
        created_by=user.sub
    )
    
    # Audit log
    await audit.log(
        policy_id=new_version.id,
        action="CREATE",
        user_id=user.sub,
        details={"version": new_version.version, "reason": change_reason}
    )
    
    # Invalidate cache
    await cache.delete(f"policy:{lender_id}:*")
    
    return {"policy_id": new_version.id, "version": new_version.version}
```

### 5.2 gRPC Service (High-Performance Evaluation)
```protobuf
syntax = "proto3";

service PolicyEvaluationService {
  rpc EvaluatePolicy(PolicyEvaluationRequest) returns (PolicyEvaluationResponse);
}

message PolicyEvaluationRequest {
  string lender_id = 1;
  MortgageApplication application = 2;
  string request_id = 3;  // For idempotency
}

message PolicyEvaluationResponse {
  bool approved = 1;
  repeated string reasons = 2;
  string request_id = 3;
  int32 processing_time_ms = 4;
}
```

---

## 6. Security & Compliance Architecture

### 6.1 Authentication Flow
```
Client → OAuth2 Proxy (Envoy) → JWT Validation → RBAC Check → Endpoint
  ↓
mTLS Verification (gRPC only) → Service Identity → Authorization
```

### 6.2 Audit Trail Implementation
```python
class AuditLogger:
    async def log(self, policy_id: UUID, action: str, user_id: str, details: dict):
        # Get previous hash for chain
        result = await db.execute(
            select(PolicyAuditLog.current_hash)
            .order_by(PolicyAuditLog.timestamp.desc())
            .limit(1)
        )
        previous_hash = result.scalar() or "0"
        
        # Create audit entry
        audit_entry = PolicyAuditLog(
            policy_id=policy_id,
            action=action,
            user_id=user_id,
            ip_address=get_client_ip(),
            details=details,
            previous_hash=previous_hash
        )
        
        # Write to primary DB
        db.add(audit_entry)
        await db.commit()
        
        # Async replication to immutable audit store
        await message_queue.publish(
            "audit.events",
            AuditEvent(
                timestamp=audit_entry.timestamp,
                compliance_hash=audit_entry.current_hash,
                payload=audit_entry
            )
        )
```

---

## 7. Operational Excellence

### 7.1 Caching Strategy Details
```python
# Multi-level cache with event-driven invalidation
class CacheManager:
    def __init__(self, redis: Redis):
        self.memory_cache = LRUCache(maxsize=100)
        self.redis = redis
    
    async def get_policy(self, lender_id: str, version: str) -> PolicyConfig:
        # L1: Memory
        key = f"{lender_id}:{version}"
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # L2: Redis
        cache_key = f"policy:{key}"
        if cached := await self.redis.get(cache_key):
            policy = PolicyConfig.parse_raw(cached)
            self.memory_cache[key] = policy
            return policy
        
        # L3: Database
        policy = await db.get_policy(lender_id, version)
        await self.redis.setex(cache_key, 3600, policy.json())
        self.memory_cache[key] = policy
        return policy
    
    async def invalidate(self, lender_id: str):
        """Event-driven invalidation on policy update"""
        pattern = f"policy:{lender_id}:*"
        await self.redis.delete_pattern(pattern)
        # Memory cache will naturally evict via LRU
```

### 7.2 Monitoring & Alerting
```yaml
prometheus_rules:
  - alert: PolicyEvaluationLatency
    expr: histogram_quantile(0.99, rate(policy_evaluation_duration_seconds_bucket[5m])) > 0.05
    for: 2m
    labels: {severity: critical}
    annotations: {summary: "99th percentile evaluation latency >50ms"}
  
  - alert: CacheHitRate
    expr: rate(policy_cache_hits[5m]) / rate(policy_cache_requests[5m]) < 0.8
    for: 5m
    labels: {severity: warning}
  
  - alert: XMLValidationFailures
    expr: increase(policy_xml_validation_failures[5m]) > 5
    for: 1m
    labels: {severity: high}
```

---

## 8. Deployment Architecture

### 8.1 Kubernetes Manifests
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xml-policy-service
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
      - name: policy-api
        image: mortgage-ca/policy-service:1.0.0
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        env:
        - name: DB_POOL_SIZE
          value: "20"
        - name: REDIS_CLUSTER
          value: "redis-cluster:6379"
        - name: XSD_PATH
          value: "/schemas/mismo_3.0.xsd"
        volumeMounts:
        - name: audit-log
          mountPath: /var/log/audit
          readOnly: false
      volumes:
      - name: audit-log
        persistentVolumeClaim:
          claimName: audit-log-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: policy-service-grpc
spec:
  ports:
  - port: 50051
    targetPort: 50051
    name: grpc
    appProtocol: grpc
  selector:
    app: xml-policy-service
```

---

## 9. Testing Strategy

### 9.1 Test Pyramid
```python
# Unit Tests (70%)
pytest tests/unit/test_evaluator.py::test_ltv_calculation
pytest tests/unit/test_validator.py::test_mismo_schema_validation

# Integration Tests (20%)
pytest tests/integration/test_policy_lifecycle.py
pytest tests/integration/test_cache_invalidation.py

# Contract Tests (10%)
# XML Schema compliance
pytest tests/contract/test_mismo_3_0_compliance.py
# gRPC proto contract
pytest tests/contract/test_grpc_evaluation_api.py
```

### 9.2 Performance Benchmarks
```bash
# Using k6 for load testing
k6 run --vus 100 --duration 30s scripts/evaluate_policy_load_test.js

# Target: 10,000 evaluations/sec with p99 < 50ms
```

---

## 10. Regulatory Compliance (Canada)

### 10.1 OSFI & FCAC Requirements
- **Data Residency**: All data stored in Canada (AWS ca-central-1)
- **Audit Retention**: 7-year immutable audit trail
- **Bilingual Support**: API responses in `en-CA` and `fr-CA`
- **Disaster Recovery**: RPO < 1min, RTO < 15min

### 10.2 Compliance Features
```python
# Language localization
class PolicyLocalization:
    def get_property_type_label(self, type_code: str, lang: str) -> str:
        return {
            "en-CA": {"single-family": "Single Family Home"},
            "fr-CA": {"single-family": "Maison unifamiliale"}
        }[lang][type_code]

# Geographic data residency
DB_CONFIG = {
    "host": "postgresql.ca-central-1.rds.amazonaws.com",
    "ssl_mode": "require",
    "region": "ca-central-1"
}
```

---

## 11. Rollback & Disaster Recovery

### 11.1 Version Rollback Procedure
```python
@app.post("/policy/{lender_id}/rollback")
async def rollback_policy(
    lender_id: str,
    target_version: str,
    reason: str,
    db: AsyncSession = Depends(get_db)
):
    """Atomic rollback to previous version"""
    async with db.begin():
        # Deactivate current
        await db.execute(
            update(LenderPolicy)
            .where(LenderPolicy.lender_id == lender_id)
            .where(LenderPolicy.status == "active")
            .values(status="retired")
        )
        
        # Activate target version
        await db.execute(
            update(LenderPolicy)
            .where(LenderPolicy.lender_id == lender_id)
            .where(LenderPolicy.version == target_version)
            .values(status="active", effective_date=now())
        )
        
        # Audit log
        await audit.log(
            action="ROLLBACK",
            details={"from": current_version, "to": target_version, "reason": reason}
        )
    
    # Event-driven cache purge
    await event_bus.publish("policy.rollback", {"lender_id": lender_id})
```

### 11.2 Backup Strategy
- **XML Files**: Versioned in MinIO with lifecycle policies (7-year retention)
- **Database**: Continuous archiving to AWS S3 Glacier (ca-central-1)
- **Cache**: Redis AOF persistence enabled

---

## 12. Performance Projections

| Metric | Target | Implementation |
|--------|--------|----------------|
| **Policy Load** | < 100ms | Async XML parsing + JSONB storage |
| **Evaluation p50** | < 10ms | In-memory L1 cache + Decimal math |
| **Evaluation p99** | < 50ms | Redis L2 cache + gRPC |
| **Throughput** | 10k req/s | 3 pods × 2k req/s + horizontal scaling |
| **Cache Hit Rate** | > 95% | Event-driven invalidation |

---

## 13. Implementation Roadmap

**Phase 1 (Weeks 1-2)**: Core parsing & validation
- [ ] Set up FastAPI skeleton with Pydantic models
- [ ] Implement lxml XSD validation for MISMO 3.0
- [ ] Create PostgreSQL schema with Alembic migrations

**Phase 2 (Weeks 3-4)**: CRUD & caching
- [ ] Implement policy upload/update endpoints
- [ ] Redis integration with multi-level caching
- [ ] Event-driven cache invalidation

**Phase 3 (Weeks 5-6)**: Evaluation engine & gRPC
- [ ] Policy evaluation logic with Decimal precision
- [ ] gRPC service for decision service integration
- [ ] Performance optimization (connection pooling)

**Phase 4 (Weeks 7-8)**: Security & compliance
- [ ] Keycloak OAuth2 integration
- [ ] mTLS for gRPC
- [ ] Audit logging with hash chain

**Phase 5 (Weeks 9-10)**: Production hardening
- [ ] Kubernetes deployment with Helm charts
- [ ] Prometheus monitoring & alerting
- [ ] Disaster recovery testing
- [ ] OSFI compliance audit

---

## 14. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| XML Schema Drift | Medium | High | Automated XSD validation in CI/CD |
| Cache Stampede | Low | Medium | Single-flight requests via Redis lock |
| Decimal Precision Errors | Low | Critical | 100% test coverage, `mypy --strict` |
| Audit Log Tampering | Low | Critical | Hash chain + append-only storage |
| Lender Policy Conflict | Medium | Medium | Semantic versioning with lender namespace |

---

**Architecture Owner**: Platform Engineering Team  
**Review Cycle**: Quarterly (OSFI regulation changes)  
**Last Updated**: 2024-Q1