⚠️ BLOCKED

1. [CRITICAL] models.py ~L18: Missing foreign key column `role_id` for Role relationship. The `role` relationship exists but no `role_id` column is defined. Add: `role_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("roles.id", ondelete="SET NULL"))` and update relationship type hint to `Mapped["Role | None"]`.

2. [CRITICAL] routes.py ~L15: `/register` endpoint returns `UserCreate` schema containing plain-text password from request payload. Change `response_model=UserResponse` and return the created user object: `user = await service.create_user(payload); return user`.

3. [HIGH] routes.py ~L23: Bare except clause without logging. Add structured logging before raising: `logger.error("registration_error", error=str(e))` in the `except Exception` block.

4. [HIGH] routes.py ~L36: Bare except clause without logging. Add structured logging before raising: `logger.error("login_error", error=str(e))` in the `except Exception` block.

5. [HIGH] services.py ~L70: Magic number for session expiry (24 hours). Define module-level constant `SESSION_EXPIRY_HOURS = 24` and use `timedelta(hours=SESSION_EXPIRY_HOURS)` for maintainability.

... and 3 additional warnings (lower severity, address after critical issues are resolved)