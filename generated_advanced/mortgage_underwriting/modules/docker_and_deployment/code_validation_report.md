# Code Validation Report: Docker & Deployment

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 34

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/exceptions.py:20:83: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:15:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:16:101: E501 line too long (125 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:20:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/models.py:32:101: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:19:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:30:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:49:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/schemas.py:57:47: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 66.66666666666666% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:22:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:24:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/services.py:36:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:1:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:2:1: F401 'fastapi.HTTPException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:5:1: F401 'mortgage_underwriting.modules.docker_deployment.schemas.DeploymentStatusResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:13:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/docker_and_deployment/routes.py:38:101: E501 line too long (110 > 100 characters)

### schema_model_consistency
**Errors:**
- ServiceHealthCheck: >50% of fields missing in ServiceHealthCheckResponse - check schema/model field name synchronization

