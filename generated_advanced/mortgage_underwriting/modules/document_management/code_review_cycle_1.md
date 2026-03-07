⚠️ BLOCKED

1. [HIGH] routes.py ~L65: `list_documents` endpoint missing pagination — add `skip: int = Query(0, ge=0)` and `limit: int = Query(100, ge=1, le=100)` parameters and pass to service layer with `.offset(skip).limit(limit)`

2. [HIGH] models.py ~L25: Document.status column missing index — add `Index('ix_documents_status', 'status')` to `Document.__table_args__` for frequent status filtering

3. [MEDIUM] models.py ~L55: DocumentRequirement status fields missing indexes — add `Index('ix_doc_req_is_required', 'is_required')` and `Index('ix_doc_req_is_received', 'is_received')` to `DocumentRequirement.__table_args__`

4. [MEDIUM] services.py ~L45: `upload_document` uses naive `datetime.now()` — replace with `func.now()` or timezone-aware datetime to match `DateTime(timezone=True)` model definition

5. [LOW] routes.py ~L78, ~L89, ~L100, ~L111, ~L122: Generic `except Exception` handlers should catch specific domain exceptions (NotFoundError → 404, ValidationError → 422) instead of returning 500 for all errors