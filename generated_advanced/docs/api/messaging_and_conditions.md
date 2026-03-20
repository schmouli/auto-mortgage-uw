Here is the documentation for the **Messaging & Conditions** module.

### 1. API Documentation
**File:** `docs/api/messaging_and_conditions.md`

```markdown
# Messaging & Conditions API

## Overview
This module manages communication threads between users regarding a specific mortgage application and tracks underwriting conditions (requirements) set by lenders or underwriters.

---

## Messages

### POST /applications/{id}/messages

Send a new message associated with a specific application.

**Request Headers:**
- `Content-Type: application/json`
- `Authorization: Bearer <token>`

**Path Parameters:**
- `id` (integer): The ID of the application.

**Request Body:**
```json
{
  "sender_id": 45,
  "recipient_id": 12,
  "body": "Please upload the updated Notice of Assessment."
}
```

**Response (201 Created):**
```json
{
  "id": 101,
  "application_id": 5,
  "sender_id": 45,
  "recipient_id": 12,
  "body": "Please upload the updated Notice of Assessment.",
  "is_read": false,
  "sent_at": "2026-03-02T14:30:00Z",
  "read_at": null
}
```

**Errors:**
- `400 Bad Request`: Invalid message body or user IDs.
- `401 Unauthorized`: Missing or invalid authentication token.
- `404 Not Found`: Application or User not found.

---

### GET /applications/{id}/messages

Retrieve the message history for a specific application.

**Request Headers:**
- `Authorization: Bearer <token>`

**Path Parameters:**
- `id` (integer): The ID of the application.

**Query Parameters:**
- `is_read` (boolean, optional): Filter by read status.
- `limit` (integer, optional): Number of results to return.
- `offset` (integer, optional): Pagination offset.

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 101,
      "application_id": 5,
      "sender_id": 45,
      "recipient_id": 12,
      "body": "Please upload the updated Notice of Assessment.",
      "is_read": true,
      "sent_at": "2026-03-02T14:30:00Z",
      "read_at": "2026-03-02T14:35:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Errors:**
- `401 Unauthorized`: Missing or invalid authentication token.
- `404 Not Found`: Application not found.

---

## Conditions (Data Model Reference)

*Note: While specific CRUD endpoints for conditions were not explicitly listed in the route requirements, the following data structure is managed by the module and typically exposed via standard endpoints (e.g., `POST /applications/{id}/conditions`, `PATCH /conditions/{id}`).*

**Condition Object Structure:**
```json
{
  "id": 1,
  "application_id": 5,
  "lender_submission_id": 10,
  "description": "Proof of income - 2024 T1 General",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "2026-03-15",
  "satisfied_at": null,
  "satisfied_by": null,
  "created_at": "2026-03-01T09:00:00Z"
}
```

**Condition Types:**
- `document`: Requires a file upload.
- `information`: Requires textual clarification or data entry.
- `other`: Miscellaneous requirements.

**Status Values:**
- `outstanding`: Condition is active and unmet.
- `satisfied`: Condition has been met and verified.
- `waived`: Condition has been waived by the underwriter.
```

---

### 2. Module README
**File:** `docs/modules/messaging_and_conditions.md`

```markdown
# Messaging & Conditions Module

## Overview
The Messaging & Conditions module facilitates the operational workflow of the mortgage underwriting process. It ensures secure communication between stakeholders (Brokers, Underwriters, Admins) and tracks the fulfillment of requirements required for final approval.

## Key Features

### 1. Secure Messaging
- **Contextual Communication:** Messages are strictly tied to an `application_id`, ensuring all discussions are relevant to the specific file.
- **Read Receipts:** Tracks `is_read` status and `read_at` timestamps for accountability.
- **Auditability:** All messages are immutable once sent to maintain a permanent record of negotiations and instructions.

### 2. Condition Management
- **Tracking:** Monitors outstanding requirements defined by lenders or internal underwriting logic.
- **Types:** Supports categorization of conditions (Document, Information, Other).
- **Lifecycle Management:**
  - Created when a requirement is identified.
  - Updated to `satisfied` when the borrower provides the necessary data/documents.
  - Can be marked as `waived` if the condition is no longer applicable.
- **Deadlines:** Enforces `required_by_date` to track expiring conditions.

## Data Models

### Message
- `id`: Primary Key
- `application_id`: Foreign Key to the mortgage application.
- `sender_id`: ID of the user sending the message.
- `recipient_id`: ID of the user receiving the message.
- `body`: The message content (Text).
- `is_read`: Boolean flag for read status.
- `sent_at`: Timestamp of message creation.
- `read_at`: Timestamp when the message was first read.

### Condition
- `id`: Primary Key
- `application_id`: Foreign Key to the mortgage application.
- `lender_submission_id`: Optional link to the specific lender submission if applicable.
- `description`: Textual description of what is required.
- `condition_type`: Enum (`document`, `information`, `other`).
- `status`: Enum (`outstanding`, `satisfied`, `waived`).
- `required_by_date`: Deadline for fulfillment.
- `satisfied_at`: Timestamp of when the condition was met.
- `satisfied_by`: User ID of the person who marked the condition as satisfied.
- `created_at`: Audit timestamp.

## Usage Example

### Sending a Message
```python
from modules.messaging_and_conditions.services import MessagingService

async def send_notification(application_id: int, sender: int, recipient: int, content: str):
    service = MessagingService(db_session)
    message = await service.send_message(
        application_id=application_id,
        sender_id=sender,
        recipient_id=recipient,
        body=content
    )
    return message
```

### Creating a Condition
```python
from modules.messaging_and_conditions.services import ConditionService
from datetime import date

async def create_underwriting_condition(app_id: int, description: str):
    service = ConditionService(db_session)
    condition = await service.create_condition(
        application_id=app_id,
        description=description,
        condition_type="document",
        required_by_date=date(2026, 4, 1)
    )
    return condition
```

## Compliance Notes
- **PIPEDA:** Message bodies may contain PII. Ensure logging does not output the full `body` field. Access to message history should be restricted to users associated with the `application_id`.
- **FINTRAC:** Conditions satisfied by financial documents trigger audit trails. The `satisfied_by` and `satisfied_at` fields are mandatory for the immutable audit trail.
```

---

### 3. Configuration Notes
**File:** `.env.example`

```bash
# ... existing config ...

# Messaging & Conditions Configuration
# Maximum length of a message body in characters
MESSAGE_MAX_LENGTH=5000

# Default days until a condition expires if no date is specified
DEFAULT_CONDITION_EXPIRY_DAYS=14
```

---

### 4. Changelog Update
**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Messaging & Conditions: New module for application-specific communication and requirement tracking.
- Messaging & Conditions: Added endpoints for sending (POST) and retrieving (GET) messages.
- Messaging & Conditions: Added `Condition` model to support underwriting requirements tracking (document/information/other).

### Changed
- Updated database schema to support `messages` and `conditions` tables.
```