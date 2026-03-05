# Client Portal
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Portal Module Design Plan

**File**: `docs/design/client-portal.md`  
**Module**: `modules/client_portal/`  
**Last Updated**: 2024

---

## 1. Endpoints

### 1.1 Authentication & Session
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `POST` | `/api/v1/auth/login` | Public | `LoginRequest: {email: str, password: str, role: Literal['client','broker']}` | `LoginResponse: {access_token: str, token_type: str, user: UserProfileSchema}` | `AUTH_001` Invalid credentials<br>`AUTH_002` Account locked<br>`AUTH_003` Role mismatch |

### 1.2 Dashboard
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/dashboard` | Authenticated | Query: `role: Optional[Literal['client','broker']]`, `broker_id: Optional[UUID]` | `DashboardResponse: {pipeline_summary: PipelineSummary, flagged_items: List[FlaggedItem], recent_activity: List[ActivityFeedItem]}` | `PORTAL_001` Access denied for role |

### 1.3 Applications
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications` | Authenticated | Query: `status: Optional[str]`, `page: int=1`, `limit: int=20` | `ApplicationListResponse: {items: List[ApplicationSummarySchema], total: int, page: int}` | `PORTAL_002` Invalid filter |
| `POST` | `/api/v1/applications` | Authenticated | `CreateApplicationRequest: {property_value: Decimal, purchase_price: Decimal, requested_mortgage: Decimal, purpose: str}` | `ApplicationDetailSchema` | `PORTAL_003` Amount exceeds regulatory limit<br>`PORTAL_004` Missing required client profile |
| `GET` | `/api/v1/applications/{application_id}` | Authenticated | Path: `application_id: UUID` | `ApplicationDetailSchema: {id: UUID, status: ApplicationStatus, progress_pct: int, key_numbers: KeyNumbers, outstanding_docs: int}` | `PORTAL_005` Application not found<br>`PORTAL_006` Access denied (ownership check) |
| `PUT` | `/api/v1/applications/{application_id}` | Authenticated | `UpdateApplicationRequest: {requested_mortgage: Optional[Decimal], ...}` | `ApplicationDetailSchema` | `PORTAL_007` Can only modify draft status<br>`PORTAL_008` Invalid state transition |
| `DELETE` | `/api/v1/applications/{application_id}` | Authenticated | Path: `application_id: UUID` | `204 No Content` | `PORTAL_009` Can only delete draft |

### 1.4 Documents
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{application_id}/documents` | Authenticated | Path: `application_id: UUID` | `List[DocumentSchema]: [{id: UUID, type: DocumentType, status: VerificationStatus, uploaded_at: datetime}]` | `PORTAL_010` Application not accessible |
| `POST` | `/api/v1/applications/{application_id}/documents` | Authenticated | `Multipart: {file: UploadFile, document_type: DocumentType, metadata: JSON}` | `DocumentSchema: {id: UUID, presigned_url: Optional[str]}` | `PORTAL_011` Invalid document type<br>`PORTAL_012` File size exceeds 10MB<br>`PORTAL_013` Virus scan failed |
| `PUT` | `/api/v1/applications/{application_id}/documents/{doc_id}` | Authenticated | `Multipart: {file: UploadFile}` | `DocumentSchema` | `PORTAL_014` Document not found<br>`PORTAL_015` Cannot modify verified doc |
| `GET` | `/api/v1/applications/{application_id}/documents/{doc_id}/download` | Authenticated | Path: `doc_id: UUID` | `StreamingResponse` (presigned S3 URL) | `PORTAL_016` Document not ready |

### 1.5 Document Checklist
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{application_id}/checklist` | Authenticated | Path: `application_id: UUID` | `ChecklistResponse: {items: List[ChecklistItemSchema], completed_count: int, total_count: int}` | `PORTAL_017` Application not found |
| `PUT` | `/api/v1/applications/{application_id}/checklist/{item_id}` | Authenticated (Broker only) | `ChecklistItemUpdate: {status: Literal['verified','rejected'], rejection_reason: Optional[str]}` | `ChecklistItemSchema` | `PORTAL_018` Broker access required<br>`PORTAL_019` Invalid status update |

### 1.6 Underwriting Results (Broker Only)
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{application_id}/results` | Authenticated (Broker only) | Path: `application_id: UUID` | `UWResultsSchema: {gds_ratio: Decimal, tds_ratio: Decimal, qualifying_rate: Decimal, stress_test_passed: bool, cmhc_required: bool, premium_rate: Optional[Decimal], decision: UWDecision}` | `PORTAL_020` Results not ready<br>`PORTAL_021` Broker access required |

### 1.7 FINTRAC Verification (Broker Only)
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{application_id}/fintrac` | Authenticated (Broker only) | Path: `application_id: UUID` | `FintracStatusSchema: {verification_completed: bool, risk_score: int, flags: List[str], verified_at: Optional[datetime]}` | `PORTAL_022` FINTRAC access denied |
| `POST` | `/api/v1/applications/{application_id}/fintrac/verify` | Authenticated (Broker only) | `FintracVerifyRequest: {identity_documents: List[UUID], transaction_threshold: Decimal}` | `FintracStatusSchema` | `PORTAL_023` Transaction >$10K flag required<br>`PORTAL_024` Identity verification failed |

### 1.8 Lender Comparison (Broker Only)
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/applications/{application_id}/lenders` | Authenticated (Broker only) | Path: `application_id: UUID` | `LenderComparisonSchema: {eligible_lenders: List[LenderOfferSchema], recommended: UUID}` | `PORTAL_025` Lender data unavailable |

### 1.9 Notifications
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/notifications` | Authenticated | Query: `unread_only: bool=false`, `page: int=1` | `NotificationList: {items: List[NotificationSchema], unread_count: int}` | `PORTAL_026` Invalid pagination |
| `PUT` | `/api/v1/notifications/{notification_id}/read` | Authenticated | Path: `notification_id: UUID` | `NotificationSchema: {id: UUID, read: bool}` | `PORTAL_027` Notification not found |
| `PUT` | `/api/v1/notifications/read-all` | Authenticated | Body: `filter: Optional[NotificationType]` | `{updated_count: int}` | None |

### 1.10 Settings
| Method | Path | Auth | Request Schema | Response Schema | Error Codes |
|--------|------|------|----------------|-----------------|-------------|
| `GET` | `/api/v1/settings/profile` | Authenticated | None | `UserProfileSchema: {id: UUID, email: str, role: str, notification_prefs: dict}` | `PORTAL_028` Profile not found |
| `PUT` | `/api/v1/settings/profile` | Authenticated | `UpdateProfileRequest: {notification_prefs: dict, contact_phone: Optional[str]}` | `UserProfileSchema` | `PORTAL_029` Invalid phone format |

---

## 2. Models & Database

### 2.1 `portal_applications` Table
```python
class PortalApplication(Base):
    __tablename__ = "portal_applications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    broker_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Financial data (Decimal per OSFI B-20)
    requested_mortgage_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    property_value = Column(Numeric(precision=12, scale=2), nullable=False)
    purchase_price = Column(Numeric(precision=12, scale=2), nullable=False)
    
    # CMHC insurance calculation
    ltv_ratio = Column(Numeric(precision=5, scale=2), nullable=True)  # loan_amount / property_value
    cmhc_insurance_required = Column(Boolean, default=False)
    cmhc_premium_rate = Column(Numeric(precision=4, scale=2), nullable=True)  # 2.80, 3.10, 4.00
    
    # Status workflow
    status = Column(Enum("draft", "submitted", "in_review", "conditionally_approved", "approved", "closed", "rejected", name="app_status"), nullable=False, index=True)
    progress_percentage = Column(Integer, default=0)  # Derived from checklist completion
    
    # Regulatory audit (FINTRAC)
    fintrac_verified = Column(Boolean, default=False)
    fintrac_verified_at = Column(DateTime, nullable=True)
    fintrac_risk_score = Column(Integer, nullable=True)
    transaction_threshold_flag = Column(Boolean, default=False)  # >$10K per FINTRAC
    
    # PIPEDA compliance: no PII in this table
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_applications_user_status', 'user_id', 'status'),
        Index('idx_applications_broker_status', 'broker_id', 'status'),
        Index('idx_applications_created_at', 'created_at'),
    )
    
    # Relationships
    documents = relationship("PortalDocument", back_populates="application", cascade="all, delete-orphan")
    checklist_items = relationship("DocumentChecklistItem", back_populates="application", cascade="all, delete-orphan")
    notifications = relationship("PortalNotification", back_populates="application")
```

### 2.2 `portal_documents` Table
```python
class PortalDocument(Base):
    __tablename__ = "portal_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=False, index=True)
    
    # Document classification (FINTRAC relevant)
    document_type = Column(Enum("identity", "income", "employment", "bank_statement", "property", "other", name="doc_type"), nullable=False)
    verification_status = Column(Enum("pending", "verified", "rejected", name="verify_status"), nullable=False, default="pending")
    rejection_reason = Column(Text, nullable=True)
    
    # File storage (PIPEDA: store only encrypted references)
    s3_key = Column(String(500), nullable=False)  # Encrypted path
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # FINTRAC audit trail
    uploaded_by = Column(UUID(as_uuid=True), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    verified_by = Column(UUID(as_uuid=True), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # PIPEDA: No PII in filename or metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_documents_app_type_status', 'application_id', 'document_type', 'verification_status'),
    )
    
    application = relationship("PortalApplication", back_populates="documents")
```

### 2.3 `document_checklist_items` Table
```python
class DocumentChecklistItem(Base):
    __tablename__ = "document_checklist_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=False, index=True)
    
    # CMHC-driven requirements
    document_type = Column(String(50), nullable=False)
    required = Column(Boolean, default=True)
    status = Column(Enum("pending", "uploaded", "verified", "rejected", name="checklist_status"), nullable=False, default="pending")
    
    # Due diligence
    due_date = Column(DateTime, nullable=True)
    broker_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_checklist_app_status', 'application_id', 'status'),
    )
    
    application = relationship("PortalApplication", back_populates="checklist_items")
```

### 2.4 `portal_notifications` Table
```python
class PortalNotification(Base):
    __tablename__ = "portal_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("portal_applications.id"), nullable=True, index=True)
    
    # Notification taxonomy
    type = Column(Enum("document_uploaded", "document_verified", "document_rejected", "status_changed", "message_received", "condition_added", name="notif_type"), nullable=False)
    priority = Column(Enum("low", "medium", "high", name="notif_priority"), nullable=False, default="medium")
    
    # Message content (no PII per PIPEDA)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)  # Template: "Document {type} has been {action}"
    read = Column(Boolean, default=False, index=True)
    
    # Metadata for audit
    metadata_json = Column(JSON, nullable=True)  # Stores IDs, not values
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_notifications_user_read', 'user_id', 'read'),
        Index('idx_notifications_created_at', 'created_at'),
    )
    
    application = relationship("PortalApplication", back_populates="notifications")
```

### 2.5 `user_settings` Table
```python
class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    # PIPEDA: Encrypted preferences
    notification_preferences = Column(LargeBinary, nullable=False)  # AES-256 encrypted JSON
    
    # Contact info (encrypted)
    encrypted_phone = Column(LargeBinary, nullable=True)
    encrypted_address = Column(LargeBinary, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="portal_settings")
```

---

## 3. Business Logic

### 3.1 Application Status State Machine
```python
# States: draft → submitted → in_review → conditionally_approved → approved → closed
#         draft → rejected (terminal)
#         conditionally_approved → rejected (terminal)

STATE_TRANSITIONS = {
    "draft": ["submitted", "deleted"],
    "submitted": ["in_review", "rejected"],
    "in_review": ["conditionally_approved", "rejected"],
    "conditionally_approved": ["approved", "rejected"],
    "approved": ["closed"],
    "closed": [],  # Terminal
    "rejected": []  # Terminal
}

# Transition guards:
# - draft→submitted: checklist completion ≥ 80%, all identity docs uploaded
# - submitted→in_review: broker assignment exists, FINTRAC verification complete
# - Any→rejected: must log rejection reason to audit table (PIPEDA compliance)
```

### 3.2 Document Verification Workflow
1. **Upload**: Client/broker uploads → status=`pending`, virus scan triggered
2. **AI Pre-screen**: OCR extracts data → flags missing fields
3. **Broker Review**: Broker marks as `verified` or `rejected`
4. **FINTRAC Trigger**: If `document_type=='identity'` → updates `fintrac_verified` flag
5. **Audit**: Every status change creates immutable log entry (5-year retention per FINTRAC)

### 3.3 Notification Generation Rules
```python
NOTIFICATION_TRIGGERS = {
    "document_uploaded": "Notify broker when client uploads any document",
    "document_verified": "Notify client when broker verifies document",
    "document_rejected": "Notify client with rejection reason (no PII in reason)",
    "status_changed": "Notify client on status change, notify broker on client upload",
    "message_received": "Real-time WebSocket push for new messages",
    "condition_added": "Notify client when broker adds approval condition"
}

# PIPEDA: Messages must not contain SIN, DOB, or income values
```

### 3.4 Dashboard Aggregation Logic
**Broker Pipeline Summary**:
```sql
SELECT status, COUNT(*) 
FROM portal_applications 
WHERE broker_id = :current_user_id
GROUP BY status;
```

**Flagged Files**:
```sql
SELECT a.id, a.status, COUNT(c.id) as overdue_docs
FROM portal_applications a
JOIN document_checklist_items c ON a.id = c.application_id
WHERE a.broker_id = :current_user_id
  AND c.status IN ('pending', 'rejected')
  AND c.due_date < NOW()
GROUP BY a.id;
```

**Client Key Numbers**:
- `requested_mortgage_amount` (Decimal)
- `purchase_price` (Decimal)
- `ltv_ratio` (Decimal, calculated)
- `cmhc_insurance_required` (Boolean)
- `status` (Enum)

---

## 4. Migrations

### 4.1 New Tables
```sql
-- portal_applications
CREATE TABLE portal_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    broker_id UUID REFERENCES users(id),
    requested_mortgage_amount NUMERIC(12,2) NOT NULL CHECK (requested_mortgage_amount > 0),
    property_value NUMERIC(12,2) NOT NULL,
    purchase_price NUMERIC(12,2) NOT NULL,
    ltv_ratio NUMERIC(5,2) GENERATED ALWAYS AS (requested_mortgage_amount / NULLIF(property_value, 0)) STORED,
    cmhc_insurance_required BOOLEAN DEFAULT FALSE,
    cmhc_premium_rate NUMERIC(4,2),
    status app_status NOT NULL DEFAULT 'draft',
    progress_percentage INTEGER DEFAULT 0,
    fintrac_verified BOOLEAN DEFAULT FALSE,
    fintrac_verified_at TIMESTAMP,
    fintrac_risk_score INTEGER,
    transaction_threshold_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL
);

-- portal_documents
CREATE TABLE portal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES portal_applications(id) ON DELETE CASCADE,
    document_type doc_type NOT NULL,
    verification_status verify_status NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    s3_key VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes <= 10485760),
    mime_type VARCHAR(100) NOT NULL,
    uploaded_by UUID NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    verified_by UUID,
    verified_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- document_checklist_items
CREATE TABLE document_checklist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES portal_applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    required BOOLEAN DEFAULT TRUE,
    status checklist_status NOT NULL DEFAULT 'pending',
    due_date TIMESTAMP,
    broker_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- portal_notifications
CREATE TABLE portal_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    application_id UUID REFERENCES portal_applications(id),
    type notif_type NOT NULL,
    priority notif_priority NOT NULL DEFAULT 'medium',
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    read BOOLEAN DEFAULT FALSE,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- user_settings
CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) UNIQUE,
    notification_preferences BYTEA NOT NULL,
    encrypted_phone BYTEA,
    encrypted_address BYTEA,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 4.2 Indexes
```sql
CREATE INDEX idx_applications_user_status ON portal_applications(user_id, status);
CREATE INDEX idx_applications_broker_status ON portal_applications(broker_id, status) WHERE broker_id IS NOT NULL;
CREATE INDEX idx_applications_created_at ON portal_applications(created_at);
CREATE INDEX idx_documents_app_type_status ON portal_documents(application_id, document_type, verification_status);
CREATE INDEX idx_checklist_app_status ON document_checklist_items(application_id, status);
CREATE INDEX idx_notifications_user_read ON portal_notifications(user_id, read) WHERE read = FALSE;
CREATE INDEX idx_notifications_created_at ON portal_notifications(created_at DESC);
```

### 4.3 Data Migration
```sql
-- Backfill ltv_ratio for existing applications
UPDATE portal_applications 
SET cmhc_insurance_required = CASE 
    WHEN (requested_mortgage_amount / property_value) > 0.80 THEN TRUE 
    ELSE FALSE 
END;

-- Map CMHC premium tiers
UPDATE portal_applications 
SET cmhc_premium_rate = CASE 
    WHEN ltv_ratio BETWEEN 0.8001 AND 0.85 THEN 2.80
    WHEN ltv_ratio BETWEEN 0.8501 AND 0.90 THEN 3.10
    WHEN ltv_ratio BETWEEN 0.9001 AND 0.95 THEN 4.00
    ELSE NULL 
END
WHERE cmhc_insurance_required = TRUE;
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Display**: Any displayed qualifying rate must use `max(contract_rate + 2%, 5.25%)` formula
- **Ratio Transparency**: GDS/TDS values shown to brokers must include calculation breakdown in audit log
- **Hard Limits**: Portal must reject broker submissions that exceed GDS 39% / TDS 44% with clear error (`PORTAL_003`)
- **Audit Logging**: All ratio calculations stored in `underwriting_decisions` table (immutable, 5-year retention)

### 5.2 FINTRAC Compliance
- **Transaction Threshold**: When `requested_mortgage_amount > 10000.00`, `transaction_threshold_flag = TRUE` and requires explicit `FintracVerifyRequest`
- **Identity Verification**: `document_type='identity'` uploads trigger FINTRAC verification workflow
- **5-Year Retention**: All `portal_documents` and `portal_applications` rows are soft-deleted only (archived to cold storage)
- **Immutable Audit**: `uploaded_at`, `verified_by`, `verified_at` cannot be modified after set

### 5.3 CMHC Insurance Logic
```python
def calculate_cmhc_premium(loan_amount: Decimal, property_value: Decimal) -> tuple[bool, Optional[Decimal]]:
    ltv = loan_amount / property_value
    if ltv <= Decimal('0.80'):
        return False, None
    elif ltv <= Decimal('0.85'):
        return True, Decimal('0.0280')
    elif ltv <= Decimal('0.90'):
        return True, Decimal('0.0310')
    elif ltv <= Decimal('0.95'):
        return True, Decimal('0.0400')
    else:
        raise PortalValidationError("LTV exceeds CMHC maximum")
```
- **Premium Calculation**: Displayed in `/results` endpoint for broker view only
- **Client Transparency**: Client sees only "Insurance Required: Yes/No" (no premium rate)

### 5.4 PIPEDA Data Handling
- **Encryption at Rest**: 
  - `users.encrypted_sin` (AES-256)
  - `users.encrypted_dob` (AES-256)
  - `user_settings.encrypted_phone` (AES-256)
  - `user_settings.encrypted_address` (AES-256)
- **No PII in Logs**: All logs strip SIN, DOB, income, banking data
- **Lookup Hashing**: Use `SHA256(sin)` for document correlation, never raw SIN
- **Data Minimization**: Portal only collects fields required for underwriting decision
- **Error Messages**: Never include SIN/DOB in validation errors

### 5.5 Authentication & Authorization
```python
# FastAPI dependencies
require_authenticated = Security(verify_jwt)
require_broker = Security(verify_broker_role)
require_ownership = Security(verify_application_ownership)

# Endpoint protection:
# - /applications/{id}/results: require_broker + require_ownership
# - /applications/{id}/fintrac: require_broker + FINTRAC permission
# - /applications: require_authenticated + role-based filtering
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
class PortalException(AppException):
    """Base for all portal module exceptions"""
    module_code = "PORTAL"

class PortalNotFoundError(PortalException):
    """Resource not found"""
    http_status = 404
    error_code = "PORTAL_001"
    message_pattern = "{resource_type} with id {resource_id} not found"

class PortalValidationError(PortalException):
    """Input validation failed"""
    http_status = 422
    error_code = "PORTAL_002"
    message_pattern = "{field}: {reason}"

class PortalBusinessRuleError(PortalException):
    """Regulatory or business rule violation"""
    http_status = 409
    error_code = "PORTAL_003"
    message_pattern = "Rule {rule_name} violated: {detail}"

class PortalAccessDeniedError(PortalException):
    """Authorization failure"""
    http_status = 403
    error_code = "PORTAL_004"
    message_pattern = "Access denied to {resource} for role {role}"

class PortalFintracError(PortalException):
    """FINTRAC specific violation"""
    http_status = 422
    error_code = "PORTAL_023"
    message_pattern = "FINTRAC: {detail}"
```

### 6.2 Error Response Mapping
| Scenario | Exception Class | HTTP Status | Error Code | Example Message |
|----------|-----------------|-------------|------------|-----------------|
| Application not found | `PortalNotFoundError` | 404 | PORTAL_005 | "Application with id 123e4567... not found" |
| Invalid mortgage amount | `PortalValidationError` | 422 | PORTAL_003 | "requested_mortgage: exceeds CMHC limit" |
| GDS/TDS exceeds OSFI limits | `PortalBusinessRuleError` | 409 | PORTAL_003 | "Rule OSFI_B20 violated: GDS 42% > 39%" |
| Broker accessing client-only | `PortalAccessDeniedError` | 403 | PORTAL_021 | "Access denied to results for role client" |
| Missing FINTRAC flag >$10K | `PortalFintracError` | 422 | PORTAL_023 | "FINTRAC: Transaction threshold requires explicit flag" |
| Document virus scan fail | `PortalValidationError` | 422 | PORTAL_013 | "file: Virus detected - upload blocked" |
| Status transition invalid | `PortalBusinessRuleError` | 409 | PORTAL_008 | "Rule STATE_TRANSITION violated: Cannot move from approved to draft" |

### 6.3 Structured Error Response Format
```json
{
  "detail": "Application with id 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "PORTAL_005",
  "module": "client_portal",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req_abc123",
  "metadata": {
    "resource_type": "application",
    "resource_id": "123e4567-e89b-12d3-a456-426614174000"
  }
}
```

---

## 7. Implementation Notes

### 7.1 Real-Time Notifications
- **Recommended**: WebSocket endpoint `/api/v1/ws/notifications` with JWT auth
- **Fallback**: Long polling with `ETag` on `/notifications` endpoint
- **Scalability**: Use Redis Pub/Sub for broker broadcast events

### 7.2 Document Upload Security
- **Virus Scanning**: ClamAV integration via `services.py` async worker
- **File Validation**: Magic number check + MIME type whitelist
- **Storage**: S3 with KMS encryption, presigned URLs expire in 60 seconds
- **PIPEDA**: Never log file content, only `document_type` and `file_size`

### 7.3 Performance Optimization
- Dashboard queries use materialized view `broker_pipeline_summary_mv` updated every 5 minutes
- Application list uses cursor-based pagination (no OFFSET)
- Document download redirects to CloudFront signed URLs (not through API)

### 7.4 Mobile Considerations
- Camera capture: Frontend uses `navigator.mediaDevices` API, uploads as multipart/form-data
- Progressive Web App (PWA) support for offline document upload queue
- Responsive design: Tailwind CSS breakpoints `sm`, `md`, `lg`

---

**Next Steps**: Implementation phase to create `modules/client_portal/` with files `models.py`, `schemas.py`, `services.py`, `routes.py`, `exceptions.py` per project conventions.