⚠️ BLOCKED

1. [CRITICAL] routes.py ~L30, L52, L66, L80, L97, L112, L127: All HTTPException responses missing `error_code` field. Must return `{"detail": "...", "error_code": "..."}` per project conventions.

2. [CRITICAL] routes.py ~L52, L97, L127: Catching generic `Exception` instead of specific domain exceptions. Violates "No bare except" rule and can mask unexpected bugs. Should catch `MessagingError`/`ConditionError` only.

3. [HIGH] services.py ~L58: Magic number `200` for max per_page limit. Should be module-level constant `MAX_PER_PAGE = 200`.

4. [HIGH] routes.py ~L85, L115: `get_conditions` and `get_outstanding_conditions` endpoints missing pagination Query parameters (`page`, `per_page`) and return incorrect pagination metadata (`per_page: len(conditions)`). Inconsistent with `get_messages` implementation.

5. [HIGH] services.py ~L88, L155: Using deprecated `datetime.utcnow()` instead of `datetime.now(timezone.utc)`. Not compatible with Python 3.12+ deprecation warnings.

... and 3 additional warnings (lower severity, address after critical issues are resolved)