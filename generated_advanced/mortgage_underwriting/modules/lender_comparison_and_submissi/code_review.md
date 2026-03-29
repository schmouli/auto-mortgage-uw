```json
{
  "status": "BLOCKED",
  "issues": [
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/lender/services.py",
      "line": 42,
      "description": "OSFI B-20 stress test not applied. Lender matching uses contract_rate directly without qualifying_rate = max(contract_rate + 2%, 5.25%). GDS/TDS calculations must use stress-tested mortgage payments for regulatory compliance.",
      "suggested_fix": "Add stress test calculation and use it for mortgage payment in ratio calculations:\n```python\nqualifying_rate = max(payload.contract_rate + Decimal('2.0'), Decimal('5.25'))\n# Calculate monthly payment using qualifying_rate\n# Add to GDS/TDS numerators\n```"
    },
    {
      "severity": "critical",
      "category": "regulatory_compliance",
      "file": "mortgage_underwriting/modules/lender/services.py",
      "line": 38,
      "description": "GDS/TDS calculation formulas are incorrect. GDS should be (mortgage_payment + property_tax + heating + condo_fees) / income. TDS should be GDS + other_debts / income. Missing mortgage payment component entirely.",
      "suggested_fix": "Implement correct ratio calculations with stress-tested mortgage payment:\n```python\nfrom decimal import Decimal\nqualifying_rate = max(payload.contract_rate + Decimal('2.0'), Decimal('5.25'))\n# Calculate monthly mortgage payment using qualifying_rate\nmonthly_payment = calculate_mortgage_payment(payload.loan_amount, qualifying_rate, amortization_years)\ngds_numerator = monthly_payment + payload.condo_fees + property_tax + heating_cost\ntds_numerator = gds_numerator + payload.monthly_debts\ngds_ratio = (gds_numerator / payload.gross_monthly_income) * Decimal('100')\n```"
    },
    {
      "severity": "high",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/lender/schemas.py",
      "line": 118,
      "description": "Pydantic v2 incompatible: @property decorator used instead of @computed_field. The loan_amount and ltv_ratio properties will not be included in schema/serialization as expected in Pydantic v2.",
      "suggested_fix": "Replace @property with @computed_field:\n```python\nfrom pydantic import computed_field\n\n@computed_field\n@property\ndef loan_amount(self) -> Decimal:\n    return self.purchase_price - self.down_payment\n\n@computed_field\n@property\ndef ltv_ratio(self) -> Decimal:\n    if self.purchase_price <= 0:\n        return Decimal('0')\n    return (self.loan_amount / self.purchase_price) * Decimal('100')\n```"
    },
    {
      "severity": "high",
      "category": "error_handling",
      "file": "mortgage_underwriting/modules/lender/routes.py",
      "line": 22,
      "description": "Broad exception clause violates 'no bare except' rule. Catching generic Exception masks specific errors and makes debugging difficult. Should catch specific exceptions like NotFoundError, ValidationError.",
      "suggested_fix": "Implement specific exception handlers:\n```python\nfrom fastapi import HTTPException\nfrom mortgage_underwriting.common.exceptions import AppException\n\n@router.get(\"/\")\nasync def list_lenders(...):\n    try:\n        return await service.get_lenders(skip=skip, limit=limit)\n    except AppException as e:\n        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))\n    except Exception as e:\n        logger.error(\"unexpected_error\", error=str(e))\n        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=\"Internal server error\")\n```"
    },
    {
      "severity": "high",
      "category": "database",
      "file": "mortgage_underwriting/modules/lender/services.py",
      "line": 59,
      "description": "N+1 query vulnerability. Accessing product.lender.name in a loop without explicit eager loading strategy for the lender relationship. Each iteration may trigger a separate database query.",
      "suggested_fix": "Use contains_eager to load lender relationship in initial query:\n```python\nfrom sqlalchemy.orm import contains_eager\n\nstmt = select(LenderProduct).join(Lender).options(contains_eager(LenderProduct.lender)).where(...)\n```"
    },
    {
      "severity": "high",
      "category": "testing",
      "file": "mortgage_underwriting/tests/conftest.py",
      "line": 10,
      "description": "Test module imports from incorrect package name 'lender_comparison' but actual module is named 'lender'. This will cause all tests to fail with ImportError.",
      "suggested_fix": "Correct import statements:\n```python\nfrom mortgage_underwriting.modules.lender.models import Lender, LenderProduct, LenderSubmission\nfrom mortgage_underwriting.modules.lender.schemas import LenderProductCreate, LenderMatchRequest\n```"
    },
    {
      "severity": "high",
      "category": "architecture",
      "file": "mortgage_underwriting/modules/lender/routes.py",
      "line": 85,
      "description": "Unused route parameter 'application_id' in update_submission endpoint. The parameter is accepted but never validated against the submission or used in the service layer, creating a false API contract.",
      "suggested_fix": "Either remove the parameter or validate it:\n```python\nasync def update_submission(\n    application_id: int,\n    submission_id: int,\n    payload: LenderSubmissionUpdate,\n    service: LenderService = Depends(get_lender_service)\n) -> LenderSubmissionResponse:\n    submission = await service.get_submission(submission_id)\n    if submission.application_id != application_id:\n        raise HTTPException(status_code=404, detail=\"Submission not found for this application\")\n    return await service.update_submission(submission_id, payload)\n```"
    },
    {
      "severity": "medium",
      "category": "performance",
      "file": "mortgage_underwriting/modules/lender/services.py",
      "line": 71,
      "description": "Inefficient loop with manual object construction. Using list comprehension would be more Pythonic and potentially faster for large result sets.",
      "suggested_fix": "Refactor to list comprehension:\n```python\nmatches = [\n    LenderMatchResult(\n        product_id=product.id,\n        lender_id=product.lender_id,\n        lender_name=product.lender.name,\n        product_name=product.product_name,\n        rate=product.rate,\n        term_years=product.term_years,\n        max_ltv_insured=product.max_ltv_insured,\n        max_ltv_conventional=product.max_ltv_conventional,\n        max_amortization_insured=product.max_amortization_insured,\n        max_amortization_conventional=product.max_amortization_conventional,\n        min_credit_score=product.min_credit_score,\n        max_gds=product.max_gds,\n        max_tds=product.max_tds,\n        allows_self_employed=product.allows_self_employed,\n        allows_rental_income=product.allows_rental_income,\n        allows_gifted_down_payment=product.allows_gifted_down_payment,\n        prepayment_privilege_percent=product.prepayment_privilege_percent,\n        portability=product.portability,\n        assumability=product.assumability,\n        lender_conditions=None,\n        notes=f\"Matched based on LTV: {ltv_ratio}, GDS: {gds_ratio}, TDS: {tds_ratio}\"\n    )\n    for product in products\n]\n```"
    },
    {
      "severity": "medium",
      "category": "security",
      "file": "mortgage_underwriting/modules/lender/routes.py",
      "line": 20,
      "description": "No rate limiting implemented on lender matching endpoint. The /match endpoint could be abused for scraping lender rates or denial-of-service attacks.",
      "suggested_fix": "Add rate limiting using slowapi:\n```python\nfrom slowapi import Limiter\nfrom slowapi.util import get_remote_address\n\nlimiter = Limiter(key_func=get_remote_address)\n\n@router.post(\"/match\")\n@limiter.limit(\"30/minute\")\nasync def match_lenders(...):\n    ...\n```"
    },
    {
      "severity": "medium",
      "category": "database",
      "file": "mortgage_underwriting/modules/lender/models.py",
      "line": 38,
      "description": "Rate field precision may be insufficient. Numeric(5,3) only allows 3 decimal places (e.g., 5.123). Mortgage rates often require 4+ decimal places for precision (e.g., 5.1234%).",
      "suggested_fix": "Increase precision to Numeric(6,4):\n```python\nrate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)\napproved_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)\n```"
    },
    {
      "severity": "low",
      "category": "code_smell",
      "file": "mortgage_underwriting/modules/lender/services.py",
      "line": 44,
      "description": "Magic number 100 used for percentage conversion without constant definition.",
      "suggested_fix": "Define constant:\n```python\nPERCENTAGE_CONVERSION = Decimal('100')\n# Use: gds_ratio = (gds_numerator / payload.gross_monthly_income) * PERCENTAGE_CONVERSION\n```"
    }
  ],
  "summary": "BLOCKED due to critical OSFI B-20 regulatory compliance violations and high-severity code quality issues. The lender matching service fails to apply mandatory stress test rates and uses incorrect GDS/TDS formulas. Additionally, broad exception handling, N+1 query vulnerabilities, and Pydantic v2 compatibility issues must be resolved before approval."
}
```