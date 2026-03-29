# Code Validation Report: Document Management

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 65

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/exceptions.py:18:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:13:101: E501 line too long (135 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:14:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:20:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:23:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:25:101: E501 line too long (117 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:99:24: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 87.5% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:3:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.documents.schemas.DocumentUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.documents.schemas.DocumentRequirementCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:9:1: F401 'mortgage_underwriting.modules.documents.schemas.DocumentRequirementUpdate' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:12:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:45:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:53:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/routes.py:142:10: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- DocumentRequirement: >50% of fields missing in DocumentRequirementResponse - check schema/model field name synchronization

