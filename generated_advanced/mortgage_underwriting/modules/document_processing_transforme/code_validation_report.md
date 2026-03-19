# Code Validation Report: Document Processing Transformer (DPT) Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 33

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100.0%
- services.py: 80.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:36:101: E501 line too long (132 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:43:101: E501 line too long (122 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:47:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:50:25: F821 undefined name 'MortgageApplication'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:50:101: E501 line too long (114 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:20:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:35:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:41:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:54:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:2:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:10:101: E501 line too long (138 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:44:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:69:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:7:101: E501 line too long (138 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:23:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:75:10: W292 no newline at end of file

