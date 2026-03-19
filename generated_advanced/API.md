# API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

JWT Bearer token required for most endpoints.

```
Authorization: Bearer {token}
```

## Common Response Format

### Success (2xx)
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "1.0.0"
  }
}
```

### Error (4xx/5xx)
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable error message",
    "details": { ... }
  }
}
```

## Modules

See individual module documentation:
- [Authentication API](./docs/authentication.md)
- [Client Intake API](./docs/client_intake.md)
- [Underwriting Engine API](./docs/underwriting_engine.md)

## Interactive Docs

Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`
