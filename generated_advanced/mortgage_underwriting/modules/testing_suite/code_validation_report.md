# Code Validation Report: Testing Suite

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 17

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/exceptions.py:48:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:21:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:32:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:34:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:37:35: F821 undefined name 'User'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:50:101: E501 line too long (115 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/schemas.py:115:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:117:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:143:101: E501 line too long (117 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:145:44: W292 no newline at end of file

### routes.py

### schema_model_consistency
**Errors:**
- TestRun: >50% of fields missing in TestRunResponse - check schema/model field name synchronization
- TestCase: >50% of fields missing in TestCaseResponse - check schema/model field name synchronization
- TestCoverageReport: >50% of fields missing in TestCoverageReportResponse - check schema/model field name synchronization

