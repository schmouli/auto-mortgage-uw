# Code Validation Report: FINTRAC Compliance

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 100

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/exceptions.py:30:48: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:3:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:16:101: E501 line too long (135 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:17:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:18:101: E501 line too long (120 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:23:101: E501 line too long (114 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:30:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:40:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:53:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:70:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:81:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:31:14: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:32:29: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:36:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:40:1: W293 blank line contains whitespace

### routes.py

### schema_model_consistency
**Errors:**
- FintracVerification: >50% of fields missing in FintracVerificationResponse - check schema/model field name synchronization

