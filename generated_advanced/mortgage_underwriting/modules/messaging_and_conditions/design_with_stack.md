# Design: Messaging & Conditions
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Messaging & Conditions Module Design

**File:** `docs/design/messaging-conditions.md`

---

## 1. Endpoints

### 1.1 Message Endpoints

#### `POST /api/v1/applications/{application_id}/messages`
Send a new message on an application thread.

**Request Schema:**
```python
class MessageCreateRequest(BaseModel):
    recipient_id: UUID  # Required: must be a participant in the application
    body: str  # Required: encrypted at rest; max 5000 chars
    message_type: Literal["internal", "external", "system"] = "internal"
```

**Response Schema:**
```python
class MessageResponse(BaseModel):
    id: UUID
    application_id: UUID
    sender_id: UUID
    recipient_id: UUID
    body: str  # Returned decrypted for authorized users
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime]
    message_type: str
    
    model_config = ConfigDict(from_attributes=True)
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 400 | MESSAGING_001 | Recipient not a participant in application |
| 404 | MESSAGING_002 | Application not found |
| 422 | MESSAGING_003 | Body exceeds 5000 character limit |
| 401 | AUTH_001 | Missing or invalid JWT token |

**Auth:** Authenticated users (any role) with read access to the application.

---

#### `GET /api/v1/applications/{application_id}/messages`
Retrieve paginated message thread.

**Query Parameters:**
```python
cursor: Optional[datetime] = None  # Pagination cursor (sent_at)
limit: int = Query(default=50, le=200)
is_read: Optional[bool] = None  # Filter by read status
message_type: Optional[str] = None  # Filter by type
```

**Response Schema:**
```python
class MessageThreadResponse(BaseModel):
    messages: List[MessageResponse]
    next_cursor: Optional[datetime]
    total_count: int
    
    model_config = ConfigDict(from_attributes=True)
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | MESSAGING_002 | Application not found |
| 401 | AUTH_001 | Unauthorized access to application |

**Auth:** Authenticated users with read access to the application.

---

#### `PUT /api/v1/applications/{application_id}/messages/{message_id}/read`
Mark a message as read.

**Response Schema:**
```python
class MarkReadResponse(BaseModel):
    message_id: UUID
    read_at: datetime
    status: str = "marked_read"
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 403 | MESSAGING_004 | User not the recipient of message |
| 404 | MESSAGING_005 | Message not found |
| 409 | MESSAGING_006 | Message already marked as read |

**Auth:** Authenticated user who is the recipient.

---

### 1.2 Condition Endpoints

#### `POST /api/v1/applications/{application_id}/conditions`
Add a new underwriting condition.

**Request Schema:**
```python
class ConditionCreateRequest(BaseModel):
    lender_submission_id: Optional[UUID] = None
    description: str  # Max 2000 chars; encrypted at rest
    condition_type: Literal["document", "information", "verification", "other"]
    required_by_date: Optional[date] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
```

**Response Schema:**
```python
class ConditionResponse(BaseModel):
    id: UUID
    application_id: UUID
    lender_submission_id: Optional[UUID]
    description: str  # Decrypted for authorized users
    condition_type: str
    status: Literal["outstanding", "satisfied", "waived"]
    required_by_date: Optional[date]
    priority: str
    created_at: datetime
    satisfied_at: Optional[datetime]
    satisfied_by: Optional[UUID]
    waiver_approved_by: Optional[UUID]
    waiver_reason: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | CONDITIONS_001 | Application not found |
| 422 | CONDITIONS_002 | Required by date in the past |
| 403 | CONDITIONS_003 | User lacks underwriter role |

**Auth:** Underwriter, Admin, or System roles only.

---

#### `GET /api/v1/applications/{application_id}/conditions`
List all conditions for an application.

**Query Parameters:**
```python
status: Optional[str] = None  # Filter by status
condition_type: Optional[str] = None
priority: Optional[str] = None
cursor: Optional[datetime] = None  # Pagination cursor (created_at)
limit: int = Query(default=100, le=500)
```

**Response Schema:**
```python
class ConditionListResponse(BaseModel):
    conditions: List[ConditionResponse]
    next_cursor: Optional[datetime]
    total_count: int
    outstanding_count: int
    
    model_config = ConfigDict(from_attributes=True)
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | CONDITIONS_001 | Application not found |
| 401 | AUTH_001 | Unauthorized access |

**Auth:** Authenticated users with read access to the application.

---

#### `PUT /api/v1/applications/{application_id}/conditions/{condition_id}`
Update condition status (satisfy or waive).

**Request Schema:**
```python
class ConditionUpdateRequest(BaseModel):
    status: Literal["satisfied", "waived"]
    waiver_reason: Optional[str] = None  # Required if status=waived
    waiver_approved_by: Optional[UUID] = None  # Required if status=waived
```

**Response Schema:** `ConditionResponse`

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 400 | CONDITIONS_004 | Invalid status transition |
| 403 | CONDITIONS_005 | Only supervisor can waive conditions |
| 404 | CONDITIONS_006 | Condition not found |
| 409 | CONDITIONS_007 | Condition already satisfied |

**Auth:** Underwriter for "satisfied"; Supervisor/Admin for "waived".

---

#### `GET /api/v1/applications/{application_id}/conditions/outstanding`
List outstanding conditions (shortcut endpoint).

**Query Parameters:**
```python
days_until_due: Optional[int] = None  # Filter by upcoming due date
priority: Optional[str] = None
```

**Response Schema:** `ConditionListResponse` (filtered to status='outstanding')

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | CONDITIONS_001 | Application not found |

**Auth:** Authenticated users with read access.

---

## 2. Models & Database

### 2.1 Message Model (`modules/messaging/models.py`)

```python
class Message(Base):
    __tablename__ = "messages"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sender_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    
    # Content (Encrypted)
    body: Mapped[bytes] = mapped_column(  # AES-256 encrypted
        LargeBinary,
        nullable=False
    )
    body_hash: Mapped[str] = mapped_column(  # SHA256 for deduplication/search
        String(64),
        nullable=False,
        index=True
    )
    
    # Status
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    message_type: Mapped[str] = mapped_column(  # internal/external/system
        String(20),
        default="internal",
        index=True
    )
    
    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        index=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Audit (FINTRAC)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])
    
    # Indexes
    __table_args__ = (
        Index(
            "idx_messages_application_timeline",
            "application_id",
            "sent_at",
            "is_read"
        ),
        Index(
            "idx_messages_recipient_unread",
            "recipient_id",
            "is_read",
            "sent_at"
        ),
        CheckConstraint("length(body) <= 5000", name="ck_message_body_length")
    )
```

**Encryption Details:**
- `body` encrypted via `common/security.py:encrypt_pii()` before storage
- `body_hash` used for duplicate detection and search indexing
- Encryption key rotated per application via KMS

---

### 2.2 Condition Model (`modules/conditions/models.py`)

```python
class Condition(Base):
    __tablename__ = "conditions"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lender_submission_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("lender_submissions.id"),
        nullable=True,
        index=True
    )
    satisfied_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    waiver_approved_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    
    # Content (Encrypted)
    description: Mapped[bytes] = mapped_column(  # AES-256 encrypted
        LargeBinary,
        nullable=False
    )
    description_hash: Mapped[str] = mapped_column(  # SHA256
        String(64),
        nullable=False,
        index=True
    )
    
    # Condition Details
    condition_type: Mapped[str] = mapped_column(  # document/information/verification/other
        String(20),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(  # outstanding/satisfied/waived
        String(20),
        default="outstanding",
        index=True
    )
    required_by_date: Mapped[Optional[date]] = mapped_column(
        nullable=True,
        index=True
    )
    priority: Mapped[str] = mapped_column(  # low/medium/high/critical
        String(10),
        default="medium",
        index=True
    )
    
    # Satisfaction/Waiver Timestamps
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Audit (FINTRAC)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False,
        index=True
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="conditions")
    lender_submission: Mapped[Optional["LenderSubmission"]] = relationship()
    satisfied_user: Mapped[Optional["User"]] = relationship(foreign_keys=[satisfied_by])
    waiver_approver: Mapped[Optional["User"]] = relationship(foreign_keys=[waiver_approved_by])
    
    # Indexes
    __table_args__ = (
        Index(
            "idx_conditions_application_status",
            "application_id",
            "status",
            "required_by_date"
        ),
        Index(
            "idx_conditions_overdue",
            "status",
            "required_by_date"
        ),
        CheckConstraint(
            "status IN ('outstanding', 'satisfied', 'waived')",
            name="ck_condition_status_valid"
        )
    )
```

---

### 2.3 Application Model Extension

Add relationships to existing `Application` model:

```python
# In modules/application/models.py
class Application(Base):
    # ... existing fields ...
    
    messages: Mapped[List["Message"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan"
    )
    conditions: Mapped[List["Condition"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan"
    )
```

---

## 3. Business Logic

### 3.1 Message Service (`modules/messaging/services.py`)

```python
class MessageService:
    @staticmethod
    async def send_message(
        session: AsyncSession,
        application_id: UUID,
        sender_id: UUID,
        data: MessageCreateRequest,
        background_tasks: BackgroundTasks
    ) -> Message:
        """
        1. Validate sender and recipient are application participants
        2. Encrypt message body
        3. Create message record
        4. Log audit event (structlog) - DO NOT log body
        5. Trigger notification via background task
        """
        # Validation
        participants = await get_application_participants(session, application_id)
        if data.recipient_id not in participants:
            raise MessageValidationError("Recipient not authorized for application")
        
        # Encryption
        encrypted_body = encrypt_pii(data.body.encode())
        body_hash = hashlib.sha256(data.body.encode()).hexdigest()
        
        # Create
        message = Message(
            application_id=application_id,
            sender_id=sender_id,
            recipient_id=data.recipient_id,
            body=encrypted_body,
            body_hash=body_hash,
            message_type=data.message_type,
            created_by=sender_id
        )
        
        session.add(message)
        await session.flush()
        
        # Audit log (no PII)
        logger.info(
            "message_sent",
            message_id=str(message.id),
            application_id=str(application_id),
            sender_id=str(sender_id),
            recipient_id=str(data.recipient_id),
            message_type=data.message_type
        )
        
        # Background notification
        background_tasks.add_task(
            send_notification,
            user_id=data.recipient_id,
            message_type="new_message",
            metadata={"application_id": str(application_id)}
        )
        
        return message
    
    @staticmethod
    async def mark_as_read(
        session: AsyncSession,
        message_id: UUID,
        user_id: UUID
    ) -> Message:
        """
        1. Verify user is recipient
        2. Update is_read=True and read_at=now()
        3. Idempotent - if already read, return 200
        """
        message = await session.get(Message, message_id)
        if not message:
            raise MessageNotFoundError()
        
        if message.recipient_id != user_id:
            raise MessageAccessDeniedError()
        
        if not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            
            logger.info(
                "message_read",
                message_id=str(message_id),
                user_id=str(user_id)
            )
        
        return message
```

---

### 3.2 Condition Service (`modules/conditions/services.py`)

```python
class ConditionService:
    @staticmethod
    async def create_condition(
        session: AsyncSession,
        application_id: UUID,
        user_id: UUID,
        data: ConditionCreateRequest
    ) -> Condition:
        """
        1. Validate application exists and is in underwriting state
        2. Validate required_by_date is in future
        3. Encrypt description
        4. Create condition
        5. Log audit trail
        6. Schedule reminder task (if due date < 7 days)
        """
        # State validation
        application = await session.get(Application, application_id)
        if not application:
            raise ApplicationNotFoundError()
        
        if application.status not in ["underwriting", "conditional_approval"]:
            raise ConditionBusinessRuleError(
                "Conditions can only be added during underwriting"
            )
        
        # Date validation
        if data.required_by_date and data.required_by_date <= date.today():
            raise ConditionValidationError("Required by date must be in future")
        
        # Encryption
        encrypted_desc = encrypt_pii(data.description.encode())
        desc_hash = hashlib.sha256(data.description.encode()).hexdigest()
        
        # Create
        condition = Condition(
            application_id=application_id,
            lender_submission_id=data.lender_submission_id,
            description=encrypted_desc,
            description_hash=desc_hash,
            condition_type=data.condition_type,
            required_by_date=data.required_by_date,
            priority=data.priority,
            created_by=user_id
        )
        
        session.add(condition)
        await session.flush()
        
        # Schedule reminder if due soon
        if data.required_by_date:
            days_until_due = (data.required_by_date - date.today()).days
            if days_until_due <= 7:
                await schedule_condition_reminder(
                    condition_id=condition.id,
                    due_date=data.required_by_date
                )
        
        logger.info(
            "condition_created",
            condition_id=str(condition.id),
            application_id=str(application_id),
            condition_type=data.condition_type,
            priority=data.priority
        )
        
        return condition
    
    @staticmethod
    async def update_condition_status(
        session: AsyncSession,
        condition_id: UUID,
        user_id: UUID,
        data: ConditionUpdateRequest,
        user_roles: List[str]
    ) -> Condition:
        """
        State machine:
        outstanding -> satisfied (any underwriter)
        outstanding -> waived (supervisor+ only)
        
        1. Validate transition
        2. Verify permissions
        3. Update status and timestamps
        4. If waived, capture waiver approval and reason
        5. Log audit trail
        6. Update application status if all conditions satisfied
        """
        condition = await session.get(Condition, condition_id)
        if not condition:
            raise ConditionNotFoundError()
        
        # Transition validation
        if condition.status != "outstanding":
            raise ConditionBusinessRuleError(
                f"Cannot transition from {condition.status}"
            )
        
        if data.status == "waived" and "supervisor" not in user_roles:
            raise ConditionPermissionError("Only supervisors can waive conditions")
        
        if data.status == "waived":
            if not data.waiver_reason or not data.waiver_approved_by:
                raise ConditionValidationError(
                    "Waiver reason and approver required"
                )
            condition.status = "waived"
            condition.waiver_approved_by = data.waiver_approved_by
            condition.waiver_reason = data.waiver_reason
        else:  # satisfied
            condition.status = "satisfied"
            condition.satisfied_at = datetime.utcnow()
            condition.satisfied_by = user_id
        
        logger.info(
            "condition_status_updated",
            condition_id=str(condition_id),
            new_status=data.status,
            user_id=str(user_id),
            application_id=str(condition.application_id)
        )
        
        # Check if all conditions satisfied for application
        await _check_application_conditions_complete(session, condition.application_id)
        
        return condition
```

---

### 3.3 Reminder & Escalation Logic

```python
# In modules/conditions/tasks.py
async def check_overdue_conditions(session: AsyncSession):
    """
    Cron job runs daily at 06:00 ET
    1. Query conditions where status='outstanding' AND required_by_date < today
    2. Create escalation message to underwriting supervisor
    3. Update condition priority to 'critical'
    4. Log FINTRAC audit event
    """
    overdue = await session.execute(
        select(Condition)
        .where(
            Condition.status == "outstanding",
            Condition.required_by_date < date.today()
        )
    )
    
    for condition in overdue.scalars():
        # Create escalation message
        escalation_msg = (
            f"ESCALATION: Condition {condition.id} is overdue. "
            f"Application {condition.application_id} requires immediate attention."
        )
        
        await MessageService.send_system_message(
            session=session,
            application_id=condition.application_id,
            body=escalation_msg,
            recipient_role="underwriting_supervisor"
        )
        
        condition.priority = "critical"
        
        logger.warning(
            "condition_escalated",
            condition_id=str(condition.id),
            application_id=str(condition.application_id),
            days_overdue=(date.today() - condition.required_by_date).days
        )

async def send_condition_reminders(session: AsyncSession):
    """
    Runs daily at 09:00 ET
    Queries conditions due in 3 days and sends reminder
    """
    reminder_date = date.today() + timedelta(days=3)
    
    conditions = await session.execute(
        select(Condition)
        .where(
            Condition.status == "outstanding",
            Condition.required_by_date == reminder_date
        )
    )
    
    for condition in conditions.scalars():
        await MessageService.send_system_message(
            session=session,
            application_id=condition.application_id,
            body=f"Reminder: Condition due in 3 days",
            recipient_id=condition.application.assigned_underwriter_id
        )
```

---

## 4. Migrations

### 4.1 New Tables

**File:** `alembic/versions/20240115000001_create_messaging_conditions.py`

```python
def upgrade():
    # Enable pgcrypto for encryption
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    
    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("is_read", sa.Boolean(), default=False),
        sa.Column("message_type", sa.String(20), default="internal"),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    
    # Conditions table
    op.create_table(
        "conditions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("lender_submission_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.LargeBinary(), nullable=False),
        sa.Column("description_hash", sa.String(64), nullable=False),
        sa.Column("condition_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="outstanding"),
        sa.Column("required_by_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(10), default="medium"),
        sa.Column("satisfied_at", sa.DateTime(), nullable=True),
        sa.Column("satisfied_by", sa.UUID(), nullable=True),
        sa.Column("waiver_approved_by", sa.UUID(), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lender_submission_id"], ["lender_submissions.id"]),
        sa.ForeignKeyConstraint(["satisfied_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["waiver_approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('outstanding', 'satisfied', 'waived')",
            name="ck_condition_status_valid"
        )
    )
    
    # Indexes
    op.create_index(
        "idx_messages_application_timeline",
        "messages",
        ["application_id", "sent_at", "is_read"]
    )
    op.create_index(
        "idx_messages_recipient_unread",
        "messages",
        ["recipient_id", "is_read", "sent_at"]
    )
    op.create_index(
        "idx_conditions_application_status",
        "conditions",
        ["application_id", "status", "required_by_date"]
    )
    op.create_index(
        "idx_conditions_overdue",
        "conditions",
        ["status", "required_by_date"],
        postgresql_where=sa.text("status = 'outstanding'")
    )
    
    # Row-level security policies (PostgreSQL 15+)
    op.execute("""
        ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
        ALTER TABLE conditions ENABLE ROW LEVEL SECURITY;
    """)

def downgrade():
    op.drop_index("idx_conditions_overdue")
    op.drop_index("idx_conditions_application_status")
    op.drop_index("idx_messages_recipient_unread")
    op.drop_index("idx_messages_application_timeline")
    op.drop_table("conditions")
    op.drop_table("messages")
```

---

## 5. Security & Compliance

### 5.1 PIPEDA Compliance

| Requirement | Implementation |
|-------------|----------------|
| **Encryption at Rest** | `body` and `description` columns use AES-256 encryption via `encrypt_pii()` |
| **No PII in Logs** | Log only UUIDs and metadata; never log `body`, `description`, or user identifiers |
| **Data Minimization** | Messages limited to 5000 chars; conditions to 2000 chars; no optional PII fields |
| **Access Control** | Row-level security ensures users only see messages for applications they participate in |
| **Secure Deletion** | No hard deletes; retention policy handles 5-year FINTRAC requirement |

**Code Example:**
```python
# CORRECT: No PII logged
logger.info("message_sent", message_id=msg_id, application_id=app_id)

# INCORRECT: NEVER do this
logger.info("message_sent", body=message_body, user_email=user.email)
```

---

### 5.2 FINTRAC Compliance

| Requirement | Implementation |
|-------------|----------------|
| **Immutable Audit Trail** | `created_at`, `created_by` never updated. Use `status` changes for state, no row modifications |
| **5-Year Retention** | PostgreSQL partition policy: `PARTITION BY RANGE (created_at)` with 5-year retention |
| **Transaction Logging** | All condition status changes logged with `user_id`, `timestamp`, `reason` |
| **Identity Verification** | Message access logged with `correlation_id` and JWT `sub` claim for audit reconstruction |
| **Large Transaction Flag** | Conditions related to transactions >$10K flagged via `lender_submission_id` link |

**Retention Policy SQL:**
```sql
CREATE TABLE messages_partitioned (
    LIKE messages INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Monthly partitions retained for 5 years
```

---

### 5.3 OSFI B-20 Requirements

While messaging doesn't calculate ratios, conditions **must** support audit of stress test verification:

- **Stress Test Condition**: When `condition_type = 'verification'`, description must contain stress test rate used
- **Audit Trail**: All GDS/TDS verification conditions must link to `lender_submission_id` for traceability
- **Hard Limit Enforcement**: If condition relates to ratio exceedance, system must block approval until satisfied

**Example Condition Description:**
```
"Verify GDS calculation at qualifying rate 7.25% (contract 5.25% + 2%). 
Calculated GDS: 38.2% (OSFI limit: 39%). Documentation required."
```

---

### 5.4 CMHC Insurance Conditions

| LTV Range | Premium | Condition Trigger |
|-----------|---------|-------------------|
| >80.01% | 2.80% | `condition_type = 'insurance'` + description hash |
| >85.01% | 3.10% | Auto-generated when LTV calculated |
| >90.01% | 4.00% | Block approval until insurance certificate uploaded |

**Logic in ConditionService:**
```python
if ltv > Decimal('0.80'):
    await create_condition(
        condition_type="insurance",
        description=f"CMHC insurance required: LTV={ltv:.2%}, Premium={premium:.2%}"
    )
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```
AppException (common/exceptions.py)
├── MessagingException
│   ├── MessageNotFoundError
│   ├── MessageValidationError
│   ├── MessageAccessDeniedError
│   └── MessageBusinessRuleError
└── ConditionsException
    ├── ConditionNotFoundError
    ├── ConditionValidationError
    ├── ConditionPermissionError
    └── ConditionBusinessRuleError
```

### 6.2 Error Mapping Table

| Exception Class | HTTP Status | Error Code | Message Pattern | Retryable |
|-----------------|-------------|------------|-----------------|-----------|
| `MessageNotFoundError` | 404 | MESSAGING_001 | "Message {id} not found" | No |
| `MessageValidationError` | 422 | MESSAGING_002 | "{field}: {reason}" | No |
| `MessageAccessDeniedError` | 403 | MESSAGING_003 | "Access denied to message" | No |
| `ConditionNotFoundError` | 404 | CONDITIONS_001 | "Condition {id} not found" | No |
| `ConditionValidationError` | 422 | CONDITIONS_002 | "{field}: {reason}" | No |
| `ConditionPermissionError` | 403 | CONDITIONS_003 | "Permission denied: {detail}" | No |
| `ConditionBusinessRuleError` | 409 | CONDITIONS_004 | "Business rule violated: {rule}" | No |
| `ApplicationNotFoundError` | 404 | APPLICATION_001 | "Application {id} not found" | No |

### 6.3 Structured Error Response

All errors return consistent JSON:
```json
{
  "detail": "Message recipient not authorized for application",
  "error_code": "MESSAGING_002",
  "correlation_id": "req-123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Implementation in `modules/messaging/exceptions.py`:**
```python
class MessageNotFoundError(MessagingException):
    def __init__(self, message_id: UUID):
        super().__init__(
            message=f"Message {message_id} not found",
            error_code="MESSAGING_001",
            status_code=404
        )
```

---

## 7. Additional Considerations

### 7.1 Search & Archive

**Message Search:**
- Use PostgreSQL `pg_trgm` extension on `body_hash` for fuzzy matching
- Maintain separate `message_search_index` table with encrypted trigrams
- Search endpoint: `GET /messages/search?q={hash}`

**Archive Policy:**
- Messages older than 1 year moved to `messages_archive` partition
- Archived messages require elevated permission to decrypt

### 7.2 Automated Workflows

**Reminder Scheduling:**
- Use `arq` or `celery` with Redis backend
- Job IDs stored in `condition_reminders` table
- Cancel job when condition satisfied

**Escalation Matrix:**
```
Day -3: Reminder to underwriter
Day  0: Escalation to supervisor
Day +3: Escalation to underwriting manager
Day +7: Auto-decline application (business rule)
```

### 7.3 Performance

- **Connection Pooling**: `asyncpg` pool size = 20
- **Query Optimization**: All FKs indexed; composite indexes for common filters
- **Cache**: Redis cache for `GET /conditions/outstanding` (TTL: 5 minutes)
- **Rate Limiting**: 100 messages/hour per user via `slowapi`

---

**Next Steps:**
1. Implement unit tests with `pytest-asyncio` and `anyio`
2. Add OpenTelemetry spans for all service methods
3. Create integration tests for reminder/escalation workflows
4. Document API in OpenAPI 3.1 with examples
5. Run `mypy` and `ruff` before commit