# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: OnLendHub - Canadian Mortgage Underwriting

# OnLendHub Client Portal - Architecture Design

## 1. High-Level System Architecture

### Component Topology
```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client Layer (Public)                        │
│  Web/Mobile → CDN/WAF → Next.js SSR → React SPA (TypeScript)       │
└─────────────────────────────────────────────────────────────────────┘
                                   │
┌─────────────────────────────────────────────────────────────────────┐
│                    API Gateway & Security Layer                     │
│  FastAPI → OAuth2/JWT Auth → Role-Based Access Control (RBAC)      │
│  mTLS for internal microservices                                   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
┌─────────────────────────────────────────────────────────────────────┐
│                     Core Service Layer (Python)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ App Service  │  │ Doc Service  │  │ Notif Service│            │
│  │ (Workflow)   │  │ (Storage)    │  │ (WebSocket)  │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Audit Service│  │ User Service │  │ FINTRAC Svc  │            │
│  │ (Compliance) │  │ (Profile)    │  │ (Verification)│            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                                   │
┌─────────────────────────────────────────────────────────────────────┐
│                         Data & Infrastructure                       │
│  PostgreSQL (Primary) → PITR → Read Replicas                       │
│  Redis (Cache/Queue) → Pub/Sub for real-time                       │
│  S3/Azure Blob (Docs) → Virus Scanning → Versioning                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Architecture (Next.js 14 + TypeScript)

### Framework Selection
**Next.js 14 (App Router)** - Justification:
- **Hybrid rendering**: SSR for `/login` (SEO/public), CSR for dashboard (dynamic data)
- **API Routes**: Native webhook endpoints for document processing callbacks
- **TypeScript 5.0+**: First-class support with strict mode
- **Middleware**: Perfect for role-based route protection

### Directory Structure
```
/app
  /(public)/login/page.tsx
  /(authenticated)/dashboard/page.tsx
  /(authenticated)/applications
    /page.tsx (list)
    /[id]/page.tsx (detail)
    /[id]/documents/page.tsx
    /[id]/checklist/page.tsx
    /[id]/results/page.tsx (broker only)
    /[id]/fintrac/page.tsx (broker only)
    /[id]/lenders/page.tsx (broker only)
  /notifications/page.tsx
  /settings/page.tsx
  /api
    /webhooks/document-processed/route.ts

/components
  /dashboard/ClientDashboard.tsx
  /dashboard/BrokerDashboard.tsx
  /applications/StatusProgressBar.tsx
  /documents/DragDropUploadZone.tsx
  /documents/MobileCameraCapture.tsx
  /notifications/RealTimeFeed.tsx

/lib
  /api/client.ts (REST client)
  /websocket/notifications.ts (Socket.IO)
  /store/useApplicationStore.ts (Zustand)
  /utils/decimal-calc.ts (Financial calculations)
```

### UI/UX Design System

**Component Library**: `shadcn/ui` + `Radix UI`
- **Why**: Headless, accessible, fully typed, composable
- **Styling**: Tailwind CSS 3.4+ with custom design tokens
- **Theme**: Professional banking aesthetic
  - Primary: `#0F2A56` (Canadian banking blue)
  - Success: `#006D4C` (mortgage approval green)
  - Error: `#B30000` (regulatory red)

**Design Tokens** (Tailwind config):
```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#E6F0FF',
          500: '#0F2A56',
          900: '#051428',
        },
        success: {
          500: '#006D4C',
        },
      },
      spacing: {
        'app': '1.5rem', // Consistent padding unit
      },
    },
  },
}
```

### Mobile Responsiveness Strategy

**Breakpoint Strategy**:
```typescript
// lib/hooks/useDevice.ts
export const useDevice = () => {
  const isMobile = useMediaQuery('(max-width: 768px)');
  const isTablet = useMediaQuery('(max-width: 1024px)');
  return { isMobile, isTablet };
};
```

**Implementation**:
1. **Mobile-first CSS**: All components built `sm:` up
2. **Touch-optimized uploads**: Minimum 44x44px tap targets
3. **Camera-first flow**: On mobile, camera button primary; file picker secondary
4. **Bottom sheet modals**: For document actions on <768px
5. **PWA Manifest**: `manifest.ts` for installable app experience

### Real-Time Notification Delivery

**WebSocket Implementation** (Socket.IO):
```typescript
// lib/websocket/notifications.ts
import { io } from 'socket.io-client';
import { useAuthStore } from '@/lib/store/auth';

export const notificationSocket = io(process.env.NEXT_PUBLIC_WS_URL!, {
  auth: (cb) => {
    cb({ token: useAuthStore.getState().accessToken });
  },
  transports: ['websocket'],
  reconnectionAttempts: 5,
});

// Connection management
notificationSocket.on('connect', () => {
  console.log('WS connected');
  // Subscribe to user-specific channel
  notificationSocket.emit('subscribe', `user:${userId}`);
});
```

**Fallback Strategy**: Server-Sent Events (SSE) for environments blocking WebSockets (corporate firewalls)

---

## 3. Backend Architecture (FastAPI + SQLAlchemy 2.0)

### API Design (OpenAPI 3.1)

```python
# routers/applications.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

router = APIRouter(prefix="/applications", tags=["applications"])

@router.get("/", response_model=List[ApplicationSummary])
async def list_applications(
    status: Optional[ApplicationStatus] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List applications with role-based filtering"""
    if user.role == Role.CLIENT:
        return await app_service.get_client_applications(user.id, db)
    return await app_service.get_broker_pipeline(user.id, status, db)

@router.put("/{id}/status", response_model=ApplicationDetail)
async def update_status(
    id: UUID,
    transition: StatusTransition,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """State machine transition with audit trail"""
    return await workflow_service.transition(id, transition, user.id, db)
```

### Data Models (SQLAlchemy 2.0)

```python
# models/application.py
from sqlalchemy.orm import Mapped, mapped_column
from decimal import Decimal
import pgvector  # For AI-powered document classification

class Application(Base):
    __tablename__ = "applications"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    broker_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    
    # Financial fields using DECIMAL
    requested_mortgage: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2))
    
    # State machine
    status: Mapped[ApplicationStatus] = mapped_column(
        default=ApplicationStatus.DRAFT
    )
    
    # AI-powered document classification vector
    document_vector: Mapped[pgvector.sqlalchemy.Vector] = mapped_column(
        pgvector.sqlalchemy.Vector(1536)
    )
    
    # Audit columns
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())
    version: Mapped[int] = mapped_column(default=1)  # Optimistic locking
```

### Workflow Engine (Multi-State Versioning)

```python
# services/workflow.py
from transitions import Machine
from decimal import Decimal

class ApplicationWorkflow:
    states = [
        'draft', 'submitted', 'in_review', 
        'conditionally_approved', 'approved', 'closed', 'rejected'
    ]
    
    transitions = [
        {'trigger': 'submit', 'source': 'draft', 'dest': 'submitted'},
        {'trigger': 'review', 'source': 'submitted', 'dest': 'in_review'},
        # Conditional transitions based on document verification
        {
            'trigger': 'verify_docs', 
            'source': 'in_review', 
            'dest': 'conditionally_approved',
            'conditions': ['all_documents_verified']
        },
    ]
    
    def __init__(self, application: Application):
        self.machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial=application.status
        )
        self.application = application
    
    def all_documents_verified(self) -> bool:
        # Check document checklist completion
        return self.application.document_checklist.is_fully_verified()
```

---

## 4. Document Management System

### Upload Architecture

```
Client → Presigned URL → S3 → EventBridge → Lambda → ClamAV → Metadata → DB
          (Direct upload)       (Virus scan)      (Classification)
```

**Implementation**:

```python
# services/document.py
async def generate_upload_url(
    application_id: UUID, 
    filename: str, 
    content_type: str,
    user: User
) -> dict:
    """Generate presigned URL for direct-to-S3 upload"""
    
    # Validate file type
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Invalid file type")
    
    # Virus scan policy
    scan_id = str(uuid4())
    key = f"uploads/{application_id}/{scan_id}/{filename}"
    
    # Generate presigned URL (15 min expiry)
    url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': DOC_BUCKET,
            'Key': key,
            'ContentType': content_type,
            'Metadata': {
                'scan-status': 'pending',
                'user-id': str(user.id)
            }
        },
        ExpiresIn=900
    )
    
    return {"upload_url": url, "document_id": scan_id}
```

### Drag-and-Drop Component

```typescript
// components/documents/DragDropUploadZone.tsx
'use client';
import { useDropzone } from 'react-dropzone';
import { uploadDocument } from '@/lib/api/documents';

export function DragDropUploadZone({ applicationId }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.jpg', '.jpeg', '.png'],
    },
    maxSize: 25 * 1024 * 1024, // 25MB
    onDrop: async (files) => {
      for (const file of files) {
        // Get presigned URL
        const { upload_url, document_id } = await getPresignedURL(
          applicationId,
          file.name,
          file.type
        );
        
        // Upload to S3
        await axios.put(upload_url, file, {
          headers: { 'Content-Type': file.type },
        });
        
        // Update application checklist
        await updateChecklist(applicationId, document_id);
      }
    },
  });

  return (
    <div {...getRootProps()} className={`
      border-2 border-dashed rounded-lg p-8 text-center
      ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300'}
      hover:border-primary-400 transition-colors
    `}>
      <input {...getInputProps()} />
      <CameraIcon className="mx-auto mb-4" />
      <p>Drop files here or click to upload</p>
      <p className="text-sm text-gray-500">PDF, JPG up to 25MB</p>
    </div>
  );
}
```

### Mobile Camera Capture

```typescript
// components/documents/MobileCameraCapture.tsx
import Webcam from 'react-webcam';

export function MobileCameraCapture({ onCapture }: Props) {
  const webcamRef = useRef<Webcam>(null);
  
  const capture = useCallback(() => {
    const imageSrc = webcamRef.current?.getScreenshot();
    if (imageSrc) {
      // Convert dataURL to File
      const file = dataURLtoFile(imageSrc, 'camera-capture.jpg');
      onCapture(file);
    }
  }, [webcamRef]);

  return (
    <div className="md:hidden">
      <Webcam
        ref={webcamRef}
        screenshotFormat="image/jpeg"
        videoConstraints={{ facingMode: 'environment' }}
      />
      <Button onClick={capture} className="w-full mt-4">
        <CameraIcon /> Capture Document
      </Button>
    </div>
  );
}
```

---

## 5. Notification System Architecture

### Event-Driven Design

```python
# services/notification.py
class NotificationEvent(str, Enum):
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VERIFIED = "document_verified"
    DOCUMENT_REJECTED = "document_rejected"
    STATUS_CHANGED = "status_changed"
    MESSAGE_RECEIVED = "message_received"
    CONDITION_ADDED = "condition_added"

async def publish_notification(
    event: NotificationEvent,
    application_id: UUID,
    user_id: UUID,
    metadata: dict
) -> None:
    """Publish to Redis Pub/Sub and persist to DB"""
    
    notification = Notification(
        user_id=user_id,
        event_type=event,
        application_id=application_id,
        metadata=metadata,
        read=False
    )
    
    # Persist
    await db.add(notification)
    await db.commit()
    
    # Publish to Redis for real-time delivery
    await redis.publish(
        f"notifications:user:{user_id}",
        json.dumps({
            "id": str(notification.id),
            "event": event,
            "data": metadata,
            "timestamp": notification.created_at.isoformat()
        })
    )
```

### WebSocket Gateway

```python
# websocket/notification_gateway.py
from fastapi import WebSocket, Depends
from jose import jwt

class NotificationGateway:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        token: str,
        db: AsyncSession
    ):
        # Validate JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # Subscribe to Redis channel
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"notifications:user:{user_id}")
        
        # Listen for messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
```

---

## 6. Security & Compliance (DeepWiki Best Practices)

### Authentication Flow
```python
# middleware/auth.py
async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    JWT validation with mTLS certificate pinning for internal calls
    """
    # Verify JWT signature
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    
    # Validate mTLS certificate fingerprint
    if os.getenv("ENVIRONMENT") == "production":
        cert_fingerprint = get_client_cert_fingerprint()
        if cert_fingerprint != payload.get("cert_hash"):
            raise HTTPException(403, "Invalid client certificate")
    
    # RBAC enforcement
    user_scopes = payload.get("scopes", [])
    for scope in security_scopes.scopes:
        if scope not in user_scopes:
            raise HTTPException(403, "Insufficient permissions")
    
    return await user_service.get_by_id(payload["sub"])
```

### Audit Logging (PIPEDA/FINTRAC Compliance)

```python
# services/audit.py
async def log_audit_event(
    action: AuditAction,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    old_values: dict,
    new_values: dict,
    ip_address: str,
    user_agent: str
) -> None:
    """
    Immutable audit trail for regulatory compliance
    """
    audit_record = AuditLog(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
        timestamp=datetime.utcnow()
    )
    
    # Write to separate audit database
    async with audit_db.begin() as session:
        await session.add(audit_record)
    
    # Immutable append-only log
    await append_to_wal(audit_record)
```

### Data Residency & Encryption
- **PIPEDA Compliance**: All data stored in Canada (AWS `ca-central-1`)
- **Encryption at Rest**: AWS KMS with CMK rotation
- **Encryption in Transit**: TLS 1.3 + mTLS for service-to-service
- **Field-level encryption**: SIN numbers, financial data encrypted with separate keys

---

## 7. Addressing Missing Details

### UI/UX Mockups & Design System
**Recommendation**: Create Figma library with:
- **Atoms**: Buttons, inputs, status badges
- **Molecules**: Application cards, document rows, notification items
- **Organisms**: Dashboard widgets, application timeline
- **Templates**: Page layouts for each route
- **Prototype**: Interactive flow with auto-animate for status transitions

**Progress Indicator UX**:
```typescript
// components/applications/StatusProgressBar.tsx
export function StatusProgressBar({ status }: Props) {
  const steps = [
    { id: 'draft', label: 'Draft' },
    { id: 'submitted', label: 'Submitted' },
    { id: 'in_review', label: 'In Review' },
    { id: 'conditionally_approved', label: 'Cond. Approved' },
    { id: 'approved', label: 'Approved' },
    { id: 'closed', label: 'Closed' },
  ];

  const currentIndex = steps.findIndex(s => s.id === status);

  return (
    <div className="flex items-center justify-between">
      {steps.map((step, idx) => (
        <div key={step.id} className="flex items-center">
          <div className={`
            w-10 h-10 rounded-full flex items-center justify-center
            ${idx <= currentIndex ? 'bg-primary-500 text-white' : 'bg-gray-200'}
          `}>
            {idx < currentIndex ? <CheckIcon /> : idx + 1}
          </div>
          {idx < steps.length - 1 && (
            <div className={`
              w-full h-1 mx-2
              ${idx < currentIndex ? 'bg-primary-500' : 'bg-gray-200'}
            `} />
          )}
        </div>
      ))}
    </div>
  );
}
```

### Real-Time Delivery Mechanism

**Decision Matrix**:
| Criteria | WebSockets | Server-Sent Events | Polling |
|----------|------------|-------------------|---------|
| Latency | <100ms | <200ms | 5-30s |
| Bidirectional | ✅ | ❌ | ❌ |
| Firewall Friendly | ❌ | ✅ | ✅ |
| Complexity | High | Low | Medium |
| **Recommendation** | **Primary** | **Fallback** | **Deprecated** |

**Implementation**: Use `Socket.IO` with automatic fallback to SSE

### Camera Capture Implementation

**Progressive Enhancement**:
1. **Native API**: `navigator.mediaDevices.getUserMedia()`
2. **Library**: `react-webcam` for cross-browser compatibility
3. **Mobile Optimization**:
   - `facingMode: 'environment'` for rear camera
   - `imageCapture.takePhoto()` for high-res capture
   - Auto-cropping using `cornerstone.js` for document edges

```typescript
// lib/utils/document-scanner.ts
export async function scanDocument(video: HTMLVideoElement): Promise<Blob> {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'environment' }
  });
  
  const track = stream.getVideoTracks()[0];
  const capabilities = track.getCapabilities();
  
  // Use ImageCapture API if available
  if ('ImageCapture' in window) {
    const imageCapture = new ImageCapture(track);
    const photo = await imageCapture.takePhoto({
      imageWidth: capabilities.imageWidth?.max || 1920
    });
    return photo;
  }
  
  // Fallback to canvas
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d')!.drawImage(video, 0, 0);
  
  return new Promise(resolve => 
    canvas.toBlob(resolve!, 'image/jpeg', 0.9)
  );
}
```

### Drag-and-Drop Library Selection

**Chosen**: `react-dropzone` + `@uppy/dashboard`

**Why**:
- `react-dropzone`: Lightweight, hooks-based, excellent TypeScript
- `@uppy/dashboard`: Advanced features (resumable uploads, image editor) for broker portal

**Configuration**:
```typescript
const { getRootProps } = useDropzone({
  accept: {
    'application/pdf': ['.pdf'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
  },
  maxSize: 25 * 1024 * 1024,
  validator: (file) => {
    // Check file magic numbers (prevent spoofing)
    return validateFileMagicNumber(file);
  },
});
```

### Progress Indicator UX Design

**Recommendation**: Use **skeleton screens** + **progressive disclosure**

```typescript
// components/shared/SkeletonLoader.tsx
export function ApplicationSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
      <div className="h-32 bg-gray-200 rounded-lg"></div>
    </div>
  );
}

// hooks/useProgressiveLoading.ts
export function useProgressiveLoading() {
  const [isLoading, setIsLoading] = useState(true);
  const [data, setData] = useState(null);
  
  useEffect(() => {
    // Load critical data first
    const critical = fetch('/api/applications?fields=id,status');
    // Then load secondary data
    const secondary = fetch('/api/applications?fields=documents,messages');
    
    Promise.all([critical, secondary]).then(() => setIsLoading(false));
  }, []);
  
  return { isLoading, data, Skeleton: ApplicationSkeleton };
}
```

---

## 8. Database Schema Design

```sql
-- applications table
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES users(id),
    broker_id UUID REFERENCES users(id),
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    requested_mortgage NUMERIC(12,2) NOT NULL,
    purchase_price NUMERIC(12,2) NOT NULL,
    document_vector VECTOR(1536), -- pgvector for AI classification
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    CONSTRAINT positive_mortgage CHECK (requested_mortgage > 0)
);

-- documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    application_id UUID REFERENCES applications(id),
    type VARCHAR(100) NOT NULL, -- 'T4', 'PAYSTUB', etc.
    s3_key VARCHAR(500) UNIQUE NOT NULL,
    verification_status VARCHAR(50) DEFAULT 'pending',
    ai_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    event_type VARCHAR(100) NOT NULL,
    application_id UUID REFERENCES applications(id),
    metadata JSONB,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id) WHERE read = FALSE;

-- audit_log table (immutable)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    action VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID NOT NULL,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);
```

---

## 9. Infrastructure & Scaling

### Deployment Architecture
```
┌─────────────────────────────────────────────────────────┐
│  AWS CloudFront (CDN + WAF) → Route 53                │
│  ├─ WAF Rules: Rate limiting, SQLi protection         │
│  └─ Geographic: Canada-only for PIPEDA compliance     │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  ECS Fargate (FastAPI Services)                        │
│  ├─ Auto Scaling: CPU > 70%                            │
│  ├─ Health Checks: /health (with DB probe)            │
│  └─ mTLS: Envoy Proxy for service mesh                 │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  RDS PostgreSQL 15 (Multi-AZ)                          │
│  ├─ Read Replicas for broker dashboard queries        │
│  ├─ PITR: 7-day retention                             │
│  └─ IAM Auth + Secrets Manager rotation               │
└─────────────────────────────────────────────────────────┘
```

### Monitoring & Observability
```python
# middleware/metrics.py
from prometheus_client import Counter, Histogram

APPLICATION_STATUS_TRANSITIONS = Counter(
    'app_status_transitions_total',
    'Total status transitions',
    ['from_status', 'to_status', 'user_role']
)

DOCUMENT_UPLOAD_LATENCY = Histogram(
    'document_upload_duration_seconds',
    'Time to process document upload',
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

@router.post("/documents")
async def upload_document(...):
    with DOCUMENT_UPLOAD_LATENCY.time():
        # Process upload
        APPLICATION_STATUS_TRANSITIONS.labels(
            from_status=app.status,
            to_status=new_status,
            user_role=user.role
        ).inc()
```

---

## 10. Development & Testing Strategy

### Local Development Stack
```yaml
# docker-compose.yml
services:
  api:
    build: .
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/onlendhub
      REDIS_URL: redis://cache:6379
      S3_ENDPOINT: http://minio:9000
    depends_on:
      - db
      - cache
      - minio

  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: onlendhub
    ports: ["5432:5432"]

  cache:
    image: redis:7-alpine
    command: redis-server --appendonly yes

  minio:
    image: minio/minio
    command: server /data
    ports: ["9000:9000", "9001:9001"]
```

### Testing Pyramid
- **Unit**: pytest for services, Jest for React components
- **Integration**: TestContainers for PostgreSQL/Redis
- **E2E**: Playwright for critical flows (login → upload → status change)
- **Performance**: k6 for load testing notification delivery

---

## 11. Regulatory Compliance Checklist

| Requirement | Implementation | Evidence |
|-------------|----------------|----------|
| **FINTRAC Record Keeping** | Immutable audit logs with 5-year retention | `audit_log` table, WAL archiving |
| **PIPEDA Consent** | Explicit consent checkbox on upload | `consent_records` table |
| **Data Residency** | AWS `ca-central-1` region only | AWS Config rules |
| **Access Logging** | CloudTrail + VPC Flow Logs | 90-day retention |
| **Encryption** | KMS CMK, TLS 1.3 | AWS Certificate Manager |

---

## 12. Performance Targets

| Metric | Target | Implementation |
|--------|--------|----------------|
| **Page Load** | < 2s | SSR + React.lazy() |
| **Document Upload** | < 5s | Presigned URLs + S3 Transfer Acceleration |
| **Notification Latency** | < 200ms | WebSockets + Redis Pub/Sub |
| **Dashboard Query** | < 500ms | Materialized views + Redis cache |
| **Concurrent Users** | 10,000+ | ECS auto-scaling + RDS read replicas |

---

This architecture provides a production-ready, compliant, and scalable foundation for OnLendHub's Client Portal, addressing all specified requirements while maintaining extensibility for future features like AI document classification and lender API integrations.