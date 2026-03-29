```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/mortgage/routes.py",
      "line": 16,
      "description": "Service instantiated directly in route handler instead of using dependency injection. This violates separation of concerns and makes testing difficult.",
      "suggested_fix": "Replace direct instantiation with FastAPI Depends:\n```python\nfrom fastapi import Depends\n\nasync def get_mortgage_service(db: AsyncSession = Depends(get_async_session)) -> MortgageApplicationService:\n    return MortgageApplicationService(db)\n\n@router.post(\"/\", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)\nasync def create_mortgage_application(\n    payload: ApplicationCreate,\n    service: MortgageApplicationService = Depends(get_mortgage_service),\n) -> ApplicationResponse:\n    ...\n```"
    },
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/mortgage/services.py",
      "line": 18,
      "description": "Catching broad Exception without rollback. Database transaction not rolled back on failure, leaving connection in bad state.",
      "suggested_fix": "Add specific exception handling with rollback:\n```python\nfrom sqlalchemy.exc import IntegrityError, DatabaseError\n\ntry:\n    instance = MortgageApplication(**payload.model_dump())\n    self.db.add(instance)\n    await self.db.commit()\n    await self.db.refresh(instance)\n    return instance\nexcept IntegrityError as e:\n    await self.db.rollback()\n    logger.error(\"integrity_error\", error=str(e))\n    raise MortgageApplicationValidationError(\"Invalid application data\") from e\nexcept DatabaseError as e:\n    await self.db.rollback()\n    logger.error(\"database_error\", error=str(e))\n    raise\n```"
    },
    {
      "severity": "critical",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 11,
      "description": "Using SQLite for tests when project requires PostgreSQL. This masks PostgreSQL-specific issues and violates stack conventions.",
      "suggested_fix": "Use PostgreSQL test container:\n```python\nfrom testcontainers.postgres import PostgresContainer\n\n@pytest.fixture(scope=\"session\")\nasync def postgres():\n    with PostgresContainer(\"postgres:15\") as postgres:\n        yield postgres\n\n@pytest.fixture(scope=\"function\")\nasync def engine(postgres):\n    TEST_DATABASE_URL = postgres.get_connection_url().replace(\"postgresql://\", \"postgresql+asyncpg://\")\n    engine = create_async_engine(TEST_DATABASE_URL)\n    async with engine.begin() as conn:\n        await conn.run_sync(Base.metadata.create_all)\n    yield engine\n    await engine.dispose()\n```"
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/mortgage/models.py",
      "line": 8,
      "description": "Missing FINTRAC compliance fields. No created_by audit trail, violating immutable record requirements.",
      "suggested_fix": "Add audit fields:\n```python\nclass MortgageApplication(Base):\n    __tablename__ = \"mortgage_applications\"\n    \n    id: Mapped[int] = mapped_column(primary_key=True, index=True)\n    client_id: Mapped[int] = mapped_column(ForeignKey(\"clients.id\"), nullable=False, index=True)\n    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)\n    is_active: Mapped[bool] = mapped_column(Boolean, default=True)\n    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # FINTRAC: Soft delete for retention\n    created_by: Mapped[str] = mapped_column(String(255), nullable=False)  # FINTRAC: Audit trail\n    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())\n    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())\n```"
    },
    {
      "severity": "critical",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/mortgage/services.py",
      "line": 10,
      "description": "Generic class name 'MyService' violates naming conventions and reduces code clarity. Should be domain-specific.",
      "suggested_fix": "Rename to domain-specific name:\n```python\nclass MortgageApplicationService:\n    def __init__(self, db: AsyncSession):\n        self.db = db\n    \n    async def create_mortgage_application(self, payload: ApplicationCreate, created_by: str) -> MortgageApplication:\n        ...\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/mortgage/exceptions.py",
      "line": 1,
      "description": "Generic exception class 'MyException' provides no domain context. Should have specific exception types for different error scenarios.",
      "suggested_fix": "Create domain-specific exceptions:\n```python\nclass MortgageApplicationException(Exception):\n    \"\"\"Base exception for mortgage application domain\"\"\"\n    def __init__(self, message: str, error_code: str):\n        self.message = message\n        self.error_code = error_code\n        super().__init__(self.message)\n\nclass GDSRatioExceededError(MortgageApplicationException):\n    def __init__(self, gds_ratio: Decimal):\n        super().__init__(\n            f\"GDS ratio {gds_ratio}% exceeds OSFI limit of 39%\",\n            \"GDS_EXCEEDED\"\n        )\n\nclass InvalidLTVError(MortgageApplicationException):\n    def __init__(self, ltv: Decimal):\n        super().__init__(f\"Invalid LTV ratio: {ltv}\", \"INVALID_LTV\")\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 40,
      "description": "Sample payload does not match actual ApplicationCreate schema. Mismatched fields (application_id, step_data) cause test failures.",
      "suggested_fix": "Fix payload to match schema:\n```python\n@pytest.fixture\ndef sample_application_create():\n    return {\n        \"client_id\": 1,\n        \"purchase_price\": Decimal(\"500000.00\")\n    }\n```"
    },
    {
      "severity": "high",
      "category": "performance",
      "file": "mortgage_underwriting/modules/mortgage/models.py",
      "line": 13,
      "description": "Missing composite index on (client_id, is_active) for common filter pattern. Causes full table scans.",
      "suggested_fix": "Add composite index:\n```python\nfrom sqlalchemy import Index\n\nclass MortgageApplication(Base):\n    __tablename__ = \"mortgage_applications\"\n    \n    __table_args__ = (\n        Index('ix_mortgage_applications_client_active', 'client_id', 'is_active'),\n    )\n    \n    id: Mapped[int] = mapped_column(primary_key=True, index=True)\n    client_id: Mapped[int] = mapped_column(ForeignKey(\"clients.id\"), nullable=False, index=True)\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/mortgage/routes.py",
      "line": 20,
      "description": "Only catching ValueError, missing other exceptions. No middleware for structured error responses.",
      "suggested_fix": "Add comprehensive error handling:\n```python\nfrom fastapi import Request\nfrom fastapi.responses import JSONResponse\n\n@router.exception_handler(MortgageApplicationException)\nasync def mortgage_exception_handler(request: Request, exc: MortgageApplicationException):\n    return JSONResponse(\n        status_code=400,\n        content={\"detail\": exc.message, \"error_code\": exc.error_code}\n    )\n```"
    },
    {
      "severity": "high",
      "category": "security",
      "file": "mortgage_underwriting/modules/mortgage/routes.py",
      "line": 12,
      "description": "No authentication, authorization, or rate limiting on endpoint. Exposes system to unauthorized access and abuse.",
      "suggested_fix": "Add security dependencies:\n```python\nfrom fastapi.security import HTTPBearer\nfrom mortgage_underwriting.common.security import verify_token\nfrom slowapi import Limiter\n\nsecurity = HTTPBearer()\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/\", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)\n@limiter.limit(\"10/minute\")\nasync def create_mortgage_application(\n    payload: ApplicationCreate,\n    db: AsyncSession = Depends(get_async_session),\n    token: str = Depends(verify_token),\n) -> ApplicationResponse:\n    ...\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/mortgage/models.py",
      "line": 6,
      "description": "Inconsistent SQLAlchemy 2.0 syntax. Mixing old Column() style with new mapped_column() style.",
      "suggested_fix": "Use consistent SQLAlchemy 2.0 syntax:\n```python\nclass MortgageApplication(Base):\n    __tablename__ = \"mortgage_applications\"\n    \n    id: Mapped[int] = mapped_column(primary_key=True, index=True)\n    client_id: Mapped[int] = mapped_column(ForeignKey(\"clients.id\"), nullable=False, index=True)\n    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)\n    is_active: Mapped[bool] = mapped_column(Boolean, default=True)\n    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())\n    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())\n```"
    },
    {
      "severity": "medium",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 1,
      "description": "Missing pytest markers for test categorization. Tests cannot be filtered by unit/integration.",
      "suggested_fix": "Add pytest.ini configuration:\n```ini\n[pytest]\nmarkers =\n    unit: Unit tests\n    integration: Integration tests\n    slow: Slow running tests\n```"
    },
    {
      "severity": "medium",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/mortgage/services.py",
      "line": 13,
      "description": "No correlation_id in logs for request tracing. Breaks observability requirements.",
      "suggested_fix": "Add correlation_id to logs:\n```python\nimport uuid\n\nasync def create(self, payload: ApplicationCreate, correlation_id: str = None) -> MortgageApplication:\n    correlation_id = correlation_id or str(uuid.uuid4())\n    logger.info(\"creating_mortgage_application\", correlation_id=correlation_id, client_id=payload.client_id)\n    try:\n        ...\n    except Exception as e:\n        logger.error(\"create_failed\", correlation_id=correlation_id, error=str(e))\n        raise\n```"
    }
  ],
  "summary": "Code is BLOCKED due to critical regulatory compliance violations (missing FINTRAC audit fields, OSFI B-20 calculations, CMHC insurance logic), security vulnerabilities (no auth/rate limiting), and architectural flaws (direct service instantiation, no transaction rollback). High-severity issues include generic naming, mismatched test fixtures, and missing composite indexes. Medium-severity issues involve inconsistent SQLAlchemy syntax and incomplete observability. The module requires significant rework to meet project standards and Canadian regulatory requirements."
}
```