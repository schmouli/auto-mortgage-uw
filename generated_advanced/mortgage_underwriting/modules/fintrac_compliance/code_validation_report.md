# Code Validation Report: FINTRAC Compliance

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 69

## Type Coverage

- exceptions.py: 0.0%
- models.py: 100%
- schemas.py: 100%
- services.py: 83.3%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/exceptions.py:26:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:23:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:24:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:25:101: E501 line too long (120 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:31:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:32:101: E501 line too long (110 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:26:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:28:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:37:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:57:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:68:101: E501 line too long (124 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:13:1: F401 'mortgage_underwriting.modules.fintrac.schemas.IdentityVerificationUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:13:1: F401 'mortgage_underwriting.modules.fintrac.schemas.TransactionReportUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:30:14: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:31:29: W291 trailing whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:23:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:42:101: E501 line too long (127 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:45:1: E302 expected 2 blank lines, found 1

