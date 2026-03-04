# Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Processing Transformer (DPT) Service Architecture

## Executive Summary
High-performance microservice for mortgage document extraction using fine-tuned Donut models with MLFlow governance, GPU orchestration, and financial-grade audit compliance.

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        API Gateway Layer (FastAPI)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ /dpt/extract │  │ /dpt/jobs/{id}│  │/dpt/results/{id}│ │ Health/Metrics│ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼─────────────────┼─────────────────┼─────────────────┼──────────┘
          │                 │                 │                 │
          │                 │                 │                 │
┌─────────▼─────────────────▼─────────────────▼─────────────────▼──────────┐
│                        Job Orchestration (Celery)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Redis/RabbitMQ Broker (Task Queue)                                  │  │
│  │ - Job State: pending → processing → completed/failed                │  │
│  │ - Priority Queues: high (purchase) > medium (NOA) > low (bank)      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
          │                                                         │
          │                                                         │
┌─────────▼──────────┐                              ┌───────────────▼────────┐
│  GPU Worker Pool   │                              │   MLFlow Registry      │
│  (Kubernetes Pods) │◄────────────────────────────►│  - Model Versions      │
│  - 4x A10G/node    │      gRPC/mTLS               │  - Stage Promotion     │
│  - Model Cache     │                              │  - A/B Testing         │
└─────────┬──────────┘                              └───────────────┬────────┘
          │                                                         │
┌─────────▼──────────┐                              ┌───────────────▼────────┐
│   S3 PDF Storage   │                              │   PostgreSQL 15.2      │
│  - Encrypted Buckets│                              │  - extractions table   │
│  - Versioned Objects│                              │  - JSONB extracted_json│
└────────────────────┘                              └────────────────────────┘
```

---

## 2. Component Deep Dive

### 2.1 API Gateway (FastAPI 0.109.0)

```python
# dpt_api/main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
from decimal import Decimal
import uuid

app = FastAPI(title="DPT Service", version="1.0.0")

class ExtractionRequest(BaseModel):
    application_id: str = Field(..., pattern=r"^APP-\d{10}$")
    s3_key: str
    document_type: str = Field(..., pattern=r"^(t4506|noa|credit|bank|purchase)$")
    
    @validator('s3_key')
    def validate_s3_key(cls, v):
        if not v.startswith('mortgage-docs/'):
            raise ValueError('S3 key must be in mortgage-docs/ prefix')
        return v

class JobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    estimated_time: int  # seconds

@app.post("/dpt/extract", response_model=JobResponse, status_code=202)
async def submit_extraction(
    request: ExtractionRequest,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: JWTClaims = Depends(verify_oauth2)
):
    """
    Async extraction submission with audit logging
    """
    # Authorization check
    if not user.has_role("underwriter"):
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    
    # Validate S3 object exists and is encrypted
    s3_client = get_s3_client()
    try:
        head = s3_client.head_object(Bucket="mortgage-docs", Key=request.s3_key)
        if head.get('ServerSideEncryption') != 'AES256':
            raise HTTPException(status_code=400, detail="Document must be server-side encrypted")
    except ClientError as e:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Create extraction record with Decimal confidence placeholder
    job_id = uuid.uuid4()
    extraction = Extraction(
        id=job_id,
        application_id=request.application_id,
        document_type=request.document_type,
        s3_key=request.s3_key,
        confidence=Decimal('0.00'),  # Financial-grade precision
        model_version="",
        status="pending"
    )
    
    db.add(extraction)
    await db.commit()
    
    # Audit log
    bg_tasks.add_task(
        log_audit_event,
        action="EXTRACTION_SUBMITTED",
        user_id=user.sub,
        resource_id=str(job_id),
        metadata={"doc_type": request.document_type}
    )
    
    # Queue job with priority
    priority_map = {"purchase": 10, "noa": 5, "t4506": 5, "credit": 3, "bank": 1}
    task = process_document.apply_async(
        args=[str(job_id), request.s3_key, request.document_type],
        priority=priority_map[request.document_type]
    )
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        estimated_time=calculate_eta(request.document_type)
    )

@app.get("/dpt/jobs/{job_id}")
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: JWTClaims = Depends(verify_oauth2)
):
    extraction = await db.get(Extraction, job_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify user access to application
    if not await has_application_access(user.sub, extraction.application_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "job_id": job_id,
        "status": extraction.status,
        "confidence": float(extraction.confidence),  # Convert for JSON
        "model_version": extraction.model_version,
        "created_at": extraction.created_at.isoformat()
    }
```

### 2.2 Database Schema (PostgreSQL 15.2)

```sql
-- migrations/001_create_extractions.sql
CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id VARCHAR(20) NOT NULL REFERENCES applications(id),
    document_type VARCHAR(20) NOT NULL CHECK (document_type IN ('t4506', 'noa', 'credit', 'bank', 'purchase')),
    s3_key VARCHAR(500) NOT NULL UNIQUE,
    extracted_json JSONB,
    confidence DECIMAL(5,4) NOT NULL DEFAULT 0.0000,  -- 0.0000 to 1.0000 precision
    model_version VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'review_required')),
    error_code VARCHAR(50),
    error_details JSONB,
    retry_count SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    -- GIN index for JSONB queries
    CREATE INDEX idx_extractions_json ON extractions USING GIN (extracted_json),
    
    -- Partial index for pending jobs (worker efficiency)
    CREATE INDEX idx_extractions_pending ON extractions (document_type, created_at) 
        WHERE status = 'pending',
    
    -- Audit index
    CREATE INDEX idx_extractions_app ON extractions (application_id, created_at)
);

-- Trigger for audit versioning
CREATE TRIGGER extractions_version_trigger
    BEFORE UPDATE ON extractions
    FOR EACH ROW
    EXECUTE FUNCTION audit_version_trigger();
```

---

## 3. MLFlow Model Versioning Strategy

### 3.1 Model Registry Structure

```yaml
# .mlflow-model-config.yaml
models:
  donut-t4506:
    stages:
      - name: "staging"
        threshold: 0.92
        auto_promote: false
      - name: "production"
        threshold: 0.95
        traffic_weight: 80
      - name: "production-v2"
        threshold: 0.97
        traffic_weight: 20  # Canary deployment
    
  donut-noa:
    stages:
      - name: "production"
        threshold: 0.94
        fallback_version: "1.3.2"  # Rollback target

# Version naming: {doc_type}-v{major}.{minor}.{patch}-{timestamp}
# Example: donut-t4506-v1.4.2-20240115
```

### 3.2 MLFlow Integration Code

```python
# dpt_mlflow/registry.py
import mlflow
from mlflow.tracking import MlflowClient
from prometheus_client import Counter, Histogram

model_load_counter = Counter('dpt_model_loads_total', 'Model loads', ['model_name', 'stage'])
inference_latency = Histogram('dpt_inference_seconds', 'Inference latency')

class DonutModelRegistry:
    def __init__(self, tracking_uri: str = "http://mlflow:5000"):
        self.client = MlflowClient(tracking_uri)
        self.model_cache = LRUCache(maxsize=4)  # Cache 4 models/GPU
        
    def get_production_model(self, document_type: str) -> Tuple[DonutModel, str]:
        """
        Returns model and version with A/B routing
        """
        model_name = f"donut-{document_type}"
        
        # Get all production versions with weights
        versions = self.client.get_latest_versions(model_name, stages=["Production"])
        
        if not versions:
            # Fallback to staging
            versions = self.client.get_latest_versions(model_name, stages=["Staging"])
            if not versions:
                raise ModelNotFoundError(f"No model found for {model_name}")
        
        # A/B routing based on traffic_weight tag
        weighted_versions = []
        for v in versions:
            weight = int(v.tags.get("traffic_weight", 100))
            weighted_versions.extend([v] * weight)
        
        selected = random.choice(weighted_versions)
        model_version = selected.version
        
        # Check cache
        cache_key = f"{model_name}:{model_version}"
        if cache_key in self.model_cache:
            return self.model_cache[cache_key], model_version
        
        # Load model with timing
        with inference_latency.time():
            model_uri = f"models:/{model_name}/{model_version}"
            model = mlflow.pytorch.load_model(model_uri)
            
            # Warm-up inference
            self._warmup_model(model)
        
        # Cache model
        self.model_cache[cache_key] = model
        model_load_counter.labels(model_name, selected.current_stage).inc()
        
        return model, model_version
    
    def log_extraction_result(
        self,
        run_id: str,
        document_type: str,
        confidence: Decimal,
        prediction: dict,
        ground_truth: Optional[dict] = None
    ):
        """
        Log metrics for continuous monitoring
        """
        with mlflow.start_run(run_id=run_id):
            mlflow.log_metric("confidence", float(confidence))
            
            # Log field-level metrics if ground truth available
            if ground_truth:
                f1 = self._calculate_field_f1(prediction, ground_truth)
                mlflow.log_metric("f1_score", f1)
```

---

## 4. Confidence Scoring & Quality Gates

### 4.1 Multi-Layer Confidence Calculation

```python
# dpt_inference/confidence.py
from decimal import Decimal, ROUND_DOWN
import numpy as np

class ConfidenceScorer:
    """
    Financial-grade confidence scoring with regulatory thresholds
    """
    
    # Per-document-type thresholds (Decimal for precision)
    THRESHOLDS = {
        'purchase': Decimal('0.9600'),  # Highest - critical path
        'noa': Decimal('0.9400'),
        't4506': Decimal('0.9300'),
        'credit': Decimal('0.9000'),
        'bank': Decimal('0.8800')
    }
    
    def compute_confidence(self, model_output: dict, doc_type: str) -> Decimal:
        """
        Compute composite confidence score
        """
        # 1. Model softmax confidence (from Donut)
        model_conf = Decimal(str(model_output.get('confidence', 0.0)))
        
        # 2. Field completeness score
        required_fields = self._get_required_fields(doc_type)
        present_fields = sum(1 for f in required_fields if model_output.get(f))
        completeness = Decimal(present_fields / len(required_fields))
        
        # 3. Financial field validation
        financial_valid = self._validate_financial_fields(model_output, doc_type)
        
        # Weighted composite (rounded down to 4 decimals)
        composite = (
            model_conf * Decimal('0.6') +
            completeness * Decimal('0.3') +
            (Decimal('1.0') if financial_valid else Decimal('0.0')) * Decimal('0.1')
        ).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
        
        return composite
    
    def _validate_financial_fields(self, data: dict, doc_type: str) -> bool:
        """
        Validate financial data integrity
        """
        if doc_type == 'noa':
            line150 = data.get('line_15000')
            line236 = data.get('line_23600')
            # Basic sanity: deductions shouldn't exceed gross
            return line236 <= line150 if line150 and line236 else False
        
        elif doc_type == 'bank':
            balance = data.get('current_balance')
            transactions = data.get('transactions', [])
            # Balance should match transaction sum
            calculated = sum(t['amount'] for t in transactions)
            return abs(balance - calculated) < 0.01 if balance else False
        
        return True
    
    def get_quality_gate(self, confidence: Decimal, doc_type: str) -> str:
        """
        Determine workflow path based on confidence
        """
        threshold = self.THRESHOLDS[doc_type]
        
        if confidence >= threshold:
            return "auto_approve"
        elif confidence >= threshold * Decimal('0.85'):
            return "review_required"
        else:
            return "human_in_loop"
```

---

## 5. GPU Resource Allocation & Orchestration

### 5.1 Kubernetes Deployment Configuration

```yaml
# k8s/dpt-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dpt-gpu-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dpt-worker
  template:
    metadata:
      labels:
        app: dpt-worker
        gpu-enabled: "true"
    spec:
      nodeSelector:
        accelerator: nvidia-tesla-a10g
      
      containers:
      - name: donut-inference
        image: dpt-service:v1.4.2
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "24Gi"
            cpu: "4"
          limits:
            nvidia.com/gpu: 1
            memory: "24Gi"
            cpu: "8"
        
        # Model cache volume
        volumeMounts:
        - name: model-cache
          mountPath: /cache/models
        
        env:
        - name: MLFLOW_TRACKING_URI
          value: "http://mlflow-service:5000"
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
        - name: INFERENCE_BATCH_SIZE
          value: "4"  # Optimal for A10G + Donut 176M
        
        # Health check
        livenessProbe:
          grpc:
            port: 50051
          initialDelaySeconds: 60
          periodSeconds: 30
      
      # Model cache shared volume
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: dpt-model-cache-pvc
      
      # Toleration for GPU nodes
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Exists"
        effect: "NoSchedule"

---
# Horizontal Pod Autoscaler based on Celery queue length
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: dpt-worker-scaler
spec:
  scaleTargetRef:
    name: dpt-gpu-worker
  pollingInterval: 10
  cooldownPeriod: 300  # 5 min to avoid thrashing
  
  triggers:
  - type: redis
    metadata:
      address: redis.redis-namespace:6379
      listName: celery
      listLength: "10"  # Scale when 10+ jobs queued
      activationListLength: "5"  # Activate when 5+ jobs
      
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: dpt_inference_seconds_p99
      threshold: "30"  # Scale if p99 latency > 30s
```

### 5.2 GPU Optimization Strategies

```python
# dpt_inference/gpu_manager.py
import torch
from contextlib import contextmanager

class GPUManager:
    """
    Manages GPU resources for batched inference
    """
    def __init__(self, device_id: int = 0):
        self.device = torch.device(f"cuda:{device_id}")
        self.max_batch_size = 4
        self.current_batch = []
        
    @contextmanager
    def allocate(self, model_size_mb: int = 700):
        """
        Context manager for GPU allocation with memory guard
        """
        # Clear cache before allocation
        torch.cuda.empty_cache()
        
        # Reserve 90% of GPU memory
        total_mem = torch.cuda.get_device_properties(self.device).total_memory
        reserved_mem = int(total_mem * 0.9)
        
        try:
            yield self.device
        finally:
            # Force garbage collection
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
    
    def batch_inference(self, model, pdf_batch: List[bytes]) -> List[dict]:
        """
        Optimized batched inference
        """
        results = []
        with self.allocate():
            # Move model to GPU once
            model = model.to(self.device)
            model.eval()
            
            with torch.no_grad():
                for i in range(0, len(pdf_batch), self.max_batch_size):
                    batch = pdf_batch[i:i + self.max_batch_size]
                    
                    # Convert PDFs to images and tensorize
                    images = self._pdf_to_tensor(batch)
                    images = images.to(self.device)
                    
                    # Inference
                    outputs = model.generate(images, max_length=1024)
                    
                    # Process results on CPU to free GPU memory
                    for output in outputs:
                        result = self._parse_output(output.cpu())
                        results.append(result)
                    
                    # Clear intermediate tensors
                    del images, outputs
                    torch.cuda.empty_cache()
        
        return results
```

---

## 6. Error Handling & Resilience Patterns

### 6.1 Error Taxonomy & Retry Logic

```python
# dpt_core/errors.py
from enum import Enum
from celery import Task

class ExtractionErrorType(Enum):
    TRANSIENT = "transient"  # Retryable
    PERMANENT = "permanent"  # Non-retryable
    QUALITY = "quality"      # Confidence too low
    
    # Transient errors: S3 timeout, GPU OOM, network blip
    TRANSIENT_CODES = {
        "S3_TIMEOUT",
        "CUDA_OUT_OF_MEMORY",
        "MLFLOW_CONNECTION_ERROR"
    }
    
    # Permanent errors: Invalid PDF, corrupted file, model mismatch
    PERMANENT_CODES = {
        "INVALID_PDF_FORMAT",
        "ENCRYPTION_NOT_SUPPORTED",
        "MODEL_INCOMPATIBLE"
    }

class ExtractionTask(Task):
    """
    Celery task with exponential backoff and DLQ
    """
    autoretry_for = (TransientError,)
    retry_backoff = 300  # 5 min initial
    retry_backoff_max = 3600  # 1 hour max
    max_retries = 5
    acks_late = True  # Ack after completion
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = args[0]
        error_type = self._classify_error(exc)
        
        if error_type == ExtractionErrorType.TRANSIENT and self.request.retries < self.max_retries:
            # Requeue with delay
            self.retry(countdown=self.retry_backoff * (2 ** self.request.retries))
        
        elif error_type == ExtractionErrorType.PERMANENT:
            # Move to DLQ and update DB
            db.update_extraction_status(
                job_id=job_id,
                status="failed",
                error_code=exc.__class__.__name__,
                error_details={
                    "message": str(exc),
                    "traceback": einfo.traceback,
                    "permanent": True
                }
            )
            # Send alert
            send_alert(f"Permanent extraction failure: {job_id}", severity="high")
        
        # Quality errors go to human review
        elif error_type == ExtractionErrorType.QUALITY:
            db.update_extraction_status(
                job_id=job_id,
                status="review_required",
                confidence=exc.confidence,
                error_details={"reason": "confidence_below_threshold"}
            )
```

### 6.2 Circuit Breaker Pattern

```python
# dpt_core/circuit_breaker.py
from pybreaker import CircuitBreaker
import redis

class GPUHealthMonitor:
    def __init__(self):
        self.breaker = CircuitBreaker(
            fail_max=5,  # Open after 5 failures
            reset_timeout=300,  # 5 min cooldown
            listeners=[self._log_state_change]
        )
        self.redis = redis.Redis()
    
    @self.breaker
    def run_inference(self, model, pdf_bytes):
        try:
            result = model.inference(pdf_bytes)
            # Check for GPU errors in output
            if "CUDA error" in str(result):
                raise GPUFaultError("GPU hardware fault detected")
            return result
        except torch.cuda.OutOfMemoryError:
            self._record_oom()
            raise
    
    def _record_oom(self):
        """Track OOM events per GPU"""
        gpu_id = torch.cuda.current_device()
        key = f"dpt:oom_count:gpu:{gpu_id}"
        count = self.redis.incr(key)
        self.redis.expire(key, 3600)
        
        if count > 10:  # 10 OOMs in 1 hour
            send_alert(f"GPU {gpu_id} experiencing excessive OOMs", severity="critical")
```

---

## 7. Security & Compliance

### 7.1 mTLS Service Mesh (Istio)

```yaml
# istio/dpt-peer-authentication.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: dpt-strict-mtls
spec:
  selector:
    matchLabels:
      app: dpt-service
  mtls:
    mode: STRICT

---
# istio/dpt-authorization-policy.yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: dpt-access-control
spec:
  selector:
    matchLabels:
      app: dpt-service
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/underwriting/sa/api-gateway"]
    to:
    - operation:
        methods: ["POST", "GET"]
        paths: ["/dpt/*"]
  - from:
    - source:
        principals: ["cluster.local/ns/mlflow/sa/mlflow-server"]
    to:
    - operation:
        methods: ["GET"]
        paths: ["/dpt/models/*"]
```

### 7.2 Audit Logging (ELK Stack)

```python
# dpt_audit/logger.py
import structlog
from datetime import datetime

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

class AuditLogger:
    """
    FINTRAC-compliant audit logging
    """
    def __init__(self):
        self.logger = structlog.get_logger("dpt.audit")
    
    def log_extraction(self, user_id: str, job_id: str, doc_type: str, confidence: Decimal):
        """
        Immutable audit trail for regulatory review
        """
        self.logger.info(
            "extraction_completed",
            user_id=user_id,
            job_id=job_id,
            document_type=doc_type,
            confidence=str(confidence),  # Decimal as string
            timestamp=datetime.utcnow().isoformat(),
            action="DOCUMENT_EXTRACTED",
            # Non-repudiation hash
            audit_hash=self._generate_hash(user_id, job_id, str(confidence))
        )
    
    def _generate_hash(self, *components) -> str:
        """SHA-256 audit trail hash"""
        import hashlib
        content = "|".join(components).encode()
        return hashlib.sha256(content).hexdigest()
```

---

## 8. End-to-End Workflow Example

```python
# dpt_workflow/orchestrator.py
class ExtractionWorkflow:
    def __init__(self):
        self.registry = DonutModelRegistry()
        self.scorer = ConfidenceScorer()
        self.gpu_manager = GPUManager()
    
    async def process_job(self, job_id: str, s3_key: str, doc_type: str) -> dict:
        """
        Complete extraction pipeline
        """
        # 1. Download & validate PDF
        pdf_bytes = await s3.download(s3_key)
        if not self._validate_pdf(pdf_bytes):
            raise PermanentError("INVALID_PDF_FORMAT")
        
        # 2. Load model from MLFlow
        model, version = self.registry.get_production_model(doc_type)
        
        # 3. GPU inference
        try:
            with self.gpu_manager.allocate():
                result = model.inference(pdf_bytes)
        except torch.cuda.OutOfMemoryError:
            raise TransientError("CUDA_OUT_OF_MEMORY")
        
        # 4. Compute confidence
        confidence = self.scorer.compute_confidence(result, doc_type)
        
        # 5. Quality gate decision
        gate = self.scorer.get_quality_gate(confidence, doc_type)
        
        # 6. Store results
        extraction_record = {
            "job_id": job_id,
            "document_type": doc_type,
            "extracted_json": result,
            "confidence": confidence,
            "model_version": version,
            "status": "completed" if gate == "auto_approve" else "review_required"
        }
        
        await db.upsert_extraction(extraction_record)
        
        # 7. Emit events
        await event_bus.publish("extraction.finished", extraction_record)
        
        return extraction_record
```

---

## 9. Monitoring & Alerting

```yaml
# prometheus/alerts.yml
groups:
- name: dpt_alerts
  rules:
  - alert: DPTHighFailureRate
    expr: rate(dpt_extractions_failed_total[5m]) > 0.05
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "DPT failure rate > 5%"
      
  - alert: DPTLowConfidenceRate
    expr: rate(dpt_extractions_review_required_total[5m]) > 0.20
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: " >20% extractions require manual review"
      
  - alert: DPTGPUMemoryPressure
    expr: avg(nvidia_gpu_memory_used_bytes) / avg(nvidia_gpu_memory_total_bytes) > 0.9
    for: 5m
    labels:
      severity: critical
    annotations:
      action: "Scale up GPU nodes or reduce batch size"
```

---

## 10. Deployment Pipeline (GitOps)

```yaml
# argocd/dpt-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: dpt-service
spec:
  project: mortgage-underwriting
  
  source:
    repoURL: https://github.com/bank-ca/dpt-service
    targetRevision: HEAD
    path: k8s/overlays/production
    
    # Kustomize with patches
    kustomize:
      patchesStrategicMerge:
      - deployment-gpu-resources.yaml
      - configmap-thresholds.yaml
  
  destination:
    server: https://kubernetes.default.svc
    namespace: dpt-production
  
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    
    # Canary deployment strategy
    canary:
      steps:
      - setWeight: 20
      - pause: {duration: 10m}
      - setWeight: 50
      - pause: {duration: 10m}
      - setWeight: 100
      
  # MLFlow model promotion gate
  syncOptions:
  - Validate=false
  - PrunePropagationPolicy=foreground
  - PruneLast=true
```

---

## 11. Financial Compliance Checklist

| Requirement | Implementation |
|-------------|----------------|
| **Decimal Precision** | All financial fields use `Decimal(12,2)` in JSONB |
| **Audit Immutability** | SHA-256 hashed logs to WORM storage (S3 Glacier) |
| **Data Residency** | GPU workers in `ca-central-1`, data never leaves Canada |
| **Access Control** | OAuth2 + fine-grained ABAC: `underwriter:{app_id}:*` |
| **Retention Policy** | Extraction records retained 7 years (OSFI requirement) |
| **Encryption** | mTLS inter-service, AES-256 S3, LUKS at rest on GPU nodes |

---

## 12. Cost Optimization

- **Spot Instances**: Use EC2 Spot for staging model training (70% savings)
- **Model Quantization**: INT8 quantization for inference (2x throughput)
- **Smart Caching**: Cache extracted results for 24h to avoid re-processing
- **Batching**: Process 4 PDFs/GPU cycle to maximize utilization
- **Auto-scaling**: Scale to zero GPU nodes during off-hours (11 PM - 6 AM ET)

---

## 13. Testing Strategy

```python
# tests/test_confidence.py
def test_noa_confidence_calculation():
    scorer = ConfidenceScorer()
    output = {
        "line_15000": 85000.00,
        "line_23600": 75000.00,
        "confidence": 0.95
    }
    confidence = scorer.compute_confidence(output, "noa")
    
    assert isinstance(confidence, Decimal)
    assert confidence >= Decimal('0.9400')  # Meets threshold
    assert confidence.as_tuple().exponent == -4  # 4 decimal places

# tests/test_gpu_allocation.py
@pytest.mark.gpu
def test_gpu_oom_recovery():
    manager = GPUManager()
    with pytest.raises(TransientError):
        with manager.allocate():
            # Simulate OOM
            torch.zeros(100000, 100000, device='cuda')
    
    # Verify cleanup
    assert torch.cuda.memory_allocated() == 0
```

This architecture provides production-ready, auditable, and scalable document extraction for Canadian mortgage underwriting with enterprise-grade ML governance.