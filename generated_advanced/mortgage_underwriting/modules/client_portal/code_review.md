```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "security",
      "file": "mortgage_underwriting/modules/client_portal/routes.py",
      "line": 28,
      "description": "Authentication endpoints lack rate limiting, enabling brute-force attacks on /auth/login and /auth/refresh. This violates security best practices for public-facing auth endpoints.",
      "suggested_fix": "Add rate limiting using slowapi or FastAPI middleware. Example:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/auth/login\")\n@limiter.limit(\"5/minute\")\nasync def client_login(...):\n    ...\n```"
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/client_portal/models.py",
      "line": 51,
      "description": "ClientNotification model missing created_by audit field. FINTRAC requires immutable audit trail (created_at, created_by) for all records that support financial transactions. Notifications may contain compliance-related communications.",
      "suggested_fix": "Add created_by field to ClientNotification:\n```python\nclass ClientNotification(Base):\n    ...\n    created_by: Mapped[int] = mapped_column(\n        Integer, \n        ForeignKey(\"client_portal_users.id\"), \n        nullable=False\n    )\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/client_portal/routes.py",
      "line": 54,
      "description": "Routes lack exception handling for service-layer errors. Only /auth/login handles ClientPortalAuthError. NotFoundError, validation errors, and database errors will return 500 errors instead of structured responses.",
      "suggested_fix": "Add global exception handler or wrap routes in try/except:\n```python\nfrom mortgage_underwriting.common.exceptions import NotFoundError\n\n@router.get(\"/dashboard\", response_model=DashboardResponse)\nasync def client_dashboard(...):\n    try:\n        service = ClientDashboardService(db)\n        return await service.get_dashboard(client_id)\n    except NotFoundError as e:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail={\"detail\": str(e), \"error_code\": \"CLIENT_PORTAL_003\"},\n        )\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "mortgage_underwriting/modules/client_portal/tests.py",
      "line": 1,
      "description": "No actual test implementations provided. All public service and route functions lack unit and integration tests, violating the requirement that all public functions have corresponding tests.",
      "suggested_fix": "Create comprehensive test suites:\n- Unit tests for each service method (test_auth_service.py, test_dashboard_service.py)\n- Integration tests for each route (test_client_portal_routes.py)\n- Test edge cases: empty document lists, missing clients, invalid pagination parameters\n- Use pytest fixtures to create test data"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_portal/services.py",
      "line": 104,
      "description": "Hardcoded document checklist in get_document_checklist() violates DRY and makes business rules difficult to maintain. Document requirements should be configurable and version-controlled.",
      "suggested_fix": "Move document requirements to a configuration table or enum:\n```python\n# In models.py\nclass DocumentRequirement(Base):\n    __tablename__ = \"document_requirements\"\n    id = Column(Integer, primary_key=True)\n    document_type = Column(String(50), unique=True)\n    is_required = Column(Boolean, default=True)\n    applicable_scenarios = Column(JSON)  # JSONB in PostgreSQL\n\n# In services.py\nasync def get_document_checklist(...):\n    stmt = select(DocumentRequirement)\n    required_docs = (await self.db.execute(stmt)).scalars().all()\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/client_portal/services.py",
      "line": 45,
      "description": "ClientDashboardService.get_dashboard executes separate queries for application and documents, then manually merges data. This creates unnecessary database round trips and inefficient data processing.",
      "suggested_fix": "Use eager loading to fetch application and documents in one query:\n```python\nfrom sqlalchemy.orm import selectinload\n\nstmt = (\n    select(MortgageApplication)\n    .options(selectinload(MortgageApplication.documents))\n    .where(MortgageApplication.client_id == client_id)\n    .order_by(MortgageApplication.created_at.desc())\n    .limit(1)\n)\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/client_portal/services.py",
      "line": 21,
      "description": "Services instantiated directly in route handlers instead of using FastAPI dependency injection. This creates tight coupling and makes unit testing routes difficult.",
      "suggested_fix": "Create service dependencies:\n```python\nasync def get_auth_service(db: AsyncSession = Depends(get_async_session)):\n    return ClientAuthService(db)\n\n@router.post(\"/auth/login\")\nasync def client_login(\n    payload: LoginRequest,\n    service: ClientAuthService = Depends(get_auth_service),\n) -> LoginResponse:\n    return await service.authenticate_and_login(payload)\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/client_portal/services.py",
      "line": 67,
      "description": "list_applications() lacks pagination, risking memory exhaustion and slow response times for clients with many applications.",
      "suggested_fix": "Add pagination parameters:\n```python\nasync def list_applications(\n    self, client_id: int, skip: int = 0, limit: int = 100\n) -> List[ApplicationSummary]:\n    stmt = select(MortgageApplication).where(...).offset(skip).limit(limit)\n    ...\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_portal/schemas.py",
      "line": 65,
      "description": "Magic number 10485760 (10MB) for file size limit is hardcoded. Should be a named constant for maintainability and reusability.",
      "suggested_fix": "Add constant in config.py:\n```python\n# common/config.py\nMAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB\n\n# schemas.py\nfile_size: int = Field(..., gt=0, le=settings.MAX_UPLOAD_SIZE_BYTES)\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_portal/services.py",
      "line": 45,
      "description": "Hardcoded progress steps and latest_message in get_dashboard() create maintenance burden and prevent dynamic status tracking.",
      "suggested_fix": "Store progress configuration in database or enum:\n```python\nclass ApplicationStatus(Base):\n    __tablename__ = \"application_statuses\"\n    status = Column(String, primary_key=True)\n    label = Column(String)\n    display_order = Column(Integer)\n\n# Fetch dynamically\nprogress_steps = await self.db.execute(\n    select(ApplicationStatus).order_by(ApplicationStatus.display_order)\n)\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/client_portal/routes.py",
      "line": 16,
      "description": "Mock authentication dependency get_current_client_user returns hardcoded user ID, bypassing real JWT validation. This is a security risk and prevents proper authorization testing.",
      "suggested_fix": "Implement real JWT authentication:\n```python\nfrom fastapi.security import HTTPBearer\n\nsecurity = HTTPBearer()\n\nasync def get_current_client_user(\n    credentials: HTTPAuthorizationCredentials = Depends(security),\n    db: AsyncSession = Depends(get_async_session),\n) -> int:\n    token = credentials.credentials\n    payload = verify_jwt_token(token)  # Implement with PyJWT\n    return payload[\"user_id\"]\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/client_portal/services.py",
      "line": 106,
      "description": "DocumentChecklistItem instantiated with id=0 for missing documents, creating inconsistent data model. Should use Optional[int] = None.",
      "suggested_fix": "Use Optional for id field:\n```python\nitems.append(\n    DocumentChecklistItem(\n        id=doc.id if doc else None,  # Change schema to Optional[int]\n        document_type=req_doc,\n        is_uploaded=bool(doc),\n        ...\n    )\n)\n```"
    },
    {
      "severity": "medium",
      "category": "testing",
      "file": "mortgage_underwriting/tests/conftest.py",
      "line": 14,
      "description": "Tests use SQLite instead of PostgreSQL, risking compatibility issues with PostgreSQL-specific features (JSONB, enums, asyncpg drivers).",
      "suggested_fix": "Use PostgreSQL test container for integration tests:\n```python\n@pytest.fixture(scope=\"session\")\ndef postgres_container():\n    # Use testcontainers-python\n    container = PostgresContainer(\"postgres:15\")\n    container.start()\n    yield container\n    container.stop()\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_portal/routes.py",
      "line": 91,
      "description": "upload_document stub returns plain dict instead of Pydantic model, inconsistent with other endpoints.",
      "suggested_fix": "Create and return proper response model:\n```python\nclass DocumentUploadResponse(BaseModel):\n    message: str\n    document_id: int\n    upload_status: str\n\nreturn DocumentUploadResponse(...)\n```"
    }
  ],
  "summary": "BLOCKED: Critical security vulnerabilities (missing rate limiting) and compliance gaps (incomplete audit trails) require immediate attention. High-severity issues include inadequate error handling, zero test coverage, hardcoded business logic, and performance bottlenecks. Address critical issues before merge."
}
```