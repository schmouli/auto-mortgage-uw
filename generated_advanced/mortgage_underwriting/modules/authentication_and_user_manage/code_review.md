⚠️ BLOCKED

1. **[CRITICAL] services.py ~L52**: Password hashing uses SHA-256 with salt. This is cryptographically insecure and violates security best practices. Must use `passlib` with bcrypt or Argon2:
   - Run: `uv add passlib[bcrypt]`
   - Replace `_hash_password` method with: `CryptContext(schemes=["bcrypt"], deprecated="auto").hash(password)`

2. **[CRITICAL] routes.py ~L54-57, ~L71-75, ~L88-92**: Bare `except Exception as e` clauses catch all exceptions and return unstructured `detail=str(e)`. Violates structured error response requirement. Must catch specific exceptions (`UserAlreadyExistsError`, `InvalidCredentialsError`, etc.) and return `{"detail": "...", "error_code": "..."}` format with correct HTTP status codes.

3. **[CRITICAL] conftest.py ~L8**: Incorrect import path `mortgage_underwriting.modules.auth.models` does not match the module structure. Must be `mortgage_underwriting.modules.authentication.models` or tests will fail with `ModuleNotFoundError`.

4. **[CRITICAL] services.py (logout_user method)**: FINTRAC compliance violation - physically deletes refresh tokens. Must implement soft-delete: add `is_valid: Mapped[bool] = mapped_column(Boolean, default=True)` to `RefreshToken` model and set `is_valid = False` instead of calling `delete()`.

5. **[HIGH] schemas.py ~L17-24**: Password validator uses `@staticmethod` which Pydantic v2 will not execute during validation. Must replace with `@field_validator('password')` decorator for the validator to run.

... and 8 additional warnings (lower severity, address after critical issues are resolved)