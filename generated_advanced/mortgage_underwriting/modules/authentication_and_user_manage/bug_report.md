```json
[
  {
    "title": "User creation fails due to missing email validation",
    "description": "The test_create_user_missing_email unit test fails because the service does not validate that the email field is required.",
    "test_name": "tests/unit/test_auth_services.py::test_create_user_missing_email",
    "error_type": "ValidationError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_auth_services.py\", line 42, in test_create_user_missing_email\n    await user_service.create_user({\"username\": \"jdoe\", \"password\": \"secure123\"})\n  File \"mortgage_underwriting/modules/auth/services.py\", line 31, in create_user\n    user = UserModel(**user_data)\n  File \"pydantic/main.py\", line 342, in pydantic.main.BaseModel.__init__\npydantic_core._pydantic_core.ValidationError: 1 validation error for UserModel\nemail\n  Field required [type=missing, input_value={'username': 'jdoe', 'password': 'secure123'}, input_type=dict]",
    "error_message": "Field required [type=missing, input_value={'username': 'jdoe', 'password': 'secure123'}, input_type=dict]",
    "affected_code": [
      "mortgage_underwriting/modules/auth/models.py",
      "line 15"
    ],
    "suggested_fix": "Add email field as required in UserModel schema and ensure input validation enforces presence of email before saving to DB.",
    "severity": "high"
  },
  {
    "title": "Password hashing skipped during user registration",
    "description": "Integration test shows password stored in plain text instead of being hashed using configured security method.",
    "test_name": "tests/integration/test_auth_integration.py::test_password_hashing_on_create",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_auth_integration.py\", line 67, in test_password_hashing_on_create\n    assert stored_password == raw_password  # Should fail!\nAssertionError",
    "error_message": "assert 'password123' == '$argon2id$v=19$m=1024,t=2,p=2$...' # Plain-text match should not occur",
    "affected_code": [
      "mortgage_underwriting/modules/auth/services.py",
      "line 28"
    ],
    "suggested_fix": "Ensure password is passed through encrypt_password() utility from common/security.py prior to storing in database.",
    "severity": "critical"
  },
  {
    "title": "Login endpoint returns 500 on invalid credentials",
    "description": "Authentication route raises unhandled exception when username/password do not match any known user record.",
    "test_name": "tests/integration/test_auth_routes.py::test_login_invalid_credentials",
    "error_type": "HTTPException",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_auth_routes.py\", line 88, in test_login_invalid_credentials\n    response = client.post(\"/api/v1/auth/login\", json={\"username\": \"fakeuser\", \"password\": \"wrongpass\"})\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/testclient.py\", line 123, in post\n    return super().post(url, json=json, **kwargs)\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 987, in post\n    return self.request(\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 814, in request\n    return self.send(request, auth=auth, follow_redirects=follow_redirects)\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 901, in send\n    response = self._send_handling_auth(\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 929, in _send_handling_auth\n    response = self._send_handling_redirects(\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 966, in _send_handling_redirects\n    response = self._send_single_request(request)\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 1002, in _send_single_request\n    response = transport.handle_request(request)\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_transports/asgi.py\", line 171, in handle_request\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_transports/asgi.py\", line 168, in handle_request\n    resp = app(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/applications.py\", line 270, in __call__\n    await super().__call__(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/applications.py\", line 124, in __call__\n    await self.middleware_stack(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/errors.py\", line 184, in __call__\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/errors.py\", line 162, in __call__\n    await self.app(scope, receive, _send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/cors.py\", line 91, in __call__\n    await self.app(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/exceptions.py\", line 79, in __call__\n    raise exc\n  File \"/usr/local/lib/python3.12/site-packages/starlette/middleware/exceptions.py\", line 68, in __call__\n    await self.app(scope, receive, sender)\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/middleware/asyncexitstack.py\", line 20, in __call__\n    raise e\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/middleware/asyncexitstack.py\", line 17, in __call__\n    await self.app(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 706, in __call__\n    await self.middleware_stack(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 683, in handle\n    await self.app(scope, receive, send)\n  File \"/usr/local/lib/python3.12/site-packages/starlette/routing.py\", line 276, in handle\n    response = await func(request)\n  File \"/usr/local/lib/python3.12/site-packages/fastapi/routing.py\", line 235, in app\n    response_data = await dependant.call(**values)\n  File \"mortgage_underwriting/modules/auth/routes.py\", line 45, in login\n    user = await authenticate_user(username, password)\n  File \"mortgage_underwriting/modules/auth/services.py\", line 55, in authenticate_user\n    raise ValueError(\"Invalid credentials\")\nValueError: Invalid credentials",
    "error_message": "Invalid credentials",
    "affected_code": [
      "mortgage_underwriting/modules/auth/routes.py",
      "line 45"
    ],
    "suggested_fix": "Wrap ValueError in HTTPException(status_code=401, detail=\"Incorrect username or password\") inside login handler.",
    "severity": "high"
  },
  {
    "title": "DOB decryption error causes user fetch to fail",
    "description": "Fetching user by ID fails with decryption error when retrieving encrypted DOB from database.",
    "test_name": "tests/unit/test_user_retrieval.py::test_fetch_user_decrypt_dob",
    "error_type": "DecryptionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_user_retrieval.py\", line 29, in test_fetch_user_decrypt_dob\n    user = await user_service.get_user(user_id=1)\n  File \"mortgage_underwriting/modules/auth/services.py\", line 72, in get_user\n    decrypted_dob = decrypt_pii(encrypted_dob)\n  File \"mortgage_underwriting/common/security.py\", line 38, in decrypt_pii\n    raise DecryptionError(\"Failed to decrypt PII data\")\ncommon.exceptions.DecryptionError: Failed to decrypt PII data",
    "error_message": "Failed to decrypt PII data",
    "affected_code": [
      "mortgage_underwriting/common/security.py",
      "line 38"
    ],
    "suggested_fix": "Verify encryption key consistency across environments and check that encrypted value isn't corrupted or null.",
    "severity": "medium"
  },
  {
    "title": "User session timeout ignored after logout",
    "description": "Session token remains valid even after explicit logout action, indicating lack of proper session invalidation mechanism.",
    "test_name": "tests/integration/test_session_management.py::test_logout_revokes_token",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_session_management.py\", line 54, in test_logout_revokes_token\n    assert verify_token(logout_response.headers['Authorization']) is None\nAssertionError",
    "error_message": "Token verification still succeeds despite logout",
    "affected_code": [
      "mortgage_underwriting/modules/auth/services.py",
      "line 90"
    ],
    "suggested_fix": "Implement token blacklist/cache invalidation upon logout and enforce checks in authentication middleware.",
    "severity": "high"
  }
]
```