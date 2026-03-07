# Code Validation Report: Docker & Deployment

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 47

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:11:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:4:1: F401 'sqlalchemy.Boolean' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:21:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:23:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:27:101: E501 line too long (126 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:3:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:56:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:66:79: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:4:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:4:1: F401 'typing.Dict' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:20:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:34:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:47:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:47:31: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:64:1: E302 expected 2 blank lines, found 1

### schema_model_consistency
**Errors:**
- DependencyHealth: >50% of fields missing in DependencyHealthResponse - check schema/model field name synchronization

