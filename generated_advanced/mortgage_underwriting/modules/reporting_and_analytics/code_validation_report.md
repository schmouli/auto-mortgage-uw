# Code Validation Report: Reporting & Analytics

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 56

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/exceptions.py:24:22: W292 no newline at end of file
- exceptions.py: Found potential hardcoded values - consider moving to config/constants

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:11:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:21:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:25:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:27:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/models.py:28:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/schemas.py:98:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:4:1: F401 'typing.Dict' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:4:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:4:1: F401 'typing.Tuple' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/services.py:7:1: F401 'sqlalchemy.text' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:5:1: F401 'fastapi.HTTPException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:5:1: F401 'fastapi.status' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:8:1: F401 'mortgage_underwriting.modules.reporting.schemas.PipelineQueryParams' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:8:1: F401 'mortgage_underwriting.modules.reporting.schemas.VolumeQueryParams' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/reporting_and_analytics/routes.py:83:42: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- ReportCache: >50% of fields missing in ReportCacheResponse - check schema/model field name synchronization
- FintracReportEntry: >50% of fields missing in FintracReportEntryResponse - check schema/model field name synchronization

