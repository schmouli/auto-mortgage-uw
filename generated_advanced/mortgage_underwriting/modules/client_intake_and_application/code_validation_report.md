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
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/exceptions.py:6:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:1:1: F401 'sqlalchemy.Column' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:1:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:21:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:24:101: E501 line too long (131 > 100 characters)

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::validate_date_of_birth: missing parameters, return type
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:96:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 77.77777777777779% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:7:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:11:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:12:101: E501 line too long (144 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:22:101: E501 line too long (110 > 100 characters)

### routes.py
**Warnings:**
- Type hints missing in routes.py::create_client: missing return type
- Type hints missing in routes.py::get_client: missing return type
- Type hints missing in routes.py::update_client: missing return type
- Type hints missing in routes.py::create_application: missing return type
- Type hints missing in routes.py::get_application: missing return type

### schema_model_consistency
**Errors:**
- Client: >50% of fields missing in ClientResponse - check schema/model field name synchronization
- ClientAddress: >50% of fields missing in ClientAddressResponse - check schema/model field name synchronization
- MortgageApplication: >50% of fields missing in MortgageApplicationResponse - check schema/model field name synchronization

