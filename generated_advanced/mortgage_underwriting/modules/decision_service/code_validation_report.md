# Code Validation Report: Decision Service

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 27

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/exceptions.py:15:70: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:1:1: F401 'sqlalchemy.Column' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:1:1: F401 'sqlalchemy.ForeignKey' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:1:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:4:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:7:1: E302 expected 2 blank lines, found 1

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:1:1: F401 'pydantic.EmailStr' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:30:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:5:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:9:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:34:78: E712 comparison to True should be 'if cond is True:' or 'if cond:'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:46:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:7:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:26:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:40:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:55:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:69:101: E501 line too long (106 > 100 characters)

### schema_model_consistency
**Errors:**
- Client: >50% of fields missing in ClientResponse - check schema/model field name synchronization

