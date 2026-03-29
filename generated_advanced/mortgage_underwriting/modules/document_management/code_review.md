```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 27,
      "description": "Bare except clause catching generic Exception. All route handlers catch Exception instead of specific exceptions, violating the 'no bare except' rule and masking potential bugs.",
      "suggested_fix": "Replace generic Exception handling with specific exception handlers:\n```python\nfrom mortgage_underwriting.common.exceptions import NotFoundError, AppException\n\n@router.get(\"/checklist\", response_model=DocumentChecklistResponse)\nasync def get_document_checklist(...) -> DocumentChecklistResponse:\n    try:\n        return await service.get_checklist(application_id)\n    except NotFoundError as e:\n        raise HTTPException(status_code=404, detail={\"detail\": str(e), \"error_code\": \"APPLICATION_NOT_FOUND\"})\n    except Exception as e:\n        logger.error(\"checklist_fetch_failed\", error=str(e), application_id=application_id)\n        raise HTTPException(status_code=500, detail={\"detail\": \"Internal server error\", \"error_code\": \"INTERNAL_ERROR\"})\n```"
    },
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 55,
      "description": "Bare except clause catching generic Exception in upload_document endpoint.",
      "suggested_fix": "Add specific exception handling for validation errors and implement proper error codes:\n```python\nexcept ValidationError as e:\n    raise HTTPException(status_code=422, detail={\"detail\": e.errors(), \"error_code\": \"VALIDATION_FAILED\"})\nexcept AppException as e:\n    raise HTTPException(status_code=400, detail={\"detail\": e.message, \"error_code\": e.error_code})\nexcept Exception as e:\n    logger.error(\"document_upload_failed\", error=str(e), application_id=application_id)\n    raise HTTPException(status_code=500, detail={\"detail\": \"Upload failed\", \"error_code\": \"UPLOAD_FAILED\"})\n```"
    },
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 72,
      "description": "Bare except clause catching generic Exception in list_documents endpoint.",
      "suggested_fix": "Implement specific exception handling as shown in previous fixes, logging errors with structlog before raising HTTPException."
    },
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 88,
      "description": "Bare except clause catching generic Exception in download_document endpoint.",
      "suggested_fix": "Handle NotFoundError specifically and log errors properly:\n```python\nexcept NotFoundError:\n    raise HTTPException(status_code=404, detail={\"detail\": \"Document not found\", \"error_code\": \"DOCUMENT_NOT_FOUND\"})\n```"
    },
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 167,
      "description": "FINTRAC violation: Hard document deletion violates 5-year retention requirement. Financial records must be immutable and retained for 5 years.",
      "suggested_fix": "Implement soft delete with retention policy:\n```python\n# Add to models.py\nclass Document(Base):\n    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)\n    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)\n    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey(\"users.id\", ondelete=\"SET NULL\"), nullable=True)\n\n# In services.py\nasync def delete_document(self, application_id: int, doc_id: int, user_id: int) -> None:\n    logger.info(\"document_soft_delete\", application_id=application_id, doc_id=doc_id, deleted_by=user_id)\n    doc = await self.get_document(application_id, doc_id)\n    doc.is_deleted = True\n    doc.deleted_at = datetime.now(timezone.utc)\n    doc.deleted_by = user_id\n    await self.db.commit()\n```"
    },
    {
      "severity": "critical",
      "category": "security",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 48,
      "description": "Security vulnerability: document_type derived from MIME type split is insecure and incorrect. Content-Type can be spoofed and doesn't map to document taxonomy.",
      "suggested_fix": "Accept document_type as a validated form field:\n```python\nfrom fastapi import Form\nfrom mortgage_underwriting.modules.documents.schemas import DocumentType\n\n@router.post(\"/upload\", ...)\nasync def upload_document(\n    application_id: int = Path(..., gt=0),\n    document_type: str = Form(..., description=\"Document type from taxonomy\"),\n    file: UploadFile = File(...),\n    ...\n) -> DocumentResponse:\n    # Validate against DocumentType enum\n    if document_type not in DocumentType.__dict__.values():\n        raise HTTPException(status_code=422, detail={\"detail\": \"Invalid document type\", \"error_code\": \"INVALID_DOC_TYPE\"})\n    # ... rest of implementation\n```"
    },
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 81,
      "description": "PIPEDA risk: Logging file hash of document content may indirectly expose PII if hash is reversible or used for correlation. Document content may contain SIN, DOB, or banking data.",
      "suggested_fix": "Remove or mask file hash logging. Implement virus scanning before logging:\n```python\n# Remove hash logging\n# logger.info(\"file_virus_scan_placeholder\", file_hash=file_hash)\n\n# Instead, log scan result only\nscan_result = await virus_scan_service.scan(file_content)\nif not scan_result.clean:\n    logger.warning(\"virus_detected\", application_id=application_id, doc_type=payload.document_type)\n    raise AppException(\"Virus detected\", \"VIRUS_DETECTED\")\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 71,
      "description": "Magic number: Hardcoded 10MB file size limit without named constant. Violates DRY principle if limit needs to change.",
      "suggested_fix": "Define constant in config or module:\n```python\n# In services.py or common/config.py\nMAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB\n\n# Use constant\nif payload.file_size > MAX_FILE_SIZE_BYTES:\n    raise AppException(\"File too large\", \"FILE_TOO_LARGE\")\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 75,
      "description": "Magic list: Hardcoded allowed MIME types without named constant. Difficult to maintain and test.",
      "suggested_fix": "Define as constant:\n```python\nALLOWED_MIME_TYPES = [\"application/pdf\", \"image/jpeg\", \"image/png\"]\nif payload.mime_type not in ALLOWED_MIME_TYPES:\n    raise AppException(\"Invalid file type\", \"INVALID_MIME_TYPE\")\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 98,
      "description": "Deprecated datetime.utcnow() used instead of timezone-aware datetime. Can cause timezone bugs and doesn't comply with modern Python standards.",
      "suggested_fix": "Replace with timezone-aware datetime:\n```python\nfrom datetime import datetime, timezone\n\nuploaded_at=datetime.now(timezone.utc)\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 147,
      "description": "Deprecated datetime.utcnow() used in verify_document method.",
      "suggested_fix": "Use datetime.now(timezone.utc) as shown in previous fix."
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 66,
      "description": "Missing transaction management and application existence validation. No atomicity guarantees and potential foreign key errors.",
      "suggested_fix": "Add transaction handling and validation:\n```python\nfrom sqlalchemy.ext.asyncio import AsyncSession\n\nasync def upload_document(...) -> Document:\n    async with self.db.begin():\n        # Validate application exists\n        app_exists = await self.db.execute(select(MortgageApplication.id).where(MortgageApplication.id == application_id))\n        if not app_exists.scalar():\n            raise NotFoundError(\"Application not found\")\n        # ... rest of logic\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "mortgage_underwriting/tests/conftest.py",
      "line": 1,
      "description": "Incomplete test suite. No actual test cases provided for any service or route methods. Missing unit and integration tests.",
      "suggested_fix": "Create comprehensive test files:\n```python\n# tests/unit/test_documents_service.py\n@pytest.mark.unit\nasync def test_upload_document_success(db_session, mock_s3_client):\n    service = DocumentService(db_session)\n    payload = DocumentCreate(...)\n    result = await service.upload_document(1, 1, payload, b\"test content\")\n    assert result.document_type == payload.document_type\n    assert result.file_size == payload.file_size\n\n@pytest.mark.unit\nasync def test_upload_document_exceeds_size_limit(db_session):\n    service = DocumentService(db_session)\n    payload = DocumentCreate(file_size=15 * 1024 * 1024, ...)  # 15MB\n    with pytest.raises(AppException) as exc:\n        await service.upload_document(1, 1, payload, b\"x\" * (15 * 1024 * 1024))\n    assert exc.value.error_code == \"FILE_TOO_LARGE\"\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/documents/exceptions.py",
      "line": 1,
      "description": "Custom exceptions defined but never used. Service uses generic AppException and NotFoundError from common module, creating inconsistent error handling.",
      "suggested_fix": "Use custom exceptions in service layer:\n```python\n# In services.py\nfrom mortgage_underwriting.modules.documents.exceptions import DocumentNotFoundError, DocumentUploadError\n\nasync def get_document(...):\n    if not doc:\n        raise DocumentNotFoundError(f\"Document {doc_id} not found\")\n    return doc\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 79,
      "description": "Misleading endpoint name '/download' returns metadata instead of file content. Does not implement actual file download functionality.",
      "suggested_fix": "Either implement actual file download or rename endpoint:\n```python\n# Option 1: Implement download\n@router.get(\"/{doc_id}/download\")\nasync def download_document(...):\n    doc = await service.get_document(application_id, doc_id)\n    file_content = await storage_service.get_file(doc.file_path)\n    return Response(content=file_content, media_type=doc.mime_type)\n\n# Option 2: Rename endpoint\n@router.get(\"/{doc_id}\", response_model=DocumentResponse)\nasync def get_document_metadata(...):\n    return await service.get_document(application_id, doc_id)\n```"
    },
    {
      "severity": "medium",
      "category": "security",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 39,
      "description": "Authentication bypass: user_id passed as query parameter instead of derived from authentication token. Security vulnerability.",
      "suggested_fix": "Implement proper authentication:\n```python\nfrom fastapi.security import HTTPBearer\n\nsecurity = HTTPBearer()\n\nasync def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:\n    token = credentials.credentials\n    user_id = await verify_token(token)\n    return user_id\n\n@router.post(\"/upload\", ...)\nasync def upload_document(\n    application_id: int = Path(..., gt=0),\n    file: UploadFile = File(...),\n    service: DocumentService = Depends(get_document_service),\n    user_id: int = Depends(get_current_user)\n):\n    # ...\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/documents/routes.py",
      "line": 19,
      "description": "Missing rate limiting on public endpoints. Vulnerable to DoS attacks and abuse.",
      "suggested_fix": "Add rate limiting:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.get(\"/checklist\", ...)\n@limiter.limit(\"30/minute\")\nasync def get_document_checklist(...) -> DocumentChecklistResponse:\n    # ...\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/documents/services.py",
      "line": 30,
      "description": "Missing application existence check before operations. Can lead to orphaned records or foreign key violations.",
      "suggested_fix": "Add validation method:\n```python\nasync def _validate_application(self, application_id: int) -> None:\n    result = await self.db.execute(select(MortgageApplication.id).where(MortgageApplication.id == application_id))\n    if not result.scalar():\n        raise NotFoundError(\"Application not found\")\n\n# Call in each method\nasync def upload_document(self, application_id: int, ...):\n    await self._validate_application(application_id)\n    # ...\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/documents/models.py",
      "line": 15,
      "description": "Redundant index on primary key. Primary keys are automatically indexed, explicit index=True is unnecessary.",
      "suggested_fix": "Remove explicit index from primary key:\n```python\nid: Mapped[int] = mapped_column(Integer, primary_key=True)\n```"
    }
  ],
  "summary": "Document Management module has critical FINTRAC compliance violations (hard deletion), security vulnerabilities (authentication bypass, insecure document_type parsing), and widespread error handling issues (bare except clauses). High-severity issues include magic numbers, deprecated datetime usage, missing transaction management, and incomplete test coverage. Architecture suffers from unused custom exceptions and misleading API endpoints. Must be blocked until critical issues are resolved."
}
```