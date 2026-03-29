# Code Validation Report: XML Policy Service

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 40

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/exceptions.py:16:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:24:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:27:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/models.py:45:96: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:23:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:37:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/schemas.py:49:14: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 85.71428571428571% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:9:1: F401 'mortgage_underwriting.modules.policy.schemas.LenderPolicyResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:17:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:26:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/xml_policy_service/services.py:28:1: W293 blank line contains whitespace

### routes.py

### schema_model_consistency
**Errors:**
- LenderPolicy: >50% of fields missing in LenderPolicyResponse - check schema/model field name synchronization

