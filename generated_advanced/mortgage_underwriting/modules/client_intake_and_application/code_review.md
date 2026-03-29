```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "regulatory",
      "file": "mortgage_underwriting/modules/client_intake/models.py",
      "line": 0,
      "description": "Missing FINTRAC compliance fields: MortgageApplication model lacks 'created_by' audit field and 'transaction_type_flag' for transactions >CAD $10,000. All financial transaction records must have immutable audit trail with creator identity and explicit flags for large transactions.",
      "suggested_fix": "Add fields to MortgageApplication model:\n```python\n    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)\n    transaction_type_flag: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)\n```\nImplement logic in services.py to set flag when requested_loan_amount > 10000."
    },
    {
      "severity": "critical",
      "category": "regulatory",
      "file": "mortgage_underwriting/modules/client_intake/models.py",
      "line": 0,
      "description": "Missing CMHC compliance fields: MortgageApplication model lacks 'ltv_ratio' and 'insurance_required' fields. LTV must be calculated as loan_amount / property_value with precision, and insurance flag must be set when LTV > 80%.",
      "suggested_fix": "Add fields to MortgageApplication model:\n```python\n    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)\n    insurance_required: Mapped[bool] = mapped_column(default=False, nullable=False)\n    insurance_premium: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)\n```\nImplement LTV calculation and insurance logic in services.py create_application method."
    },
    {
      "severity": "critical",
      "category": "regulatory",
      "file": "mortgage_underwriting/modules/client_intake/models.py",
      "line": 0,
      "description": "Missing OSFI B-20 compliance fields: MortgageApplication model lacks 'gds_ratio', 'tds_ratio', and 'qualifying_rate' fields. All ratio calculations must be stored for auditability with stress test at qualifying_rate = max(contract_rate + 2%, 5.25%).",
      "suggested_fix": "Add fields to MortgageApplication model:\n```python\n    gds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)\n    tds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)\n    qualifying_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)\n```\nImplement ratio calculations in a dedicated underwriting service module."
    },
    {
      "severity": "critical",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/client_intake/models.py",
      "line": 29,
      "description": "Invalid relationship mapping: Client.co_borrowers references CoBorrower with back_populates='application', but CoBorrower table has no client_id foreign key. This creates a broken ORM relationship that will cause runtime errors.",
      "suggested_fix": "Remove the invalid relationship from Client model:\n```python\n# Delete lines 29-30 (co_borrowers relationship)\n```\nAccess co_borrowers through the application: client.applications[0].co_borrowers"
    },
    {
      "severity": "critical",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/client_intake/routes.py",
      "line": 26,
      "description": "Bare except clause catching all exceptions violates error handling best practices and can mask bugs. Should catch specific exceptions like NotFoundError, AppException.",
      "suggested_fix": "Replace bare except with specific exception handling:\n```python\nfrom mortgage_underwriting.common.exceptions import NotFoundError, AppException\n\ntry:\n    return await service.create_client(user_id, payload)\nexcept NotFoundError as e:\n    raise HTTPException(status_code=404, detail={\"error_code\": \"USER_NOT_FOUND\", \"detail\": str(e)})\nexcept AppException as e:\n    raise HTTPException(status_code=400, detail={\"error_code\": \"CLIENT_CREATE_FAILED\", \"detail\": str(e)})\n```\nApply this pattern to all endpoints (lines 26, 36, 48, 60, 71, 82, 93, 104, 115)."
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/client_intake/services.py",
      "line": 62,
      "description": "N+1 query vulnerability: list_applications() does not eager-load relationships (client, co_borrowers). If routes access these relationships, each will trigger separate database queries.",
      "suggested_fix": "Add eager loading to list_applications:\n```python\nstmt = select(MortgageApplication).options(\n    selectinload(MortgageApplication.client),\n    selectinload(MortgageApplication.co_borrowers)\n).offset(offset).limit(limit)\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "mortgage_underwriting/tests/test_client_intake.py",
      "line": 0,
      "description": "Incomplete test coverage: Tests are truncated and do not cover all public service methods (create_client, update_client, create_application, list_applications, update_application, submit_application, add_co_borrower, get_application_summary) or edge cases (invalid data, concurrent updates, validation failures).",
      "suggested_fix": "Create comprehensive tests:\n- Unit tests for each service method\n- Integration tests for each route\n- Edge cases: negative amounts, invalid enums, missing required fields\n- Concurrent submission attempts\n- Test PII encryption/decryption\n- Test pagination and N+1 query prevention\n- Test regulatory compliance logic"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/client_intake/services.py",
      "line": 73,
      "description": "Unsafe mass assignment in update_application(): model_dump(exclude_unset=True) allows updating any model field including foreign keys (client_id, broker_id) which could lead to data integrity issues.",
      "suggested_fix": "Restrict updatable fields:\n```python\nallowed_fields = {'property_address', 'property_type', 'property_value', 'down_payment', ...}\nfor field, value in payload.model_dump(exclude_unset=True).items():\n    if field in allowed_fields:\n        setattr(application, field, value)\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_intake/schemas.py",
      "line": 18,
      "description": "Weak date validation: date_of_birth uses string type instead of date with proper format validation, allowing invalid dates like '2023-13-45'.",
      "suggested_fix": "Use proper date type:\n```python\nfrom datetime import date\n\ndate_of_birth: date = Field(..., description=\"Date of birth\")\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_intake/schemas.py",
      "line": 17,
      "description": "Insufficient SIN validation: sin field only checks length (9 chars) but doesn't validate numeric format or Luhn algorithm checksum.",
      "suggested_fix": "Add SIN format validator:\n```python\n@field_validator('sin')\ndef validate_sin(cls, v):\n    if not v.isdigit() or len(v) != 9:\n        raise ValueError('SIN must be 9 digits')\n    # Optional: implement Luhn checksum validation\n    return v\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_intake/routes.py",
      "line": 12,
      "description": "Broken import statement: imports are split across lines incorrectly causing syntax errors and poor readability.",
      "suggested_fix": "Fix import grouping:\n```python\nfrom mortgage_underwriting.modules.client_intake.schemas import (\n    ClientCreate,\n    ClientUpdate,\n    ClientResponse,\n    MortgageApplicationCreate,\n    MortgageApplicationUpdate,\n    MortgageApplicationResponse,\n    CoBorrowerCreate,\n    CoBorrowerResponse,\n    ApplicationSummaryResponse\n)\nfrom mortgage_underwriting.modules.client_intake.services import ClientIntakeService\n```"
    },
    {
      "severity": "medium",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/client_intake/services.py",
      "line": 115,
      "description": "Service layer returns raw dict instead of Pydantic model, bypassing schema validation and making the API contract less explicit.",
      "suggested_fix": "Return Pydantic model from service:\n```python\nfrom mortgage_underwriting.modules.client_intake.schemas import ApplicationSummaryResponse\n\nreturn ApplicationSummaryResponse(\n    id=app.id,\n    client=app.client,\n    application=app,\n    co_borrowers=app.co_borrowers\n)\n```"
    },
    {
      "severity": "medium",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_intake/schemas.py",
      "line": 67,
      "description": "Validator only checks down_payment against purchase_price but not against property_value, which is used for LTV calculation in refinance scenarios.",
      "suggested_fix": "Enhance validator:\n```python\n@field_validator('down_payment')\ndef validate_down_payment(cls, v, info):\n    purchase_price = info.data.get('purchase_price')\n    property_value = info.data.get('property_value')\n    if purchase_price and v > purchase_price:\n        raise ValueError('Down payment cannot exceed purchase price')\n    if property_value and v > property_value:\n        raise ValueError('Down payment cannot exceed property value')\n    return v\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/client_intake/routes.py",
      "line": 20,
      "description": "Missing type hint on path parameter user_id in create_client endpoint function signature.",
      "suggested_fix": "Add type hint: `user_id: int`"
    }
  ],
  "summary": "Code is BLOCKED due to multiple critical regulatory compliance violations (FINTRAC, CMHC, OSFI B-20), a broken ORM relationship causing architectural errors, and pervasive bare except clauses in all route handlers. High-severity issues include N+1 query vulnerability, incomplete test coverage, and unsafe mass assignment. Must address regulatory fields, fix relationship mapping, implement proper exception handling, and add comprehensive tests before approval."
}
```