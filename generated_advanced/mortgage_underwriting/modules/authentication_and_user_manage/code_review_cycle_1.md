⚠️ BLOCKED

1. **[CRITICAL]** routes.py ~L30: `login_user` endpoint accepts `email` and `password` as plain function parameters, which FastAPI interprets as query parameters. This exposes credentials in URLs and violates input validation requirements. **Fix**: Create a `LoginRequest` Pydantic schema with `email: EmailStr` and `password: str` fields, and use it as the request body parameter.

2. **[MEDIUM]** routes.py ~L1: Unused imports `Query`, `SessionCreate`, and `UserUpdate` should be removed to clean up dependencies.

3. **[MEDIUM]** models.py ~L1: Unused import `Text` should be removed.

... and 2 additional warnings (lower severity, address after critical issues are resolved)