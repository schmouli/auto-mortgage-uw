# Messaging & Conditions
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Messaging & Conditions Module Design

**File:** `docs/design/messaging-conditions.md`

---

## 1. Endpoints

### Message Endpoints

#### `POST /api/v1/applications/{application_id}/messages`
Send a new message within an application thread.

**Auth:** Authenticated user (must have access to application)

**Request Body:**
```json
{
  "recipient_id": "uuid",           // required, UUID
  "body": "string",                 // required, max 5000 chars
  "lender_submission_id": "uuid"    // optional, UUID
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "lender_submission_id": "uuid|null",
  "sender_id": "uuid",
  "recipient_id": "uuid",
  "body": "string",
  "is_read": false,
  "sent_at": "datetime",
  "read_at": "datetime|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404` `MESSAGING_005` Application not found or access denied
- `422` `MESSAGING_003` Body exceeds max length or recipient not found
- `403` `MESSAGING_002` User not authorized for this application

---

#### `GET /api/v1/applications/{application_id}/messages`
Retrieve paginated message thread for an application.

**Auth:** Authenticated user (must have access to application)

**Query Parameters:**
- `page`: int (default: 1)
- `page_size`: int (default: 50, max: 200)
- `is_read`: bool (optional filter)
- `sender_id`: uuid (optional filter)
- `date_from`: datetime (optional filter)
- `date_to`: datetime (optional filter)

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "uuid",
      "application_id": "uuid",
      "lender_submission_id": "uuid|null",
      "sender_id": "uuid",
      "recipient_id": "uuid",
      "body": "string",
      "is_read": false,
      "sent_at": "datetime",
      "read_at": "datetime|null",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

**Error Responses:**
- `404` `MESSAGING_005` Application not found or access denied
- `422` `MESSAGING_003` Invalid pagination parameters

---

#### `PUT /api/v1/applications/{application_id}/messages/{message_id}/read`
Mark a message as read.

**Auth:** Authenticated user (must be the recipient)

**Response (200 OK):**
```json
{
  "success": true,
  "read_at": "datetime"
}
```

**Error Responses:**
- `404` `MESSAGING_001` Message not found
- `403` `MESSAGING_002` User is not the recipient
- `409` `MESSAGING_004` Message already marked as read

---

### Condition Endpoints

#### `POST /api/v1/applications/{application_id}/conditions`
Add a new underwriting condition.

**Auth:** Authenticated underwriter or admin

**Request Body:**
```json
{
  "description": "string",            // required, max 2000 chars
  "condition_type": "document|information|other",  // required, enum
  "required_by_date": "date",         // required, ISO 8601 date
  "lender_submission_id": "uuid"      // optional, UUID
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "lender_submission_id": "uuid|null",
  "description": "string",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "date",
  "satisfied_at": "datetime|null",
  "satisfied_by": "uuid|null",
  "waiver_reason": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404` `CONDITIONS_005` Application not found
- `422` `CONDITIONS_003` Required by date in past or invalid type
- `403` `CONDITIONS_002` Insufficient permissions (requires underwriter role)

---

#### `GET /api/v1/applications/{application_id}/conditions`
List all conditions for an application.

**Auth:** Authenticated user (must have access to application)

**Query Parameters:**
- `page`: int (default: 1)
- `page_size`: int (default: 100)
- `status`: string (optional filter: outstanding|satisfied|waived)
- `condition_type`: string (optional filter)

**Response (200 OK):**
```json
{
  "items": [...],  // Array of ConditionResponse objects
  "total": 25,
  "page": 1,
  "page_size": 100
}
```

**Error Responses:**
- `404` `CONDITIONS_005` Application not found or access denied

---

#### `PUT /api/v1/applications/{application_id}/conditions/{condition_id}`
Update condition status (satisfy or waive).

**Auth:** Authenticated underwriter or admin

**Request Body:**
```json
{
  "status": "satisfied|waived",  // required, enum
  "waiver_reason": "string"      // required if status=waived
}
```

**Response (200 OK):**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "lender_submission_id": "uuid|null",
  "description": "string",
  "condition_type": "document",
  "status": "satisfied|waived",
  "required_by_date": "date",
  "satisfied_at": "datetime",
  "satisfied_by": "uuid",
  "waiver_reason": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404` `CONDITIONS_001` Condition not found
- `403` `CONDITIONS_002` Insufficient permissions
- `422` `CONDITIONS_003` Invalid status transition
- `409` `CONDITIONS_004` Cannot modify satisfied/waived condition

---

#### `GET /api/v1/applications/{application_id}/conditions/outstanding`
List only outstanding conditions (shortcut endpoint).

**Auth:** Authenticated user (must have access to application)

**Query Parameters:**
- `days_until_due`: int (optional: filter conditions due within N days)
- `overdue_only`: bool (optional: filter only overdue conditions)

**Response (200 OK):**
```json
{
  "items": [...],  // Array of outstanding ConditionResponse objects
  "total": 5,
  "escalated_count": 2  // Conditions overdue by >5 days
}
```

**Error Responses:**
- `404` `CONDITIONS_005` Application not found or access denied

---

## 2. Models & Database

### `messages` Table

```python
class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    lender_submission_id = Column(UUID(as_uuid=True), ForeignKey("lender_submissions.id"), nullable=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Body encrypted at rest if contains PII (configurable per deployment)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="messages")
    lender_submission = relationship("LenderSubmission", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
```

**Indexes:**
```sql
CREATE INDEX idx_messages_application_sent_at ON messages(application_id, sent_at DESC);
CREATE INDEX idx_messages_recipient_read ON messages(recipient_id, is_read) WHERE is_read = false;
CREATE INDEX idx_messages_sent_at ON messages(sent_at DESC);
```

---

### `conditions` Table

```python
class Condition(Base):
    __tablename__ = "conditions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    lender_submission_id = Column(UUID(as_uuid=True), ForeignKey("lender_submissions.id"), nullable=True)
    
    description = Column(Text, nullable=False)
    condition_type = Column(SQLAlchemyEnum(ConditionType), nullable=False)
    status = Column(SQLAlchemyEnum(ConditionStatus), default=ConditionStatus.OUTSTANDING, nullable=False)
    
    required_by_date = Column(Date, nullable=False)  # Business date, no timezone
    satisfied_at = Column(DateTime(timezone=True), nullable=True)
    satisfied_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    waiver_reason = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="conditions")
    lender_submission = relationship("LenderSubmission", back_populates="conditions")
    satisfied_user = relationship("User", foreign_keys=[satisfied_by])
```

**Indexes:**
```sql
CREATE INDEX idx_conditions_application_status ON conditions(application_id, status);
CREATE INDEX idx_conditions_status_required_by ON conditions(status, required_by_date) 
  WHERE status = 'outstanding';
CREATE INDEX idx_conditions_required_by_date ON conditions(required_by_date);
```

---

## 3. Business Logic

### Message Thread Management
- **Sending:** Validates sender/recipient belong to application stakeholder set (borrower, broker, underwriter, lender). Encrypts body using `common.security.encrypt_pii()` if content pattern matches SIN/DOB/banking data.
- **Thread Retrieval:** Returns messages sorted by `sent_at DESC`. Supports cursor-based pagination for large threads.
- **Read Receipts:** Idempotent operation; subsequent calls return same `read_at` timestamp.

### Condition Lifecycle State Machine
```
[outstanding] --(satisfy)--> [satisfied]
    |
    |--(waive)----> [waived] (requires waiver_reason + underwriter role)
```

**Validation Rules:**
- `required_by_date` must be ≥ business date + 2 days (minimum processing window)
- Only `outstanding` conditions can be modified
- `satisfied` status requires authenticated user to be recorded in `satisfied_by`
- `waived` status requires `waiver_reason` (minimum 10 characters)

### Automated Workflows
**Condition Reminders:**
- Daily scheduled job (2:00 AM EST) queries `idx_conditions_status_required_by` for conditions due within 3 days
- Sends email/push notification to assigned underwriter and applicant
- Logs reminder event to immutable audit trail

**Escalation Mechanism:**
- Conditions overdue > 5 days trigger escalation to underwriting manager
- Updates internal `escalated_count` metric exposed via `GET /conditions/outstanding`
- Creates system-generated message in application thread

### Search & Archive
- **Search:** Full-text GIN index on `messages.body` supports keyword search (excluding encrypted content)
- **Archive:** Messages > 1 year auto-archived to cold storage per FINTRAC 5-year retention policy; primary DB keeps metadata only

---

## 4. Migrations

### New Tables
```sql
-- Create messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    lender_submission_id UUID REFERENCES lender_submissions(id) ON DELETE SET NULL,
    sender_id UUID NOT NULL REFERENCES users(id),
    recipient_id UUID NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create conditions table
CREATE TABLE conditions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    lender_submission_id UUID REFERENCES lender_submissions(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    condition_type condition_type_enum NOT NULL,
    status condition_status_enum DEFAULT 'outstanding' NOT NULL,
    required_by_date DATE NOT NULL,
    satisfied_at TIMESTAMPTZ,
    satisfied_by UUID REFERENCES users(id),
    waiver_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

### Indexes
```sql
-- Message indexes
CREATE INDEX idx_messages_application_sent_at ON messages(application_id, sent_at DESC);
CREATE INDEX idx_messages_recipient_read ON messages(recipient_id, is_read) WHERE is_read = false;
CREATE INDEX idx_messages_sent_at ON messages(sent_at DESC);

-- Condition indexes
CREATE INDEX idx_conditions_application_status ON conditions(application_id, status);
CREATE INDEX idx_conditions_status_required_by ON conditions(status, required_by_date) 
  WHERE status = 'outstanding';
CREATE INDEX idx_conditions_required_by_date ON conditions(required_by_date);

-- Full-text search (optional, for archive search)
CREATE INDEX idx_messages_body_fts ON messages USING gin(to_tsvector('english', body));
```

### Enum Types
```sql
CREATE TYPE condition_type_enum AS ENUM ('document', 'information', 'other');
CREATE TYPE condition_status_enum AS ENUM ('outstanding', 'satisfied', 'waived');
```

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption:** Message body encrypted using AES-256-GCM via `common.security.encrypt_pii()` when content matches regex patterns for SIN (###-###-###), DOB (YYYY-MM-DD), or banking info. Encryption key derived from `settings.MESSAGE_ENCRYPTION_KEY`.
- **Data Minimization:** Message body limited to underwriting-relevant content. System scans and rejects messages containing unnecessary PII.
- **No Logging:** Message body never logged; only metadata (sender, recipient, timestamp) appears in logs.

### FINTRAC Compliance
- **Immutable Audit Trail:** All message sends, reads, condition creates, updates logged to dedicated `audit_log` table with `created_by`, `action`, `resource_id`, `application_id`, `timestamp`. Records never updated or deleted.
- **Transaction Flagging:** Conditions requiring documents > $10,000 automatically flagged with `high_value_document = True` in audit metadata.
- **5-Year Retention:** Messages and conditions retained for 5 years + 1 day; archived to cold storage after 1 year.

### OSFI B-20 Indirect Impact
- Conditions tagged with `affects_gds_tds = True` must be satisfied before final B-20 calculation. System blocks approval if outstanding conditions affect debt ratios.

### Authorization Matrix
| Role | Send Message | Read Thread | Create Condition | Update Condition | Waive Condition |
|------|--------------|-------------|------------------|------------------|-----------------|
| Borrower | ✓ (own app) | ✓ (own app) | ✗ | ✗ | ✗ |
| Broker | ✓ (assigned apps) | ✓ (assigned apps) | ✗ | ✗ | ✗ |
| Underwriter | ✓ (assigned apps) | ✓ (assigned apps) | ✓ | ✓ (satisfy) | ✓ |
| Admin | ✓ (all apps) | ✓ (all apps) | ✓ | ✓ | ✓ |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern |
|-----------------|-------------|------------|-----------------|
| `MessageNotFoundError` | 404 | MESSAGING_001 | "Message {msg_id} not found" |
| `MessagePermissionError` | 403 | MESSAGING_002 | "Access denied to message {msg_id}" |
| `MessageValidationError` | 422 | MESSAGING_003 | "{field}: {reason}" |
| `MessageAlreadyReadError` | 409 | MESSAGING_004 | "Message already marked as read" |
| `ApplicationAccessError` | 404 | MESSAGING_005 | "Application {app_id} not found or access denied" |
| `ConditionNotFoundError` | 404 | CONDITIONS_001 | "Condition {cond_id} not found" |
| `ConditionPermissionError` | 403 | CONDITIONS_002 | "Access denied to condition {cond_id}" |
| `ConditionValidationError` | 422 | CONDITIONS_003 | "{field}: {reason}" |
| `ConditionBusinessRuleError` | 409 | CONDITIONS_004 | "Cannot {action} condition: {detail}" |
| `ConditionApplicationError` | 404 | CONDITIONS_005 | "Application {app_id} not found or access denied" |
| `WaiverAuthorizationError` | 403 | CONDITIONS_006 | "Waiving conditions requires underwriter or admin role" |

**Error Response Format:**
```json
{
  "detail": "Message {msg_id} not found",
  "error_code": "MESSAGING_001",
  "correlation_id": "uuid",
  "timestamp": "datetime"
}
```

---

## Implementation Notes

- **Scheduled Jobs:** Use Celery Beat for reminder/escalation tasks with idempotency keys.
- **Encryption Key Rotation:** Implement annual key rotation with re-encryption job for `messages.body`.
- **Observability:** Add Prometheus counters `messaging_messages_sent_total` and `conditions_outstanding_duration_hours`.
- **Rate Limiting:** 100 messages/hour per user to prevent spam; 50 condition updates/hour per underwriter.