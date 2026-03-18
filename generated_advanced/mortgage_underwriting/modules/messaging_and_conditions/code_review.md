⚠️ BLOCKED

1. **[CRITICAL] models.py ~L11 & ~L33**: Missing audit fields `created_at` and `updated_at` on `Message` model and `updated_at` on `Condition` model. Violates "ALWAYS include created_at, updated_at audit fields on every model". Fix: Add `created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())` and `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to both models.

2. **[CRITICAL] services.py ~L73 & ~L102**: Use of `datetime.utcnow()` for `read_at` and `satisfied_at` sets timezone‑naive values, but models declare `DateTime(timezone=True)`. This mismatch causes runtime errors. Fix: Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` (import `timezone` from `datetime`).

3. **[CRITICAL] routes.py ~L26, L48, L78**: Hardcoded `sender_id=1` and `user_id=1` placeholders in three endpoints. Violates "NEVER hardcode secrets or connection strings" and bypasses authentication. Fix: Implement `get_current_user_id` dependency and inject real user ID.

4. **[CRITICAL] services.py**: Raises generic `AppException` instead of the specific `MessageNotFoundError`, `ConditionNotFoundError`, etc., defined in `exceptions.py`. This prevents returning structured error codes. Fix: Import and raise the specific exception subclasses.

5. **[CRITICAL] routes.py**: No exception handler mapping `MessagingConditionsException` subclasses to JSON responses with `error_code`. Violates "ALWAYS return structured error responses: `{'detail': '...', 'error_code': '...'}`". Fix: Add `@router.exception_handler(MessagingConditionsException)` to return `{'detail': str(exc), 'error_code': exc.error_code}`.

... and 8 additional warnings (lower severity, address after critical issues are resolved).