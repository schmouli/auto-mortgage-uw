# Code Validation Report: Decision Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 60

## Type Coverage

- exceptions.py: 100%
- models.py: 0.0%
- schemas.py: 100%
- services.py: 42.9%
- routes.py: 0.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/exceptions.py:11:9: W292 no newline at end of file

### models.py
**Warnings:**
- models.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:3:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:6:1: F401 'sqlalchemy.Column' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:6:1: F401 'sqlalchemy.ForeignKey' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:6:1: F401 'sqlalchemy.Text' imported but unused

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:3:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:12:101: E501 line too long (124 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:84:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 42.857142857142854% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:11:1: F401 'mortgage_underwriting.modules.decision_service.schemas.BorrowerData' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:11:1: F401 'mortgage_underwriting.modules.decision_service.schemas.PropertyData' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:11:1: F401 'mortgage_underwriting.modules.decision_service.schemas.LoanData' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:11:1: F401 'mortgage_underwriting.modules.decision_service.schemas.DebtData' imported but unused

### routes.py
**Warnings:**
- Type hints missing in routes.py::evaluate_decision: missing return type
- Type hints missing in routes.py::get_decision: missing return type
- Type hints missing in routes.py::get_decision_audit: missing return type
- routes.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:4:1: F401 'fastapi.Query' imported but unused

