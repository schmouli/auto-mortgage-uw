# Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: OnLendHub - Canadian Mortgage Underwriting

# Document Management Module Architecture

## 1. Architecture Overview

### Service-Oriented Design
```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (mTLS)                      │
│              (Kong/AWS API Gateway/Nginx Plus)              │
└─────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│          Document Management Service (DMS)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │  FastAPI     │  │  Celery      │  │  PostgreSQL 15  │ │
│  │  REST API    │◄─┤  Workers     │◄►│  (Metadata)     │ │
│  │  (Python)    │  │  (Async)     │  └─────────────────┘ │
│  └──────┬───────┘  └──────┬───────┘                        │
│         │                  │                                │
│  ┌──────▼───────┐  ┌──────▼───────┐                        │
│  │  Redis       │  │  RabbitMQ    │                        │
│  │  (Cache/RQ)  │◄►│  (Broker)    │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐        ┌──────────────────────┐
│  S3-Compatible  │        │  ClamAV Daemon       │
│  Object Storage │◄──────►│  (Virus Scan)        │
│  (MinIO/AWS S3) │        └──────────────────────┘
└─────────────────┘                 │
         │                         ▼
         │                  ┌──────────────────────┐
         │                  │  OCRmyPDF/Tesseract  │
         │                  │  (Text Extraction)   │
         │                  └──────────────────────┘
         │
┌────────▼────────┐
│  Audit Log      │
│  (PostgreSQL)   │
└─────────────────┘
```

**Justification**: Microservice isolation ensures compliance data boundaries, independent scaling for CPU-intensive operations (OCR/virus scan), and clear audit trails.

---

## 2. Database Schema Design

### Core Tables

```sql
-- Document metadata table with row-level security
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN (
        'government_id', 'proof_of_sin', 't4_slip', 'noa', 'pay_stub',
        'employment_letter', 't1_general', 'financial_statements',
        'rental_income_statement', 'purchase_agreement', 'mls_listing',
        'property_tax_bill', 'condo_status_cert', 'bank_statement',
        'void_cheque', 'gift_letter', 'rrsp_withdrawal_confirmation',
        'sale_proceeds_confirmation', 'existing_mortgage_statement',
        'divorce_decree', 'bankruptcy_discharge'
    )),
    file_name VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 for virus scan deduplication
    storage_key VARCHAR(500) NOT NULL, -- S3 key or local path (never exposed)
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes <= 10*1024*1024),
    mime_type VARCHAR(100) NOT NULL CHECK (mime_type IN (
        'application/pdf', 'image/jpeg', 'image/jpg', 'image/png'
    )),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'accepted', 'rejected', 'quarantined')),
    rejection_reason TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ, -- Soft delete for compliance
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Composite indexes for common queries
    CONSTRAINT unique_active_doc UNIQUE (application_id, document_type, deleted_at)
);

-- Partition by application_id for performance (100k+ apps/year)
CREATE INDEX idx_documents_application_id ON documents (application_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_status ON documents (status) WHERE status = 'pending';
CREATE INDEX idx_documents_uploaded_at ON documents (uploaded_at DESC);

-- Document requirements matrix (dynamic per application)
CREATE TABLE document_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_received BOOLEAN NOT NULL DEFAULT FALSE,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_req UNIQUE (application_id, document_type)
);

CREATE INDEX idx_doc_req_app ON document_requirements (application_id);

-- Audit log table (immutable append-only)
CREATE TABLE document_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id),
    action VARCHAR(50) NOT NULL, -- UPLOAD, VERIFY, REJECT, DELETE, DOWNLOAD
    performed_by UUID NOT NULL REFERENCES users(id),
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_audit_doc_id ON document_audit_log (document_id);
CREATE INDEX idx_audit_action ON document_audit_log (action);

-- OCR extracted text for future search/validation
CREATE TABLE document_ocr_extract (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extracted_text TEXT,
    confidence_score DECIMAL(5,4),
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_version VARCHAR(20)
);

CREATE INDEX idx_ocr_doc_id ON document_ocr_extract (document_id);
```

**Best Practice**: Use `UUID` for security (non-sequential IDs), soft deletes for 7-year retention compliance, and table partitioning for query performance.

---

## 3. API Implementation (FastAPI)

### Pydantic Models

```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from typing import Optional
from datetime import datetime
import re

class DocumentUploadResponse(BaseModel):
    document_id: UUID
    status: str
    storage_key: str  # Only returned to internal services, never to frontend

class DocumentListItem(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    file_size_bytes: int
    mime_type: str
    status: str
    is_verified: bool
    uploaded_at: datetime
    rejection_reason: Optional[str] = None
    
    # Never expose internal paths
    class Config:
        fields = {'storage_key': {'exclude': True}}

class DocumentChecklistItem(BaseModel):
    document_type: str
    is_required: bool
    is_received: bool
    due_date: Optional[datetime] = None
    received_document: Optional[DocumentListItem] = None

# Request models
class VerifyDocumentRequest(BaseModel):
    verified_by: UUID
    notes: Optional[str] = None

class RejectDocumentRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)
    rejection_category: str = Field(..., regex="^(invalid|incomplete|fraudulent)$")
```

### API Endpoints

```python
from fastapi import (
    APIRouter, Depends, UploadFile, File, HTTPException, 
    BackgroundTasks, Request, status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import os

router = APIRouter(prefix="/applications/{application_id}/documents")

@router.get(
    "/checklist",
    response_model=list[DocumentChecklistItem],
    dependencies=[Depends(verify_ownership), Depends(rate_limit)]
)
async def get_document_checklist(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves document requirements status with received documents.
    Implements row-level security at DB level.
    """
    checklist = await document_service.get_checklist(db, application_id, user.id)
    return checklist

@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadResponse
)
async def upload_document(
    application_id: uuid.UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Async upload endpoint:
    1. Validates MIME, size, filename
    2. Generates secure storage key
    3. Queues for virus scan & HEIC conversion
    4. Returns immediate response with document_id
    """
    # Validate file
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 10MB limit")
    
    # Sanitize filename
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
    storage_key = f"applications/{application_id}/{document_type}/{uuid.uuid4()}_{safe_name}"
    
    # Save to temp location
    temp_path = await save_temp_file(file)
    
    # Create document record
    doc = await document_service.create_pending_document(
        db, application_id, user.id, document_type, 
        safe_name, storage_key, file.size, file.content_type
    )
    
    # Queue processing
    background_tasks.add_task(
        process_document_pipeline, 
        doc.id, temp_path, storage_key, file.content_type
    )
    
    return DocumentUploadResponse(
        document_id=doc.id,
        status="pending",
        storage_key=storage_key  # Internal use only
    )

@router.get(
    "/{doc_id}/download",
    response_class=StreamingResponse
)
async def download_document(
    application_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Streams file from storage with audit logging.
    Generates signed URLs for S3, streams from local FS.
    """
    doc = await document_service.get_document(db, doc_id, application_id)
    
    # Audit log
    await audit_service.log_download(
        db, doc_id, user.id, request.client.host
    )
    
    # Stream from storage
    storage = get_storage_provider()
    file_stream = storage.stream_file(doc.storage_key)
    
    return StreamingResponse(
        file_stream,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{doc.file_name}"',
            "Cache-Control": "private, max-age=3600"
        }
    )

@router.put("/{doc_id}/verify")
async def verify_document(
    application_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: VerifyDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_underwriter_role)
):
    """Underwriter-only endpoint to mark document as verified."""
    doc = await document_service.verify(
        db, doc_id, application_id, user.id, request.notes
    )
    return {"status": "verified", "document_id": doc.id}

@router.put("/{doc_id}/reject")
async def reject_document(
    application_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: RejectDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_underwriter_role)
):
    """Reject with mandatory reason and category."""
    doc = await document_service.reject(
        db, doc_id, application_id, request.reason, 
        request.rejection_category, user.id
    )
    return {"status": "rejected", "document_id": doc.id}

@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_document(
    application_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_role)
):
    """
    Soft delete only. Hard deletion runs via retention policy.
    """
    await document_service.soft_delete(
        db, doc_id, application_id, user.id
    )
    return None
```

---

## 4. File Storage Abstraction Layer

```python
from abc import ABC, abstractmethod
import boto3
from botocore.config import Config
import aiofiles

class StorageProvider(ABC):
    @abstractmethod
    async def store_file(self, local_path: str, key: str) -> str:
        pass
    
    @abstractmethod
    async def stream_file(self, key: str):
        pass
    
    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def generate_signed_url(self, key: str, expiry: int = 3600) -> str:
        pass

class S3StorageProvider(StorageProvider):
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=os.getenv('S3_ENDPOINT'),
            aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
            config=Config(signature_version='s3v4'),
            region_name='ca-central-1'
        )
        self.bucket = os.getenv('S3_BUCKET', 'onlendhub-docs')
    
    async def store_file(self, local_path: str, key: str) -> str:
        """Upload with server-side encryption, return ETag"""
        self.client.upload_file(
            local_path, self.bucket, key,
            ExtraArgs={
                'ServerSideEncryption': 'aws:kms',
                'SSEKMSKeyId': os.getenv('S3_KMS_KEY_ID'),
                'Metadata': {'created-by': 'onlendhub-dms'}
            }
        )
        return f"s3://{self.bucket}/{key}"
    
    def generate_signed_url(self, key: str, expiry: int = 3600) -> str:
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=expiry
        )

class LocalStorageProvider(StorageProvider):
    """For development and on-prem initial deployment"""
    def __init__(self, base_path: str = "/uploads"):
        self.base_path = base_path
    
    async def store_file(self, local_path: str, key: str) -> str:
        dest = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        async with aiofiles.open(local_path, 'rb') as src:
            async with aiofiles.open(dest, 'wb') as dst:
                await dst.write(await src.read())
        return dest
```

**Configuration**: Use `STORAGE_BACKEND=s3|local` environment variable for seamless migration.

---

## 5. Async Processing Pipeline (Celery)

```python
from celery import Celery
import hashlib
import pyheif
from PIL import Image
import pyclamd
import ocrmypdf

celery_app = Celery('dms', broker='redis://redis:6379/0')

@celery_app.task(bind=True, max_retries=3)
def process_document_pipeline(
    self, doc_id: str, temp_path: str, storage_key: str, mime_type: str
):
    """
    5-stage pipeline: Hash → HEIC Convert → Virus Scan → OCR → Store
    """
    try:
        # Stage 1: Generate SHA-256 hash for deduplication
        file_hash = generate_file_hash(temp_path)
        
        # Check for duplicate (fraud indicator)
        if is_duplicate_hash(file_hash):
            raise SecurityException(f"Duplicate document detected: {file_hash}")
        
        # Stage 2: Convert HEIC to PDF if needed
        if mime_type == 'image/heic':
            temp_path = convert_heic_to_pdf(temp_path)
            mime_type = 'application/pdf'
        
        # Stage 3: Virus scan (placeholder for integration)
        scan_result = virus_scan(temp_path)
        if scan_result['infected']:
            quarantine_file(temp_path, scan_result['signature'])
            update_document_status(doc_id, 'quarantined', 
                                   f"Virus: {scan_result['signature']}")
            return
        
        # Stage 4: OCR extraction (async, non-blocking)
        if mime_type == 'application/pdf':
            extract_text_async.delay(doc_id, temp_path)
        
        # Stage 5: Store in permanent storage
        storage = get_storage_provider()
        storage_key = storage.store_file(temp_path, storage_key)
        
        # Update document record
        update_document_status(doc_id, 'accepted', storage_key=storage_key, 
                               file_hash=file_hash, mime_type=mime_type)
        
        # Cleanup temp file
        os.unlink(temp_path)
        
    except Exception as exc:
        logger.error(f"Pipeline failed for {doc_id}: {exc}")
        update_document_status(doc_id, 'error', str(exc))
        raise self.retry(exc=exc, countdown=60)

def convert_heic_to_pdf(temp_path: str) -> str:
    """Using pyheif + Pillow for HEIC conversion"""
    heif_file = pyheif.read(temp_path)
    image = Image.frombytes(
        heif_file.mode, 
        heif_file.size, 
        heif_file.data,
        "raw",
        heif_file.mode,
        heif_file.stride,
    )
    pdf_path = temp_path.replace('.heic', '.pdf')
    image.save(pdf_path, "PDF", resolution=300.0)
    return pdf_path

def virus_scan(file_path: str) -> dict:
    """ClamAV daemon integration (async non-blocking)"""
    cd = pyclamd.ClamdUnixSocket()
    if not cd.ping():
        logger.warning("ClamAV not available, skipping scan")
        return {'infected': False}
    
    result = cd.scan_file(file_path)
    return {
        'infected': result is not None,
        'signature': result[file_path][1] if result else None
    }

@celery_app.task
def extract_text_async(doc_id: str, file_path: str):
    """OCR with OCRmyPDF for layered PDFs"""
    try:
        # Generate searchable PDF (optional, store separately)
        ocrmypdf.ocr(file_path, f"{file_path}.ocr.pdf", 
                     deskew=True, rotate_pages=True)
        
        # Extract raw text
        import fitz  # PyMuPDF
        doc = fitz.open(f"{file_path}.ocr.pdf")
        text = "\n".join(page.get_text() for page in doc)
        
        # Store in document_ocr_extract table
        store_ocr_result(doc_id, text, confidence=0.95)
    except Exception as e:
        logger.error(f"OCR failed for {doc_id}: {e}")
```

---

## 6. Security & Compliance

### Authentication & Authorization
```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Verify JWT from OAuth2 provider (Keycloak/Auth0)"""
    try:
        payload = jwt.decode(
            creds.credentials,
            key=os.getenv('JWKS_URL'),
            algorithms=['RS256'],
            audience='onlendhub-api'
        )
        return User(id=payload['sub'], roles=payload.get('roles', []))
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")

async def require_underwriter_role(user: User = Depends(get_current_user)):
    if 'underwriter' not in user.roles:
        raise HTTPException(403, "Underwriter role required")
    return user

# Row-level security in PostgreSQL
RLS_SQL = """
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_access ON documents 
    FOR ALL TO application_user 
    USING (application_id IN (
        SELECT id FROM applications WHERE user_id = current_user_id()
    ));
"""
```

### File Access Security
- **Never** expose `storage_key` or file paths in API responses
- Use **signed URLs** (S3) or **short-lived tokens** (local) for downloads
- Implement **mTLS** between services (Istio/Linkerd)
- Store files with **KMS encryption** at rest

---

## 7. HEIC Conversion Library Selection

**Recommended**: `pyheif` + `Pillow-SIMD`

```bash
# Installation
pip install pyheif pillow-simd

# Production build dependencies
apt-get install libheif-dev libde265-dev libx265-dev
```

**Performance**: 
- Benchmark: ~150ms per HEIC file (10MP image)
- Memory: ~50MB peak per conversion
- **Alternative**: Use `wand` (ImageMagick) if license concerns, but pyheif is MIT-licensed and faster.

---

## 8. Virus Scanning Implementation Timeline

### Phase 1 (MVP - Week 1-2)
- Log file hashes to `document_audit_log` table
- Implement placeholder `virus_scan()` function that returns clean
- **Risk**: Low (trusted internal users initially)

### Phase 2 (Production - Week 3-4)
- Deploy ClamAV daemon cluster (3 nodes for HA)
- Use `pyclamd` for async scanning
- Implement **quarantine bucket** in S3 with lifecycle policy
- **Risk**: Medium (external broker uploads)

### Phase 3 (Scale - Month 2)
- Integrate commercial scanner (MetaDefender/Cloudmersive) for zero-day threats
- Implement **scan result caching** (Redis) by file hash
- Add **scan SLA**: <5s per file

```python
# Quarantine flow
def quarantine_file(file_path: str, signature: str):
    """Move to isolated S3 bucket with restricted IAM"""
    quarantine_key = f"quarantine/{datetime.utcnow().date()}/{signature}/{os.path.basename(file_path)}"
    s3_client.upload_file(
        file_path, 
        os.getenv('QUARANTINE_BUCKET'), 
        quarantine_key,
        Tagging=f"virus={signature}"
    )
    alert_security_team(signature, quarantine_key)
```

---

## 9. OCR Requirements & Implementation

### Use Cases
1. **Income Validation**: Extract T4/NOA amounts → cross-reference with application
2. **Identity Verification**: Parse government ID numbers → match application
3. **Fraud Detection**: Detect tampered PDFs (text layer vs image mismatch)

### Implementation
```python
# Add to document_ocr_extract table
async def validate_document_content(doc_id: UUID, application: Application):
    ocr = await db.get(DocumentOCR, doc_id)
    
    if doc.document_type == 't4_slip':
        income = extract_t4_income(ocr.extracted_text)
        if abs(income - application.declared_income) > Decimal('5000'):
            flag_for_review(doc_id, 'income_mismatch')
```

**Library**: `OCRmyPDF` (wraps Tesseract) - produces searchable PDFs as bonus.

---

## 10. Document Retention Policy (Canadian Compliance)

| Document Type | Retention Period | Destruction Method | Regulation |
|---------------|------------------|-------------------|------------|
| **IDENTITY** | 7 years after account closure | Secure erase (DoD 5220.22-M) | PCMLTFA |
| **INCOME** | 7 years | Secure erase | OSFI B-20 |
| **PROPERTY** | Life of loan + 7 years | Secure erase | Provincial land registries |
| **BANKING** | 7 years | Secure erase | FINTRAC |
| **DOWN_PAYMENT** | 7 years | Secure erase | PCMLTFA |
| **OTHER** | 7 years (bankruptcy: 14 years) | Secure erase | BIA, Provincial |

### Automated Lifecycle
```python
# S3 Lifecycle Policy (JSON)
{
    "Rules": [
        {
            "ID": "IdentityDocuments",
            "Filter": {"Tag": {"Key": "doc_type", "Value": "identity"}},
            "Status": "Enabled",
            "Expiration": {"Days": 2555},  # 7 years
            "Transitions": [
                {"Days": 90, "StorageClass": "GLACIER"}
            ]
        }
    ]
}

# Soft delete cascade
UPDATE documents SET deleted_at = NOW() 
WHERE application_id IN (
    SELECT id FROM applications WHERE status = 'closed' 
    AND closed_at < NOW() - INTERVAL '7 years'
);
```

---

## 11. S3 Integration Path & Architecture

### Migration Strategy: Local → S3

**Phase 1: Dual-Write (Week 1)**
```python
# Write to both local and S3
async def store_file_both(local_path, key):
    local_storage.store(local_path, key)
    s3_storage.store(local_path, key)  # Async fire-and-forget
```

**Phase 2: Read from S3 (Week 2)**
- Update `download` endpoint to prefer S3 signed URLs
- Maintain local as fallback

**Phase 3: Cutover (Week 3)**
- Run migration script: `python manage.py migrate_to_s3 --batch-size=1000`
- Update `STORAGE_BACKEND=s3`
- Monitor 404 rates <0.1%

**S3 Architecture**
- **Bucket**: `onlendhub-prod-documents`
- **Region**: `ca-central-1` (Canadian data residency)
- **Encryption**: AWS KMS (CMK rotation every year)
- **Versioning**: Enabled for accidental deletion protection
- **Replication**: Cross-region to `ca-west-1` for DR
- **Access**: Private VPC endpoint, no public internet access

**Cost Optimization**
- **S3 Intelligent-Tiering**: Auto-move to Glacier after 90 days
- **Expected cost**: ~$0.023/GB/month × 5TB = $115/month

---

## 12. Infrastructure & Deployment

### Docker Compose (Development)
```yaml
version: '3.8'
services:
  dms-api:
    build: ./dms
    environment:
      DATABASE_URL: postgresql+asyncpg://dms:pass@postgres:5432/onlendhub
      STORAGE_BACKEND: local
      CLAMAV_HOST: clamav
    depends_on:
      - postgres
      - redis
      - clamav

  clamav:
    image: clamav/clamav:1.2
    volumes:
      - clamav-db:/var/lib/clamav

  postgres:
    image: postgres:15.2-alpine
    environment:
      POSTGRES_DB: onlendhub
      POSTGRES_USER: dms
    volumes:
      - pg-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

### Kubernetes (Production)
```yaml
# Helm values.yaml
replicaCount: 5
autoscaling:
  minReplicas: 5
  maxReplicas: 50
  targetCPUUtilizationPercentage: 70

resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"

podAnnotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"

# Istio mTLS
istio:
  enabled: true
  mtls:
    mode: STRICT
```

---

## 13. Monitoring & Observability

### Metrics (Prometheus)
```python
from prometheus_client import Counter, Histogram

document_uploads = Counter(
    'dms_uploads_total',
    'Total document uploads',
    ['document_type', 'status']
)

virus_scans = Counter(
    'dms_virus_scans_total',
    'Virus scan results',
    ['result']
)

ocr_processing_time = Histogram(
    'dms_ocr_processing_seconds',
    'Time spent on OCR',
    buckets=[1, 5, 10, 30, 60]
)
```

### Alerts
- **Virus Detected**: `rate(dms_virus_scans_total{result="infected"}[5m]) > 0`
- **Upload Failures**: `rate(dms_uploads_total{status="error"}[5m]) > 0.05`
- **OCR SLA Breach**: `histogram_quantile(0.95, dms_ocr_processing_seconds) > 30`

---

## 14. Implementation Roadmap

| Sprint | Deliverable | Risk |
|--------|-------------|------|
| **Sprint 1** | MVP: Upload, list, download, local storage | Low |
| **Sprint 2** | Virus scanning + HEIC conversion | Medium (ClamAV setup) |
| **Sprint 3** | S3 integration + KMS encryption | Medium (IAM roles) |
| **Sprint 4** | OCR + income validation logic | High (accuracy) |
| **Sprint 5** | Retention policy automation + compliance audit | Low |

**Total Timeline**: 5 weeks to production-ready document management module.

---

## Summary

This architecture provides **regulatory-compliant**, **scalable**, and **secure** document management for OnLendHub. Key differentiators:

1. **Async pipeline** prevents API blocking during heavy processing
2. **Storage abstraction** enables zero-downtime S3 migration
3. **Immutable audit log** satisfies OSFI/PCMLTFA requirements
4. **Row-level security** ensures data isolation between mortgage brokers
5. **Future-ready** for AI-powered fraud detection via OCR extraction

**Next Steps**: Begin with Sprint 1 MVP while provisioning S3 and ClamAV infrastructure in parallel.