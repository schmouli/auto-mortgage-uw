⚠️ **BLOCKED**

1. **[CRITICAL] services.py ~L35-45**: GDS calculation missing heating cost component. OSFI B-20 requires GDS = (Principal + Interest + Taxes + Heating) / Gross Income. Current `pith_monthly` only includes PIT. **Fix**: Add `heating_cost_annual: Decimal` field to `PropertyDetailsDTO` in schemas.py, include `monthly_heating = payload.property_details.heating_cost_annual / Decimal('12')` in calculation, and update `pith_monthly` to include heating.

2. **[CRITICAL] routes.py ~L25, ~L40, ~L55**: Error response format violates project convention. Returns `{"error": str(e), "error_code": "..."}` instead of required `{"detail": "...", "error_code": "..."}`. **Fix**: Change all HTTPException `detail` dictionaries to use `"detail"` key instead of `"error"`.

3. **[CRITICAL] services.py ~L15 & exceptions.py**: Conflicting exception definitions. `DecisionServiceError` defined in both files with different base classes (AppException vs Exception), bypassing exceptions.py module entirely. **Fix**: Remove exception class from services.py, add `from mortgage_underwriting.modules.decision.exceptions import DecisionServiceError, DecisionNotFoundError` import, and ensure exceptions.py classes inherit from `AppException`.

4. **[HIGH] services.py evaluate() ~L28-110**: Function exceeds 50-line limit (≈80 lines). **Fix**: Extract helper methods: `_calculate_ratios()`, `_apply_policy_rules()`, `_create_audit_entries()`, `_save_decision_record()` to improve readability and maintainability.

5. **[HIGH] routes.py ~L25, ~L40, ~L55**: Catches generic `Exception` instead of specific domain exceptions. **Fix**: Import `DecisionServiceError` and catch only that exception type. Add separate error handling for unexpected errors that returns 500 status code.

... and 4 additional warnings (lower severity, address after critical issues are resolved)