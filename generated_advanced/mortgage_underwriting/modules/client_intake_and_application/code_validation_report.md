# Code Validation Report: Client Intake & Application

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 69

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/exceptions.py:13:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:3:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:16:101: E501 line too long (112 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:26:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:27:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/models.py:30:18: F821 undefined name 'User'

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::purchase_price_not_exceed_value: missing parameters, return type
- Type hints missing in schemas.py::loan_equals_purchase_minus_down: missing parameters, return type
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:92:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/schemas.py:102:101: E501 line too long (108 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 81.81818181818183% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:11:1: F401 'mortgage_underwriting.modules.application.schemas.CoBorrowerCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:70:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:73:101: E501 line too long (135 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_intake_and_application/services.py:86:101: E501 line too long (107 > 100 characters)

### routes.py
**Warnings:**
- Type hints missing in routes.py::create_application: missing return type
- Type hints missing in routes.py::list_applications: missing return type
- Type hints missing in routes.py::get_application: missing return type
- Type hints missing in routes.py::update_application: missing return type
- Type hints missing in routes.py::submit_application: missing return type

### schema_model_consistency
**Errors:**
- Client: >50% of fields missing in ClientResponse - check schema/model field name synchronization
- CoBorrower: >50% of fields missing in CoBorrowerResponse - check schema/model field name synchronization

