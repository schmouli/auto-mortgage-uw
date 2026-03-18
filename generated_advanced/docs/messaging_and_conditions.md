# Messaging & Conditions
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Messaging & Conditions Module Design

**Design Document Version:** 1.0  
**Module:** `messaging_conditions`  
**Feature Slug:** `messaging-conditions`  
**Date:** 2024

---

## 1. Endpoints

### 1.1 Message Management

#### `POST /api/v1/applications/{application_id}/messages`
Send a new message within an application thread.

- **Authentication:** Required (JWT)
- **Authorization:** User must be a participant (borrower, co-borrower, broker, underwriter) in the application
- **Request Body Schema:**
  ```python
  class MessageCreateRequest(BaseModel):
      recipient_id: UUID  # Target user_id
      body: constr(min_length=1, max_length=5000)  # Enforced PIPEDA data minimization
  ```

- **Response Schema (201 Created):**
  ```python
  class MessageResponse(BaseModel):
      id: UUID
      application_id: UUID
      sender_id: UUID
      recipient_id: UUID
      body: str  # Truncated to 200 chars in list view
      is_read: bool
      sent_at: datetime
      read_at: datetime | None
  ```

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | MSG_001 | "Application {id} not found" | Invalid application_id |
  | 403 | MSG_002 | "Not authorized to message on this application" | User not a participant |
  | 422 | MSG_003 | "body: exceeds maximum length 5000" | Validation failure |
  | 422 | MSG_004 | "recipient_id: user is not an application participant" | Invalid recipient |

#### `GET /api/v1/applications/{application_id}/messages`
Retrieve paginated message thread with optional filters.

- **Authentication:** Required (JWT)
- **Authorization:** User must be a participant in the application
- **Query Parameters:**
  - `page: int = 1` (1-indexed)
  - `page_size: int = 50` (max 100)
  - `is_read: bool | None` - filter by read status
  - `search: str | None` - full-text search on body (min 3 chars)

- **Response Schema (200 OK):**
  ```python
  class MessageThreadResponse(BaseModel):
      messages: list[MessageResponse]
      pagination: PaginationMeta
      total_unread: int
  ```

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | MSG_001 | "Application {id} not found" | Invalid application_id |
  | 403 | MSG_002 | "Not authorized to access this thread" | User not a participant |
  | 422 | MSG_005 | "search: minimum 3 characters required" | Invalid search query |

#### `PUT /api/v1/applications/{application_id}/messages/{message_id}/read`
Mark a specific message as read (recipient only).

- **Authentication:** Required (JWT)
- **Authorization:** User must be the message recipient
- **Request Body:** None (idempotent operation)

- **Response Schema (200 OK):** `MessageResponse` with `is_read=true`

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | MSG_006 | "Message {id} not found" | Invalid message_id |
  | 403 | MSG_007 | "Only recipient can mark as read" | Unauthorized user |
  | 409 | MSG_008 | "Message already marked as read" | Duplicate operation |

---

### 1.2 Condition Management

#### `POST /api/v1/applications/{application_id}/conditions`
Add a new underwriting condition.

- **Authentication:** Required (JWT)
- **Authorization:** Underwriter or Lender role only
- **Request Body Schema:**
  ```python
  class ConditionCreateRequest(BaseModel):
      description: constr(min_length=10, max_length=2000)
      condition_type: Literal['document', 'information', 'other']
      required_by_date: date  # Must be >= today + 2 business days
      lender_submission_id: UUID | None  # Optional linkage to submission
  ```

- **Response Schema (201 Created):**
  ```python
  class ConditionResponse(BaseModel):
      id: UUID
      application_id: UUID
      lender_submission_id: UUID | None
      description: str
      condition_type: str
      status: Literal['outstanding', 'satisfied', 'waived']
      required_by_date: date
      satisfied_at: datetime | None
      satisfied_by: UUID | None
      created_at: datetime
      days_until_due: int  # Calculated field
  ```

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | COND_001 | "Application {id} not found" | Invalid application_id |
  | 403 | COND_002 | "Insufficient privileges to create conditions" | Non-underwriter role |
  | 422 | COND_003 | "required_by_date: must be at least 2 business days in future" | Validation failure |
  | 422 | COND_004 | "description: contains restricted PII pattern" | PIPEDA violation detected |

#### `GET /api/v1/applications/{application_id}/conditions`
List all conditions for an application with filtering.

- **Authentication:** Required (JWT)
- **Authorization:** User must be a participant in the application
- **Query Parameters:**
  - `status: str | None` - filter by status
  - `condition_type: str | None` - filter by type
  - `include_history: bool = false` - include status change audit trail

- **Response Schema (200 OK):** `list[ConditionResponse]`

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | COND_001 | "Application {id} not found" | Invalid application_id |
  | 403 | COND_005 | "Not authorized to view conditions" | User not a participant |

#### `PUT /api/v1/applications/{application_id}/conditions/{condition_id}`
Update condition status (satisfy or waive).

- **Authentication:** Required (JWT)
- **Authorization:** 
  - Status `satisfied`: Any application participant (with proof submission)
  - Status `waived`: Senior Underwriter role only
- **Request Body Schema:**
  ```python
  class ConditionUpdateRequest(BaseModel):
      status: Literal['satisfied', 'waived']
      waiver_reason: str | None  # Required if status=waived
      supporting_document_id: UUID | None  # Required if status=satisfied
  ```

- **Response Schema (200 OK):** `ConditionResponse`

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | COND_006 | "Condition {id} not found" | Invalid condition_id |
  | 403 | COND_007 | "Only Senior Underwriters may waive conditions" | Insufficient role |
  | 403 | COND_008 | "Cannot modify satisfied condition" | Invalid state transition |
  | 409 | COND_009 | "Application has outstanding critical conditions" | Business rule violation |
  | 422 | COND_010 | "waiver_reason: required when waiving" | Missing required field |

#### `GET /api/v1/applications/{application_id}/conditions/outstanding`
Quick retrieval of blocking conditions.

- **Authentication:** Required (JWT)
- **Authorization:** User must be a participant
- **Response Schema (200 OK):** `list[ConditionResponse]` (only outstanding status)

- **Error Responses:**
  | HTTP Status | Error Code | Detail Pattern | Trigger |
  |-------------|------------|----------------|---------|
  | 404 | COND_001 | "Application {id} not found" | Invalid application_id |
  | 403 | COND_005 | "Not authorized to view conditions" | User not a participant |

---

## 2. Models & Database

### 2.1 ORM Models

```python
# modules/messaging_conditions/models.py

from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, DateTime, Date, 
    Enum as SQLEnum, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from datetime import datetime
import uuid

class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[UUID] = Column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), 
        nullable=False, index=True
    )
    sender_id: Mapped[UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    recipient_id: Mapped[UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    body: Mapped[str] = Column(Text, nullable=False)  # Encrypted at rest via pgcrypto
    is_read: Mapped[bool] = Column(Boolean, default=False, nullable=False, index=True)
    sent_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])
    
    __table_args__ = (
        # Optimize thread retrieval and pagination
        Index("idx_messages_application_sent", "application_id", "sent_at"),
        Index("idx_messages_recipient_unread", "recipient_id", "is_read", "sent_at"),
    )


class Condition(Base):
    __tablename__ = "conditions"
    
    id: Mapped[UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[UUID] = Column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    lender_submission_id: Mapped[UUID | None] = Column(
        UUID(as_uuid=True), ForeignKey("lender_submissions.id"), nullable=True, index=True
    )
    description: Mapped[str] = Column(Text, nullable=False)
    condition_type: Mapped[str] = Column(
        SQLEnum("document", "information", "other", name="condition_type_enum"),
        nullable=False, index=True
    )
    status: Mapped[str] = Column(
        SQLEnum("outstanding", "satisfied", "waived", name="condition_status_enum"),
        default="outstanding", nullable=False, index=True
    )
    required_by_date: Mapped[date] = Column(Date, nullable=False, index=True)
    satisfied_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    satisfied_by: Mapped[UUID | None] = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    
    # Audit fields
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="conditions")
    lender_submission: Mapped["LenderSubmission | None"] = relationship(back_populates="conditions")
    satisfied_user: Mapped["User | None"] = relationship(foreign_keys=[satisfied_by])
    
    __table_args__ = (
        # Filter by application and status
        Index("idx_conditions_app_status", "application_id", "status"),
        # Find overdue conditions
        Index("idx_conditions_due_date", "required_by_date", "status"),
    )


class ConditionStatusAuditLog(Base):
    """FINTRAC immutable audit trail for condition status changes."""
    __tablename__ = "condition_status_audit_log"
    
    id: Mapped[UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id: Mapped[UUID] = Column(
        UUID(as_uuid=True), ForeignKey("conditions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    previous_status: Mapped[str] = Column(String(20), nullable=False)
    new_status: Mapped[str] = Column(String(20), nullable=False)
    changed_by: Mapped[UUID] = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    reason: Mapped[str | None] = Column(Text, nullable=True)  # Waiver reason or notes
    supporting_document_id: Mapped[UUID | None] = Column(UUID(as_uuid=True), nullable=True)
    
    # FINTRAC compliance: never updated or deleted
    __table_args__ = (
        {"comment": "FINTRAC 5-year retention: immutable audit trail"},
    )
```

### 2.2 Encryption & Security Configuration

```sql
-- Migration: Enable pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Migration: Encrypt message bodies at rest
ALTER TABLE messages 
ALTER COLUMN body 
SET DATA TYPE TEXT USING pgp_sym_encrypt(body, current_setting('app.encryption_key'));
```

**PIPEDA Compliance:**
- `Message.body` encrypted via PostgreSQL `pgp_sym_encrypt()` with AES-256
- Encryption key managed via `common/config.py` (never hardcoded)
- Application-level decryption in service layer only
- No SIN/DOB patterns allowed in message body (regex validation)

---

## 3. Business Logic

### 3.1 Message Thread Logic

**Thread Retrieval Algorithm:**
1. Validate user participation in application via `application_participants` table
2. Fetch messages with `application_id` filter, ordered by `sent_at DESC`
3. Apply pagination: `OFFSET (page-1)*page_size LIMIT page_size`
4. If `search` parameter provided, use PostgreSQL `to_tsvector()` full-text index on encrypted body
5. Decrypt body in service layer using `pgp_sym_decrypt()`
6. Update `total_unread` count for recipient in same query
7. **Audit Log:** Log `message.thread.access` event with `correlation_id`, `user_id`, `application_id` (no body content)

**Auto-mark-as-read Logic:**
- When recipient calls GET thread, all unread messages older than 1 minute are marked `is_read=true` and `read_at=now()` via background task

### 3.2 Condition State Machine

```python
# modules/messaging_conditions/services.py

class ConditionStatus(Enum):
    OUTSTANDING = "outstanding"
    SATISFIED = "satisfied"
    WAIVED = "waived"

VALID_TRANSITIONS = {
    ConditionStatus.OUTSTANDING: [
        ConditionStatus.SATISFIED, 
        ConditionStatus.WAIVED
    ],
    # No transitions allowed from SATISFIED/WAIVED (immutable final states)
}
```

**Condition Creation Rules:**
1. `required_by_date` must be ≥ `today + 2 business days` (excluding weekends and Canadian statutory holidays)
2. If `lender_submission_id` provided, validate it belongs to same application
3. `description` scanned for SIN/DOB patterns (regex: `\d{3}-\d{3}-\d{3}` and date patterns) - reject if found
4. **OSFI B-20 Integration:** If condition relates to income verification, trigger recalculation of GDS/TDS with stress test `qualifying_rate = max(contract_rate + 2%, 5.25%)` and enforce `GDS ≤ 39%, TDS ≤ 44%` before allowing status change to `satisfied`

**Condition Update Workflow:**
1. **Satisfy Condition:**
   - Requires `supporting_document_id` (FK to documents table)
   - Set `satisfied_at=now()`, `satisfied_by=current_user`
   - Create audit log entry
   - **CMHC Check:** If condition was for insurance premium and LTV > 80%, verify premium tier calculation:
     - `LTV = loan_amount / property_value` (Decimal precision)
     - Premium tiers: 80.01-85% = 2.80%, 85.01-90% = 3.10%, 90.01-95% = 4.00%
   - Trigger application status re-evaluation

2. **Waive Condition:**
   - Requires `Senior Underwriter` role
   - `waiver_reason` mandatory, min length 50 chars
   - Create audit log entry with reason
   - **FINTRAC Reporting:** If waiver involves transaction > CAD $10,000, log `fintrac.condition.waiver` event with `application_id`, `condition_id`, `user_id`

3. **Blocking Logic:** Application cannot transition to `approved` status if any `outstanding` conditions exist. Enforced in `services.py` via `validate_application_approval()` method.

### 3.3 Automated Reminders & Escalation

**Reminder Scheduling Algorithm:**
```python
# Runs daily at 6 AM EST via Celery beat
def schedule_condition_reminders():
    outstanding = db.query(Condition).filter(
        Condition.status == "outstanding",
        Condition.required_by_date >= date.today(),
        Condition.required_by_date <= date.today() + timedelta(days=7)
    ).all()
    
    for condition in outstanding:
        days_until = (condition.required_by_date - date.today()).days
        if days_until in [7, 3, 1]:
            create_notification(
                user_id=condition.application.primary_borrower_id,
                type="condition_reminder",
                priority="high" if days_until <= 3 else "medium",
                metadata={"condition_id": condition.id, "due_date": condition.required_by_date}
            )
```

**Escalation Mechanism:**
```python
# Runs daily at 9 AM EST
def escalate_overdue_conditions():
    overdue = db.query(Condition).filter(
        Condition.status == "outstanding",
        Condition.required_by_date < date.today()
    ).all()
    
    for condition in overdue:
        # Create escalation ticket
        create_escalation(
            application_id=condition.application_id,
            escalation_type="overdue_condition",
            assigned_to=condition.application.underwriter.manager_id,
            priority="critical",
            details={
                "condition_id": condition.id,
                "days_overdue": (date.today() - condition.required_by_date).days
            }
        )
        # Log FINTRAC audit event
        logger.info(
            "condition.overdue.escalation",
            condition_id=condition.id,
            application_id=condition.application_id,
            days_overdue=(date.today() - condition.required_by_date).days,
            correlation_id=correlation_id.get()
        )
```

---

## 4. Migrations

### 4.1 New Tables

```python
# alembic/versions/XXXX_add_messaging_conditions.py

def upgrade():
    # Enable pgcrypto for encryption
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    
    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),  # Encrypted via pgcrypto
        sa.Column("is_read", sa.Boolean, default=False, nullable=False),
        sa.Column("sent_at", sa.DateTime, default=datetime.utcnow, nullable=False),
        sa.Column("read_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow, nullable=False),
        sa.Column("updated_at", sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
    )
    
    # Conditions table
    op.create_table(
        "conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lender_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("condition_type", sa.Enum("document", "information", "other", name="condition_type_enum"), nullable=False),
        sa.Column("status", sa.Enum("outstanding", "satisfied", "waived", name="condition_status_enum"), default="outstanding", nullable=False),
        sa.Column("required_by_date", sa.Date, nullable=False),
        sa.Column("satisfied_at", sa.DateTime, nullable=True),
        sa.Column("satisfied_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow, nullable=False),
        sa.Column("updated_at", sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lender_submission_id"], ["lender_submissions.id"]),
        sa.ForeignKeyConstraint(["satisfied_by"], ["users.id"]),
    )
    
    # FINTRAC audit trail (immutable)
    op.create_table(
        "condition_status_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_status", sa.String(20), nullable=False),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("changed_at", sa.DateTime, default=datetime.utcnow, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("supporting_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["condition_id"], ["conditions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        comment="FINTRAC 5-year retention: immutable audit trail"
    )
    
    # Reminder schedule table
    op.create_table(
        "condition_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reminder_date", sa.Date, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, default=datetime.utcnow, nullable=False),
        sa.ForeignKeyConstraint(["condition_id"], ["conditions.id"], ondelete="CASCADE"),
    )

def downgrade():
    op.drop_table("condition_reminders")
    op.drop_table("condition_status_audit_log")
    op.drop_table("conditions")
    op.drop_table("messages")
    op.execute("DROP TYPE condition_type_enum")
    op.execute("DROP TYPE condition_status_enum")
```

### 4.2 Indexes

```python
# Composite indexes for performance
op.create_index("idx_messages_application_sent", "messages", ["application_id", "sent_at"])
op.create_index("idx_messages_recipient_unread", "messages", ["recipient_id", "is_read", "sent_at"])
op.create_index("idx_conditions_app_status", "conditions", ["application_id", "status"])
op.create_index("idx_conditions_due_date", "conditions", ["required_by_date", "status"])
op.create_index("idx_audit_log_condition", "condition_status_audit_log", ["condition_id", "changed_at"])
```

### 4.3 Data Migration

- **None** for new module. For existing applications, seed with default "welcome" message from system.

---

## 5. Security & Compliance

### 5.1 FINTRAC Requirements

**Mandatory Implementation:**
1. **Immutable Audit Trail:** `condition_status_audit_log` table is **append-only**. Grant INSERT only to application role; no UPDATE/DELETE privileges.
   ```sql
   REVOKE UPDATE, DELETE ON condition_status_audit_log FROM app_user;
   ```

2. **5-Year Retention:** Archive policy moves messages to `messages_archive` table after 5 years:
   ```python
   # Celery task: monthly execution
   def archive_old_messages():
       cutoff_date = date.today() - timedelta(days=5*365)
       db.execute("""
           INSERT INTO messages_archive 
           SELECT * FROM messages WHERE sent_at < :cutoff
       """)
       db.execute("DELETE FROM messages WHERE sent_at < :cutoff")
   ```

3. **Transaction Monitoring:** Log `condition.created` and `condition.satisfied` events for amounts > CAD $10,000:
   ```python
   if application.loan_amount > 10000:
       logger.info(
           "fintrac.condition.high_value",
           application_id=application.id,
           condition_id=condition.id,
           transaction_amount=str(application.loan_amount),  # Decimal as string
           correlation_id=correlation_id.get()
       )
   ```

### 5.2 PIPEDA Data Handling

**Encryption at Rest:**
- `Message.body`: Encrypted using PostgreSQL `pgp_sym_encrypt()` with AES-256-CBC
- Key rotation managed via `common/security.py::rotate_encryption_key()`
- Application service layer handles decryption transparently

**Data Minimization:**
- Message body scanned for SIN/DOB patterns on create/update
- Regex patterns: 
  - SIN: `r'\b\d{3}-\d{3}-\d{3}\b'`
  - DOB: `r'\b(19|20)\d{2}-\d{2}-\d{2}\b'`
- Reject with error code `MSG_010` if detected

**Logging Policy:**
- **NEVER** log message bodies, SIN, DOB, income, or banking data
- **ALLOWED** log fields: `message_id`, `sender_id`, `recipient_id`, `application_id`, `sent_at`, `correlation_id`

### 5.3 OSFI B-20 Integration

When a condition is satisfied that affects income or debt:
```python
def recalculate_debt_service_ratios(application_id: UUID):
    # Fetch updated financial data
    income = get_verified_income(application_id)
    debts = get_verified_debts(application_id)
    property_value = get_property_value(application_id)
    
    # OSFI stress test
    contract_rate = get_contract_rate(application_id)
    qualifying_rate = max(contract_rate + Decimal('2.0'), Decimal('5.25'))
    
    gds = calculate_gds(income, property_value, qualifying_rate)
    tds = calculate_tds(income, debts, qualifying_rate)
    
    # Enforce hard limits
    if gds > Decimal('0.39') or tds > Decimal('0.44'):
        raise ConditionBusinessRuleError(
            "GDS/TDS exceeds OSFI B-20 limits after condition satisfaction"
        )
    
    # Log auditable calculation
    logger.info(
        "osfi.b20.calculation",
        application_id=application_id,
        gds=str(gds.quantize(Decimal('0.001'))),
        tds=str(tds.quantize(Decimal('0.001'))),
        qualifying_rate=str(qualifying_rate),
        correlation_id=correlation_id.get()
    )
```

### 5.4 Authorization Matrix

| Endpoint | Borrower | Broker | Underwriter | Senior Underwriter | Lender |
|----------|----------|--------|-------------|-------------------|--------|
| POST messages | ✓ | ✓ | ✓ | ✓ | ✓ |
| GET messages | ✓ | ✓ | ✓ | ✓ | ✓ |
| PUT message/read | ✓ (own) | ✓ (own) | ✓ (own) | ✓ (own) | ✓ (own) |
| POST conditions | ✗ | ✗ | ✓ | ✓ | ✓ |
| GET conditions | ✓ | ✓ | ✓ | ✓ | ✓ |
| PUT conditions (satisfy) | ✓* | ✓* | ✓ | ✓ | ✓ |
| PUT conditions (waive) | ✗ | ✗ | ✗ | ✓ | ✗ |

*Requires supporting document upload

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```python
# modules/messaging_conditions/exceptions.py

class MessagingException(AppException):
    """Base exception for messaging module."""
    module_code = "MSG"

class ConditionException(AppException):
    """Base exception for conditions module."""
    module_code = "COND"
```

### 6.2 Error Code Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Logging Level |
|-----------------|-------------|------------|-----------------|---------------|
| `ApplicationNotFoundError` | 404 | MSG_001/COND_001 | "Application {id} not found" | WARNING |
| `AuthorizationError` | 403 | MSG_002/COND_002 | "Not authorized to {action}" | INFO |
| `ValidationError` | 422 | MSG_003/COND_003 | "{field}: {reason}" | WARNING |
| `PIPEDAViolationError` | 422 | MSG_010/COND_010 | "PII detected in {field}: restricted pattern" | ERROR |
| `ResourceNotFoundError` | 404 | MSG_006/COND_006 | "{Resource} {id} not found" | WARNING |
| `StateTransitionError` | 409 | COND_009 | "Invalid state transition from {old} to {new}" | WARNING |
| `BusinessRuleViolation` | 409 | COND_011 | "OSFI B-20: {rule} violated" | ERROR |
| `FintracReportingError` | 500 | COND_012 | "Failed to generate FINTRAC report" | CRITICAL |

### 6.3 Structured Error Response Example

```json
{
  "detail": "PII detected in body: restricted pattern SIN format",
  "error_code": "MSG_010",
  "module": "messaging_conditions",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "a1b2c3d4-e5f6-7890",
  "request_id": "req_123456",
  "meta": {
    "application_id": "app_789",
    "violation_field": "body",
    "violation_pattern": "\\d{3}-\\d{3}-\\d{3}"
  }
}
```

---

## 7. Additional Considerations

### 7.1 Message Archive & Search

**Archive Table:**
```python
class MessageArchive(Base):
    __tablename__ = "messages_archive"
    # Same schema as messages but partitioned by year
    __table_args__ = {
        "postgresql_partition_by": "RANGE (sent_at)",
        "comment": "FINTRAC 5-year retention partition"
    }
```

**Full-Text Search:**
- Create GIN index on encrypted body using `pgcrypto` and `to_tsvector`
- Search function decrypts on-the-fly for authorized users only

### 7.2 Waiver Approval Workflow

**Two-Step Waiver Process:**
1. Underwriter requests waiver with reason
2. System creates `WaiverRequest` task assigned to Senior Underwriter
3. Senior Underwriter approves/rejects via separate endpoint
4. On approval, condition status changes to `waived` and audit log created
5. Rejection notifies requester with mandatory feedback

### 7.3 Observability

**Prometheus Metrics:**
```
messaging_messages_sent_total{application_id, sender_role}
messaging_messages_unread_total{recipient_id}
conditions_outstanding_total{application_id, condition_type}
conditions_overdue_total{}
conditions_waived_total{senior_underwriter_id}
```

**OpenTelemetry Traces:**
- Span `message.send` includes attributes: `application.id`, `recipient.role`
- Span `condition.update` includes attributes: `condition.status`, `osfi.b20.triggered`

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_messaging_conditions.py`)
- Test state machine transitions
- Test PIPEDA regex pattern matching
- Test OSFI B-20 ratio recalculation
- Test authorization decorators

### 8.2 Integration Tests (`tests/integration/test_messaging_conditions_integration.py`)
- End-to-end message thread with pagination
- Condition satisfaction blocking application approval
- FINTRAC audit log immutability verification
- Encryption/decryption round-trip

### 8.3 Compliance Tests (`tests/compliance/`)
- FINTRAC 5-year retention verification
- OSFI B-20 stress test enforcement
- PIPEDA encryption key rotation

---

**Document Location:** `docs/design/messaging-conditions.md`  
**Next Steps:** Implementation ticket creation and sprint planning.