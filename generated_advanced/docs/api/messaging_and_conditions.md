Here is the documentation for the **Messaging & Conditions** module.

### 1. API Documentation
**File:** `docs/api/messaging_conditions.md`

```markdown
# Messaging & Conditions API

This module manages communication threads between stakeholders (Borrowers, Underwriters, Brokers) and the lifecycle of lending conditions (requirements) tied to specific applications.

## Messages Endpoints

### POST /api/v1/applications/{id}/messages

Send a new message to a user regarding a specific mortgage application.

**Request:**
```json
{
  "recipient_id": 42,
  "body": "Please upload the latest notice of assessment."
}
```

**Response (201):**
```json
{
  "id": 101,
  "application_id": 5,
  "sender_id": 1,
  "recipient_id": 42,
  "body": "Please upload the latest notice of assessment.",
  "is_read": false,
  "sent_at": "2026-03-02T14:30:00Z",
  "read_at": null
}
```

**Errors:**
- 400: Invalid recipient or application ID
- 422: Validation error (e.g., body empty)
- 403: User not authorized to message this recipient

---

### GET /api/v1/applications/{id}/messages

Retrieve the message thread for a specific application. Supports filtering by read status.

**Query Parameters:**
- `unread_only` (boolean, optional): If true, returns only messages not read by the current user.

**Response (200):**
```json
[
  {
    "id": 100,
    "application_id": 5,
    "sender_id": 42,
    "recipient_id": 1,
    "body": "Here is the document you requested.",
    "is_read": true,
    "sent_at": "2026-03-02T13:00:00Z",
    "read_at": "2026-03-02T13:05:00Z"
  },
  {
    "id": 101,
    "application_id": 5,
    "sender_id": 1,
    "recipient_id": 42,
    "body": "Please upload the latest notice of assessment.",
    "is_read": false,
    "sent_at": "2026-03-02T14:30:00Z",
    "read_at": null
  }
]
```

**Errors:**
- 401: Not authenticated
- 403: User not authorized to view this application's messages

---

### PATCH /api/v1/messages/{id}

Mark a specific message as read.

**Request:**
```json
{
  "is_read": true
}
```

**Response (200):**
```json
{
  "id": 101,
  "is_read": true,
  "read_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 404: Message not found

---

## Conditions Endpoints

### POST /api/v1/applications/{id}/conditions

Create a new condition (outstanding requirement) for an application.

**Request:**
```json
{
  "lender_submission_id": 15,
  "condition_type": "document",
  "description": "Updated letter of employment confirming probation period passed.",
  "required_by_date": "2026-03-15T00:00:00Z"
}
```

**Response (201):**
```json
{
  "id": 50,
  "application_id": 5,
  "lender_submission_id": 15,
  "description": "Updated letter of employment confirming probation period passed.",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "2026-03-15T00:00:00Z",
  "satisfied_at": null,
  "satisfied_by": null,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid date or condition_type
- 404: Application or Lender Submission not found

---

### GET /api/v1/applications/{id}/conditions

List all conditions for a specific application.

**Response (200):**
```json
[
  {
    "id": 49,
    "application_id": 5,
    "description": "Proof of insurance.",
    "condition_type": "other",
    "status": "satisfied",
    "required_by_date": "2026-02-28T00:00:00Z",
    "satisfied_at": "2026-02-27T16:00:00Z",
    "satisfied_by": 1
  },
  {
    "id": 50,
    "application_id": 5,
    "description": "Updated letter of employment...",
    "condition_type": "document",
    "status": "outstanding",
    "required_by_date": "2026-03-15T00:00:00Z",
    "satisfied_at": null,
    "satisfied_by": null
  }
]
```

---

### PATCH /api/v1/conditions/{id}

Update the status of a condition (e.g., mark as satisfied or waived).

**Request:**
```json
{
  "status": "satisfied"
}
```

**Response (200):**
```json
{
  "id": 50,
  "status": "satisfied",
  "satisfied_at": "2026-03-02T11:00:00Z",
  "satisfied_by": 1
}
```

**Errors:**
- 400: Invalid status transition
- 403: Only authorized underwriters can satisfy/waive conditions
```

### 2. Module README
**File:** `docs/messaging_conditions.md`

```markdown
# Messaging & Conditions Module

## Overview
This module facilitates the communication workflow between internal users (underwriters, brokers) and external users (borrowers) during the mortgage underwriting process. It also manages the lifecycle of "conditions"—specific requirements set by lenders that must be met before funding.

## Key Functions

### 1. Messaging Service
*   **Send Message:** Delivers messages from a sender to a recipient within the context of an application.
*   **Thread Retrieval:** Fetches the chronological history of communications for an application.
*   **Read Tracking:** Updates the `read_at` timestamp when a recipient views a message.

### 2. Conditions Service
*   **Condition Creation:** Allows underwriters to create outstanding requirements (Documents, Information, Other) linked to a specific Lender Submission.
*   **Status Management:** Tracks the lifecycle of a condition: `outstanding` -> `satisfied` or `waived`.
*   **Audit Trail:** Automatically records `satisfied_by` (user ID) and `satisfied_at` timestamp to comply with FINTRAC audit requirements.

## Usage Examples

### Sending a Message
```python
from fastapi import FastAPI
from modules.messaging_conditions.services import MessagingService

app = FastAPI()
msg_service = MessagingService()

@app.post("/applications/{app_id}/messages")
async def send_message(app_id: int, recipient_id: int, body: str):
    # Ensure body does not contain PII like SIN (PIPEDA compliance)
    message = await msg_service.send_message(
        application_id=app_id,
        sender_id=get_current_user_id(),
        recipient_id=recipient_id,
        body=body
    )
    return message
```

### Creating a Lender Condition
```python
from modules.messaging_conditions.services import ConditionsService

cond_service = ConditionsService()

# Create a condition for a document
new_condition = await cond_service.create_condition(
    application_id=5,
    lender_submission_id=15,
    condition_type="document",
    description="Updated T1 General",
    required_by_date=datetime(2026, 3, 15)
)
```

### Satisfying a Condition
```python
# Mark condition as satisfied by an underwriter
await cond_service.update_condition_status(
    condition_id=50,
    status="satisfied",
    user_id=get_current_user_id()
)
```

## Compliance Notes
*   **PIPEDA:** Message bodies are scanned for PII patterns. Do not log raw message bodies to STDOUT/JSON logs.
*   **FINTRAC:** All condition status changes are immutable. The `created_at` and `updated_at` (via `satisfied_at`) fields provide the necessary immutable audit trail.
```

### 3. Configuration Notes
**File:** `.env.example` (Update)

```bash
# ... existing config ...

# Messaging & Conditions Configuration
# Default days before a condition becomes overdue for alerts
CONDITION_OVERDUE_ALERT_DAYS=3

# Maximum retention period for messages (years) - Compliance default
MESSAGE_RETENTION_YEARS=7
```

### 4. Changelog Update
**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Messaging & Conditions: New endpoints for application-specific messaging and lender condition tracking.
- Messaging: `POST /applications/{id}/messages` and `GET /applications/{id}/messages` endpoints.
- Conditions: `POST /applications/{id}/conditions` and `PATCH /conditions/{id}` endpoints.
- Audit Trail: Added `satisfied_by` and `satisfied_at` tracking for conditions to meet FINTRAC requirements.

### Changed
- Updated common/exceptions.py to include `MessageDeliveryException` and `ConditionUpdateException`.
```