⚠️ BLOCKED

1. **[CRITICAL] routes.py ~L35, L75:** Exception handling mismatch - `services.py` raises `NotFoundError` from `common.exceptions` but `routes.py` catches `PolicyNotFoundException` from module exceptions. This causes unhandled 500 errors instead of 404s. **Fix:** In `services.py`, raise `PolicyNotFoundException` instead of `NotFoundError`, or update `routes.py` to catch `NotFoundError`.

2. **[CRITICAL] services.py ~L85, L95, L103:** Financial data type violation - `evaluate_policy()` uses `float()` conversion for LTV, GDS, and TDS ratios in the `details` dict, violating "NEVER use float for money" and "Decimal for ALL financial values". **Fix:** Remove all `float()` conversions; keep values as `Decimal` throughout. Use Pydantic's `model_validate` with proper JSON serialization if needed.

3. **[CRITICAL] conftest.py ~L12:** Test module mismatch - imports reference non-existent `xml_policy_service` module and `XmlPolicy` model. **Fix:** Update to `from mortgage_underwriting.modules.policy.models import LenderPolicy` and align all test fixtures with the actual module structure.

4. **[CRITICAL] services.py ~L70-120:** Regulatory compliance gap - `evaluate_policy()` does not apply OSFI B-20 stress test rate (`max(contract_rate + 2%, 5.25%)`) when validating GDS/TDS ratios, and uses simplified LTV insurance logic without CMHC premium tier lookup (80.01-85% = 2.80%, etc.). **Fix:** Implement stress test calculation for ratios and proper CMHC premium tier determination with `insurance_required` flag.

5. **[HIGH] schemas.py ~L25:** Weak input validation - `PolicyEvaluationRequest` uses `Dict[str, Any]` for `applicant_data`, `property_data`, and `loan_data`, bypassing Pydantic validation and allowing malformed requests. **Fix:** Create specific nested Pydantic models (e.g., `ApplicantData`, `PropertyData`, `LoanData`) with explicit field validation.

... and 4 additional warnings (lower severity, address after critical issues are resolved)