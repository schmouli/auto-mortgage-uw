```json
[
  {
    "title": "User creation fails due to missing email validation",
    "description": "The test_create_user_missing_email test expects a ValidationError when email is omitted, but instead receives a generic Exception due to improper exception handling in service layer.",
    "test_name": "tests/unit/test_auth.py::test_create_user_missing_email",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_auth.py\", line 42, in test_create_user_missing_email\n    with pytest.raises(ValidationError):\n  File \"/app/mortgage_underwriting/modules/auth/services.py\", line 31, in create_user\n    raise Exception(\"Email is required\")\nException: Email is required",
    "error_message": "Expected ValidationError, got Exception",
    "affected_code": [
      "mortgage_underwriting/modules/auth/services.py",
      "line 31"
    ],
    "suggested_fix": "Replace generic Exception with Pydantic ValidationError or custom AppException for better error categorization",
    "severity": "high"
  },
  {
    "title": "Login endpoint returns 500 instead of 401 for invalid credentials",
    "description": "When login is attempted with incorrect password, server raises unhandled ValueError instead of returning structured 401 response.",
    "test_name": "tests/unit/test_auth.py::test_login_invalid_password",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_auth.py\", line 78, in test_login_invalid_password\n    response = client.post('/api/v1/auth/login', json=data)\n  File \"/app/mortgage_underwriting/modules/auth/routes.py\", line 55, in login\n    user = await authenticate_user(data.username, data.password)\n  File \"/app/mortgage_underwriting/modules/auth/services.py\", line 62, in authenticate_user\n    raise ValueError(\"Invalid password provided\")\nValueError: Invalid password provided",
    "error_message": "Invalid password provided",
    "affected_code": [
      "mortgage_underwriting/modules/auth/services.py",
      "line 62",
      "mortgage_underwriting/modules/auth/routes.py",
      "line 55"
    ],
    "suggested_fix": "Catch ValueError in route handler and return structured 401 Unauthorized response using AppException pattern",
    "severity": "high"
  },
  {
    "title": "Password hashing uses weak algorithm",
    "description": "Security scan detected that bcrypt library isn't properly configured, leading to weak hash generation which violates PIPEDA encryption standards.",
    "test_name": "tests/integration/test_auth_integration.py::test_password_hash_strength",
    "error_type": "SecurityWarning",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_auth_integration.py\", line 23, in test_password_hash_strength\n    assert len(hashed_pw) >= 60\nAssertionError: Hashed password length insufficient",
    "error_message": "Hashed password length insufficient",
    "affected_code": [
      "mortgage_underwriting/modules/auth/security.py",
      "line 15"
    ],
    "suggested_fix": "Upgrade bcrypt configuration to enforce minimum rounds=12 and validate hash length meets industry standard (~60 chars)",
    "severity": "critical"
  },
  {
    "title": "Refresh token reuse not prevented",
    "description": "Multiple requests using same refresh token succeed, violating OAuth2 security best practices. Should invalidate previous tokens after use.",
    "test_name": "tests/unit/test_auth.py::test_refresh_token_reuse_fails",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_auth.py\", line 105, in test_refresh_token_reuse_fails\n    assert second_response.status_code == 401\nAssertionError: assert 200 == 401",
    "error_message": "Expected status code 401, got 200",
    "affected_code": [
      "mortgage_underwriting/modules/auth/services.py",
      "line 90"
    ],
    "suggested_fix": "Implement refresh token blacklisting mechanism by storing used tokens temporarily in Redis/cache with TTL matching refresh window",
    "severity": "high"
  },
  {
    "title": "User role assignment allows escalation to admin",
    "description": "Low-privilege users can self-modify roles through direct API manipulation, allowing privilege escalation without authorization checks.",
    "test_name": "tests/integration/test_auth_integration.py::test_role_assignment_privilege_escalation",
    "error_type": "PermissionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_auth_integration.py\", line 67, in test_role_assignment_privilege_escalation\n    assert response.json()['role'] != 'admin'\nAssertionError",
    "error_message": "User able to assign themselves admin privileges",
    "affected_code": [
      "mortgage_underwriting/modules/auth/routes.py",
      "line 82"
    ],
    "suggested_fix": "Enforce RBAC middleware check in update_role route ensuring only authorized admins can modify user roles",
    "severity": "critical"
  }
]
```