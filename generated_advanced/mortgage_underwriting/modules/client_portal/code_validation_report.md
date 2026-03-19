# Code Validation Report: Client Portal

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 121

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 91.7%
- routes.py: 7.7%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/exceptions.py:23:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:4:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:4:1: F401 'sqlalchemy.Enum as SQLEnum' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:19:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:24:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:25:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:129:25: W292 no newline at end of file

### services.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:41:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:45:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:48:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:54:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:57:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- Type hints missing in routes.py::login: missing return type
- Type hints missing in routes.py::logout: missing return type
- Type hints missing in routes.py::refresh_token: missing return type
- Type hints missing in routes.py::get_client_dashboard: missing return type
- Type hints missing in routes.py::get_broker_dashboard: missing return type

