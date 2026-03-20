# Code Validation Report: Lender Comparison & Submission

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 76

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/exceptions.py:36:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:24:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:29:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:30:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:33:101: E501 line too long (117 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/models.py:34:101: E501 line too long (126 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:35:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:105:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:151:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/schemas.py:203:40: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:10:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:10:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:10:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderProductCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/services.py:10:1: F401 'mortgage_underwriting.modules.lender.schemas.LenderProductUpdate' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:42:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:55:101: E501 line too long (134 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:68:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:73:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/lender_comparison_and_submissi/routes.py:85:101: E501 line too long (112 > 100 characters)

### schema_model_consistency
**Errors:**
- Lender: >50% of fields missing in LenderSchema - check schema/model field name synchronization
- LenderProduct: >50% of fields missing in LenderProductSchema - check schema/model field name synchronization
- LenderSubmission: >50% of fields missing in LenderSubmissionSchema - check schema/model field name synchronization

