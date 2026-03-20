# Code Validation Report: Docker & Deployment

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 39

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 83.3%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:9:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:3:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:13:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:19:101: E501 line too long (121 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:5:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:12:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:17:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:20:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:6:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:9:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:13:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:31:101: E501 line too long (116 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:34:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:45:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:48:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:60:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:63:101: E501 line too long (103 > 100 characters)

