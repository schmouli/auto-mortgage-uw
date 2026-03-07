# Code Validation Report: Document Processing Transformer (DPT) Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 48

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 75.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:12:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:17:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:20:22: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:11:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:17:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:19:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:25:101: E501 line too long (128 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:27:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:3:1: F401 'typing.Union' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:11:101: E501 line too long (162 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:13:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:25:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:10:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:11:1: F401 'mortgage_underwriting.modules.dpt.exceptions.JobNotFoundError' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:15:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:21:58: W291 trailing whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:8:101: E501 line too long (123 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:10:1: F401 'mortgage_underwriting.modules.dpt.exceptions.DPTException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:14:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:37:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:52:1: E302 expected 2 blank lines, found 1

