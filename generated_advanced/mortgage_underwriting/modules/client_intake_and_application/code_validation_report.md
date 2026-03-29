# Code Validation Report: Client Intake & Application

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 42

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/exceptions.py:26:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:16:101: E501 line too long (112 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:26:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:27:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:30:101: E501 line too long (146 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:31:101: E501 line too long (133 > 100 characters)

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::validate_down_payment: missing parameters, return type
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:105:43: W292 no newline at end of file

### services.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:10:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:11:1: F401 'mortgage_underwriting.modules.client_intake.schemas.CoBorrowerUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:45:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:62:1: W293 blank line contains whitespace

### routes.py

### schema_model_consistency
**Errors:**
- Client: >50% of fields missing in ClientResponse - check schema/model field name synchronization
- MortgageApplication: >50% of fields missing in MortgageApplicationResponse - check schema/model field name synchronization
- CoBorrower: >50% of fields missing in CoBorrowerResponse - check schema/model field name synchronization

