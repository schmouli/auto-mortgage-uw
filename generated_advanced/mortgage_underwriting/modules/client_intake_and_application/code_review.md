⚠️ BLOCKED

1. **[CRITICAL]** schemas.py ~L45: ClientResponse inherits PII fields (date_of_birth, sin) from ClientBase, violating PIPEDA. Response schemas must never include plain text SIN/DOB. Fix: Create separate ClientResponseBase excluding PII fields or use `exclude={'date_of_birth', 'sin'}` in ConfigDict.

2. **[CRITICAL]** routes.py ~L28: Exception handling mismatch - handlers catch `ClientIntakeException` but services raise `AppException`. This breaks structured error responses. Fix: Change all `except ClientIntakeException` to `except AppException` or have services raise `ClientIntakeException`.

3. **[CRITICAL]** conftest.py ~L10: Incorrect import `from mortgage_underwriting.modules.client_intake.models import Client, Application`. Model `Application` doesn't exist. Fix: Import `MortgageApplication` instead.

4. **[CRITICAL]** services.py ~L120: `calculate_gds_tds()` implementation is incomplete/truncated, missing OSFI B-20 stress test logic and audit logging. Fix: Complete function with qualifying rate = max(contract_rate + 2%, 5.25%), GDS/TDS calculations, and structured logging of breakdown.

5. **[HIGH]** services.py ~L35: Uses deprecated Pydantic v1 `dict()` method. Fix: Replace all `.dict()` calls with `.model_dump()` for Pydantic v2 compatibility (lines ~35, ~70, ~105).

... and 3 additional warnings (lower severity, address after critical issues are resolved)