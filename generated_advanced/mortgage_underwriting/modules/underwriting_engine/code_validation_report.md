# Code Validation Report: Underwriting Engine

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 63

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/exceptions.py:6:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/exceptions.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/exceptions.py:10:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:13:101: E501 line too long (148 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:14:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:16:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:28:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:6:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:13:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:14:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:15:101: E501 line too long (120 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:49:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:16:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:27:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:35:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:1:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:6:1: F401 'mortgage_underwriting.modules.underwriting.schemas.UnderwritingResultCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:28:12: F821 undefined name 'AppException'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:33:5: F841 local variable 'e' is assigned to but never used
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:40:101: E501 line too long (135 > 100 characters)

### schema_model_consistency
**Errors:**
- UnderwritingResult: >50% of fields missing in UnderwritingResultResponse - check schema/model field name synchronization

