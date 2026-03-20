# Code Validation Report: Messaging & Conditions

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 109

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 77.8%
- routes.py: 0.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/exceptions.py:11:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:21:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:22:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:23:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:26:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/models.py:28:101: E501 line too long (123 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:17:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:19:101: E501 line too long (117 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:24:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:39:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/schemas.py:63:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 77.77777777777779% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:9:1: F401 'mortgage_underwriting.common.exceptions.AppException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:29:14: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/messaging_and_conditions/services.py:30:29: W291 trailing whitespace

### routes.py
**Warnings:**
- Type hints missing in routes.py::send_message: missing parameters
- Type hints missing in routes.py::get_message_thread: missing parameters
- Type hints missing in routes.py::mark_message_as_read: missing parameters
- Type hints missing in routes.py::add_condition: missing parameters
- Type hints missing in routes.py::list_conditions: missing parameters

