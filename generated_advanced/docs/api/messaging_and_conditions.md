# Messaging & Conditions API

## Module Overview

The Messaging & Conditions module facilitates secure communication between users (underwriters, brokers, and applicants) regarding specific mortgage applications and tracks outstanding lending conditions required for approval.

### Key Functions

- **Messaging**: Send and retrieve messages tied to a specific application. Supports read/unread status tracking.
- **Conditions**: Track lending requirements (documents, information, or other) linked to an application or lender submission. Manages the lifecycle of conditions from "outstanding" to "satisfied" or "waived".

### Regulatory & Compliance Notes

- **PIPEDA**: The `body` field in messages may contain PII. It is encrypted at rest (AES-256) via `common/security.py` and never exposed in logs.
- **FINTRAC**: All condition updates are immutable. Audit trails (`created_at`, `satisfied_at`, `satisfied_by`) are strictly maintained for 5 years.
- **Data Minimization**: Only the necessary communication metadata is stored; financial details are referenced via IDs rather than duplicated in message bodies.

---

## API Endpoints

### POST /api/v1/applications/{id}/messages

Send a new message to a user regarding a specific application.

**Request:**
```json
{
  "recipient_id": 45,
  "body": "Please provide the updated Notice of Assessment."
}
```

**Response (201):**
```json
{
  "id": 101,
  "application_id": 5,
  "sender_id": 12,
  "recipient_id": 45,
  "body": "Please provide the updated Notice of Assessment.",
  "is_read": false,
  "sent_at": "2026-03-02T14:30:00Z",
  "read_at": null
}
```

**Errors:**
- `400`: Invalid request data (e.g., empty body).
- `401`: Not authenticated.
- `403`: Permission denied (sender not associated with application).
- `404`: Application or recipient not found.

---

### GET /api/v1/applications/{id}/messages

Retrieve the message history for a specific application.

**Parameters:**
- `id` (path): Application ID.
- `limit` (query, optional): Number of messages to return.
- `offset` (query, optional): Pagination offset.

**Response (200):**
```json
{
  "items": [
    {
      "id": 101,
      "application_id": 5,
      "sender_id": 12,
      "recipient_id": 45,
      "body": "Please provide the updated Notice of Assessment.",
      "is_read": true,
      "sent_at": "2026-03-02T14:30:00Z",
      "read_at": "2026-03-02T14:35:00Z"
    },
    {
      "id": 99,
      "application_id": 5,
      "sender_id": 45,
      "recipient_id": 12,
      "body": "Attached is the document.",
      "is_read": true,
      "sent_at": "2026-03-01T09:15:00Z",
      "read_at": "2026-03-01T09:20:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

**Errors:**
- `401`: Not authenticated.
- `403`: Permission denied (user not authorized to view these messages).
- `404`: Application not found.

---

## Configuration Notes

This module relies on the base application configuration. No specific environment variables are required strictly for this module beyond the standard database and security settings.

However, ensure the following are configured in `.env` for PII compliance:

```bash
# Security (Required for PII encryption in messages)
ENCRYPTION_KEY=your-generated-aes-256-key-here
```