# Code Validation Report: Client Intake & Application

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 83

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:17:101: E501 line too long (125 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:27:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:28:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:31:18: F821 undefined name 'User'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:32:101: E501 line too long (130 > 100 characters)

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::validate_down_payment: missing parameters, return type
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:14:101: E501 line too long (125 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:31:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:36:101: E501 line too long (103 > 100 characters)

### services.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:12:1: F401 'mortgage_underwriting.modules.client_intake.schemas.CoBorrowerCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:30:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:33:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:37:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:42:1: W293 blank line contains whitespace

### routes.py

### schema_model_consistency
**Errors:**
- Client: >50% of fields missing in ClientResponse - check schema/model field name synchronization
- Application: >50% of fields missing in ApplicationResponse - check schema/model field name synchronization
- CoBorrower: >50% of fields missing in CoBorrowerResponse - check schema/model field name synchronization

