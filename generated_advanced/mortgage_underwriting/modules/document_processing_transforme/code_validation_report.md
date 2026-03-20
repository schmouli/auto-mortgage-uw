# Code Validation Report: Document Processing Transformer (DPT) Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 40

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 75.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:20:101: E501 line too long (138 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:33:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:36:25: F821 undefined name 'Application'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/models.py:36:99: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:28:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:29:101: E501 line too long (111 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:35:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/schemas.py:59:52: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:3:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/services.py:31:101: E501 line too long (104 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:23:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_processing_transforme/routes.py:73:10: W292 no newline at end of file

