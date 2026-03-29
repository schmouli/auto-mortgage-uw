```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/orchestrator/services.py",
      "line": 31,
      "description": "PIPEDA compliance failure: SIN, DOB, and address are encrypted but never persisted to database. The encrypted_pii values are calculated and immediately discarded, making them unavailable for any future operations requiring decrypted data.",
      "suggested_fix": "Add encrypted fields to the Borrower model to store the encrypted PII data:\n```python\n# In models.py Borrower class:\nencrypted_sin: Mapped[str] = mapped_column(Text, nullable=False)\nencrypted_dob: Mapped[str] = mapped_column(Text, nullable=False)\nencrypted_address: Mapped[str] = mapped_column(Text, nullable=False)\n\n# In services.py submit_application:\nborrower = Borrower(\n    full_name=payload.borrower.full_name,\n    sin_hash=sin_hash,\n    encrypted_sin=encrypted_sin,  # Add this\n    encrypted_dob=encrypted_dob,  # Add this\n    encrypted_address=encrypted_address,  # Add this\n    employment_type=payload.borrower.employment_type.value,\n    gross_income=payload.borrower.gross_annual_income,\n    credit_score=payload.borrower.credit_score,\n)\n```"
    },
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/orchestrator/services.py",
      "line": 66,
      "description": "OSFI B-20 regulatory requirement violation: No GDS/TDS ratio calculation or stress test implementation (qualifying_rate = max(contract_rate + 2%, 5.25%)). The service only calculates LTV but skips mandatory debt service ratio evaluation.",
      "suggested_fix": "Implement GDS/TDS calculation with stress test:\n```python\n# Add to services.py\nfrom decimal import Decimal, ROUND_HALF_UP\n\nQUALIFYING_RATE = Decimal('0.0525')  # 5.25% minimum\nSTRESS_TEST_BUFFER = Decimal('0.02')  # 2%\n\nasync def calculate_debt_service_ratios(\n    self, income: Decimal, mortgage_payment: Decimal, \n    property_tax: Decimal, heating: Decimal, \n    other_debt: Decimal, contract_rate: Decimal\n) -> tuple[Decimal, Decimal, Decimal]:\n    stress_rate = max(contract_rate + STRESS_TEST_BUFFER, QUALIFYING_RATE)\n    \n    # GDS = (PITH) / Income\n    gds = ((mortgage_payment + property_tax + heating) / income * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n    \n    # TDS = (PITH + Other Debt) / Income\n    tds = ((mortgage_payment + property_tax + heating + other_debt) / income * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n    \n    if gds > 39 or tds > 44:\n        raise PolicyEvaluationError(\n            detail=f\"GDS/TDS exceeds OSFI limits: GDS={gds}%, TDS={tds}%\",\n            error_code=\"DEBT_SERVICE_RATIO_EXCEEDED\"\n        )\n    \n    return gds, tds, stress_rate\n```"
    },
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/orchestrator/services.py",
      "line": 130,
      "description": "FINTRAC compliance failure: Identity verification is only logged, not persisted. FINTRAC requires immutable audit trail records with 5-year retention for all identity verification events.",
      "suggested_fix": "Create a FINTRAC verification model and persist records:\n```python\n# In models.py\nclass IdentityVerificationRecord(Base):\n    __tablename__ = \"identity_verifications\"\n    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)\n    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey(\"applications.id\"), nullable=False)\n    verified: Mapped[bool] = mapped_column(Boolean, nullable=False)\n    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)\n    verified_by: Mapped[str] = mapped_column(String(255), nullable=False)\n    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)\n    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())\n\n# In services.py verify_identity:\nverification_record = IdentityVerificationRecord(\n    application_id=application_id,\n    verified=payload.verified,\n    verified_at=datetime.now(timezone.utc),\n    verified_by=verified_by,\n    notes=payload.notes\n)\nself.db.add(verification_record)\nawait self.db.commit()\n```"
    },
    {
      "severity": "critical",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 11,
      "description": "Test database uses SQLite (sqlite+aiosqlite:///:memory:) but production uses PostgreSQL with PG_UUID columns. This incompatibility will cause test failures and prevents testing PostgreSQL-specific features. Tests must use the same database engine as production.",
      "suggested_fix": "Use PostgreSQL test container:\n```python\n# In conftest.py\nimport pytest\nfrom testcontainers.postgres import PostgresContainer\n\n@pytest.fixture(scope=\"session\")\ndef postgres_container():\n    container = PostgresContainer(\"postgres:15\")\n    container.start()\n    yield container\n    container.stop()\n\n@pytest.fixture(scope=\"function\")\nasync def db_engine(postgres_container):\n    connection_url = postgres_container.get_connection_url().replace(\"postgresql://\", \"postgresql+asyncpg://\")\n    engine = create_async_engine(connection_url, echo=False)\n    # Run migrations\n    async with engine.begin() as conn:\n        await conn.run_sync(Base.metadata.create_all)\n    yield engine\n    await engine.dispose()\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/orchestrator/routes.py",
      "line": 35,
      "description": "Bare except clause catches all exceptions including critical system errors, masking root causes. This violates the 'no bare except' rule and prevents proper error diagnostics.",
      "suggested_fix": "Catch specific exceptions:\n```python\nfrom mortgage_underwriting.common.exceptions import NotFoundError, AppException\nfrom sqlalchemy.exc import DatabaseError\n\n@router.post(\"/\", response_model=ApplicationSchema, status_code=status.HTTP_201_CREATED)\nasync def submit_application(...):\n    try:\n        service = OrchestratorService(db)\n        return await service.submit_application(payload, user_email)\n    except ValidationError as e:\n        raise HTTPException(status_code=400, detail={\"detail\": str(e), \"error_code\": \"VALIDATION_FAILED\"})\n    except DatabaseError as e:\n        logger.error(\"database_error\", error=str(e))\n        raise HTTPException(status_code=500, detail={\"detail\": \"Database error\", \"error_code\": \"DB_ERROR\"})\n    except Exception as e:\n        logger.exception(\"unexpected_error\")\n        raise HTTPException(status_code=500, detail={\"detail\": \"Internal server error\", \"error_code\": \"INTERNAL_ERROR\"})\n```"
    },
    {
      "severity": "high",
      "category": "security",
      "file": "mortgage_underwriting/modules/orchestrator/routes.py",
      "line": 24,
      "description": "Missing rate limiting on all endpoints. Public-facing mortgage APIs without rate limiting are vulnerable to abuse, DDoS attacks, and credential stuffing.",
      "suggested_fix": "Add rate limiting:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/\")\n@limiter.limit(\"10/minute\")\nasync def submit_application(request: Request, ...):\n    ...\n\n@router.get(\"/{application_id}\")\n@limiter.limit(\"100/minute\")\nasync def get_application(...):\n    ...\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/orchestrator/services.py",
      "line": 58,
      "description": "Magic numbers for CMHC insurance premium tiers (80.01, 85, 85.01, 90, 90.01, 95, 2.80, 3.10, 4.00) are hardcoded. Changes to CMHC policies require code changes instead of configuration updates.",
      "suggested_fix": "Extract to configuration constants:\n```python\n# In common/config.py or module constants\nCMHC_PREMIUM_TIERS = [\n    (Decimal('80.01'), Decimal('85.00'), Decimal('2.80')),\n    (Decimal('85.01'), Decimal('90.00'), Decimal('3.10')),\n    (Decimal('90.01'), Decimal('95.00'), Decimal('4.00')),\n]\nINSURANCE_THRESHOLD = Decimal('80.00')\n\n# In services.py:\ninsurance_required = ltv_ratio > INSURANCE_THRESHOLD\nif insurance_required:\n    for min_ltv, max_ltv, premium in CMHC_PREMIUM_TIERS:\n        if min_ltv <= ltv_ratio <= max_ltv:\n            insurance_premium = premium\n            break\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/orchestrator/services.py",
      "line": 69,
      "description": "Missing transaction management context manager. If commit fails after borrower flush, application state will be inconsistent with no rollback capability.",
      "suggested_fix": "Use async context manager for transactions:\n```python\nasync with self.db.begin():\n    if not borrower:\n        borrower = Borrower(...)\n        self.db.add(borrower)\n        await self.db.flush()\n    \n    application = MortgageApplication(...)\n    self.db.add(application)\n    # Commit happens automatically on exit\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/orchestrator/services.py",
      "line": 138,
      "description": "datetime.utcnow() is deprecated in Python 3.12+. Using deprecated methods can lead to timezone-naive datetime objects causing audit trail inconsistencies.",
      "suggested_fix": "Replace with timezone-aware datetime:\n```python\nfrom datetime import datetime, timezone\n\nverified_at=datetime.now(timezone.utc)\n```"
    },
    {
      "severity": "high",
      "category": "security",
      "file": "mortgage_underwriting/modules/orchestrator/models.py",
      "line": 55,
      "description": "Sensitive financial data (gross_income) and PII (full_name) stored in plain text without encryption. While PIPEDA only mandates SIN/DOB encryption, storing income and name in plain text violates data minimization and security best practices.",
      "suggested_fix": "Encrypt sensitive PII fields:\n```python\n# In models.py\nencrypted_full_name: Mapped[str] = mapped_column(Text, nullable=False)\nencrypted_gross_income: Mapped[str] = mapped_column(Text, nullable=False)\n\n# In services.py\nborrower = Borrower(\n    encrypted_full_name=encrypt_pii(payload.borrower.full_name),\n    encrypted_gross_income=encrypt_pii(str(payload.borrower.gross_annual_income)),\n    ...\n)\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/orchestrator/routes.py",
      "line": 35,
      "description": "Service instantiation in each endpoint violates dependency injection pattern. Direct instantiation makes testing difficult and couples routes to service implementation.",
      "suggested_fix": "Inject service as dependency:\n```python\nasync def get_orchestrator_service(db: AsyncSession = Depends(get_async_session)):\n    return OrchestratorService(db)\n\n@router.post(\"/\")\nasync def submit_application(\n    payload: ApplicationCreateSchema,\n    service: OrchestratorService = Depends(get_orchestrator_service),\n    user_email: str = Depends(get_current_user),\n):\n    return await service.submit_application(payload, user_email)\n```"
    },
    {
      "severity": "medium",
      "category": "testing",
      "file": "tests/conftest.py",
      "line": 20,
      "description": "Missing structlog and encryption mocks. Tests will attempt real encryption and logging, causing side effects and test flakiness.",
      "suggested_fix": "Add mocks for external dependencies:\n```python\n@pytest.fixture(autouse=True)\ndef mock_structlog():\n    with patch('mortgage_underwriting.modules.orchestrator.services.structlog') as mock_log:\n        mock_log.get_logger.return_value = MagicMock()\n        yield\n\n@pytest.fixture(autouse=True)\ndef mock_encryption():\n    with patch('mortgage_underwriting.common.security.encrypt_pii') as mock_enc:\n        mock_enc.side_effect = lambda x: f\"encrypted_{x}\"\n        yield\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/orchestrator/models.py",
      "line": 68,
      "description": "Borrower model missing audit trail fields (updated_at, updated_by, created_by) required by FINTRAC for 5-year retention and immutability compliance.",
      "suggested_fix": "Add audit fields to Borrower model:\n```python\nclass Borrower(Base):\n    ...\n    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())\n    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())\n    created_by: Mapped[str] = mapped_column(String(255), nullable=False)\n    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/orchestrator/routes.py",
      "line": 90,
      "description": "Unused custom exceptions defined in exceptions.py (InvalidApplicationData, DocumentProcessingError, PolicyEvaluationError, DecisionEngineError) leading to dead code and confusion.",
      "suggested_fix": "Either use the exceptions in service logic or remove them:\n```python\n# In services.py, replace generic errors with specific ones:\nfrom mortgage_underwriting.modules.orchestrator.exceptions import InvalidApplicationData\n\nif not borrower:\n    raise InvalidApplicationData(detail=\"Invalid borrower data\", error_code=\"INVALID_BORROWER\")\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/orchestrator/routes.py",
      "line": 99,
      "description": "Reprocess endpoint returns generic dict instead of proper Pydantic response model, breaking API contract consistency.",
      "suggested_fix": "Create and use response schema:\n```python\n# In schemas.py\nclass ReprocessResponseSchema(BaseModel):\n    message: str\n    application_id: UUID\n\n# In routes.py\n@router.post(\"/{application_id}/reprocess\", response_model=ReprocessResponseSchema)\nasync def reprocess_application(...):\n    return ReprocessResponseSchema(message=\"Reprocessing started\", application_id=application_id)\n```"
    },
    {
      "severity": "low",
      "category": "performance",
      "file": "mortgage_underwriting/modules/orchestrator/models.py",
      "line": 81,
      "description": "Missing composite index on (borrower_id, status) for common query patterns filtering by both fields.",
      "suggested_fix": "Add composite index:\n```python\n__table_args__ = (\n    Index(\"ix_applications_borrower_id\", \"borrower_id\"),\n    Index(\"ix_applications_lender_id\", \"lender_id\"),\n    Index(\"ix_applications_status\", \"status\"),\n    Index(\"ix_applications_borrower_status\", \"borrower_id\", \"status\"),  # Composite index\n)\n```"
    }
  ],
  "summary": "Code is BLOCKED due to critical regulatory compliance failures: PII encryption is implemented but not persisted, OSFI B-20 stress test calculations are missing entirely, and FINTRAC immutable audit trails are not stored. Additionally, bare except clauses, missing rate limiting, and test database incompatibility with PostgreSQL create high-severity issues. Must fix critical items before deployment."
}
```