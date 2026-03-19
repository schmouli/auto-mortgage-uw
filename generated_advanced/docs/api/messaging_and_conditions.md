# Documentation: Messaging & Conditions Module

Here is the documentation for the **Messaging & Conditions** module.

## 1. API Documentation

**File:** `docs/api/messaging_and_conditions.md`

```markdown
# Messaging & Conditions API

This module handles communication between users regarding mortgage applications and tracks the status of lending conditions (outstanding, satisfied, or waived).

## Messages

### POST /api/v1/applications/{id}/messages

Send a message to a user regarding a specific application.

**Request:**
```json
{
  "recipient_id": 42,
  "body": "Please upload the updated T4 slip."
}
```

**Response (201):**
```json
{
  "id": 101,
  "application_id": 5,
  "sender_id": 1,
  "recipient_id": 42,
  "body": "Please upload the updated T4 slip.",
  "is_read": false,
  "sent_at": "2026-03-02T14:30:00Z",
  "read_at": null
}
```

**Errors:**
- 400: Invalid recipient or application ID
- 403: User not authorized to message this recipient
- 404: Application not found
- 422: Validation error (e.g., empty body)

---

### GET /api/v1/applications/{id}/messages

Retrieve the message thread for a specific application.

**Parameters:**
- `limit` (query, optional): Number of messages to return (default: 50).
- `offset` (query, optional): Number of messages to skip (default: 0).

**Response (200):**
```json
{
  "items": [
    {
      "id": 100,
      "application_id": 5,
      "sender_id": 42,
      "recipient_id": 1,
      "body": "I have attached the document.",
      "is_read": true,
      "sent_at": "2026-03-02T14:15:00Z",
      "read_at": "2026-03-02T14:16:00Z"
    },
    {
      "id": 101,
      "application_id": 5,
      "sender_id": 1,
      "recipient_id": 42,
      "body": "Please upload the updated T4 slip.",
      "is_read": false,
      "sent_at": "2026-03-02T14:30:00Z",
      "read_at": null
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

**Errors:**
- 401: Not authenticated
- 403: User not authorized to view these messages
- 404: Application not found

---

## Conditions

### POST /api/v1/applications/{id}/conditions

Create a new condition (e.g., document requirement) for an application.

**Request:**
```json
{
  "lender_submission_id": 15,
  "description": "Letter of employment confirming start date",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "2026-03-15T23:59:59Z"
}
```

**Response (201):**
```json
{
  "id": 201,
  "application_id": 5,
  "lender_submission_id": 15,
  "description": "Letter of employment confirming start date",
  "condition_type": "document",
  "status": "outstanding",
  "required_by_date": "2026-03-15T23:59:59Z",
  "satisfied_at": null,
  "satisfied_by": null,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid status or type
- 404: Application or Lender Submission not found
- 422: Validation error

---

### GET /api/v1/applications/{id}/conditions

List all conditions associated with an application.

**Parameters:**
- `status` (query, optional): Filter by status (`outstanding`, `satisfied`, `waived`).

**Response (200):**
```json
{
  "items": [
    {
      "id": 201,
      "application_id": 5,
      "lender_submission_id": 15,
      "description": "Letter of employment confirming start date",
      "condition_type": "document",
      "status": "outstanding",
      "required_by_date": "2026-03-15T23:59:59Z",
      "satisfied_at": null,
      "satisfied_by": null,
      "created_at": "2026-03-02T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Errors:**
- 401: Not authenticated
- 404: Application not found

---

### PATCH /api/v1/applications/{id}/conditions/{condition_id}

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
  "id": 201,
  "status": "satisfied",
  "satisfied_at": "2026-03-02T16:45:00Z",
  "satisfied_by": 1
}
```

**Errors:**
- 400: Invalid status transition
- 403: User not authorized to update condition
- 404: Condition not found
- 422: Validation error
```

## 2. Module README

**File:** `docs/modules/messaging_and_conditions.md`

```markdown
# Messaging & Conditions Module

## Overview
The Messaging & Conditions module facilitates the underwriting workflow by enabling secure communication between underwriters, brokers, and applicants, and tracking specific conditions placed on a mortgage file by lenders.

## Key Functions

### Messaging
- **Send Message:** Persists messages linked to a specific `application_id`. Supports `sender_id` and `recipient_id` mapping.
- **Message Threading:** Retrieves chronological message history for an application.
- **Read Tracking:** Automatically updates `read_at` timestamps when a recipient fetches messages.

### Conditions
- **Condition Creation:** Allows underwriters or lenders to place conditions (Document, Information, Other) on an application.
- **Status Management:** Tracks the lifecycle of a condition: `outstanding` -> `satisfied` or `waived`.
- **Audit Trail:** Records who satisfied a condition (`satisfied_by`) and when (`satisfied_at`).

## Usage Examples

### Sending a Message
```python
import httpx

async def send_message(application_id: int, recipient_id: int, content: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://api/v1/applications/{application_id}/messages",
            json={"recipient_id": recipient_id, "body": content},
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

### Creating a Condition
```python
async def create_condition(application_id: int, description: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://api/v1/applications/{application_id}/conditions",
            json={
                "description": description,
                "condition_type": "document",
                "required_by_date": "2026-04-01T00:00:00Z"
            },
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

## Compliance Notes
- **PIPEDA:** Message bodies may contain PII. Ensure logs do not expose `body` content.
- **FINTRAC:** Audit fields (`created_at`, `satisfied_by`) are immutable and retained for 5 years.
```

## 3. Configuration Notes

**File:** `.env.example`

```bash
# Messaging & Conditions Configuration
# No specific module-level environment variables are required.
# This module relies on the common database and security configurations.

# Optional: Timeframe in hours before a message is considered "stale" for notifications
# MESSAGE_STALENESS_THRESHOLD_HOURS=24
```