# Code Validation Report: Client Intake & Application

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 77

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/exceptions.py:31:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:16:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:20:101: E501 line too long (125 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:30:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:33:18: F821 undefined name 'User'

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::validate_purchase_price: missing parameters
- Type hints missing in schemas.py::validate_property_value: missing parameters
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:6:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:102:29: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:10:1: F401 'mortgage_underwriting.modules.intake.schemas.CoBorrowerCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:27:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:31:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:44:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/routes.py:3:1: F401 'fastapi.HTTPException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/routes.py:21:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/routes.py:32:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/routes.py:42:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/routes.py:51:101: E501 line too long (106 > 100 characters)

### schema_model_consistency
**Errors:**
- Client: >50% of fields missing in ClientResponse - check schema/model field name synchronization
- CoBorrower: >50% of fields missing in CoBorrowerResponse - check schema/model field name synchronization

