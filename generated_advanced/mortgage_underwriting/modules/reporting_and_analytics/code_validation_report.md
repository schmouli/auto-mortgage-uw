# Code Validation Report: Reporting & Analytics

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 106

## Type Coverage

- exceptions.py: 0.0%
- models.py: 100.0%
- schemas.py: 100%
- services.py: 44.4%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/exceptions.py:42:10: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:18:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:19:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:22:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:25:101: E501 line too long (121 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:12:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:19:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:26:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:32:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 44.44444444444444% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:11:1: F401 'mortgage_underwriting.modules.reporting.schemas.PipelinePeriod' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:11:1: F401 'mortgage_underwriting.modules.reporting.schemas.PipelineMetrics' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:11:1: F401 'mortgage_underwriting.modules.reporting.schemas.VolumeFilter' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:11:1: F401 'mortgage_underwriting.modules.reporting.schemas.VolumeMetrics' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:6:1: F401 'fastapi.status' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:8:1: F401 'mortgage_underwriting.modules.reporting.schemas.PipelineQueryParams' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:8:1: F401 'mortgage_underwriting.modules.reporting.schemas.VolumeQueryParams' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:25:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:39:1: W293 blank line contains whitespace

