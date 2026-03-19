# Code Validation Report: Document Management

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 78

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/exceptions.py:30:93: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:4:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:4:1: F401 'sqlalchemy.CheckConstraint' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:69:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:72:25: F821 undefined name 'Application'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/models.py:72:101: E501 line too long (108 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:144:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/schemas.py:144:111: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 87.5% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:11:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:12:1: F401 'mortgage_underwriting.modules.documents.schemas.DocumentUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:12:1: F401 'mortgage_underwriting.modules.documents.schemas.DocumentRequirementCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/document_management/services.py:12:1: F401 'mortgage_underwriting.modules.documents.schemas.DocumentRequirementUpdate' imported but unused

### routes.py

### schema_model_consistency
**Errors:**
- DocumentRequirement: >50% of fields missing in DocumentRequirementResponse - check schema/model field name synchronization

