# Documentation: Messaging & Conditions Module

## 1. API Documentation

**File:** `docs/api/messaging_and_conditions.md`

```markdown
# Messaging & Conditions API

This module manages communication threads between applicants/brokers and underwriters, as well as the tracking of lending conditions (outstanding requirements) specific to a mortgage application.

## Messages

### POST /api/v1/applications/{id}/messages

Send a new message related to a specific application.

**Request:**
```json
{
  "sender_id": 123,
  "recipient_id": 456,
  "body": "Please provide the updated T4 slip."
}
```

**Response (201):**
```json
{
  "id": 987,
  "application_id": 1,
  "sender_id": 123,
  "recipient_id": 456,
  "body": "Please provide the updated T4 slip.",
  "is_read": false,
  "sent_at": "2026-03-02T14:30:00Z",
  "read_at": null
}
```

**Errors:**
- 400: Invalid sender or recipient ID
- 404: Application not found
- 422: Validation error (empty body)

---

### GET /api/v1/applications/{id}/messages

Retrieve the message thread for a specific application.

**Parameters:**
- `id` (path): Application ID

**Response (200):**
```json
[
  {
    "id": 987,
    "application_id": 1,
    "sender_id": 123,
    "recipient_id": 456,
    "body": "Please provide the updated T4 slip.",
    "is_read": true,
    "sent_at": "2026-03-02T14:30:00Z",
    "read_at": "2026-03-02T14:35:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated
- 404: Application not found

---

## Conditions

### POST /api/v1/applications/{id}/conditions

Create a new underwriting condition for an application.

**Request:**
```json
{
  "lender_submission_id": 55,
  "description": "Confirmation of employment letter dated within 30 days.",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "2026-03-15"
}
```

**Response (201):**
```json
{
  "id": 101,
  "application_id": 1,
  "lender_submission_id": 55,
  "description": "Confirmation of employment letter dated within 30 days.",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "2026-03-15T00:00:00Z",
  "satisfied_at": null,
  "satisfied_by": null,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid date format or condition_type
- 404: Application not found

---

### GET /api/v1/applications/{id}/conditions

List all conditions associated with an application.

**Response (200):**
```json
[
  {
    "id": 101,
    "application_id": 1,
    "description": "Confirmation of employment letter dated within 30 days.",
    "condition_type": "document",
    "status": "outstanding",
    "required_by_date": "2026-03-15T00:00:00Z",
    "created_at": "2026-03-02T10:00:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated

---

### PATCH /api/v1/applications/{id}/conditions/{condition_id}

Update the status of a condition (e.g., mark as satisfied or waived).

**Request:**
```json
{
  "status": "satisfied",
  "satisfied_at": "2026-03-05T09:00:00Z"
}
```
*(Note: `satisfied_by` is automatically populated from the authenticated user context)*

**Response (200):**
```json
{
  "id": 101,
  "status": "satisfied",
  "satisfied_at": "2026-03-05T09:00:00Z",
  "satisfied_by": 789,
  "updated_at": "2026-03-05T09:00:01Z"
}
```

**Errors:**
- 400: Invalid status transition
- 403: User not authorized to modify conditions
- 404: Condition not found
```

## 2. Module README

**File:** `docs/modules/messaging_and_conditions.md`

```markdown
# Messaging & Conditions Module

## Overview
The Messaging & Conditions module facilitates the communication and compliance tracking workflow within the Canadian Mortgage Underwriting System. It ensures that all interactions between brokers, applicants, and underwriters are logged and that specific lender requirements (conditions) are tracked from creation to satisfaction.

## Key Functions

### Messaging
- **Threaded Communication:** Links messages directly to `application_id` to maintain context.
- **Read Receipts:** Tracks `is_read` status and `read_at` timestamps for accountability.
- **PII Handling:** Message bodies are treated as potential PII and are encrypted at rest per PIPEDA requirements.

### Conditions
- **Condition Lifecycle:** Tracks statuses: `outstanding`, `satisfied`, or `waived`.
- **Categorization:** Supports `document`, `information`, or `other` types.
- **Audit Trail:** Automatically records `created_at`, `satisfied_at`, and the `user_id` of the user who satisfied the condition (`satisfied_by`).
- **Deadlines:** Enforces `required_by_date` to ensure timely fulfillment of lender requirements.

## Usage Examples

### Creating a Document Condition
When a lender requires an additional document, the underwriter creates a condition record.

```python
from modules.messaging_conditions.schemas import ConditionCreate
from modules.messaging_conditions.services import ConditionService

# Data input
condition_data = ConditionCreate(
    lender_submission_id=101,
    description="Updated Notice of Assessment",
    condition_type="document",
    required_by_date="2026-04-01"
)

# Service call
new_condition = await ConditionService.create_condition(
    db_session, application_id=5, data=condition_data
)
```

### Sending a Message
To notify the broker about the new condition.

```python
from modules.messaging_conditions.schemas import MessageCreate
from modules.messaging_conditions.services import MessageService

message_data = MessageCreate(
    sender_id=1, # Underwriter
    recipient_id=2, # Broker
    body="A new condition has been added to your application."
)

await MessageService.send_message(
    db_session, application_id=5, data=message_data
)
```

## Compliance Notes
- **FINTRAC:** Message logs and condition updates are part of the immutable audit trail. Records are never hard-deleted.
- **PIPEDA:** Message content containing sensitive applicant details is encrypted. Searchable fields (like IDs) are used for retrieval.
```

## 3. Configuration Notes

**File:** `.env.example`

```bash
# Messaging & Conditions Configuration
# No specific module configuration variables are required beyond standard DB/API settings.
# Ensure encryption keys are set in common/security.py for PII protection in message bodies.
```

## 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Messaging & Conditions: New endpoints for application-level messaging (`POST /applications/{id}/messages`, `GET /applications/{id}/messages`).
- Messaging & Conditions: New endpoints for managing lender conditions (`POST /applications/{id}/conditions`, `GET /applications/{id}/conditions`, `PATCH /applications/{id}/conditions/{condition_id}`).
- Messaging & Conditions: Added audit fields for conditions (`satisfied_by`, `satisfied_at`) to track who fulfilled requirements.
- Messaging & Conditions: Implemented read status tracking for messages (`is_read`, `read_at`).

### Changed
- N/A

### Fixed
- N/A
```