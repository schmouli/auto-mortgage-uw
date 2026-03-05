# Messaging & Conditions
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Messaging & Conditions Module

**Module ID:** `messaging_conditions`  
**Feature Slug:** `messaging-conditions`  
**Document Path:** `docs/design/messaging-conditions.md`

---

## 1. Endpoints

### 1.1 Message Endpoints

#### `POST /api/v1/applications/{application_id}/messages`
Send a new message on an application thread.

**Auth:** Authenticated (JWT) — sender must have `APPLICATION_ACCESS` permission for target application.

**Request Schema:**
```python
class MessageCreateRequest(BaseModel):
    recipient_id: UUID  # Target user_id
    body: str  # Min length 1, max length 5000 characters
```

**Response Schema (201 Created):**
```python
class MessageResponse(BaseModel):
    id: UUID
    application_id: UUID
    sender_id: UUID
    recipient_id: UUID
    body: str
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime]
```

**Error Responses:**
| Status | Error Code | Detail Pattern | Condition |
|--------|------------|----------------|-----------|
| 401 | AUTH_001 | "Invalid or missing token" | Authentication failure |
| 403 | MESSAGING_002 | "Access denied to application {id}" | User lacks APPLICATION_ACCESS |
| 404 | MESSAGING_004 | "Application {id} not found" | Invalid application_id |
| 422 | MESSAGING_003 | "body: exceeds maximum length 5000" | Validation failure |

---

#### `GET /api/v1/applications/{application_id}/messages`
Retrieve paginated message thread.

**Auth:** Authenticated — user must be participant (sender or recipient) on the application.

**Query Parameters:**
- `page`: int ≥ 1 (default: 1)
- `page_size`: int ∈ [10, 100] (default: 50)
- `is_read`: bool (optional filter)

**Response Schema (200 OK):**
```python
class MessageThreadResponse(BaseModel):
    messages: List[MessageResponse]
    total_count: int
    page: int
    page_size: int
    unread_count: int  # Total unread for this user on this application
```

**Error Responses:**
| Status | Error Code | Detail Pattern | Condition |
|--------|------------|----------------|-----------|
| 401 | AUTH_001 | "Invalid or missing token" | Authentication failure |
| 403 | MESSAGING_002 | "Access denied to application {id}" | User not a participant |
| 404 | MESSAGING_004 | "Application {id} not found" | Invalid application_id |
| 422 | MESSAGING_003 | "page_size: must be ≤ 100" | Validation failure |

---

#### `PUT /api/v1/applications/{application_id}/messages/{message_id}/read`
Mark a message as read (idempotent).

**Auth:** Authenticated — user must be the message recipient.

**Response Schema (200 OK):**
```python
class MessageReadResponse(BaseModel):
    id: UUID
    is_read: bool  # Always True after operation
    read_at: datetime
```

**Error Responses:**
| Status | Error Code | Detail Pattern | Condition |
|--------|------------|----------------|-----------|
| 401 | AUTH_001 | "Invalid or missing token" | Authentication failure |
| 403 | MESSAGING_002 | "Only recipient can mark as read" | User is not recipient |
| 404 | MESSAGING_001 | "Message {msg_id} not found" | Invalid message_id |
| 409 | MESSAGING_005 | "Message already marked read" | read_at already set |

---

### 1.2 Condition Endpoints

#### `POST /api/v1/applications/{application_id}/conditions`
Add a new underwriting condition.

**Auth:** Authenticated — requires `UNDERWRITER` or `LENDER` role.

**Request Schema:**
```python
class ConditionCreateRequest(BaseModel):
    lender_submission_id: Optional[UUID]  # If condition relates to specific submission
    description: str  # Min 10, max 2000 characters
    condition_type: Literal["document", "information", "other"]
    required_by_date: Optional[datetime]  # Must be ≥ now + 1 day
```

**Response Schema (201 Created):**
```python
class ConditionResponse(BaseModel):
    id: UUID
    application_id: UUID
    lender_submission_id: Optional[UUID]
    description: str
    condition_type: str
    status: str  # Always "outstanding" on creation
    required_by_date: Optional[datetime]
    satisfied_at: Optional[datetime]
    satisfied_by: Optional[UUID]
    created_at: datetime
```

**Error Responses:**
| Status | Error Code | Detail Pattern | Condition |
|--------|------------|----------------|-----------|
| 401 | AUTH_001 | "Invalid or missing token" | Authentication failure |
| 403 | CONDITIONS_002 | "Insufficient privileges" | User lacks UNDERWRITER/LENDER role |
| 404 | MESSAGING_004 | "Application {id} not found" | Invalid application_id |
| 422 | CONDITIONS_003 | "required_by_date: must be future date" | Validation failure |

---

#### `GET /api/v1/applications/{application_id}/conditions`
List all conditions for an application.

**Auth:** Authenticated — user must have APPLICATION_ACCESS.

**Query Parameters:**
- `status`: enum ["outstanding", "satisfied", "waived"] (optional)
- `condition_type`: enum ["document", "information", "other"] (optional)

**Response Schema (200 OK):**
```python
class ConditionListResponse(BaseModel):
    conditions: List[ConditionResponse]
    summary: ConditionSummary  # Counts by status
```

**Error Responses:**
| Status | Error Code | Detail Pattern | Condition |
|--------|------------|----------------|-----------|
| 401 | AUTH_001 | "Invalid or missing token" | Authentication failure |
| 403 | MESSAGING_002 | "Access denied to application {id}" | User lacks APPLICATION_ACCESS |
| 404 | MESSAGING_004 | "Application {id} not found" | Invalid application_id |

---

#### `PUT /api/v1/applications/{application_id}/conditions/{condition_id}`
Update condition status (satisfy or waive).

**Auth:** Authenticated — role-based permission required.

**Request Schema:**
```python
class ConditionUpdateRequest(BaseModel):
    status: Literal["satisfied", "waived"]
    # Required if status="satisfied"
    satisfied_by: Optional[UUID]  # Must match authenticated user unless admin
    waiver_justification: Optional[str]  # Required if status="waived"
```

**Response Schema (200 OK):** `ConditionResponse`

**Error Responses:**
| Status | Error Code | Detail Pattern | Condition |
|--------|------------|----------------|-----------|
| 401 | AUTH_001 | "Invalid or missing token" | Authentication failure |
| 403 | CONDITIONS_005 | "Waiver requires MANAGER approval" | Unauthorized waiver attempt |
| 404 | CONDITIONS_001 | "Condition {cond_id} not found" | Invalid condition_id |
| 409 | CONDITIONS_004 | "Invalid transition: satisfied → waived" | Illegal state change |
| 422 | CONDITIONS_003 | "waiver_justification: required" | Missing justification |

---

#### `GET /api/v1/applications/{application_id}/conditions/outstanding`
Fast-path endpoint for outstanding conditions only.

**Auth:** Authenticated — APPLICATION_ACCESS required.

**Response Schema (200 OK):**
```python
class OutstandingConditionsResponse(BaseModel):
    conditions: List[ConditionResponse]  # Only status="outstanding"
    overdue_count: int
    due_within_48h_count: int
```

**Error Responses:** Same as GET /conditions.

---

## 2. Models & Database

### 2.1 SQLAlchemy ORM Models

**File:** `modules/messaging_conditions/models.py`

```python
from sqlalchemy import (
    Column, UUID, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum,
    Index, Integer
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from common.database import Base
import uuid

# Enum types
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
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)  # FINTRAC: immutable audit trail
    is_read = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # PIPEDA: No PII in message body (enforced at service layer)
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application = relationship("Application", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])

    # Indexes
    __table_args__ = (
        Index("idx_messages_application_sent", application_id, sent_at.desc()),
        Index("idx_messages_recipient_read", recipient_id, is_read),
        Index("idx_messages_application_read", application_id, is_read),
    )

class Condition(Base):
    __tablename__ = "conditions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    lender_submission_id = Column(UUID(as_uuid=True), ForeignKey("lender_submissions.id"), nullable=True)
    description = Column(Text, nullable=False)  # FINTRAC: immutable
    condition_type = Column(SQLEnum(ConditionType), nullable=False)
    status = Column(SQLEnum(ConditionStatus), default=ConditionStatus.OUTSTANDING, nullable=False)
    required_by_date = Column(DateTime(timezone=True), nullable=True)
    satisfied_at = Column(DateTime(timezone=True), nullable=True)
    satisfied_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application = relationship("Application", back_populates="conditions")
    lender_submission = relationship("LenderSubmission", back_populates="conditions")
    satisfied_user = relationship("User", foreign_keys=[satisfied_by])

    # Indexes
    __table_args__ = (
        Index("idx_conditions_application_status", application_id, status),
        Index("idx_conditions_status_date", status, required_by_date),
        Index("idx_conditions_app_type_status", application_id, condition_type, status),
    )
```

**Regulatory Notes:**
- **FINTRAC:** Both tables enforce immutable audit trail via `created_at` and no DELETE operations. `updated_at` tracks only metadata changes, never core financial/identity data.
- **PIPEDA:** `body` and `description` fields must not contain encrypted PII (SIN/DOB). Service layer validates and rejects submissions containing SIN patterns.
- **OSFI B-20:** When condition status changes to "satisfied", triggers async recalculation of GDS/TDS ratios in underwriting module with stress test `max(contract_rate + 2%, 5.25%)`.

---

## 3. Business Logic

### 3.1 Message Thread Algorithm
**Service:** `modules/messaging_conditions/services.py`

```python
async def get_message_thread(
    session: AsyncSession,
    application_id: UUID,
    user_id: UUID,
    page: int = 1,
    page_size: int = 50,
    is_read: Optional[bool] = None
) -> MessageThreadResponse:
    """
    1. Verify user has APPLICATION_ACCESS on application_id
    2. Build query: SELECT * FROM messages WHERE application_id = ?
    3. Apply is_read filter if provided
    4. ORDER BY sent_at DESC
    5. Paginate using LIMIT/OFFSET
    6. Count total rows for pagination metadata
    7. Fetch unread count: SELECT COUNT(*) WHERE recipient_id = ? AND is_read = false
    8. Return structured response
    """
```

**Audit Logging:** Log `correlation_id`, `user_id`, `application_id`, `action="get_message_thread"` with structlog. **NEVER** log message body content.

### 3.2 Condition State Machine

**Valid Transitions:**
```
┌─────────────┐     satisfy()     ┌─────────────┐
│ outstanding ├──────────────────►│  satisfied  │
└──────┬──────┘                   └─────────────┘
       │ waive()                        ▲
       │ (MANAGER only)                 │
       ▼                                │
┌─────────────┐                        │
│   waived    ├────────────────────────┘
└─────────────┘       (no transitions out)
```

**Transition Rules:**
- `outstanding → satisfied`: Requires `satisfied_by` = authenticated user ID. Sets `satisfied_at = now()`.
- `outstanding → waived`: Requires `waiver_justification` and user role ∈ {MANAGER, SENIOR_UNDERWRITER}. Creates audit log entry in `condition_waiver_audits` table.
- **Illegal transitions:** Return `CONDITIONS_004` error.

### 3.3 Automated Condition Reminder Scheduler

**Cron Job:** `uv run python -m modules.messaging_conditions.tasks.reminders`

**Algorithm:**
```python
async def send_condition_reminders():
    """
    1. Query outstanding conditions due within 48h:
       SELECT * FROM conditions 
       WHERE status = 'outstanding' 
       AND required_by_date BETWEEN NOW() AND NOW() + INTERVAL '2 days'
    
    2. For each condition:
       - Send email/SMS to applicant
       - Send notification to assigned underwriter
       - Log reminder event (no PII in log)
    
    3. Query overdue conditions (> required_by_date):
       - Escalate to manager via notification
       - Update escalation flag in conditions table
       - Log escalation event
    """
```

**FINTRAC Compliance:** Reminder events are logged as "system actions" with `created_by = SYSTEM` for 5-year retention.

### 3.4 Waiver Approval Workflow

**Sub-Module:** `modules/messaging_conditions/waiver_workflow.py`

1. Underwriter submits waiver request: `POST /conditions/{id}/waiver-request`
   - Stores in `condition_waiver_requests` table
   - Status: `PENDING_MANAGER_REVIEW`

2. Manager approves/denies: `PUT /waiver-requests/{id}/approve`
   - Approved: Updates condition status to `waived`
   - Denied: Sets condition status back to `outstanding` with rejection note

3. Both actions create immutable audit records.

---

## 4. Migrations

**File:** `alembic/versions/{timestamp}_add_messaging_conditions.py`

```python
def upgrade():
    # Create enum types
    op.execute("CREATE TYPE condition_type_enum AS ENUM ('document', 'information', 'other')")
    op.execute("CREATE TYPE condition_status_enum AS ENUM ('outstanding', 'satisfied', 'waived')")
    
    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", UUID(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("sender_id", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_id", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", Text(), nullable=False),
        sa.Column("is_read", Boolean(), default=False, nullable=False),
        sa.Column("sent_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("read_at", DateTime(timezone=True), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    
    # Create conditions table
    op.create_table(
        "conditions",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", UUID(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("lender_submission_id", UUID(), sa.ForeignKey("lender_submissions.id"), nullable=True),
        sa.Column("description", Text(), nullable=False),
        sa.Column("condition_type", SQLEnum(ConditionType), nullable=False),
        sa.Column("status", SQLEnum(ConditionStatus), default="outstanding", nullable=False),
        sa.Column("required_by_date", DateTime(timezone=True), nullable=True),
        sa.Column("satisfied_at", DateTime(timezone=True), nullable=True),
        sa.Column("satisfied_by", UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    
    # Create indexes
    op.create_index("idx_messages_application_sent", "messages", ["application_id", sa.text("sent_at DESC")])
    op.create_index("idx_messages_recipient_read", "messages", ["recipient_id", "is_read"])
    op.create_index("idx_conditions_application_status", "conditions", ["application_id", "status"])
    op.create_index("idx_conditions_status_date", "conditions", ["status", "required_by_date"])
    
    # Create waiver audit table for FINTRAC compliance
    op.create_table(
        "condition_waiver_audits",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("condition_id", UUID(), sa.ForeignKey("conditions.id"), nullable=False),
        sa.Column("requested_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("justification", Text(), nullable=False),
        sa.Column("status", SQLEnum(["approved", "denied", "pending"]), nullable=False),
        sa.Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
```

**Data Migration:** None required. New tables are additive.

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Trigger:** When condition status transitions to `satisfied` AND condition_type = "document" (e.g., income verification).
- **Action:** Async task publishes `ConditionSatisfiedEvent` to message queue.
- **Consumer:** Underwriting module recalculates GDS/TDS with stress test:
  - `qualifying_rate = max(contract_rate + 2%, 5.25%)`
  - Enforce hard limits: GDS ≤ 39%, TDS ≤ 44%
  - Log calculation breakdown with `correlation_id` for audit.

### 5.2 FINTRAC Reporting Triggers
- **Condition Creation:** Log `condition_id`, `application_id`, `created_by`, `created_at`. Retain 5 years.
- **Condition Satisfaction:** Log `condition_id`, `satisfied_by`, `satisfied_at`. This is a "financial transaction record" if condition relates to income verification.
- **Message Sent:** Log `message_id`, `application_id`, `sender_id`, `sent_at` (no body). Retain 5 years.
- **Immutable Records:** No DELETE endpoint exists. No UPDATE allowed on `body`, `description`, `sent_at`, `created_at`.

### 5.3 PIPEDA Data Handling
- **Encryption:** `body` and `description` are encrypted at rest using AES-256 via pgcrypto (PostgreSQL).
- **Data Minimization:** Service layer validates that `body` and `description` do not contain:
  - SIN patterns (regex: `\b\d{3}-\d{3}-\d{3}\b`)
  - DOB patterns (regex: `\b\d{4}-\d{2}-\d{2}\b`)
  - Banking details (regex for MICR/ABA numbers)
- **Rejection:** If PII detected, return `MESSAGING_003` or `CONDITIONS_003` with message: "Field contains prohibited PII data."
- **Logging:** Never log `body`, `description`, or any field containing free-text PII.

### 5.4 Authentication & Authorization Matrix

| Endpoint | Required Scope | Role Restrictions | Custom Check |
|----------|----------------|-------------------|--------------|
| POST /messages | `APPLICATION_ACCESS` | None | User is application participant |
| GET /messages | `APPLICATION_ACCESS` | None | User is sender OR recipient |
| PUT /messages/read | `APPLICATION_ACCESS` | None | User is message recipient |
| POST /conditions | `CONDITION_CREATE` | UNDERWRITER, LENDER | User assigned to application |
| GET /conditions | `APPLICATION_ACCESS` | None | User is application stakeholder |
| PUT /conditions | `CONDITION_UPDATE` | UNDERWRITER, LENDER, MANAGER | Role-based status transition |
| GET /conditions/outstanding | `APPLICATION_ACCESS` | None | Same as GET /conditions |

**Permission Enforcement:** Implemented in `services.py` using `verify_application_access()` and `verify_role()` helpers.

---

## 6. Error Codes & HTTP Responses

**File:** `modules/messaging_conditions/exceptions.py`

```python
from common.exceptions import AppException

class MessagingException(AppException):
    module_code = "MESSAGING"

class ConditionsException(AppException):
    module_code = "CONDITIONS"

class MessagingNotFoundError(MessagingException):
    http_status = 404
    error_code = "MESSAGING_001"
    message_template = "Message {resource_id} not found"

class MessagingAccessDeniedError(MessagingException):
    http_status = 403
    error_code = "MESSAGING_002"
    message_template = "Access denied to message {resource_id}"

class MessagingValidationError(MessagingException):
    http_status = 422
    error_code = "MESSAGING_003"
    message_template = "{field}: {reason}"

class MessagingApplicationNotFoundError(MessagingException):
    http_status = 404
    error_code = "MESSAGING_004"
    message_template = "Application {application_id} not found"

class ConditionsNotFoundError(ConditionsException):
    http_status = 404
    error_code = "CONDITIONS_001"
    message_template = "Condition {resource_id} not found"

class ConditionsAccessDeniedError(ConditionsException):
    http_status = 403
    error_code = "CONDITIONS_002"
    message_template = "Access denied to condition {resource_id}"

class ConditionsValidationError(ConditionsException):
    http_status = 422
    error_code = "CONDITIONS_003"
    message_template = "{field}: {reason}"

class ConditionsStatusTransitionError(ConditionsException):
    http_status = 409
    error_code = "CONDITIONS_004"
    message_template = "Invalid status transition from {old_status} to {new_status}"

class ConditionsWaiverApprovalError(ConditionsException):
    http_status = 403
    error_code = "CONDITIONS_005"
    message_template = "Waiver requires MANAGER approval"
```

**FastAPI Exception Handlers:**
```python
# In modules/messaging_conditions/routes.py
@app.exception_handler(MessagingException)
async def messaging_exception_handler(request: Request, exc: MessagingException):
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": exc.message, "error_code": exc.error_code, "correlation_id": get_correlation_id()}
    )
```

---

## 7. Future Enhancements (Out of Scope)

- **Message Search:** Add `POST /messages/search` with PostgreSQL full-text search on `body` field (with PII masking).
- **Archive:** Implement `POST /messages/archive` to move messages > 1 year to cold storage (S3 with Glacier) while retaining metadata for FINTRAC.
- **Real-time:** Add WebSocket endpoint `/ws/applications/{id}/messages` for live thread updates.
- **Escalation Rules:** Configurable escalation matrix via `common/config.py` (e.g., overdue 5 days → manager, 10 days → director).

---

**Design Approval Checklist:**
- [ ] All endpoints include authz checks
- [ ] No PII logging in any code path
- [ ] FINTRAC 5-year retention documented
- [ ] OSFI B-20 trigger mechanism defined
- [ ] Composite indexes cover query patterns
- [ ] Waiver workflow audit table created
- [ ] Error codes unique per module
- [ ] Automated reminder task scheduled in production cron