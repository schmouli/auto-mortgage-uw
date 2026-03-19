# Code Validation Report: Underwriting Engine

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 109

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:3:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:23:101: E501 line too long (126 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:25:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:36:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:37:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:13:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:14:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:15:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:16:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:17:101: E501 line too long (101 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 50.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:11:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:12:1: F401 'mortgage_underwriting.modules.underwriting.schemas.UnderwritingResultCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:27:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:29:101: E501 line too long (101 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:2:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:19:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:28:12: F821 undefined name 'ValidationError'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:34:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/routes.py:45:12: F821 undefined name 'ValidationError'

### schema_model_consistency
**Errors:**
- UnderwritingResult: >50% of fields missing in UnderwritingResultResponse - check schema/model field name synchronization

