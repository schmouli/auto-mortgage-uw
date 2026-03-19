# Code Validation Report: Docker & Deployment

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 49

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:11:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:15:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:17:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:24:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:39:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:43:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:43:122: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:12:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:17:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:24:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:27:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:20:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:49:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:52:28: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:53:75: W504 line break after binary operator

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:3:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:4:1: F401 'fastapi.HTTPException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:4:1: F401 'fastapi.Query' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:18:1: E302 expected 2 blank lines, found 1

### schema_model_consistency
**Errors:**
- ServiceHealth: >50% of fields missing in ServiceHealthResponse - check schema/model field name synchronization
- DeploymentLog: >50% of fields missing in DeploymentLogResponse - check schema/model field name synchronization

