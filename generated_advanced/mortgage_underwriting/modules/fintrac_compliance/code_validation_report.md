# Code Validation Report: FINTRAC Compliance

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 122

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/exceptions.py:24:60: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:12:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:19:101: E501 line too long (129 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:20:101: E501 line too long (139 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:27:101: E501 line too long (135 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:11:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:13:101: E501 line too long (142 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:14:101: E501 line too long (147 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:15:101: E501 line too long (131 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:17:101: E501 line too long (118 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:1:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:29:14: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:30:30: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:31:44: W291 trailing whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:1:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:23:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:23:101: E501 line too long (143 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:36:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:36:101: E501 line too long (102 > 100 characters)

### schema_model_consistency
**Errors:**
- FintracVerification: >50% of fields missing in FintracVerificationResponse - check schema/model field name synchronization

