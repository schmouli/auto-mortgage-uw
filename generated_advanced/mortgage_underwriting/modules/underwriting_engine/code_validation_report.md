# Code Validation Report: Underwriting Engine

## Overall Status
Valid: False
Files Checked: 5
Files with Errors: 0
Total Warnings: 130

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/exceptions.py:21:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:23:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:24:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:25:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:27:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/models.py:30:101: E501 line too long (103 > 100 characters)

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::validate_loan_vs_property: missing parameters, return type
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:11:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:20:101: E501 line too long (119 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/schemas.py:21:101: E501 line too long (101 > 100 characters)

### services.py
**Warnings:**
- services.py: Type hint coverage only 80.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:10:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:30:101: E501 line too long (120 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/underwriting_engine/services.py:35:1: W293 blank line contains whitespace

### routes.py

