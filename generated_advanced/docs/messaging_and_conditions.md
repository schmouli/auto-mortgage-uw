# Messaging & Conditions
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

**WARNING**: This design assumes the existence of an `applications` table, a `users` table, and a `lender_submissions` table that are managed by other modules. Details such as the exact encryption key‑management service, the scheduling backend for automated reminders (e.g., Celery beat), and the specific escalation hierarchy (e.g., “manager” role) are not provided in the requirements and are therefore called out as implementation‑time decisions.

---

# Messaging & Conditions Module Design

**Module name:** `messaging_conditions`  
**File location:** `modules/messaging_conditions/`  

---

## 1. Endpoints

| Method | Path | Auth | Request Body | Response Body | Error Codes |
|--------|------|------|--------------|---------------|-------------|
| **POST**   | `/api/v1/applications/{id}/messages` | JWT (participant) | `{ "recipient_id": int, "body": str }` | `{ "id": int, "application_id": int, "sender_id": int, "recipient_id": int, "body": str, "is_read": bool, "sent_at": datetime, "read_at": datetime \| null }` | `MESSAGING_003` (validation) <br> `MESSAGING_004` (permission) |
| **GET**    | `/api/v1/applications/{id}/messages` | JWT (participant) | Query: `page` (int, ≥1), `limit` (int, 1‑100), `sender_id` (int, optional), `recipient_id` (int, optional), `date_from` (ISO8601, optional), `date_to` (ISO8601, optional), `is_read` (bool, optional) | `{ "messages": […], "total": int, "page": int, "limit": int }` | `MESSAGING_004` (permission) |
| **PUT**    | `/api/v1/applications/{id}/messages/{msg_id}/read` | JWT (recipient) | — | `{ "id": int, "is_read": true, "read_at": datetime }` | `MESSAGING_001` (not found) <br> `MESSAGING_004` (permission) |
| **POST**   | `/api/v1/applications/{id}/conditions` | JWT (underwriter/broker) | `{ "description": str, "condition_type": "document" \| "information" \| "other", "required_by_date": date, "lender_submission_id": int \| null }` | `{ "id": int, "application_id": int, "lender_submission_id": int \| null, "description": str, "condition_type": str, "status": "outstanding", "required_by_date": date, "satisfied_at": datetime \| null, "satisfied_by": int \| null, "waived_at": datetime \| null, "waived_by": int \| null, "created_at": datetime }` | `MESSAGING_003` (validation) <br> `MESSAGING_004` (permission) |
| **GET**    | `/api/v1/applications/{id}/conditions` | JWT (participant) | Query: `status` (optional), `condition_type` (optional), `page`, `limit` | `{ "conditions": […], "total": int, "page": int, "limit": int }` | `MESSAGING_004` (permission) |
| **PUT**    | `/api/v1/applications/{id}/conditions/{cond_id}` | JWT (underwriter) | `{ "status": "satisfied" \| "waived", "waiver_reason": str \| null }` | `{ "id": int, … (full condition object) }` | `MESSAGING_002` (not found) <br> `MESSAGING_003` (validation) <br> `MESSAGING_004` (permission) <br> `MESSAGING_005` (conflict) |
| **GET**    | `/api/v1/applications/{id}/conditions/outstanding` | JWT (participant) | Query: `page`, `limit` | `{ "conditions": […], "total": int, "page": int, "limit": int }` | `MESSAGING_004` (permission) |

**Notes**

- All endpoints require a valid JWT issued by the OAuth 2.0 authorization server.  
- The token must contain a `user_id` claim; the service verifies that the user is a participant of the `{id}` application before allowing any operation.  
- `body` and `description` are stored encrypted at rest (AES‑256) and are never written to logs.  
- Pagination follows the convention: `page` starts at 1, `limit` capped at 100. The response includes `total` count.  
- Filtering by date range uses inclusive `date_from` and `date_to` on `sent_at` (messages) or `required_by_date` (conditions).  

---

## 2. Models & Database

### `messages` Table

| Column          | Type          | Constraints                     | Index                     |
|-----------------|---------------|---------------------------------|---------------------------|
| `id`            | `Integer`     | PrimaryKey, autoincrement       | —                         |
| `application_id`| `Integer`     | ForeignKey(`applications.id`), not null | `IX_messages_application_id` |
| `sender_id`     | `Integer`     | ForeignKey(`users.id`), not null | `IX_messages_sender_id`   |
| `recipient_id`  | `Integer`     | ForeignKey(`users.id`), not null | `IX_messages_recipient_id` |
| `body`          | `Text`        | Not null (AES‑256 encrypted)    | —                         |
| `is_read`       | `Boolean`     | Default `False`, not null       | `IX_messages_is_read`     |
| `sent_at`       | `DateTime`    | Default `now()`, not null       | `IX_messages_sent_at`     |
| `read_at`       | `DateTime`    | Nullable                        | —                         |
| `created_at`    | `DateTime`    | Default `now()`, not null       | —                         |
| `updated_at`    | `DateTime`    | Default `now()`, onupdate `now()`, not null | —                         |

**Composite indexes**

- `(application_id, sent_at DESC)` – for thread‑ordered queries.  
- `(sender_id, sent_at DESC)` – for “sent by user” views.  
- `(recipient_id, sent_at DESC)` – for “received by user” views.  

### `conditions` Table

| Column                | Type          | Constraints                     | Index                     |
|-----------------------|---------------|---------------------------------|---------------------------|
| `id`                  | `Integer`     | PrimaryKey, autoincrement       | —                         |
| `application_id`      | `Integer`     | ForeignKey(`applications.id`), not null | `IX_conditions_application_id` |
| `lender_submission_id`| `Integer`     | ForeignKey(`lender_submissions.id`), nullable | `IX_conditions_lender_submission_id` |
| `description`         | `Text`        | Not null (AES‑256 encrypted)    | —                         |
| `condition_type`      | `String(20)`  | Check `IN ('document','information','other')`, not null | `IX_conditions_type` |
| `status`              | `String(20)`  | Default `'outstanding'`, Check `IN ('outstanding','satisfied','waived')`, not null | `IX_conditions_status` |
| `required_by_date`    | `Date`        | Not null                        | `IX_conditions_required_by` |
| `satisfied_at`        | `DateTime`    | Nullable                        | —                         |
| `satisfied_by`        | `Integer`     | ForeignKey(`users.id`), nullable | `IX_conditions_satisfied_by` |
| `waived_at`           | `DateTime`    | Nullable                        | —                         |
| `waived_by`           | `Integer`     | ForeignKey(`users.id`), nullable | `IX_conditions_waived_by` |
| `created_at`          | `DateTime`    | Default `now()`, not null       | —                         |
| `updated_at`          | `DateTime`    | Default `now()`, onupdate `now()`, not null | —                         |

**Composite indexes**

- `(application_id, status, required_by_date)` – for “outstanding by due date” queries.  
- `(status, required_by_date)` – for the daily reminder job.  

---

## 3. Business Logic

### 3.1 Message Lifecycle

1. **Send Message** (`POST /applications/{id}/messages`)  
   - Validate that `recipient_id` belongs to a user who is a participant of the application.  
   - Validate `body` not empty and ≤ 10 000 characters.  
   - Encrypt `body` with AES‑256 (key retrieved from the secrets manager).  
   - Insert record with `sent_at = now()`, `is_read = False`.  
   - Emit a domain event `MessageSent` (for notifications).  
   - Log action with `correlation_id` – **never log the body**.

2. **Retrieve Thread** (`GET /applications/{id}/messages`)  
   - Apply participant permission check.  
   - Apply filters and pagination.  
   - Decrypt `body` on‑the‑fly before returning.  
   - Return sorted by `sent_at DESC`.

3. **Mark as Read** (`PUT /applications/{id}/messages/{msg_id}/read`)  
   - Ensure the caller is the `recipient_id`.  
   - Idempotent – if already read, return existing `read_at`.  
   - Update `is_read = True`, `read_at = now()`.  
   - Emit `MessageRead` event.

### 3.2 Condition Lifecycle

1. **Create Condition** (`POST /applications/{id}/conditions`)  
   - Validate `description` not empty, ≤ 2 000 characters.  
   - Validate `condition_type` is one of the allowed enums.  
   - Validate `required_by_date` ≥ today.  
   - If `lender_submission_id` provided, verify it belongs to the same application.  
   - Encrypt `description` (AES‑256).  
   - Insert with `status = 'outstanding'`.  
   - Emit `ConditionCreated` event.  

2. **List Conditions** (`GET …/conditions`)  
   - Participant‑only access.  
   - Allow filtering by `status`, `condition_type`.  
   - Decrypt `description` before returning.  

3. **Update Status** (`PUT …/conditions/{cond_id}`)  
   - Allowed transitions:  
     - `outstanding → satisfied` (caller must be underwriter; set `satisfied_at`, `satisfied_by`).  
     - `outstanding → waived` (caller must be underwriter; requires `waiver_reason`; set `waived_at`, `waived_by`).  
   - Reject any other transition (`MESSAGING_005`).  
   - Emit `ConditionSatisfied` or `ConditionWaived` event.  

4. **Outstanding View** (`GET …/conditions/outstanding`)  
   - Same permission as list, but pre‑filtered to `status = 'outstanding'`.  
   - Sorted by `required_by_date ASC`.

### 3.3 Automated Reminders & Escalation

- **Daily job** (e.g., Celery beat) queries:
  ```sql
  SELECT * FROM conditions
  WHERE status = 'outstanding'
    AND required_by_date <= CURRENT_DATE + INTERVAL '3 days';
  ```
  For each, send a notification to the assigned underwriter (derived from `application_id`). Log reminder with `correlation_id`.

- **Escalation** (overdue conditions):  
  If `required_by_date < CURRENT_DATE` and `status = 'outstanding'`, the job:
  - Sets an `escalated` flag (or inserts into an `escalations` table).  
  - Assigns the condition to a manager (role‑based).  
  - Emits `ConditionEscalated` event.  

### 3.4 Search & Archive

- **Search**: PostgreSQL full‑text search is not directly compatible with encrypted `body`. A separate `body_tsv` column (populated with a hashed/tokenized version before encryption) can be used. This is an implementation‑time trade‑off.  
- **Archive**: Messages older than 1 year are moved to `messages_archive` (same schema) by a monthly job. Both tables are retained for 5 years per FINTRAC.

---

## 4. Migrations

```python
# Alembic revision identifiers (example)
revision = '2024_06_01_001'
down_revision = None

def upgrade():
    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('application_id', sa.Integer, sa.ForeignKey('applications.id'), nullable=False),
        sa.Column('sender_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('recipient_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('body', sa.Text, nullable=False),  # encrypted at app layer
        sa.Column('is_read', sa.Boolean, default=False, nullable=False),
        sa.Column('sent_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('read_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('IX_messages_application_id', 'messages', ['application_id', 'sent_at'], unique=False)
    op.create_index('IX_messages_sender_id', 'messages', ['sender_id', 'sent_at'], unique=False)
    op.create_index('IX_messages_recipient_id', 'messages', ['recipient_id', 'sent_at'], unique=False)
    op.create_index('IX_messages_is_read', 'messages', ['is_read'], unique=False)

    # Create conditions table
    op.create_table(
        'conditions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('application_id', sa.Integer, sa.ForeignKey('applications.id'), nullable=False),
        sa.Column('lender_submission_id', sa.Integer, sa.ForeignKey('lender_submissions.id'), nullable=True),
        sa.Column('description', sa.Text, nullable=False),  # encrypted at app layer
        sa.Column('condition_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), default='outstanding', nullable=False),
        sa.Column('required_by_date', sa.Date, nullable=False),
        sa.Column('satisfied_at', sa.DateTime, nullable=True),
        sa.Column('satisfied_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('waived_at', sa.DateTime, nullable=True),
        sa.Column('waived_by', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('IX_conditions_application_id', 'conditions', ['application_id', 'status', 'required_by_date'], unique=False)
    op.create_index('IX_conditions_status', 'conditions', ['status', 'required_by_date'], unique=False)
    op.create_index('IX_conditions_type', 'conditions', ['condition_type'], unique=False)
    op.create_index('IX_conditions_required_by', 'conditions', ['required_by_date'], unique=False)
    op.create_index('IX_conditions_satisfied_by', 'conditions', ['satisfied_by'], unique=False)
    op.create_index('IX_conditions_waived_by', 'conditions', ['waived_by'], unique=False)

def downgrade():
    op.drop_table('conditions')
    op.drop_table('messages')
```

---

## 5. Security & Compliance

| Requirement | Implementation |
|-------------|----------------|
| **OSFI B‑20** | Conditions may be used to enforce stress‑test documentation; the module logs every status change (satisfied/waived) to provide an auditable trail that can be linked back to the underwriting decision. |
| **FINTRAC** | All `messages` and `conditions` records are immutable (no `DELETE` endpoint). `created_at`/`updated_at` provide a 5‑year retention anchor. A daily job archives records older than 1 year into `*_archive` tables but never purges them before the 5‑year horizon. |
| **CMHC** | Not directly applicable; however, if a condition relates to insurance verification, the `condition_type = 'document'` can be used to track the CMHC insurance certificate, and the module ensures the document is stored encrypted. |
| **PIPEDA** | `body` (messages) and `description` (conditions) are encrypted with AES‑256 before persistence. The encryption key is fetched from a secrets manager (e.g., HashiCorp Vault) and is never logged. SIN/DOB are never stored in these tables. Error responses do not include plaintext PII. |
| **Authentication** | All endpoints require a JWT (`Authorization: Bearer <token>`). The token is validated via the `security.verify_token()` helper. |
| **Authorization** | Each endpoint checks that the caller is a participant of the referenced application (via a `participants` table or similar). Role checks enforce that only underwriters may waive conditions. |
| **Audit Logging** | Every write operation (`send_message`, `mark_read`, `create_condition`, `update_condition`) emits a `structlog` JSON record with `correlation_id`, `user_id`, `application_id`, and action type. The `body`/`description` are never included. |
| **Observability** | OpenTelemetry spans cover each service method. Prometheus metrics (`messages_sent_total`, `conditions_overdue_total`) are exposed on `/metrics`. |
| **Secure Communication** | Internal service‑to‑service calls use mTLS. External clients communicate over HTTPS only. |

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy (in `modules/messaging_conditions/exceptions.py`)

```python
class MessagingConditionError(AppException):
    """Base for all messaging/condition errors."""
    pass

class MessageNotFoundError(MessagingConditionError):
    status_code = 404
    error_code = "MESSAGING_001"
    message_template = "Message {msg_id} not found"

class ConditionNotFoundError(MessagingConditionError):
    status_code = 404
    error_code = "MESSAGING_002"
    message_template = "Condition {cond_id} not found"

class ValidationError(MessagingConditionError):
    status_code = 422
    error_code = "MESSAGING_003"
    message_template = "{field}: {reason}"

class BusinessRuleError(MessagingConditionError):
    status_code = 409
    error_code = "MESSAGING_004"
    message_template = "Business rule violated: {detail}"

class PermissionDeniedError(MessagingConditionError):
    status_code = 403
    error_code = "MESSAGING_005"
    message_template = "Access denied to {resource}"
```

### Mapping to HTTP Responses

| Exception                | HTTP Status | Error Code | Example Response Body |
|--------------------------|-------------|------------|-----------------------|
| `MessageNotFoundError`   | 404         | MESSAGING_001 | `{"detail": "Message 123 not found", "error_code": "MESSAGING_001"}` |
| `ConditionNotFoundError`| 404         | MESSAGING_002 | `{"detail": "Condition 456 not found", "error_code": "MESSAGING_002"}` |
| `ValidationError`        | 422         | MESSAGING_003 | `{"detail": "body: must not be empty", "error_code": "MESSAGING_003"}` |
| `BusinessRuleError`      | 409         | MESSAGING_004 | `{"detail": "Business rule violated: cannot transition from satisfied to outstanding", "error_code": "MESSAGING_004"}` |
| `PermissionDeniedError`  | 403         | MESSAGING_005 | `{"detail": "Access denied to messages", "error_code": "MESSAGING_005"}` |

---

## 7. Implementation Checklist (for developer)

- [ ] Create `modules/messaging_conditions/` with `__init__.py`, `models.py`, `schemas.py`, `services.py`, `routes.py`, `exceptions.py`.  
- [ ] Define Pydantic schemas for request/response DTOs (use v2).  
- [ ] Implement `services.py` with async functions for each business operation; inject `AsyncSession` and `current_user`.  
- [ ] Use `common.security.encrypt_pii()` to encrypt `body` and `description` before saving.  
- [ ] Add `get_async_session()` dependency in routes.  
- [ ] Wire up `structlog` and OpenTelemetry in services.  
- [ ] Write unit tests (pytest‑asyncio) covering validation, permission, and encryption.  
- [ ] Write integration tests covering the full lifecycle (send → read → condition → satisfy).  
- [ ] Add Alembic migration script (see §4).  
- [ ] Configure Prometheus metrics for counts and overdue conditions.  
- [ ] Document the reminder & escalation jobs (Celery tasks) in a separate `jobs/` module.  
- [ ] Update `.env.example` with encryption key and reminder schedule placeholders.  
- [ ] Run `ruff` and `mypy` – zero errors.  
- [ ] Run `pip-audit` before merging.  

---