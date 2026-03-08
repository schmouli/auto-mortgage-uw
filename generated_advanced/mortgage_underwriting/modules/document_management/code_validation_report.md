# Code Validation Report: Document Management

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 107

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 63.6%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:6:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:18:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:19:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:30:101: E501 line too long (117 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:31:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:48:101: E501 line too long (112 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:72:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:118:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:118:103: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 63.63636363636363% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.document_management.schemas.DocumentUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.document_management.schemas.DocumentRequirementCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.document_management.schemas.DocumentRequirementUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.document_management.schemas.DocumentRequirementResponse' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:3:1: F401 'uuid' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:6:1: F401 'mortgage_underwriting.modules.document_management.schemas.DocumentUploadRequest' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:6:1: F401 'mortgage_underwriting.modules.document_management.schemas.DocumentRequirementResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:14:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:23:12: F821 undefined name 'NotFoundError'

