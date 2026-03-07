# Code Validation Report: Testing Suite

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 56

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/exceptions.py:9:9: W292 no newline at end of file

### models.py
**Warnings:**
- models.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:3:1: F401 'sqlalchemy.ForeignKey' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:3:1: F401 'sqlalchemy.Boolean' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:3:1: F401 'sqlalchemy.Text' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/models.py:4:1: F401 'sqlalchemy.orm.relationship' imported but unused

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/schemas.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/schemas.py:34:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/schemas.py:38:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:13:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:15:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:18:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/services.py:21:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/routes.py:8:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/routes.py:13:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/routes.py:19:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/routes.py:26:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/testing_suite/routes.py:32:1: W293 blank line contains whitespace

### schema_model_consistency
**Errors:**
- TestRun: >50% of fields missing in TestRunResponse - check schema/model field name synchronization

