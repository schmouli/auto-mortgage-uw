# Code Validation Report: Infrastructure & Deployment

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 60

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/exceptions.py:13:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/exceptions.py:18:1: E302 expected 2 blank lines, found 1

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:28:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:30:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:35:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:36:101: E501 line too long (101 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:41:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:67:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:85:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:94:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:4:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:4:1: F401 'typing.Optional' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:1:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:13:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:18:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:49:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:63:49: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- ServiceHealth: >50% of fields missing in ServiceHealthResponse - check schema/model field name synchronization
- ConfigValidation: >50% of fields missing in ConfigValidationResponse - check schema/model field name synchronization

