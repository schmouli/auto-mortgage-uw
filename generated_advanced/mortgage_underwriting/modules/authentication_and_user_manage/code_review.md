⚠️ BLOCKED

1. **[CRITICAL] routes.py ~L58, L71**: Placeholder authentication dependency `current_user_id: int = Depends(lambda: 1)` hardcodes user ID 1, bypassing all security. Replace with real JWT authentication dependency that extracts user_id from token.

2. **[CRITICAL] services.py ~L33, L48**: Logging PII violation - `logger.info()` includes `email=payload.email`. PIPEDA prohibits logging PII. Remove email from logs or replace with hashed value.

3. **[CRITICAL] routes.py ~L42**: Routes directly access service private method `service._create_refresh_token()`, breaking encapsulation. Make this method public or move token generation entirely into the service layer.

4. **[CRITICAL] exceptions.py**: All custom exceptions (`InvalidCredentialsException`, `UserExistsException`, etc.) are defined but never used. Services raise `AppException` directly. Either use the custom exceptions consistently or remove the unused definitions.

5. **[CRITICAL] conftest.py**: Import error - `from mortgage_underwriting.modules.auth.security import hash_password` references non-existent module. The hashing logic is in `services.py`. Remove this import or refactor hashing to a dedicated security module.

... and 15 additional warnings (address after critical issues are resolved)