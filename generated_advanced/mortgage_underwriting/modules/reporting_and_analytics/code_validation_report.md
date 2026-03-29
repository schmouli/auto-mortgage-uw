# Code Validation Report: Reporting & Analytics

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 83

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
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/exceptions.py:30:51: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:15:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:20:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:31:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:38:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:42:101: E501 line too long (123 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:16:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:20:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:29:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:30:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:31:101: E501 line too long (122 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:4:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:4:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:6:1: F401 'sqlalchemy.text' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:6:1: F401 'sqlalchemy.and_' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:3:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:105:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:110:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:116:10: W292 no newline at end of file

