# Messaging & Conditions
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Messaging & Conditions Module Design

**Feature Slug:** `messaging-conditions`  
**Module Path:** `mortgage_underwriting/modules/messaging/`  
**Design Document:** `docs/design/messaging-conditions.md`

---

## 1. Endpoints

### 1.1 Message Management

#### `POST /api/v1/applications/{application_id}/messages`
Send a new message within an application thread.

**Auth:** Authenticated user (must have `view:application` scope on target application)

**Request Body:**
```json
{
  "recipient_id": "uuid",  // required, UUID format
  "body": "string"          // required, min_length=1, max_length=5000
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "sender_id": "uuid",
  "recipient_id": "uuid",
  "body": "string",
  "is_read": false,
  "sent_at": "datetime",
  "read_at": null,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_008`) - Application not found or user lacks access
- `422 Unprocessable Entity` (`MESSAGING_002`) - Body exceeds max length or recipient_id invalid
- `403 Forbidden` (`MESSAGING_003`) - Sender cannot message this recipient (different organization without shared application)

---

#### `GET /api/v1/applications/{application_id}/messages`
Retrieve paginated message thread for an application.

**Auth:** Authenticated user (must have `view:application` scope)

**Query Parameters:**
- `page`: integer (default: 1, min: 1)
- `per_page`: integer (default: 50, min: 1, max: 200)
- `is_read`: boolean (optional filter)
- `sender_id`: uuid (optional filter)
- `before_date`: datetime (optional, ISO 8601)
- `after_date`: datetime (optional, ISO 8601)

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "uuid",
      "sender_id": "uuid",
      "recipient_id": "uuid",
      "body": "string",
      "is_read": false,
      "sent_at": "datetime",
      "read_at": null
    }
  ],
  "total": 100,
  "page": 1,
  "per_page": 50,
  "total_pages": 2
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_008`) - Application not found
- `403 Forbidden` (`MESSAGING_003`) - User lacks access to application
- `422 Unprocessable Entity` (`MESSAGING_002`) - Invalid pagination parameters

---

#### `PUT /api/v1/applications/{application_id}/messages/{message_id}/read`
Mark a message as read (recipient only).

**Auth:** Authenticated user (must be the recipient)

**Request Body:** `None` (idempotent operation)

**Response (200 OK):**
```json
{
  "id": "uuid",
  "is_read": true,
  "read_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_001`) - Message not found
- `403 Forbidden` (`MESSAGING_003`) - User is not the recipient
- `409 Conflict` (`MESSAGING_007`) - Message already marked as read

---

### 1.2 Condition Management

#### `POST /api/v1/applications/{application_id}/conditions`
Add a new underwriting condition.

**Auth:** Authenticated user with `underwriter:write` scope

**Request Body:**
```json
{
  "description": "string",           // required, max_length=2000
  "condition_type": "document",      // required: Enum["document", "information", "other"]
  "required_by_date": "date",        // required, must be ≥ today + 1 day
  "lender_submission_id": "uuid"     // optional, links to specific submission
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
  "satisfied_at": null,
  "satisfied_by": null,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_008`) - Application not found
- `422 Unprocessable Entity` (`MESSAGING_005`) - Invalid date or description too long
- `403 Forbidden` (`MESSAGING_006`) - User lacks underwriter permissions

---

#### `GET /api/v1/applications/{application_id}/conditions`
List all conditions for an application.

**Auth:** Authenticated user with `view:application` scope

**Query Parameters:**
- `status`: string (optional: "outstanding", "satisfied", "waived")
- `condition_type`: string (optional)
- `page`: integer (default: 1)
- `per_page`: integer (default: 50)

**Response (200 OK):**
```json
{
  "items": [...],
  "total": 15,
  "page": 1,
  "per_page": 50,
  "total_pages": 1,
  "summary": {
    "outstanding_count": 3,
    "satisfied_count": 10,
    "waived_count": 2,
    "overdue_count": 1
  }
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_008`) - Application not found
- `403 Forbidden` (`MESSAGING_003`) - User lacks access

---

#### `PUT /api/v1/applications/{application_id}/conditions/{condition_id}`
Update condition status (satisfy or waive).

**Auth:** Authenticated user with `underwriter:write` scope (waive requires `underwriter:manage`)

**Request Body:**
```json
{
  "status": "satisfied",  // required: Enum["satisfied", "waived"]
  "notes": "string"       // optional, max_length=1000, required if status="waived"
}
```

**Response (200 OK):**
```json
{
  "id": "uuid",
  "status": "satisfied",
  "satisfied_at": "datetime",
  "satisfied_by": "uuid",
  "notes": "string|null",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_004`) - Condition not found
- `422 Unprocessable Entity` (`MESSAGING_005`) - Invalid status or missing waiver notes
- `403 Forbidden` (`MESSAGING_006`) - User lacks permission (especially for waive)
- `409 Conflict` (`MESSAGING_007`) - Condition already satisfied/waived

---

#### `GET /api/v1/applications/{application_id}/conditions/outstanding`
Get outstanding conditions (with optional overdue filter).

**Auth:** Authenticated user with `view:application` scope

**Query Parameters:**
- `overdue`: boolean (optional: filter for past required_by_date)
- `required_by_before`: date (optional: conditions due before date)

**Response (200 OK):**
```json
{
  "items": [...],
  "total": 3,
  "summary": {
    "total_outstanding": 3,
    "overdue_count": 1,
    "due_within_7_days": 2
  }
}
```

**Error Responses:**
- `404 Not Found` (`MESSAGING_008`) - Application not found
- `403 Forbidden` (`MESSAGING_003`) - User lacks access

---

## 2. Models & Database

### 2.1 SQLAlchemy Models

```python
# modules/messaging/models.py

from sqlalchemy import (
    Column, UUID, Text, Boolean, DateTime, Date, 
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base
import enum

class ConditionType(str, enum.Enum):
    DOCUMENT = "document"
    INFORMATION = "information"
    OTHER = "other"

class ConditionStatus(str, enum.Enum):
    OUTSTANDING = "outstanding"
    SATISFIED = "satisfied"
    WAIVED = "waived"

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    application_id = Column(UUID, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    application = relationship("Application", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])

    # Indexes
    __table_args__ = (
        Index("idx_messages_application_sent", "application_id", "sent_at", postgresql_using="btree"),
        Index("idx_messages_recipient_read", "recipient_id", "is_read", "sent_at", postgresql_using="btree"),
        Index("idx_messages_sent_at", "sent_at", postgresql_using="btree"),
    )

class Condition(Base):
    __tablename__ = "conditions"
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    application_id = Column(UUID, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    lender_submission_id = Column(UUID, ForeignKey("lender_submissions.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=False)
    condition_type = Column(SQLEnum(ConditionType), nullable=False)
    status = Column(SQLEnum(ConditionStatus), nullable=False, default=ConditionStatus.OUTSTANDING)
    required_by_date = Column(Date, nullable=False)
    satisfied_at = Column(DateTime(timezone=True), nullable=True)
    satisfied_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    application = relationship("Application", back_populates="conditions")
    lender_submission = relationship("LenderSubmission", back_populates="conditions")
    satisfied_user = relationship("User", foreign_keys=[satisfied_by])

    # Indexes
    __table_args__ = (
        Index("idx_conditions_application_status", "application_id", "status", "required_by_date", postgresql_using="btree"),
        Index("idx_conditions_status_date", "status", "required_by_date", postgresql_using="btree"),
        Index("idx_conditions_lender_submission", "lender_submission_id", postgresql_using="btree"),
    )
```

### 2.2 Pydantic Schemas

```python
# modules/messaging/schemas.py

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

class MessageCreateDTO(BaseModel):
    recipient_id: UUID
    body: str = Field(..., min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def validate_no_pii(cls, v: str) -> str:
        # Basic check to prevent SIN/DOB in messages
        if any(pattern in v.lower() for pattern in ["sin:", "date of birth:", "dob:"]):
            raise ValueError("Messages cannot contain SIN or DOB data")
        return v

class MessageResponseDTO(BaseModel):
    id: UUID
    application_id: UUID
    sender_id: UUID
    recipient_id: UUID
    body: str
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ConditionCreateDTO(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    condition_type: str = Field(..., pattern="^(document|information|other)$")
    required_by_date: date
    lender_submission_id: Optional[UUID] = None

    @field_validator("required_by_date")
    @classmethod
    def validate_future_date(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("required_by_date must be in the future")
        return v

class ConditionUpdateDTO(BaseModel):
    status: str = Field(..., pattern="^(satisfied|waived)$")
    notes: Optional[str] = Field(None, max_length=1000)

class ConditionResponseDTO(BaseModel):
    id: UUID
    application_id: UUID
    lender_submission_id: Optional[UUID]
    description: str
    condition_type: str
    status: str
    required_by_date: date
    satisfied_at: Optional[datetime]
    satisfied_by: Optional[UUID]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

---

## 3. Business Logic

### 3.1 Message Thread Logic
- **Immutability:** Messages cannot be edited or deleted after sending. This satisfies FINTRAC 5-year retention requirements.
- **Access Control:** Users can only send/receive messages for applications where they are a party (borrower, co-borrower, lender, underwriter).
- **Read Receipt:** Only the `recipient_id` user can mark a message as read. `read_at` is set exactly once.
- **PIPEDA Compliance:** Messages are scanned for SIN/DOB patterns. If detected, request is rejected with 422 error.
- **Audit Logging:** Every message creation logs `correlation_id`, `sender_id`, `application_id` (body content is never logged).

### 3.2 Condition State Machine
```
[outstanding] --(satisfied)--> [satisfied]
[outstanding] --(waived)-----> [waived]  (requires underwriter:manage role)
```

**Transition Rules:**
- `satisfied` transition: Any underwriter assigned to application can mark as satisfied. Sets `satisfied_at=now()` and `satisfied_by=current_user`.
- `waived` transition: Requires `underwriter:manage` scope. Must include waiver notes explaining regulatory justification. OSFI B-20 requires audit trail for any waived conditions affecting GDS/TDS.
- Terminal states: `satisfied` and `waived` cannot transition back to `outstanding`.

### 3.3 Automated Reminders & Escalation
**Background Job (Daily at 08:00 EST):**
1. Query conditions with status='outstanding' AND required_by_date = today + 7/3/1 days
2. Send email + in-app notification to assigned underwriter
3. Log reminder event with `correlation_id` (FINTRAC audit)

**Escalation Job (Daily at 09:00 EST):**
1. Query conditions overdue by ≥3 days
2. Create escalation message to underwriter manager
3. Update condition with `notes=concat("ESCALATED: ", notes)`
4. Log escalation event (FINTRAC audit)

### 3.4 Search & Archive
- **Search:** PostgreSQL `tsvector` index on `messages.body` for full-text search. Only accessible to users with `view:application` scope.
- **Archive:** After 1 year of `sent_at`, messages are soft-archived (`is_archived=True`). After 5 years (FINTRAC retention), moved to cold storage partition `messages_archive_YYYY`.

### 3.5 Waiver Approval Workflow
- **Standard Waiver:** Underwriter manager can waive conditions directly if LTV < 80% and condition is non-material.
- **Material Condition Waiver:** If condition affects income verification, property valuation, or debt ratios (OSFI B-20 triggers), requires secondary approval from Chief Risk Officer.
- **Audit Trail:** All waivers log `waiver_reason`, `approved_by`, `risk_approval_id` to separate `condition_waiver_approvals` table.

---

## 4. Migrations

### 4.1 New Tables

```sql
-- alembic/versions/XXXX_add_messaging_conditions.py

def upgrade():
    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("sender_id", UUID, nullable=False),
        sa.Column("recipient_id", UUID, nullable=False),
        sa.Column("body", Text, nullable=False),
        sa.Column("is_read", Boolean, default=False, nullable=False),
        sa.Column("sent_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.Column("read_at", DateTime(timezone=True), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
    )
    
    # Create conditions table
    op.create_table(
        "conditions",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", UUID, nullable=False),
        sa.Column("lender_submission_id", UUID, nullable=True),
        sa.Column("description", Text, nullable=False),
        sa.Column("condition_type", SQLEnum("document", "information", "other"), nullable=False),
        sa.Column("status", SQLEnum("outstanding", "satisfied", "waived"), nullable=False, default="outstanding"),
        sa.Column("required_by_date", Date, nullable=False),
        sa.Column("satisfied_at", DateTime(timezone=True), nullable=True),
        sa.Column("satisfied_by", UUID, nullable=True),
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lender_submission_id"], ["lender_submissions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["satisfied_by"], ["users.id"]),
    )

    # Create indexes
    op.create_index("idx_messages_application_sent", "messages", ["application_id", sa.text("sent_at DESC")])
    op.create_index("idx_messages_recipient_read", "messages", ["recipient_id", "is_read", sa.text("sent_at DESC")])
    op.create_index("idx_conditions_application_status", "conditions", ["application_id", "status", "required_by_date"])
    op.create_index("idx_conditions_status_date", "conditions", ["status", "required_by_date"])
    op.create_index("idx_conditions_lender_submission", "conditions", ["lender_submission_id"])

def downgrade():
    op.drop_index("idx_conditions_lender_submission")
    op.drop_index("idx_conditions_status_date")
    op.drop_index("idx_conditions_application_status")
    op.drop_index("idx_messages_recipient_read")
    op.drop_index("idx_messages_application_sent")
    op.drop_table("conditions")
    op.drop_table("messages")
```

### 4.2 Partitioning for Archive (Future Migration - Year 5)
```sql
-- alembic/versions/XXXX_partition_messages_archive.py
# Scheduled for 5-year FINTRAC retention implementation
op.execute("""
    CREATE TABLE messages_archive_2029 PARTITION OF messages
    FOR VALUES FROM ('2029-01-01') TO ('2030-01-01');
""")
```

---

## 5. Security & Compliance

### 5.1 FINTRAC Requirements
- **Immutable Audit Trail:** All `messages` and `conditions` records are INSERT-only. `updated_at` tracks status changes but history is preserved in separate `audit_log` table.
- **5-Year Retention:** Automatic archival to cold storage after 5 years. Retention policy enforced via PostgreSQL partitioning.
- **Transaction Flagging:** If `condition.description` contains "funds transfer", "deposit", or "withdrawal" AND amount > CAD 10,000, log FINTRAC `large_cash_transaction` event (see `common/audit.py`).
- **Identity Verification:** Messages from borrowers must not contain identity docs. Validation rejects base64-encoded content.

### 5.2 PIPEDA Data Handling
- **No PII in Logs:** `body`, `description`, and `notes` fields are **never** logged. Only metadata (IDs, timestamps, status) is logged.
- **Encryption at Rest:** `messages.body` and `conditions.description` use PostgreSQL `pgcrypto` extension with AES-256 encryption. TDE key managed by `common/security.py::encrypt_pii()`.
- **Data Minimization:** Messages auto-purged (soft delete) if application is withdrawn and 30 days have passed.

### 5.3 OSFI B-20 Integration
- If condition relates to income verification, property appraisal, or debt service ratios, status change triggers recalculation of GDS/TDS with stress test (qualifying_rate = max(rate + 2%, 5.25%)).
- Waived conditions that affect affordability metrics require manual GDS/TDS override approval logged in `risk_exceptions` table.

### 5.4 Authorization Matrix

| Endpoint | Borrower | Co-borrower | Lender | Underwriter | Underwriter Manager |
|----------|----------|-------------|--------|-------------|---------------------|
| POST /messages | ✓ (own app) | ✓ (own app) | ✓ (assigned) | ✓ (assigned) | ✓ (any) |
| GET /messages | ✓ (own app) | ✓ (own app) | ✓ (assigned) | ✓ (assigned) | ✓ (any) |
| PUT /messages/read | ✓ (recipient) | ✓ (recipient) | ✓ (recipient) | ✓ (recipient) | ✓ (recipient) |
| POST /conditions | ✗ | ✗ | ✗ | ✓ (assigned) | ✓ (any) |
| GET /conditions | ✓ (own app) | ✓ (own app) | ✓ (assigned) | ✓ (assigned) | ✓ (any) |
| PUT /conditions | ✗ | ✗ | ✗ | ✓ (satisfy only) | ✓ (satisfy/waive) |

---

## 6. Error Codes & HTTP Responses

**Module Identifier:** `MESSAGING`

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `MessageNotFoundError` | 404 | `MESSAGING_001` | "Message {message_id} not found" | Invalid message_id or user lacks access |
| `MessageValidationError` | 422 | `MESSAGING_002` | "{field}: {reason}" | Body too long, contains PII, or recipient_id invalid |
| `MessagePermissionError` | 403 | `MESSAGING_003` | "Not authorized to access message" | User not party to application or not recipient for read |
| `ConditionNotFoundError` | 404 | `MESSAGING_004` | "Condition {condition_id} not found" | Invalid condition_id |
| `ConditionValidationError` | 422 | `MESSAGING_005` | "{field}: {reason}" | required_by_date in past, invalid status enum |
| `ConditionPermissionError` | 403 | `MESSAGING_006` | "Not authorized to modify condition" | User lacks underwriter role or manager role for waive |
| `ConditionStateError` | 409 | `MESSAGING_007` | "Invalid condition state transition: {from} → {to}" | Attempting to modify satisfied/waived condition |
| `ApplicationNotFoundError` | 404 | `MESSAGING_008` | "Application {application_id} not found" | Invalid application_id or user lacks access |

**Error Response Format (consistent across all endpoints):**
```json
{
  "detail": "Message msg_123 not found",
  "error_code": "MESSAGING_001",
  "correlation_id": "req-550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## 7. Background Jobs & Scheduling

### 7.1 Condition Reminder Job
- **Schedule:** Daily 08:00 EST via Celery Beat
- **Logic:** Query `conditions` where `status='outstanding'` AND `required_by_date` IN (today+7, today+3, today+1)
- **Action:** Send email + push notification. Log `notification_sent` event.

### 7.2 Escalation Job
- **Schedule:** Daily 09:00 EST
- **Logic:** Query `conditions` where `status='outstanding'` AND `required_by_date < today - interval '3 days'`
- **Action:** Create internal message to manager, update condition notes, log `escalation` event.

### 7.3 Archive Job
- **Schedule:** Monthly, 1st day at 02:00 EST
- **Logic:** Move messages with `sent_at < now() - interval '5 years'` to archive partition.
- **Action:** Execute PostgreSQL partition swap, verify row counts, log archival.

---

## 8. Testing Strategy

### 8.1 Unit Tests (pytest -m unit)
- Message body PII validation
- Condition state machine transitions
- Pagination logic
- Authorization checks with mocked user scopes

### 8.2 Integration Tests (pytest -m integration)
- Full message thread workflow between borrower and underwriter
- Condition creation → satisfaction → GDS recalculation
- Background job execution (Celery tasks with test broker)
- FINTRAC audit log verification in PostgreSQL

### 8.3 Load Tests
- Message thread query performance with 10,000+ messages per application
- Condition reminder job with 50,000+ outstanding conditions

---

## 9. Observability

### 9.1 Logging
- All operations log `correlation_id`, `user_id`, `application_id`, `operation` (create/read/update)
- **NEVER log:** `body`, `description`, `notes` fields
- Use `structlog` with JSON format for Splunk ingestion

### 9.2 Metrics (Prometheus)
- `messaging_messages_sent_total` (counter, labeled by sender_role)
- `messaging_conditions_outstanding` (gauge, labeled by condition_type)
- `messaging_conditions_overdue` (gauge)
- `messaging_reminders_sent_total` (counter)
- `messaging_escalations_total` (counter)

### 9.3 Tracing (OpenTelemetry)
- Span per endpoint covering DB query, authorization check, and notification dispatch
- Trace parent ID propagated from API gateway

---

## 10. Future Enhancements

- **Message Attachments:** Separate `message_attachments` table with S3 storage and virus scanning
- **Condition Templates:** Pre-defined condition library for common underwriting requirements
- **SLA Tracking:** Business hours calculation for `required_by_date` based on lender SLA
- **Real-time Notifications:** WebSocket integration for instant message delivery
- **Advanced Search:** ElasticSearch integration for cross-application message search (compliance-approved)