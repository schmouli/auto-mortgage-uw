# Code Validation Report: Messaging & Conditions

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 31

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 87.5%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:31:28: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:2:1: F401 'sqlalchemy.String' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:37:101: E501 line too long (135 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:38:101: E501 line too long (124 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:39:101: E501 line too long (127 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:46:25: F821 undefined name 'Application'

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:30:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:31:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:32:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:67:19: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 87.5% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:10:1: F401 'mortgage_underwriting.modules.messaging_conditions.schemas.PaginatedConditionsResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:28:101: E501 line too long (120 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:85:101: E501 line too long (128 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:110:101: E501 line too long (109 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:7:1: F401 'mortgage_underwriting.modules.messaging_conditions.schemas.PaginatedConditionsResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:94:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/routes.py:104:69: W292 no newline at end of file

