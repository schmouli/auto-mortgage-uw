# Code Validation Report: FINTRAC Compliance

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 30

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 50.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/exceptions.py:4:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/exceptions.py:5:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:1:1: F401 'sqlalchemy.Column' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:1:1: F401 'sqlalchemy.String' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:1:1: F401 'sqlalchemy.Text' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/models.py:11:101: E501 line too long (105 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:7:101: E501 line too long (126 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/schemas.py:13:61: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 50.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:3:1: F401 'sqlalchemy.select' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:4:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/services.py:12:37: F821 undefined name 'ApplicationCreate'

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:4:1: F401 'mortgage_underwriting.modules.mortgage.models.MortgageApplication' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:21:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/fintrac_compliance/routes.py:21:106: W292 no newline at end of file

